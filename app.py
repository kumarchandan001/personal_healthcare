from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash, g
import sqlite3
import os
import json
import traceback
from datetime import datetime, timedelta
import pandas as pd
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import sys
import re
from flask.json.tag import TaggedJSONSerializer
from itsdangerous import URLSafeTimedSerializer
import flask
import pickle

app = Flask(__name__)
app.secret_key = "health_assistant_fixed_secret_key_updated_2"
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Helper function to check if all navigation links have corresponding routes
def check_navigation_routes():
    nav_links = [
        'home', 'disease_prediction', 'health_advice', 'health_monitor', 
        'activity', 'medication_reminder', 'bmi', 'medical_prescription',
        'record_management', 'emergency', 'tips'
    ]
    
    missing_routes = []
    for link in nav_links:
        if link not in app.view_functions:
            missing_routes.append(link)
    
    if missing_routes:
        print(f"WARNING: Missing routes for navigation links: {', '.join(missing_routes)}")

class MockUser:
    def __init__(self, is_authenticated=False, username="Guest"):
        self.is_authenticated = is_authenticated
        self.username = username

@app.context_processor
def inject_user():
    user_id = session.get('user_id')
    if user_id:
        username = session.get('username', 'User')
        return {'current_user': MockUser(is_authenticated=True, username=username)}
    return {'current_user': MockUser()}

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this feature', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_db_connection():
    try:
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'health.db')
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys = ON')
        conn.execute('PRAGMA busy_timeout = 5000')
        
        if session.get('is_admin', False):
            return conn
        
        if 'user_id' in session:
            user_id = session.get('user_id')
            def row_level_security_filter(row):
                if hasattr(row, 'keys') and 'user_id' in row.keys():
                    return row['user_id'] == user_id
                return True
                
            original_row_factory = conn.row_factory
            def secure_row_factory(cursor, row):
                result = original_row_factory(cursor, row)
                if row_level_security_filter(result):
                    return result
                return None
                
            conn.row_factory = secure_row_factory
                
        return conn
    except Exception as e:
        print(f"Database connection error: {str(e)}")
        return None

def sanitize_user_data(data, user_id=None):
    if user_id is None and 'user_id' in session:
        user_id = session.get('user_id')
    elif user_id is None:
        return []
        
    if not data:
        return data
        
    if isinstance(data, list):
        return [item for item in data if (
            (isinstance(item, dict) and item.get('user_id') == user_id) or
            (hasattr(item, 'keys') and 'user_id' in item.keys() and item['user_id'] == user_id)
        )]
        
    if isinstance(data, dict) and data.get('user_id') != user_id:
        return {}
        
    if hasattr(data, 'keys') and 'user_id' in data.keys() and data['user_id'] != user_id:
        return {}
        
    return data

@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/home')
def home_redirect():
    return redirect(url_for('home'))

@app.route('/health_monitor')
@login_required
def health_monitor():
    return render_template('health_monitor.html')

@app.route('/health_advice')
@login_required
def health_advice():
    return render_template('health_advice.html')

@app.route('/disease_prediction')
@login_required
def disease_prediction():
    return render_template('disease_prediction.html')

@app.route('/activity')
@login_required
def activity():
    return render_template('activity_tracking.html')

@app.route('/medication_reminder')
@login_required
def medication_reminder():
    return render_template('medication_reminder.html')

@app.route('/bmi')
@login_required
def bmi():
    return render_template('bmi_calculator.html')

@app.route('/medical_prescription')
@login_required
def medical_prescription():
    return render_template('medical_prescription.html')

@app.route('/record_management')
@login_required
def record_management():
    return render_template('record_management.html')

@app.route('/emergency')
@login_required
def emergency():
    return render_template('emergency_support.html')

@app.route('/tips')
@login_required
def tips():
    return render_template('tips_section.html')

@app.route('/api/health-monitoring', methods=['POST'])
@login_required
def save_health_data():
    try:
        user_id = session.get('user_id')
        data = request.json
        if not data:
            return jsonify({'success': False, 'error': 'No data received'}), 400
            
        print(f"Received data: {data}")
        
        if 'heart_rate' not in data or 'blood_pressure' not in data or 'oxygen_level' not in data:
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
        blood_pressure = data.get('blood_pressure')
        if isinstance(blood_pressure, dict):
            blood_pressure = json.dumps(blood_pressure)
        
        print(f"Processed blood pressure: {blood_pressure}")
        
        if not os.path.exists('health.db'):
            print("Database file not found, creating new one")
            import create_db
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500
            
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
            if not cursor.fetchone():
                return jsonify({'success': False, 'error': 'Invalid user session'}), 401
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='health_monitoring'")
            if not cursor.fetchone():
                print("Tables not found, creating them")
                conn.close()
                import create_db
                conn = get_db_connection()
                if not conn:
                    return jsonify({'success': False, 'error': 'Database connection failed after table creation'}), 500
                cursor = conn.cursor()
            
            params = (
                user_id,
                data.get('heart_rate'),
                blood_pressure,
                data.get('oxygen_level'),
                data.get('body_temperature'),
                data.get('glucose_level'),
                data.get('notes')
            )
            
            cursor.execute('''
                INSERT INTO health_monitoring 
                (user_id, heart_rate, blood_pressure, oxygen_level, body_temperature, glucose_level, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', params)
            
            metrics = [
                ('heart_rate', data.get('heart_rate')),
                ('oxygen_level', data.get('oxygen_level'))
            ]
            
            if data.get('glucose_level'):
                metrics.append(('glucose_level', data.get('glucose_level')))
            
            if data.get('body_temperature'):
                metrics.append(('body_temperature', data.get('body_temperature')))
                
            if isinstance(data.get('blood_pressure'), dict):
                bp = data.get('blood_pressure')
                if 'systolic' in bp:
                    metrics.append(('blood_pressure_systolic', bp['systolic']))
                if 'diastolic' in bp:
                    metrics.append(('blood_pressure_diastolic', bp['diastolic']))
            
            for metric, value in metrics:
                cursor.execute('''
                    INSERT INTO health_data (user_id, metric, value)
                    VALUES (?, ?, ?)
                ''', (user_id, metric, value))
            
            conn.commit()
            return jsonify({'success': True, 'message': 'Health data saved successfully'})
            
        except sqlite3.Error as e:
            conn.rollback()
            print(f"Database error: {str(e)}")
            return jsonify({'success': False, 'error': f'Database error: {str(e)}'}), 500
        finally:
            conn.close()
            
    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"Error saving health data: {str(e)}")
        print(f"Error trace: {error_trace}")
        return jsonify({'success': False, 'error': str(e)}), 500

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
            
        start_date = datetime.now() - timedelta(days=days)
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500
            
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
            if not cursor.fetchone():
                return jsonify({'success': False, 'error': 'Invalid user session'}), 401
            
            cursor.execute('''
                SELECT * FROM health_monitoring
                WHERE user_id = ? AND created_at >= ?
                ORDER BY created_at DESC
            ''', (user_id, start_date.strftime('%Y-%m-%d %H:%M:%S')))
            
            history = []
            for row in cursor.fetchall():
                item = dict(row)
                if item.get('user_id') != user_id:
                    continue
                    
                if item.get('blood_pressure'):
                    try:
                        item['blood_pressure'] = json.loads(item['blood_pressure'])
                    except:
                        pass
                history.append(item)
            
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

@app.route('/predict', methods=['POST'])
@login_required
def predict_disease():
    try:
        user_id = session.get('user_id')
        data = request.json
        
        if not data:
            return jsonify({'error': 'No data received'}), 400
        
        print(f"Received symptom data: {data}")
        selected_symptoms = list(data.keys())
        
        try:
            model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'health_assistant_model.pkl')
            if os.path.exists(model_path):
                model = pickle.load(open(model_path, 'rb'))
                label_encoder = pickle.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'label_encoder.pkl'), 'rb'))
                disease_precautions = pickle.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'disease_precautions.pkl'), 'rb'))
                disease_descriptions = pickle.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'disease_descriptions.pkl'), 'rb'))
                feature_names = pickle.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'feature_names.pkl'), 'rb'))
                display_to_data = pickle.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'display_to_data.pkl'), 'rb'))
                
                features = [0] * len(feature_names)
                for symptom in data.keys():
                    if symptom in display_to_data:
                        data_symptom = display_to_data[symptom]
                        if data_symptom in feature_names:
                            idx = feature_names.index(data_symptom)
                            features[idx] = 1
                    elif symptom in feature_names:
                        idx = feature_names.index(symptom)
                        features[idx] = 1
                
                prediction = model.predict([features])
                predicted_disease = label_encoder.inverse_transform(prediction)[0]
                confidence = max(model.predict_proba([features])[0])
                
                description = disease_descriptions.get(predicted_disease, "No description available")
                precautions = disease_precautions.get(predicted_disease, ["Consult a doctor"])
                
                print(f"Model prediction: {predicted_disease} with confidence {confidence}")
            else:
                raise FileNotFoundError("Model file not found")
        except Exception as e:
            print(f"Error using model: {str(e)}, using dataset-based prediction")
            
            try:
                dataset_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Disease_Symptom_Dataset.csv')
                description_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'symptom_Description.csv')
                precaution_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'symptom_precaution.csv')
                severity_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Symptom-severity.csv')
                
                disease_data = pd.read_csv(dataset_path)
                descriptions = pd.read_csv(description_path)
                precautions_data = pd.read_csv(precaution_path)
                severity_data = pd.read_csv(severity_path)
                
                for col in disease_data.columns[1:]:
                    if col.startswith('Symptom'):
                        disease_data[col] = disease_data[col].str.strip() if disease_data[col].dtype == 'object' else disease_data[col]
                
                disease_matches = {}
                symptom_severity = {}
                
                for _, row in severity_data.iterrows():
                    symptom_severity[row['Symptom']] = row['weight']
                
                selected_severity = 0
                for symptom in selected_symptoms:
                    if symptom in symptom_severity:
                        selected_severity += symptom_severity[symptom]
                
                for _, row in disease_data.iterrows():
                    disease = row['Disease']
                    disease_symptoms = []
                    for col in disease_data.columns[1:]:
                        if pd.notna(row[col]) and row[col] != '':
                            disease_symptoms.append(row[col].strip() if isinstance(row[col], str) else row[col])
                    
                    match_count = 0
                    severity_score = 0
                    for symptom in selected_symptoms:
                        if symptom in disease_symptoms:
                            match_count += 1
                            if symptom in symptom_severity:
                                severity_score += symptom_severity[symptom]
                    
                    if len(disease_symptoms) > 0:
                        match_percentage = match_count / len(disease_symptoms)
                        if disease not in disease_matches or match_percentage > disease_matches[disease]['match_percentage']:
                            disease_matches[disease] = {
                                'match_count': match_count,
                                'match_percentage': match_percentage,
                                'severity_score': severity_score,
                                'total_symptoms': len(disease_symptoms)
                            }
                
                if disease_matches:
                    sorted_matches = sorted(
                        disease_matches.items(), 
                        key=lambda x: (x[1]['match_percentage'], x[1]['severity_score']), 
                        reverse=True
                    )
                    
                    top_matches = sorted_matches[:3]
                    best_match = top_matches[0]
                    predicted_disease = best_match[0]
                    match_data = best_match[1]
                    
                    confidence = min(0.95, match_data['match_percentage'] * 0.7 + 
                                    (match_data['severity_score'] / (selected_severity + 0.1)) * 0.3)
                    
                    disease_info = descriptions[descriptions['Disease'] == predicted_disease]
                    if not disease_info.empty:
                        description = disease_info.iloc[0]['Description']
                    else:
                        description = f"Information about {predicted_disease} is not available."
                    
                    precaution_info = precautions_data[precautions_data['Disease'] == predicted_disease]
                    if not precaution_info.empty:
                        precautions = []
                        for i in range(1, 5):
                            precaution = precaution_info.iloc[0].get(f'Precaution_{i}')
                            if pd.notna(precaution) and precaution:
                                precautions.append(precaution)
                    else:
                        precautions = ["Consult a healthcare professional"]
                    
                    print(f"Dataset-based prediction: {predicted_disease} with confidence {confidence:.2f}")
                else:
                    predicted_disease = "Unknown Condition"
                    confidence = 0.3
                    description = "Based on the symptoms provided, we couldn't determine a specific condition. Please consult a healthcare professional."
                    precautions = ["Consult a doctor", "Monitor your symptoms", "Rest and stay hydrated"]
            except Exception as dataset_error:
                print(f"Error using dataset for prediction: {str(dataset_error)}, using fallback prediction")
                symptom_count = len(data)
                
                if "skin_rash" in data and "itching" in data:
                    predicted_disease = "Fungal infection"
                    confidence = 0.75
                    description = "A fungal infection is caused by fungi that take over an area of the body."
                    precautions = ["Keep the affected area clean and dry", "Use antifungal medications", "Maintain good hygiene"]
                elif "high_fever" in data and "headache" in data and "chills" in data:
                    predicted_disease = "Malaria"
                    confidence = 0.80
                    description = "Malaria is a serious disease caused by a parasite that is transmitted by the bite of infected mosquitoes."
                    precautions = ["Consult a doctor immediately", "Take prescribed medications", "Use mosquito repellent"]
                elif "continuous_sneezing" in data and "chills" in data:
                    predicted_disease = "Allergy"
                    confidence = 0.70
                    description = "An allergy is an immune system response to a foreign substance that's not typically harmful to your body."
                    precautions = ["Avoid allergens", "Take antihistamines", "Use nasal sprays if prescribed"]
                elif "vomiting" in data and "stomach_pain" in data:
                    predicted_disease = "GERD"
                    confidence = 0.65
                    description = "Gastroesophageal reflux disease (GERD) occurs when stomach acid frequently flows back into the tube connecting your mouth and stomach."
                    precautions = ["Avoid spicy and fatty foods", "Don't lie down after eating", "Elevate your head while sleeping"]
                elif "fatigue" in data and "weight_loss" in data and "restlessness" in data:
                    predicted_disease = "Diabetes"
                    confidence = 0.75
                    description = "Diabetes is a disease that occurs when your blood glucose is too high."
                    precautions = ["Monitor blood sugar regularly", "Follow a balanced diet", "Exercise regularly"]
                elif symptom_count > 5:
                    predicted_disease = "Influenza"
                    confidence = 0.65
                    description = "Influenza is a viral infection that attacks your respiratory system."
                    precautions = ["Rest and drink plenty of fluids", "Take over-the-counter pain relievers", "Stay home to avoid spreading infection"]
                elif "fatigue" in data and "mild_fever" in data:
                    predicted_disease = "Common Cold"
                    confidence = 0.70
                    description = "The common cold is a viral infection of your nose and throat."
                    precautions = ["Rest and stay hydrated", "Use saline nasal drops", "Take over-the-counter cold medications"]
                else:
                    predicted_disease = "General Viral Infection"
                    confidence = 0.50
                    description = "A viral infection is any illness caused by a virus."
                    precautions = ["Rest well", "Stay hydrated", "Take fever reducers if needed"]
        
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                symptoms_json = json.dumps(list(data.keys()))
                
                cursor.execute('''
                    INSERT INTO disease_predictions 
                    (user_id, symptoms, predicted_disease, confidence_score, recommendations, predicted_at)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (user_id, symptoms_json, predicted_disease, confidence, json.dumps(precautions)))
                
                conn.commit()
                conn.close()
        except Exception as e:
            print(f"Failed to save prediction: {str(e)}")
        
        top_symptoms = [{"symptom": symptom.replace("_", " ").title()} for symptom in list(data.keys())[:5]]
        
        response = {
            'predicted_disease': predicted_disease,
            'confidence': confidence,
            'description': description,
            'precautions': precautions,
            'top_symptoms': top_symptoms
        }
        
        return jsonify(response)
        
    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"Error in disease prediction: {str(e)}")
        print(f"Error trace: {error_trace}")
        return jsonify({'error': str(e)}), 500

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('home'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Please provide both username/email and password', 'error')
            return render_template('login.html')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT id, username, email, password_hash FROM users WHERE username = ? OR email = ?", 
                          (username, username))
            user_data = cursor.fetchone()
            
            if user_data and check_password_hash(user_data['password_hash'], password):
                session.clear()
                session['user_id'] = user_data['id']
                session['username'] = user_data['username']
                session.permanent = True
                
                cursor.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?", (user_data['id'],))
                conn.commit()
                
                return redirect(url_for('home'))
            else:
                flash('Invalid username or password', 'error')
        except Exception as e:
            print(f"Login error: {str(e)}")
            flash('An error occurred during login', 'error')
        finally:
            conn.close()
        
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if 'user_id' in session:
        return redirect(url_for('home'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not username or not email or not password:
            flash('All fields are required', 'error')
            return render_template('signup.html')
            
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('signup.html')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT id FROM users WHERE username = ? OR email = ?", (username, email))
            if cursor.fetchone():
                flash('Username or email already exists', 'error')
                return render_template('signup.html')
                
            password_hash = generate_password_hash(password)
            cursor.execute(
                "INSERT INTO users (username, email, password_hash, created_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
                (username, email, password_hash)
            )
            conn.commit()
            
            cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
            user_id = cursor.fetchone()['id']
            
            session.clear()
            session['user_id'] = user_id
            session['username'] = username
            session.permanent = True
        
            flash('Account created successfully!', 'success')
            return redirect(url_for('home'))
        except Exception as e:
            conn.rollback()
            print(f"Error creating user: {str(e)}")
            flash('An error occurred during registration', 'error')
            return render_template('signup.html')
        finally:
            conn.close()
        
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'success')
    return redirect(url_for('home'))

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('admin_login'))
        
        try:
            conn = get_db_connection()
            if not conn:
                return redirect(url_for('admin_login'))
            
            cursor = conn.cursor()
            cursor.execute("SELECT is_admin FROM users WHERE id = ?", (session['user_id'],))
            user = cursor.fetchone()
            
            if not user or not user['is_admin']:
                session.clear()
                return redirect(url_for('admin_login'))
                
            return f(*args, **kwargs)
        except Exception as e:
            print(f"Admin auth error: {str(e)}")
            session.clear()
            return redirect(url_for('admin_login'))
        finally:
            if conn:
                conn.close()
    return decorated_function

def initialize_app():
    print("Initializing Health Assistant application...")
    check_navigation_routes()
    print("Database integrity check skipped - use fix_admin_redirect.py to repair database if needed")
    app.config['DB_CHECK_RESULT'] = {'status': 'skipped', 'message': 'Database check skipped'}

@app.route('/get_health_advice', methods=['POST'])
@login_required
def get_health_advice():
    try:
        data = request.json
        if not data or 'symptoms' not in data or 'severity' not in data:
            return jsonify({
                'error': 'Missing required fields'
            }), 400

        symptoms = data['symptoms']
        severity = data['severity']

        # Basic validation
        if not isinstance(symptoms, list) or not symptoms:
            return jsonify({
                'error': 'Invalid symptoms format'
            }), 400

        if severity not in ['mild', 'moderate', 'severe']:
            return jsonify({
                'error': 'Invalid severity level'
            }), 400

        # Generate advice based on symptoms and severity
        advice = generate_health_advice(symptoms, severity)
        
        return jsonify(advice)

    except Exception as e:
        print(f"Error in get_health_advice: {str(e)}")
        return jsonify({
            'error': 'Internal server error'
        }), 500

def generate_health_advice(symptoms, severity):
    # Common immediate actions based on severity
    immediate_actions = {
        'mild': [
            "Rest and monitor your symptoms",
            "Stay hydrated by drinking plenty of water",
            "Get adequate sleep and rest"
        ],
        'moderate': [
            "Contact your healthcare provider for guidance",
            "Monitor your symptoms closely",
            "Rest and avoid strenuous activities"
        ],
        'severe': [
            "Seek immediate medical attention",
            "Call emergency services if symptoms worsen",
            "Do not delay getting professional help"
        ]
    }

    # Home care recommendations based on symptoms
    home_care = []
    for symptom in symptoms:
        if 'fever' in symptom:
            home_care.extend([
                "Use over-the-counter fever reducers as directed",
                "Apply cool compresses",
                "Dress in light clothing"
            ])
        if 'cough' in symptom or 'sore_throat' in symptom:
            home_care.extend([
                "Use warm salt water gargles",
                "Stay in a humid environment",
                "Use throat lozenges for temporary relief"
            ])
        if 'headache' in symptom:
            home_care.extend([
                "Rest in a quiet, dark room",
                "Apply cold or warm compress to head",
                "Practice relaxation techniques"
            ])
        if 'nausea' in symptom or 'vomiting' in symptom:
            home_care.extend([
                "Eat bland foods (BRAT diet)",
                "Take small sips of clear fluids",
                "Avoid solid foods temporarily"
            ])

    # Remove duplicates while preserving order
    home_care = list(dict.fromkeys(home_care))

    # Medical advice based on severity and symptoms
    medical_advice = {
        'mild': [
            "Monitor symptoms for 24-48 hours",
            "Use over-the-counter medications as needed",
            "Rest and maintain good hygiene"
        ],
        'moderate': [
            "Schedule an appointment with your doctor",
            "Keep a symptom diary to share with healthcare provider",
            "Follow up if symptoms persist or worsen"
        ],
        'severe': [
            "Go to the emergency room or call emergency services",
            "Do not attempt to drive yourself if severely ill",
            "Have someone stay with you until help arrives"
        ]
    }

    # Additional resources
    resources = [
        {
            "title": "Understanding Your Symptoms",
            "description": "Comprehensive guide to common health symptoms and their meanings",
            "url": "https://www.who.int/health-topics"
        },
        {
            "title": "When to Seek Emergency Care",
            "description": "Guidelines for recognizing serious medical conditions",
            "url": "https://www.cdc.gov/emergency"
        },
        {
            "title": "Home Care Guidelines",
            "description": "Expert advice on managing symptoms at home",
            "url": "https://www.mayoclinic.org/first-aid"
        }
    ]

    return {
        "immediate_actions": immediate_actions[severity],
        "home_care": home_care[:5],  # Limit to top 5 most relevant
        "medical_advice": medical_advice[severity],
        "resources": resources
    }

@app.route('/submit_prescription', methods=['POST'])
@login_required
def submit_prescription():
    if request.method == 'POST':
        try:
            # Get form data
            data = request.get_json()
            
            conn = get_db_connection()
            if not conn:
                return jsonify({'success': False, 'message': 'Database connection error'}), 500
                
            cursor = conn.cursor()
            
            # Insert prescription data
            cursor.execute('''
                INSERT INTO medical_prescriptions 
                (user_id, doctor_name, specialization, patient_name, patient_age, 
                patient_gender, allergies, diagnosis, medications, instructions, follow_up)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                session['user_id'],
                data.get('doctor_name', ''),
                data.get('specialization', ''),
                data.get('patient_name', ''),
                data.get('age', 0),
                data.get('gender', ''),
                data.get('allergies', ''),
                data.get('diagnosis', ''),
                data.get('medications', ''),
                data.get('instructions', ''),
                data.get('follow_up', '')
            ))
            
            conn.commit()
            conn.close()
            
            return jsonify({'success': True, 'message': 'Prescription saved successfully'}), 200
        except Exception as e:
            return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500
    
    return jsonify({'success': False, 'message': 'Invalid request method'}), 405

if __name__ == "__main__":
    check_navigation_routes()
    initialize_app()
    app.run(debug=True, port=5000) 