import sqlite3
import os
import sys
import json
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash

# Create a minimal Flask app for direct admin access
app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = "direct_admin_access_key"  # Different key to avoid cookie conflicts
app.config['SESSION_COOKIE_NAME'] = 'direct_admin'  # Different cookie name

# Disable HTTPS requirement for cookies
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Helper function to process JSON fields in database rows
def process_json_fields(items, field_mappings):
    """
    Process JSON fields in a list of database rows
    
    Args:
        items: List of dictionaries containing database rows
        field_mappings: Dict mapping field names to default values if parsing fails
                        e.g. {'blood_pressure': {'systolic': None, 'diastolic': None}}
    """
    for item in items:
        for field, default_value in field_mappings.items():
            if field in item and item[field]:
                try:
                    item[field] = json.loads(item[field])
                except:
                    item[field] = default_value
    return items

# Connection helper
def get_db_connection():
    try:
        # Use absolute path to the database in the current directory
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'health.db')
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        print(f"Database connection error: {str(e)}")
        return None

# Fix admin account
def ensure_admin_exists():
    conn = get_db_connection()
    if not conn:
        return False
        
    cursor = conn.cursor()
    
    try:
        # Check if admin exists
        cursor.execute("SELECT id, username, is_admin FROM users WHERE username = 'admin'")
        admin_user = cursor.fetchone()
        
        if admin_user:
            # Ensure admin flag is set
            if not admin_user['is_admin']:
                cursor.execute("UPDATE users SET is_admin = 1 WHERE id = ?", (admin_user['id'],))
                
            # Reset password
            password_hash = generate_password_hash("admin123")
            cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", 
                          (password_hash, admin_user['id']))
        else:
            # Create admin user
            password_hash = generate_password_hash("admin123")
            cursor.execute("""
                INSERT INTO users (username, email, password_hash, is_admin, created_at) 
                VALUES ('admin', 'admin@healthassistant.com', ?, 1, CURRENT_TIMESTAMP)
            """, (password_hash,))
            
        conn.commit()
        return True
    except Exception as e:
        print(f"Error ensuring admin exists: {str(e)}")
        return False
    finally:
        conn.close()

# Basic routes for direct admin access
@app.route('/')
def home():
    if 'admin_authenticated' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'admin_authenticated' in session:
        return redirect(url_for('dashboard'))
        
    error = None
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_db_connection()
        if not conn:
            error = "Database connection error"
        else:
            cursor = conn.cursor()
            cursor.execute("SELECT id, username, password_hash, is_admin FROM users WHERE username = ?", (username,))
            user = cursor.fetchone()
            conn.close()
            
            if user and check_password_hash(user['password_hash'], password):
                if user['is_admin']:
                    # Set session explicitly for this app
                    session.clear()
                    session['admin_authenticated'] = True
                    session['admin_id'] = user['id']
                    session['admin_username'] = user['username']
                    return redirect(url_for('dashboard'))
                else:
                    error = "You do not have admin privileges"
            else:
                error = "Invalid username or password"
    
    return render_template('direct_admin_login.html', error=error)

@app.route('/dashboard')
def dashboard():
    if 'admin_authenticated' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    if not conn:
        return "Database connection error", 500
        
    cursor = conn.cursor()
    
    # Get system stats
    stats = {}
    
    # Total users
    cursor.execute("SELECT COUNT(*) as count FROM users")
    stats['total_users'] = cursor.fetchone()['count']
    
    # Recent users
    cursor.execute("SELECT id, username, email, created_at FROM users ORDER BY created_at DESC LIMIT 5")
    recent_users = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    return render_template('direct_admin_dashboard.html', stats=stats, recent_users=recent_users)

@app.route('/users', methods=['GET', 'POST'])
def users():
    if 'admin_authenticated' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    if not conn:
        return "Database connection error", 500
    
    # Handle form submission for creating new user
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        is_admin = True if request.form.get('is_admin') else False
        
        # Basic validation
        if not username or not email or not password:
            flash("All fields are required", "error")
        elif password != confirm_password:
            flash("Passwords do not match", "error")
        else:
            cursor = conn.cursor()
            try:
                # Check if username already exists
                cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
                if cursor.fetchone():
                    flash(f"Username '{username}' already exists", "error")
                else:
                    # Create new user
                    password_hash = generate_password_hash(password)
                    cursor.execute("""
                        INSERT INTO users (username, email, password_hash, is_admin, created_at) 
                        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """, (username, email, password_hash, is_admin))
                    conn.commit()
                    flash(f"User '{username}' created successfully", "success")
            except Exception as e:
                flash(f"Error creating user: {str(e)}", "error")
        
        return redirect(url_for('users'))
    
    # Get query parameters for GET request
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('search', '')
    per_page = 10  # Number of users per page
    
    cursor = conn.cursor()
    
    # If search query is provided, filter users
    if search_query:
        cursor.execute("""
            SELECT id, username, email, is_admin, created_at 
            FROM users 
            WHERE username LIKE ? OR email LIKE ?
            ORDER BY created_at DESC
        """, (f'%{search_query}%', f'%{search_query}%'))
    else:
        cursor.execute("""
            SELECT id, username, email, is_admin, created_at 
            FROM users 
            ORDER BY created_at DESC
        """)
    
    all_users = [dict(row) for row in cursor.fetchall()]
    
    # Get total number of pages
    total_users = len(all_users)
    total_pages = (total_users + per_page - 1) // per_page  # Ceiling division
    
    # Calculate pagination
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    users = all_users[start_idx:end_idx] if start_idx < total_users else []
    
    conn.close()
    
    return render_template('direct_admin_users.html', 
                          users=users, 
                          page=page, 
                          total_pages=total_pages, 
                          search_query=search_query)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/users/delete/<int:user_id>')
def delete_user(user_id):
    if 'admin_authenticated' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    if not conn:
        return "Database connection error", 500
    
    cursor = conn.cursor()
    
    # Don't allow deleting the current admin user
    if user_id == session.get('admin_id'):
        flash("You cannot delete your own admin account.", "error")
        return redirect(url_for('users'))
    
    try:
        # Check if user exists and is not the main admin
        cursor.execute("SELECT username FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            flash("User not found.", "error")
        else:
            # Delete user
            cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()
            flash(f"User '{user['username']}' has been deleted successfully.", "success")
    except Exception as e:
        flash(f"Error deleting user: {str(e)}", "error")
    finally:
        conn.close()
    
    return redirect(url_for('users'))

@app.route('/home')
def main_site():
    # Redirect to the main site - adjust the URL as needed
    return redirect('/')

# Add new route for viewing user history
@app.route('/user/<int:user_id>/history')
def user_history(user_id):
    if 'admin_authenticated' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    if not conn:
        return "Database connection error", 500
        
    cursor = conn.cursor()
    
    # First get user details
    cursor.execute("SELECT id, username, email, is_admin, created_at FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    
    if not user:
        conn.close()
        return "User not found", 404
    
    user = dict(user)
    
    # Get user health monitoring data
    cursor.execute("""
        SELECT id, heart_rate, blood_pressure, oxygen_level, body_temperature, glucose_level,
               created_at
        FROM health_monitoring
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT 10
    """, (user_id,))
    health_data = [dict(row) for row in cursor.fetchall()]
    
    # Process JSON fields in health data
    health_data = process_json_fields(health_data, {
        'blood_pressure': {'systolic': None, 'diastolic': None}
    })
    
    # Get user's disease predictions
    cursor.execute("""
        SELECT id, symptoms, predicted_disease, confidence_score, predicted_at
        FROM disease_predictions
        WHERE user_id = ?
        ORDER BY predicted_at DESC
        LIMIT 10
    """, (user_id,))
    predictions = [dict(row) for row in cursor.fetchall()]
    
    # Process JSON fields in predictions
    predictions = process_json_fields(predictions, {
        'symptoms': []
    })
    
    # Get user's BMI history
    cursor.execute("""
        SELECT id, height, weight, bmi, bmi_category, recorded_at, notes
        FROM bmi_history
        WHERE user_id = ?
        ORDER BY recorded_at DESC
        LIMIT 10
    """, (user_id,))
    bmi_history = [dict(row) for row in cursor.fetchall()]
    
    # Get user's activity tracking data
    cursor.execute("""
        SELECT id, activity_type, duration, steps, calories_burned, 
               activity_date, notes, created_at
        FROM activity_tracking
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT 10
    """, (user_id,))
    activity_data = [dict(row) for row in cursor.fetchall()]
    
    # Get user's medical records
    cursor.execute("""
        SELECT id, record_name, record_type, file_path, record_date, notes, uploaded_at
        FROM medical_records
        WHERE user_id = ?
        ORDER BY uploaded_at DESC
        LIMIT 10
    """, (user_id,))
    medical_records = [dict(row) for row in cursor.fetchall()]
    
    # Get user's prescriptions
    prescriptions = []
    try:
        # Check if table exists before querying
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='medical_prescriptions'")
        if cursor.fetchone():
            cursor.execute("""
                SELECT id, doctor_name, specialization, patient_name, patient_age, 
                       patient_gender, allergies, diagnosis, medications, 
                       instructions, follow_up, created_at
                FROM medical_prescriptions
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT 10
            """, (user_id,))
            prescriptions = [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"Error fetching prescriptions: {e}")
    
    conn.close()
    
    return render_template('user_history.html',
                           user=user,
                           health_data=health_data,
                           predictions=predictions,
                           bmi_history=bmi_history,
                           activity_data=activity_data,
                           medical_records=medical_records,
                           prescriptions=prescriptions)

# Add new routes for specific data sections
@app.route('/medical-records')
def medical_records():
    if 'admin_authenticated' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    if not conn:
        return "Database connection error", 500
        
    cursor = conn.cursor()
    
    # Get all medical records with user data
    cursor.execute("""
        SELECT mr.id, mr.user_id, u.username, mr.record_name, mr.record_type, 
               mr.file_path, mr.record_date, mr.notes, mr.uploaded_at
        FROM medical_records mr
        JOIN users u ON mr.user_id = u.id
        ORDER BY mr.uploaded_at DESC
        LIMIT 100
    """)
    records = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    return render_template('admin_medical_records.html', records=records)

@app.route('/activity-tracking')
def activity_tracking():
    if 'admin_authenticated' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    if not conn:
        return "Database connection error", 500
        
    cursor = conn.cursor()
    
    # Get all activity tracking data with user data
    cursor.execute("""
        SELECT at.id, at.user_id, u.username, at.activity_type, at.duration, 
               at.steps, at.calories_burned, at.activity_date, at.created_at
        FROM activity_tracking at
        JOIN users u ON at.user_id = u.id
        ORDER BY at.created_at DESC
        LIMIT 100
    """)
    activities = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    return render_template('admin_activity_tracking.html', activities=activities)

@app.route('/bmi-history')
def bmi_history():
    if 'admin_authenticated' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    if not conn:
        return "Database connection error", 500
        
    cursor = conn.cursor()
    
    # Get all BMI history data with user data
    cursor.execute("""
        SELECT bh.id, bh.user_id, u.username, bh.height, bh.weight, 
               bh.bmi, bh.bmi_category, bh.recorded_at
        FROM bmi_history bh
        JOIN users u ON bh.user_id = u.id
        ORDER BY bh.recorded_at DESC
        LIMIT 100
    """)
    bmi_entries = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    return render_template('admin_bmi_history.html', bmi_entries=bmi_entries)

@app.route('/health-monitoring')
def health_monitoring():
    if 'admin_authenticated' not in session:
        return redirect(url_for('login'))
    
    health_entries = []
    
    try:
        conn = get_db_connection()
        if not conn:
            flash("Database connection error", "error")
            return render_template('admin_health_monitoring.html', health_entries=health_entries)
        
        cursor = conn.cursor()
        
        # Check if health_monitoring table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='health_monitoring'")
        table_exists = cursor.fetchone() is not None
        
        if table_exists:
            try:
                # Get all health monitoring data with user data
                cursor.execute("""
                    SELECT hm.id, hm.user_id, u.username, hm.heart_rate, hm.blood_pressure,
                           hm.oxygen_level, hm.body_temperature, hm.glucose_level, hm.created_at
                    FROM health_monitoring hm
                    JOIN users u ON hm.user_id = u.id
                    ORDER BY hm.created_at DESC
                    LIMIT 100
                """)
                
                health_entries = [dict(row) for row in cursor.fetchall()]
                
                # Process blood pressure JSON using the helper function
                health_entries = process_json_fields(health_entries, {
                    'blood_pressure': {'systolic': None, 'diastolic': None}
                })
                
            except Exception as e:
                flash(f"Error querying health data: {str(e)}", "error")
        else:
            # Create sample data for demonstration if table doesn't exist
            flash("Health monitoring table doesn't exist. Showing sample data for demonstration.", "warning")
            health_entries = [
                {
                    'id': 1, 
                    'user_id': 1, 
                    'username': 'demo_user', 
                    'heart_rate': 75, 
                    'blood_pressure': {'systolic': 120, 'diastolic': 80},
                    'oxygen_level': 98, 
                    'body_temperature': 36.8, 
                    'glucose_level': 100, 
                    'created_at': '2023-05-01'
                },
                {
                    'id': 2, 
                    'user_id': 1, 
                    'username': 'demo_user', 
                    'heart_rate': 82, 
                    'blood_pressure': {'systolic': 125, 'diastolic': 85},
                    'oxygen_level': 97, 
                    'body_temperature': 37.1, 
                    'glucose_level': 110, 
                    'created_at': '2023-05-02'
                }
            ]
    except Exception as e:
        flash(f"Error accessing database: {str(e)}", "error")
    finally:
        if 'conn' in locals() and conn:
            conn.close()
    
    return render_template('admin_health_monitoring.html', health_entries=health_entries)

@app.route('/medical-prescriptions')
def medical_prescriptions():
    if 'admin_authenticated' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    if not conn:
        return "Database connection error", 500
    
    prescriptions = []
    try:
        cursor = conn.cursor()
        
        # Check if medical_prescriptions table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='medical_prescriptions'")
        table_exists = cursor.fetchone() is not None
        
        if table_exists:
            try:
                # Get all prescriptions with user data
                cursor.execute("""
                    SELECT mp.id, mp.user_id, u.username, mp.doctor_name, mp.specialization,
                           mp.patient_name, mp.patient_age, mp.patient_gender, mp.allergies,
                           mp.diagnosis, mp.medications, mp.instructions, mp.follow_up,
                           mp.created_at
                    FROM medical_prescriptions mp
                    JOIN users u ON mp.user_id = u.id
                    ORDER BY mp.created_at DESC
                    LIMIT 100
                """)
                
                prescriptions = [dict(row) for row in cursor.fetchall()]
            except Exception as e:
                flash(f"Error querying prescriptions data: {str(e)}", "error")
        else:
            flash("Medical prescriptions table does not exist in the database", "warning")
    except Exception as e:
        flash(f"Database error: {str(e)}", "error")
    finally:
        conn.close()
    
    return render_template('admin_medical_prescriptions.html', prescriptions=prescriptions)

# Create basic templates if they don't exist
def create_templates():
    templates_dir = 'templates'
    if not os.path.exists(templates_dir):
        os.makedirs(templates_dir)
    
    # Template files are auto-generated for direct admin access
    # Basic templates for login, dashboard, users, and user history 
    # Additional templates for specialized data viewing:
    # - admin_medical_records.html: View all medical records across users
    # - admin_activity_tracking.html: View activity tracking data across users
    # - admin_bmi_history.html: View BMI history data across users
    # - admin_health_monitoring.html: View health monitoring data across users
    
    # Login template
    login_template = """<!DOCTYPE html>
<html>
<head>
    <title>Direct Admin Access - Login</title>
    <style>
        body { font-family: Arial, sans-serif; background-color: #f5f5f5; margin: 0; padding: 0; display: flex; justify-content: center; align-items: center; height: 100vh; }
        .container { background-color: white; padding: 30px; border-radius: 5px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); width: 400px; }
        h1 { text-align: center; color: #333; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; font-weight: bold; }
        input[type="text"], input[type="password"] { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
        button { width: 100%; padding: 10px; background-color: #4285f4; color: white; border: none; border-radius: 4px; cursor: pointer; }
        button:hover { background-color: #357ae8; }
        .error { color: red; margin-bottom: 15px; }
        .note { margin-top: 20px; font-size: 12px; color: #666; text-align: center; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Direct Admin Access</h1>
        {% if error %}
        <div class="error">{{ error }}</div>
        {% endif %}
        <form method="post">
            <div class="form-group">
                <label for="username">Username:</label>
                <input type="text" id="username" name="username" required>
            </div>
            <div class="form-group">
                <label for="password">Password:</label>
                <input type="password" id="password" name="password" required>
            </div>
            <button type="submit">Login</button>
        </form>
        <div class="note">
            Default credentials: admin / admin123<br>
            This is a direct admin access portal that bypasses the regular admin flow.
        </div>
    </div>
</body>
</html>"""

    # Dashboard template
    dashboard_template = """<!DOCTYPE html>
<html>
<head>
    <title>Admin Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 0; background-color: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        header { background-color: #333; color: white; padding: 10px 20px; display: flex; justify-content: space-between; align-items: center; }
        .header-title { font-size: 20px; font-weight: bold; }
        nav { margin-top: 20px; background-color: white; padding: 10px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        nav ul { list-style: none; padding: 0; margin: 0; display: flex; }
        nav ul li { margin-right: 20px; }
        nav ul li a { text-decoration: none; color: #333; font-weight: bold; }
        .card { background-color: white; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); margin-bottom: 20px; overflow: hidden; }
        .card-header { background-color: #4285f4; color: white; padding: 15px; font-weight: bold; }
        .card-body { padding: 15px; }
        .stats { display: flex; flex-wrap: wrap; }
        .stat-item { flex: 1; min-width: 200px; margin: 10px; padding: 20px; background-color: white; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); text-align: center; }
        .stat-value { font-size: 24px; font-weight: bold; margin-bottom: 10px; color: #4285f4; }
        .stat-label { color: #666; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px 15px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background-color: #f2f2f2; }
        tr:hover { background-color: #f5f5f5; }
        .logout { color: white; text-decoration: none; }
    </style>
</head>
<body>
    <header>
        <div class="header-title">Health Assistant Admin</div>
        <a href="{{ url_for('logout') }}" class="logout">Logout</a>
    </header>
    
    <div class="container">
        <nav>
            <ul>
                <li><a href="{{ url_for('dashboard') }}">Dashboard</a></li>
                <li><a href="{{ url_for('users') }}">Users</a></li>
            </ul>
        </nav>
        
        <h1>Admin Dashboard</h1>
        
        <div class="stats">
            <div class="stat-item">
                <div class="stat-value">{{ stats.total_users }}</div>
                <div class="stat-label">Total Users</div>
            </div>
        </div>
        
        <div class="card">
            <div class="card-header">Recent Users</div>
            <div class="card-body">
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Username</th>
                            <th>Email</th>
                            <th>Created At</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for user in recent_users %}
                        <tr>
                            <td>{{ user.id }}</td>
                            <td>{{ user.username }}</td>
                            <td>{{ user.email }}</td>
                            <td>{{ user.created_at }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</body>
</html>"""

    # Users template
    users_template = """<!DOCTYPE html>
<html>
<head>
    <title>Admin Users</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 0; background-color: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        header { background-color: #333; color: white; padding: 10px 20px; display: flex; justify-content: space-between; align-items: center; }
        .header-title { font-size: 20px; font-weight: bold; }
        nav { margin-top: 20px; background-color: white; padding: 10px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        nav ul { list-style: none; padding: 0; margin: 0; display: flex; }
        nav ul li { margin-right: 20px; }
        nav ul li a { text-decoration: none; color: #333; font-weight: bold; }
        .card { background-color: white; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); margin-bottom: 20px; overflow: hidden; }
        .card-header { background-color: #4285f4; color: white; padding: 15px; font-weight: bold; }
        .card-body { padding: 15px; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px 15px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background-color: #f2f2f2; }
        tr:hover { background-color: #f5f5f5; }
        .logout { color: white; text-decoration: none; }
        .badge { display: inline-block; padding: 3px 8px; border-radius: 3px; font-size: 12px; }
        .badge-admin { background-color: #4CAF50; color: white; }
        .view-link { color: #4285f4; text-decoration: none; }
        .view-link:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <header>
        <div class="header-title">Health Assistant Admin</div>
        <a href="{{ url_for('logout') }}" class="logout">Logout</a>
    </header>
    
    <div class="container">
        <nav>
            <ul>
                <li><a href="{{ url_for('dashboard') }}">Dashboard</a></li>
                <li><a href="{{ url_for('users') }}">Users</a></li>
            </ul>
        </nav>
        
        <h1>User Management</h1>
        
        <div class="card">
            <div class="card-header">All Users</div>
            <div class="card-body">
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Username</th>
                            <th>Email</th>
                            <th>Role</th>
                            <th>Created At</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for user in users %}
                        <tr>
                            <td>{{ user.id }}</td>
                            <td>{{ user.username }}</td>
                            <td>{{ user.email }}</td>
                            <td>
                                {% if user.is_admin %}
                                <span class="badge badge-admin">Admin</span>
                                {% else %}
                                User
                                {% endif %}
                            </td>
                            <td>{{ user.created_at }}</td>
                            <td>
                                <a href="{{ url_for('user_history', user_id=user.id) }}" class="view-link">View History</a>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</body>
</html>"""

    # User History template
    user_history_template = """<!DOCTYPE html>
<html>
<head>
    <title>User History</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 0; background-color: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        header { background-color: #333; color: white; padding: 10px 20px; display: flex; justify-content: space-between; align-items: center; }
        .header-title { font-size: 20px; font-weight: bold; }
        nav { margin-top: 20px; background-color: white; padding: 10px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        nav ul { list-style: none; padding: 0; margin: 0; display: flex; }
        nav ul li { margin-right: 20px; }
        nav ul li a { text-decoration: none; color: #333; font-weight: bold; }
        .card { background-color: white; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); margin-bottom: 20px; overflow: hidden; }
        .card-header { background-color: #4285f4; color: white; padding: 15px; font-weight: bold; }
        .card-body { padding: 15px; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px 15px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background-color: #f2f2f2; }
        tr:hover { background-color: #f5f5f5; }
        .logout { color: white; text-decoration: none; }
        .badge { display: inline-block; padding: 3px 8px; border-radius: 3px; font-size: 12px; }
        .badge-admin { background-color: #4CAF50; color: white; }
        .user-info { background-color: white; padding: 20px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); margin-bottom: 20px; }
        .user-info h2 { margin-top: 0; color: #333; }
        .back-link { display: inline-block; margin-bottom: 20px; color: #4285f4; text-decoration: none; font-weight: bold; }
        .back-link:hover { text-decoration: underline; }
        .health-data { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 20px; }
        .health-item { background-color: white; padding: 15px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); flex: 1; min-width: 200px; }
        .health-label { font-weight: bold; margin-bottom: 5px; color: #666; }
        .health-value { font-size: 20px; color: #4285f4; }
        .prediction-item { background-color: white; padding: 15px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); margin-bottom: 10px; }
        .prediction-disease { font-size: 18px; font-weight: bold; color: #333; margin-bottom: 5px; }
        .prediction-confidence { color: #4285f4; margin-bottom: 10px; }
        .symptoms-list { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 10px; }
        .symptom-tag { background-color: #f2f2f2; padding: 3px 8px; border-radius: 3px; font-size: 12px; }
        .no-data { color: #666; font-style: italic; text-align: center; padding: 20px; }
    </style>
</head>
<body>
    <header>
        <div class="header-title">Health Assistant Admin</div>
        <a href="{{ url_for('logout') }}" class="logout">Logout</a>
    </header>
    
    <div class="container">
        <nav>
            <ul>
                <li><a href="{{ url_for('dashboard') }}">Dashboard</a></li>
                <li><a href="{{ url_for('users') }}">Users</a></li>
            </ul>
        </nav>
        
        <a href="{{ url_for('users') }}" class="back-link">- Back to Users</a>
        
        <div class="user-info">
            <h2>{{ user.username }}</h2>
            <p>Email: {{ user.email }}</p>
            <p>Account created: {{ user.created_at }}</p>
            <p>Role: {% if user.is_admin %}<span class="badge badge-admin">Admin</span>{% else %}User{% endif %}</p>
        </div>
        
        <div class="card">
            <div class="card-header">Health Monitoring Data</div>
            <div class="card-body">
                {% if health_data %}
                    {% for item in health_data %}
                        <div class="health-data">
                            <div class="health-item">
                                <div class="health-label">Heart Rate</div>
                                <div class="health-value">{{ item.heart_rate }} bpm</div>
                            </div>
                            {% if item.blood_pressure %}
                                <div class="health-item">
                                    <div class="health-label">Blood Pressure</div>
                                    {% if item.blood_pressure.systolic and item.blood_pressure.diastolic %}
                                        <div class="health-value">{{ item.blood_pressure.systolic }}/{{ item.blood_pressure.diastolic }} mmHg</div>
                                    {% else %}
                                        <div class="health-value">{{ item.blood_pressure }}</div>
                                    {% endif %}
                                </div>
                            {% endif %}
                            <div class="health-item">
                                <div class="health-label">Oxygen Level</div>
                                <div class="health-value">{{ item.oxygen_level }}%</div>
                            </div>
                            {% if item.body_temperature %}
                                <div class="health-item">
                                    <div class="health-label">Body Temperature</div>
                                    <div class="health-value">{{ item.body_temperature }}°C</div>
                                </div>
                            {% endif %}
                            <div class="health-item">
                                <div class="health-label">Date</div>
                                <div class="health-value">{{ item.created_at }}</div>
                            </div>
                        </div>
                        <hr>
                    {% endfor %}
                {% else %}
                    <div class="no-data">No health monitoring data available</div>
                {% endif %}
            </div>
        </div>
        
        <div class="card">
            <div class="card-header">Disease Predictions</div>
            <div class="card-body">
                {% if predictions %}
                    {% for pred in predictions %}
                        <div class="prediction-item">
                            <div class="prediction-disease">{{ pred.predicted_disease }}</div>
                            <div class="prediction-confidence">Confidence: {{ (pred.confidence_score * 100)|round(2) }}%</div>
                            <div class="prediction-date">Date: {{ pred.predicted_at }}</div>
                            {% if pred.symptoms %}
                                <div class="symptoms">
                                    <div class="symptoms-label">Symptoms:</div>
                                    <div class="symptoms-list">
                                        {% for symptom in pred.symptoms %}
                                            <span class="symptom-tag">{{ symptom|replace('_', ' ')|title }}</span>
                                        {% endfor %}
                                    </div>
                                </div>
                            {% endif %}
                        </div>
                    {% endfor %}
                {% else %}
                    <div class="no-data">No disease predictions available</div>
                {% endif %}
            </div>
        </div>
    </div>
</body>
</html>"""

    # Write templates to files
    with open(os.path.join(templates_dir, 'direct_admin_login.html'), 'w', encoding='utf-8') as f:
        f.write(login_template)
    
    with open(os.path.join(templates_dir, 'direct_admin_dashboard.html'), 'w', encoding='utf-8') as f:
        f.write(dashboard_template)
        
    with open(os.path.join(templates_dir, 'direct_admin_users.html'), 'w', encoding='utf-8') as f:
        f.write(users_template)
        
    # Add the new template
    with open(os.path.join(templates_dir, 'user_history.html'), 'w', encoding='utf-8') as f:
        f.write(user_history_template)

if __name__ == "__main__":
    # Create templates if they don't exist yet
    create_templates()
    
    print("Direct admin access enabled. Default credentials: admin / admin123")
    
    # Ensure admin account exists
    if ensure_admin_exists():
        print("Admin account verified or created.")
    else:
        print("Failed to ensure admin account exists. Check database connection.")
    
    # Run the application
    app.run(debug=True, port=5001) 