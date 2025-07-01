import sqlite3
import json
import random
from datetime import datetime, timedelta
import os

# Database connection
db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'health.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Helper function to generate a random date within the last 6 months
def random_date(start_days_ago=180, end_days_ago=1):
    start_date = datetime.now() - timedelta(days=start_days_ago)
    end_date = datetime.now() - timedelta(days=end_days_ago)
    delta = end_date - start_date
    random_days = random.randrange(delta.days)
    return start_date + timedelta(days=random_days)

# Get a demo user to add sample data for
cursor.execute("SELECT id FROM users WHERE username = 'demo_user' LIMIT 1")
user = cursor.fetchone()

if not user:
    print("Creating demo user...")
    from werkzeug.security import generate_password_hash
    cursor.execute('''
        INSERT INTO users (username, email, password_hash, first_name, last_name, date_of_birth, gender, height, weight, blood_type, is_admin, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        'demo_user',
        'demo@example.com',
        generate_password_hash('password123'),
        'Demo',
        'User',
        '1990-01-01',
        'Male',
        175,
        70,
        'O+',
        0,
        datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ))
    user_id = cursor.lastrowid
    print(f"Created demo user with ID: {user_id}")
else:
    user_id = user[0]
    print(f"Using existing demo user with ID: {user_id}")

# Add sample BMI history data
print("Adding BMI history data...")
for i in range(10):
    entry_date = random_date()
    weight = round(random.uniform(65, 75), 1)  # Random weight between 65-75 kg
    height = 175  # Height in cm
    bmi = round(weight / ((height/100) ** 2), 1)
    
    if bmi < 18.5:
        category = "Underweight"
    elif bmi < 25:
        category = "Normal"
    elif bmi < 30:
        category = "Overweight"
    else:
        category = "Obese"
    
    cursor.execute('''
        INSERT INTO bmi_history (user_id, height, weight, bmi, bmi_category, recorded_at, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        user_id,
        height,
        weight,
        bmi,
        category,
        entry_date.strftime('%Y-%m-%d %H:%M:%S'),
        f"BMI check {i+1}" if i % 3 == 0 else None
    ))

# Add sample activity tracking data
print("Adding activity tracking data...")
activities = ["walking", "running", "cycling", "swimming", "yoga", "gym_workout"]

for i in range(15):
    activity_date = random_date()
    activity_type = random.choice(activities)
    duration = random.randint(15, 120)  # 15-120 minutes
    
    steps = None
    distance = None
    calories = None
    
    if activity_type == "walking":
        steps = random.randint(2000, 8000)
        distance = round(steps * 0.0007, 2)  # Rough estimate
        calories = int(steps * 0.04)
    elif activity_type == "running":
        steps = random.randint(4000, 12000)
        distance = round(steps * 0.0008, 2)
        calories = int(steps * 0.07)
    else:
        calories = random.randint(100, 600)
    
    cursor.execute('''
        INSERT INTO activity_tracking (user_id, activity_type, duration, steps, calories_burned, activity_date, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        user_id,
        activity_type,
        duration,
        steps,
        calories,
        activity_date.strftime('%Y-%m-%d'),
        f"Felt good during this {activity_type} session" if i % 4 == 0 else None,
        activity_date.strftime('%Y-%m-%d %H:%M:%S')
    ))

# Add sample medical records
print("Adding medical records data...")
record_types = ["lab_report", "prescription", "imaging", "vaccination", "other"]
record_names = [
    "Blood Test Results", "Annual Physical", "X-Ray", "COVID-19 Vaccination", 
    "Allergy Test", "MRI Scan", "Dental Checkup", "Eye Examination"
]

for i in range(8):
    record_date = random_date()
    record_type = random.choice(record_types)
    record_name = record_names[i]
    
    cursor.execute('''
        INSERT INTO medical_records (user_id, record_name, record_type, file_path, record_date, notes, uploaded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        user_id,
        record_name,
        record_type,
        f"/uploads/records/{user_id}_{record_name.lower().replace(' ', '_')}.pdf",
        record_date.strftime('%Y-%m-%d'),
        f"Notes for {record_name}" if i % 3 == 0 else None,
        record_date.strftime('%Y-%m-%d %H:%M:%S')
    ))

# Add sample disease predictions
print("Adding disease prediction data...")
diseases = ["Common Cold", "Influenza", "Migraine", "Allergic Rhinitis", "Gastroenteritis"]
symptoms_list = [
    ["headache", "runny_nose", "sneezing", "sore_throat"],
    ["fever", "body_ache", "fatigue", "headache"],
    ["headache", "sensitivity_to_light", "nausea"],
    ["sneezing", "itchy_eyes", "congestion"],
    ["nausea", "vomiting", "diarrhea", "abdominal_pain"]
]

for i in range(6):
    prediction_date = random_date()
    disease_index = i % len(diseases)
    disease = diseases[disease_index]
    symptoms = symptoms_list[disease_index]
    confidence = round(random.uniform(0.65, 0.95), 2)
    
    cursor.execute('''
        INSERT INTO disease_predictions (user_id, symptoms, predicted_disease, confidence_score, predicted_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        user_id,
        json.dumps(symptoms),
        disease,
        confidence,
        prediction_date.strftime('%Y-%m-%d %H:%M:%S')
    ))

# Add sample prescriptions
print("Adding prescription data...")
doctors = ["John Smith", "Sarah Johnson", "Michael Lee", "Priya Patel"]
specializations = ["General Practitioner", "Cardiologist", "Neurologist", "Pediatrician", ""]
diagnoses = ["Common Cold", "Hypertension", "Migraine", "Allergic Rhinitis", "Gastroenteritis", "Vitamin D Deficiency"]
medications = [
    "Paracetamol 500mg - 1 tablet three times a day after meals for 5 days\nAntitussive syrup - 10ml twice daily for 7 days",
    "Amlodipine 5mg - 1 tablet daily in the morning\nLosartan 50mg - 1 tablet daily in the evening",
    "Sumatriptan 50mg - 1 tablet at onset of migraine, repeat after 2 hours if needed\nPropranolol 40mg - 1 tablet twice daily",
    "Cetirizine 10mg - 1 tablet daily at bedtime\nFluticasone nasal spray - 1 spray in each nostril daily",
    "Ondansetron 4mg - 1 tablet every 8 hours as needed\nOral rehydration solution - 1 packet dissolved in water after each loose stool"
]

for i in range(5):
    prescription_date = random_date()
    doctor_name = random.choice(doctors)
    diagnosis = random.choice(diagnoses)
    medication = medications[i % len(medications)]
    
    cursor.execute('''
        INSERT INTO medical_prescriptions (
            user_id, doctor_name, specialization, patient_name, patient_age, 
            patient_gender, allergies, diagnosis, medications, instructions, follow_up, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        user_id,
        doctor_name,
        random.choice(specializations),
        "Demo User",
        33,
        "Male",
        "Penicillin" if i % 3 == 0 else None,
        diagnosis,
        medication,
        "Take plenty of fluids and rest well" if i % 2 == 0 else None,
        "Follow up in 2 weeks if symptoms persist" if i % 3 == 0 else None,
        prescription_date.strftime('%Y-%m-%d %H:%M:%S')
    ))

conn.commit()
conn.close()

print("Sample data added successfully!") 