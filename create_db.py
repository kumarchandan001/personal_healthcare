import sqlite3
from datetime import datetime, timedelta
import random
import json
from werkzeug.security import generate_password_hash
import os
import sys
import hashlib
import shutil

# Get the database path
db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'health.db')

# Connect to the database (it will be created if it doesn't exist)
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("Connected to database:", db_path)

# Create the users table for authentication and profile information
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    first_name TEXT,
    last_name TEXT,
    date_of_birth DATE,
    gender TEXT,
    height REAL,  -- in cm
    weight REAL,  -- in kg
    blood_type TEXT,
    emergency_contact TEXT,
    emergency_phone TEXT,
    medical_conditions TEXT,  -- stored as JSON array
    allergies TEXT,  -- stored as JSON array
    is_admin BOOLEAN DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_login DATETIME
)
''')

# Create the health_data table for tracking individual metrics over time
cursor.execute('''
CREATE TABLE IF NOT EXISTS health_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    metric TEXT NOT NULL,  -- e.g., "steps", "heart_rate", "weight"
    value REAL NOT NULL,   -- e.g., 5000 steps, 72 bpm, 70.5 kg
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
)
''')

# Create table for health monitoring with comprehensive health metrics
cursor.execute('''
CREATE TABLE IF NOT EXISTS health_monitoring (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    heart_rate INTEGER,
    blood_pressure TEXT,  -- Stored as JSON with systolic and diastolic values
    oxygen_level INTEGER,
    body_temperature REAL,
    glucose_level REAL,
    cholesterol_level REAL,
    stress_level INTEGER,  -- Scale from 1-10
    sleep_hours REAL,
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
)
''')

# Create table for medication reminders
cursor.execute('''
CREATE TABLE IF NOT EXISTS medication_reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    medication_name TEXT NOT NULL,
    dosage TEXT,
    reminder_time TEXT NOT NULL,
    frequency TEXT DEFAULT 'daily',  -- e.g., "daily", "twice_daily", "weekly"
    days_of_week TEXT,  -- stored as JSON array, e.g., ["Mon", "Wed", "Fri"]
    start_date DATE,
    end_date DATE,
    notes TEXT,
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
)
''')

# Create table for medication history
cursor.execute('''
CREATE TABLE IF NOT EXISTS medication_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    reminder_id INTEGER,
    medication_name TEXT NOT NULL,
    dosage TEXT,
    taken_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL,  -- "taken", "skipped", "delayed"
    notes TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (reminder_id) REFERENCES medication_reminders(id)
)
''')

# Create table for medical records
cursor.execute('''
CREATE TABLE IF NOT EXISTS medical_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    record_name TEXT NOT NULL,
    record_type TEXT NOT NULL,  -- "lab_report", "prescription", "imaging", "vaccination", etc.
    file_path TEXT,
    file_type TEXT,
    file_size INTEGER,
    record_date DATE,
    provider TEXT,  -- Doctor or hospital name
    notes TEXT,
    uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
)
''')

# Create table for medical prescriptions
cursor.execute('''
CREATE TABLE IF NOT EXISTS medical_prescriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    doctor_name TEXT NOT NULL,
    specialization TEXT,
    patient_name TEXT NOT NULL,
    patient_age INTEGER,
    patient_gender TEXT,
    allergies TEXT,
    diagnosis TEXT,
    medications TEXT NOT NULL,
    instructions TEXT,
    follow_up TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
)
''')

# Create table for activity tracking
cursor.execute('''
CREATE TABLE IF NOT EXISTS activity_tracking (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    activity_type TEXT NOT NULL,  -- "walking", "running", "cycling", etc.
    duration INTEGER,  -- in minutes
    steps INTEGER,
    distance REAL,  -- in km
    calories_burned INTEGER,
    heart_rate_avg INTEGER,
    heart_rate_max INTEGER,
    activity_date DATE,
    start_time TIME,
    end_time TIME,
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
)
''')

# Create table for BMI history
cursor.execute('''
CREATE TABLE IF NOT EXISTS bmi_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    height REAL,  -- in cm
    weight REAL,  -- in kg
    bmi REAL,
    bmi_category TEXT,  -- "Underweight", "Normal", "Overweight", "Obese"
    recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
)
''')

# Create table for disease prediction history
cursor.execute('''
CREATE TABLE IF NOT EXISTS disease_predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    symptoms TEXT NOT NULL,  -- stored as JSON array
    predicted_disease TEXT,
    confidence_score REAL,
    recommendations TEXT,
    saved_to_records BOOLEAN DEFAULT 0,
    predicted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
)
''')

# Create table for daily health goal tracking
cursor.execute('''
CREATE TABLE IF NOT EXISTS health_goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    goal_type TEXT NOT NULL,  -- "steps", "water_intake", "meditation", "exercise", etc.
    target_value REAL NOT NULL,
    current_value REAL DEFAULT 0,
    start_date DATE,
    end_date DATE,
    frequency TEXT DEFAULT 'daily',  -- "daily", "weekly", "monthly"
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
)
''')

# Create table for chatbot interactions
cursor.execute('''
CREATE TABLE IF NOT EXISTS chatbot_interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    query TEXT NOT NULL,
    response TEXT NOT NULL,
    interaction_type TEXT,  -- "health_advice", "medication_help", "general", etc.
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
)
''')

# Create table for emergency contacts
cursor.execute('''
CREATE TABLE IF NOT EXISTS emergency_contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    relationship TEXT,
    phone TEXT NOT NULL,
    email TEXT,
    address TEXT,
    is_primary BOOLEAN DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
)
''')

# Create triggers to enforce user_id consistency
# These triggers ensure that all tables with user_id have proper foreign key constraints
cursor.execute('''
CREATE TRIGGER IF NOT EXISTS verify_user_id_health_monitoring 
BEFORE INSERT ON health_monitoring 
FOR EACH ROW 
BEGIN
    SELECT CASE 
        WHEN NEW.user_id NOT IN (SELECT id FROM users) 
        THEN RAISE(ABORT, 'Invalid user_id in health_monitoring')
    END;
END;
''')

cursor.execute('''
CREATE TRIGGER IF NOT EXISTS verify_user_id_health_data 
BEFORE INSERT ON health_data 
FOR EACH ROW 
BEGIN
    SELECT CASE 
        WHEN NEW.user_id NOT IN (SELECT id FROM users) 
        THEN RAISE(ABORT, 'Invalid user_id in health_data')
    END;
END;
''')

cursor.execute('''
CREATE TRIGGER IF NOT EXISTS verify_user_id_medication_reminders 
BEFORE INSERT ON medication_reminders 
FOR EACH ROW 
BEGIN
    SELECT CASE 
        WHEN NEW.user_id NOT IN (SELECT id FROM users) 
        THEN RAISE(ABORT, 'Invalid user_id in medication_reminders')
    END;
END;
''')

cursor.execute('''
CREATE TRIGGER IF NOT EXISTS verify_user_id_medical_records 
BEFORE INSERT ON medical_records 
FOR EACH ROW 
BEGIN
    SELECT CASE 
        WHEN NEW.user_id NOT IN (SELECT id FROM users) 
        THEN RAISE(ABORT, 'Invalid user_id in medical_records')
    END;
END;
''')

cursor.execute('''
CREATE TRIGGER IF NOT EXISTS verify_user_id_activity_tracking 
BEFORE INSERT ON activity_tracking 
FOR EACH ROW 
BEGIN
    SELECT CASE 
        WHEN NEW.user_id NOT IN (SELECT id FROM users) 
        THEN RAISE(ABORT, 'Invalid user_id in activity_tracking')
    END;
END;
''')

cursor.execute('''
CREATE TRIGGER IF NOT EXISTS verify_user_id_bmi_history 
BEFORE INSERT ON bmi_history 
FOR EACH ROW 
BEGIN
    SELECT CASE 
        WHEN NEW.user_id NOT IN (SELECT id FROM users) 
        THEN RAISE(ABORT, 'Invalid user_id in bmi_history')
    END;
END;
''')

cursor.execute('''
CREATE TRIGGER IF NOT EXISTS verify_user_id_disease_predictions 
BEFORE INSERT ON disease_predictions 
FOR EACH ROW 
BEGIN
    SELECT CASE 
        WHEN NEW.user_id NOT IN (SELECT id FROM users) 
        THEN RAISE(ABORT, 'Invalid user_id in disease_predictions')
    END;
END;
''')

cursor.execute('''
CREATE TRIGGER IF NOT EXISTS verify_user_id_health_goals 
BEFORE INSERT ON health_goals 
FOR EACH ROW 
BEGIN
    SELECT CASE 
        WHEN NEW.user_id NOT IN (SELECT id FROM users) 
        THEN RAISE(ABORT, 'Invalid user_id in health_goals')
    END;
END;
''')

cursor.execute('''
CREATE TRIGGER IF NOT EXISTS verify_user_id_chatbot_interactions 
BEFORE INSERT ON chatbot_interactions 
FOR EACH ROW 
BEGIN
    SELECT CASE 
        WHEN NEW.user_id NOT IN (SELECT id FROM users) 
        THEN RAISE(ABORT, 'Invalid user_id in chatbot_interactions')
    END;
END;
''')

cursor.execute('''
CREATE TRIGGER IF NOT EXISTS verify_user_id_emergency_contacts 
BEFORE INSERT ON emergency_contacts 
FOR EACH ROW 
BEGIN
    SELECT CASE 
        WHEN NEW.user_id NOT IN (SELECT id FROM users) 
        THEN RAISE(ABORT, 'Invalid user_id in emergency_contacts')
    END;
END;
''')

# Add a demo user if none exists
cursor.execute("SELECT COUNT(*) FROM users")
if cursor.fetchone()[0] == 0:
    # Create a properly hashed password for the demo user
    password_hash = generate_password_hash('demopassword')
    
    cursor.execute('''
    INSERT INTO users (
        username, email, password_hash, first_name, last_name, 
        date_of_birth, gender, height, weight, blood_type
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        'demo_user', 
        'demo@example.com', 
        password_hash,  # Use proper password hashing
        'Demo',
        'User',
        '1990-01-01',
        'Male',
        175.0,  # height in cm
        70.0,   # weight in kg
        'O+'
    ))
    user_id = cursor.lastrowid
    print(f"Demo user created with ID: {user_id}")
    
    # Only add sample data for the demo user when it's first created
    
    # Add sample health monitoring data
    print("Adding sample health monitoring data for demo user...")
    # Generate sample data for the past 7 days
    for days_ago in range(7, -1, -1):  # 7 days ago to today
        date = datetime.now() - timedelta(days=days_ago)
        
        # Morning entry
        morning_entry = {
            'user_id': user_id,
            'heart_rate': random.randint(65, 85),
            'blood_pressure': json.dumps({
                'systolic': random.randint(110, 130),
                'diastolic': random.randint(70, 90)
            }),
            'oxygen_level': random.randint(95, 99),
            'body_temperature': round(random.uniform(97.8, 99.0), 1),
            'glucose_level': round(random.uniform(80.0, 120.0), 1) if random.random() > 0.5 else None,
            'cholesterol_level': round(random.uniform(150.0, 220.0), 1) if random.random() > 0.7 else None,
            'stress_level': random.randint(2, 7) if random.random() > 0.3 else None,
            'sleep_hours': round(random.uniform(6.0, 8.5), 1) if days_ago > 0 else None,
            'notes': "Morning reading" if days_ago in [0, 2, 5] else None,
            'created_at': (date.replace(hour=8, minute=random.randint(0, 59))).strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Evening entry (not for every day to make it more realistic)
        if days_ago not in [1, 4]:
            evening_entry = {
                'user_id': user_id,
                'heart_rate': random.randint(60, 80),
                'blood_pressure': json.dumps({
                    'systolic': random.randint(110, 135),
                    'diastolic': random.randint(70, 90)
                }),
                'oxygen_level': random.randint(95, 99),
                'body_temperature': round(random.uniform(97.8, 99.0), 1),
                'glucose_level': round(random.uniform(90.0, 130.0), 1) if random.random() > 0.5 else None,
                'cholesterol_level': None,
                'stress_level': random.randint(3, 8) if random.random() > 0.3 else None,
                'sleep_hours': None,
                'notes': "Evening reading" if days_ago in [0, 3] else None,
                'created_at': (date.replace(hour=20, minute=random.randint(0, 59))).strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # Insert evening entry
            cursor.execute('''
            INSERT INTO health_monitoring 
            (user_id, heart_rate, blood_pressure, oxygen_level, body_temperature, 
             glucose_level, cholesterol_level, stress_level, sleep_hours, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                evening_entry['user_id'],
                evening_entry['heart_rate'],
                evening_entry['blood_pressure'],
                evening_entry['oxygen_level'],
                evening_entry['body_temperature'],
                evening_entry['glucose_level'],
                evening_entry['cholesterol_level'],
                evening_entry['stress_level'],
                evening_entry['sleep_hours'],
                evening_entry['notes'],
                evening_entry['created_at']
            ))
        
        # Insert morning entry
        cursor.execute('''
        INSERT INTO health_monitoring 
        (user_id, heart_rate, blood_pressure, oxygen_level, body_temperature,
         glucose_level, cholesterol_level, stress_level, sleep_hours, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            morning_entry['user_id'],
            morning_entry['heart_rate'],
            morning_entry['blood_pressure'],
            morning_entry['oxygen_level'],
            morning_entry['body_temperature'],
            morning_entry['glucose_level'],
            morning_entry['cholesterol_level'],
            morning_entry['stress_level'],
            morning_entry['sleep_hours'],
            morning_entry['notes'],
            morning_entry['created_at']
        ))
    
    print("Sample health monitoring data added for demo user")
    
    # Continue with other sample data for the demo user only
    # Add sample medication reminders
    medications = [
        {
            'user_id': user_id,
            'medication_name': 'Vitamin D',
            'dosage': '1000 IU',
            'reminder_time': '08:00',
            'frequency': 'daily',
            'days_of_week': json.dumps(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]),
            'start_date': datetime.now().strftime('%Y-%m-%d'),
            'end_date': (datetime.now() + timedelta(days=90)).strftime('%Y-%m-%d'),
            'notes': 'Take with breakfast'
        },
        {
            'user_id': user_id,
            'medication_name': 'Omega-3',
            'dosage': '500mg',
            'reminder_time': '13:00',
            'frequency': 'daily',
            'days_of_week': json.dumps(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]),
            'start_date': datetime.now().strftime('%Y-%m-%d'),
            'end_date': None,
            'notes': 'Take with lunch'
        },
        {
            'user_id': user_id,
            'medication_name': 'Magnesium',
            'dosage': '250mg',
            'reminder_time': '21:00',
            'frequency': 'daily',
            'days_of_week': json.dumps(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]),
            'start_date': datetime.now().strftime('%Y-%m-%d'),
            'end_date': None,
            'notes': 'Take before bedtime'
        },
        {
            'user_id': user_id,
            'medication_name': 'Vitamin B12',
            'dosage': '1000mcg',
            'reminder_time': '08:30',
            'frequency': 'weekly',
            'days_of_week': json.dumps(["Mon"]),
            'start_date': datetime.now().strftime('%Y-%m-%d'),
            'end_date': None,
            'notes': 'Weekly supplement'
        }
    ]
    
    for med in medications:
        cursor.execute('''
        INSERT INTO medication_reminders 
        (user_id, medication_name, dosage, reminder_time, frequency, days_of_week, start_date, end_date, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            med['user_id'],
            med['medication_name'],
            med['dosage'],
            med['reminder_time'],
            med['frequency'],
            med['days_of_week'],
            med['start_date'],
            med['end_date'],
            med['notes']
        ))
    
    print("Sample medication reminders added for demo user")
    
    # Continue with other sample data for demo user only
    
else:
    # Just check if user has height field (might be missing in existing records) and update if needed
    cursor.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]
    
    cursor.execute("SELECT id FROM users WHERE username = 'demo_user'")
    result = cursor.fetchone()
    demo_user_id = result[0] if result else None
    
    # Update user with height if needed, but only for demo user
    if demo_user_id and 'height' in columns:
        cursor.execute("SELECT height FROM users WHERE id = ?", (demo_user_id,))
        height_result = cursor.fetchone()
        if height_result is None or height_result[0] is None:
            cursor.execute("UPDATE users SET height = ?, weight = ? WHERE id = ?", 
                         (175.0, 70.0, demo_user_id))
            print(f"Updated height for demo user ID: {demo_user_id}")
    
    if demo_user_id:
        print(f"Using existing demo user with ID: {demo_user_id}")

# Check if admin user exists
cursor.execute("SELECT id FROM users WHERE username = 'admin'")
admin_exists = cursor.fetchone()

if not admin_exists:
    # Create admin user
    admin_password_hash = generate_password_hash("admin123")
    cursor.execute('''
    INSERT INTO users (username, email, password_hash, is_admin, created_at)
    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
    ''', ('admin', 'admin@healthassistant.com', admin_password_hash, True))
    print("Admin user created with credentials: admin/admin123")

# Check and fix admin templates
templates_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
if not os.path.exists(templates_dir):
    os.makedirs(templates_dir)
    print(f"Created templates directory: {templates_dir}")

# Define templates that need to be accessible for admin panel
admin_templates = [
    'admin_login.html',
    'direct_admin_login.html',
    'admin_dashboard.html',
    'direct_admin_dashboard.html',
    'admin_users.html',
    'direct_admin_users.html',
    'admin_user_history.html',
    'user_history.html'
]

# Create placeholder templates if they don't exist
for template in admin_templates:
    template_path = os.path.join(templates_dir, template)
    if not os.path.exists(template_path):
        print(f"Template {template} not found. Creating placeholder.")
        with open(template_path, 'w') as f:
            f.write(f"<!DOCTYPE html>\n<html><head><title>{template}</title></head><body><h1>Placeholder for {template}</h1></body></html>")

# Commit all changes and close the connection
conn.commit()
conn.close()

print("Database setup complete!")