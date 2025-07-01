import sqlite3
import json
import traceback
from flask import Flask, request, session, jsonify
from datetime import datetime, timedelta
from functools import wraps

# Create Flask app
app = Flask(__name__)
app.secret_key = "your_secret_key_here"  # Replace with your actual secret key

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'success': False, 'error': 'Login required'}), 401
        return f(*args, **kwargs)
    return decorated_function

# Database connection helper
def get_db_connection():
    try:
        conn = sqlite3.connect('health.db')
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        print(f"Database connection error: {str(e)}")
        return None

# Sanitize user data function
def sanitize_user_data(data, user_id):
    """Ensure data only belongs to the current user"""
    if isinstance(data, list):
        return [item for item in data if item.get('user_id') == user_id]
    elif isinstance(data, dict):
        return data if data.get('user_id') == user_id else {}
    return data

# API endpoint to get health history data
@app.route('/api/health-history', methods=['GET'])
@login_required
def get_health_history():
    try:
        user_id = session.get('user_id')
        days = request.args.get('days', '7')
        
        try:
            days = int(days)
        except ValueError:
            days = 7
            
        # Calculate start date
        start_date = datetime.now() - timedelta(days=days)
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500
            
        cursor = conn.cursor()
        
        try:
            # Verify user exists
            cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
            if not cursor.fetchone():
                return jsonify({'success': False, 'error': 'Invalid user session'}), 401
            
            # Get health history for this user - ALWAYS FILTER by user_id
            # Execute the query directly with explicit user_id filter for safety
            cursor.execute('''
            SELECT * FROM health_monitoring
            WHERE user_id = ? AND created_at >= ?
            ORDER BY created_at DESC
            ''', (user_id, start_date.strftime('%Y-%m-%d %H:%M:%S')))
            
            # Convert rows to dictionaries
            history = []
            for row in cursor.fetchall():
                item = dict(row)
                # Double-check user_id matches (additional security)
                if item.get('user_id') != user_id:
                    continue
                    
                # Handle blood pressure JSON
                if item.get('blood_pressure'):
                    try:
                        item['blood_pressure'] = json.loads(item['blood_pressure'])
                    except:
                        pass
                history.append(item)
            
            # Apply the sanitize_user_data function as an additional layer of security
            history = sanitize_user_data(history, user_id)
            
            return jsonify({'success': True, 'history': history})
        except sqlite3.Error as e:
            print(f"Database error: {str(e)}")
            return jsonify({'success': False, 'error': f'Database error: {str(e)}'}), 500
        finally:
            conn.close()
            
    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"Error fetching health history: {str(e)}")
        print(f"Error trace: {error_trace}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Only run the app when this file is executed directly
if __name__ == '__main__':
    app.run(debug=True) 