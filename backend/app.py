from flask import Flask, request, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import speech_recognition as sr
import os
import tempfile
from sentence_transformers import SentenceTransformer
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import jwt
from datetime import datetime, timedelta, timezone
import cv2
import base64
from io import BytesIO
from PIL import Image

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this'
# Changed to SQLite for prototyping — stores data in local file 'speakeval.db'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///speakeval.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'

db = SQLAlchemy(app)
CORS(app, resources={r"/api/*": {"origins": "http://localhost:5173"}})

# Initialize SBERT model for answer evaluation
sbert_model = SentenceTransformer('all-MiniLM-L6-v2')

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'student' or 'educator'
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Exam(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    educator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    duration_minutes = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('exam.id'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    expected_answer = db.Column(db.Text, nullable=False)
    points = db.Column(db.Integer, default=10)
    order = db.Column(db.Integer, nullable=False)

class ExamAttempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('exam.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    total_score = db.Column(db.Float)
    status = db.Column(db.String(20), default='in_progress')  # 'in_progress', 'completed', 'flagged'

class Answer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey('exam_attempt.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    spoken_text = db.Column(db.Text)
    audio_file_path = db.Column(db.String(255))
    similarity_score = db.Column(db.Float)
    points_awarded = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Helper Functions
def generate_token(user_id):
    payload = {
        'user_id': user_id,
        'exp': datetime.now(timezone.utc) + timedelta(days=1)
    }
    return jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')
def verify_token(token):
    try:
        payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        return payload['user_id']
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def speech_to_text(audio_file_path):
    """Convert audio file to text using speech_recognition"""
    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(audio_file_path) as source:
            audio = recognizer.record(source)
            text = recognizer.recognize_google(audio)
            return text
    except Exception as e:
        print(f"Speech recognition error: {e}")
        return None

def evaluate_answer(student_answer, expected_answer):
    """Evaluate answer using SBERT similarity"""
    try:
        # Get embeddings
        student_embedding = sbert_model.encode([student_answer])
        expected_embedding = sbert_model.encode([expected_answer])
        
        # Calculate cosine similarity
        similarity = cosine_similarity(student_embedding, expected_embedding)[0][0]
        return float(similarity)
    except Exception as e:
        print(f"Answer evaluation error: {e}")
        return 0.0

def detect_face(frame_data):
    """Basic face detection using OpenCV"""
    try:
        # Decode base64 image
        img_data = base64.b64decode(frame_data.split(',')[1])
        img = Image.open(BytesIO(img_data))
        frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        
        # Load face cascade
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)
        
        return len(faces) > 0
    except Exception as e:
        print(f"Face detection error: {e}")
        return False

# Routes
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already registered'}), 400
    
    user = User(
        email=data['email'],
        password_hash=generate_password_hash(data['password']),
        role=data['role'],
        name=data['name']
    )
    
    db.session.add(user)
    db.session.commit()
    
    token = generate_token(user.id)
    return jsonify({
        'token': token,
        'user': {
            'id': user.id,
            'email': user.email,
            'role': user.role,
            'name': user.name
        }
    })

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.json
        print("Login data received:", data)   # <-- Add this
        if not data or 'email' not in data or 'password' not in data:
            return jsonify({'error': 'Email and password required'}), 400

        user = User.query.filter_by(email=data['email']).first()
        if user:
            print("User found:", user.email)
        else:
            print("User not found")

        if user and check_password_hash(user.password_hash, data['password']):
            token = generate_token(user.id)
            return jsonify({
                'token': token,
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'role': user.role,
                    'name': user.name
                }
            })

        return jsonify({'error': 'Invalid credentials'}), 401

    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({'error': 'Server error during login'}), 500


@app.route('/api/exams', methods=['GET', 'POST'])
def handle_exams():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user_id = verify_token(token)
    
    if not user_id:
        return jsonify({'error': 'Invalid token'}), 401
    
    if request.method == 'GET':
        user = User.query.get(user_id)
        if user.role == 'educator':
            exams = Exam.query.filter_by(educator_id=user_id).all()
        else:
            exams = Exam.query.filter_by(is_active=True).all()
        
        return jsonify([{
            'id': exam.id,
            'title': exam.title,
            'description': exam.description,
            'duration_minutes': exam.duration_minutes,
            'created_at': exam.created_at.isoformat()
        } for exam in exams])
    
    elif request.method == 'POST':
        data = request.json
        exam = Exam(
            title=data['title'],
            description=data.get('description', ''),
            educator_id=user_id,
            duration_minutes=data['duration_minutes']
        )
        
        db.session.add(exam)
        db.session.flush()  # Get the exam ID
        
        # Add questions
        for i, q_data in enumerate(data['questions']):
            question = Question(
                exam_id=exam.id,
                question_text=q_data['question_text'],
                expected_answer=q_data['expected_answer'],
                points=q_data.get('points', 10),
                order=i + 1
            )
            db.session.add(question)
        
        db.session.commit()
        return jsonify({'message': 'Exam created successfully', 'exam_id': exam.id})

@app.route('/api/exams/<int:exam_id>/start', methods=['POST'])
def start_exam(exam_id):
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user_id = verify_token(token)
    
    if not user_id:
        return jsonify({'error': 'Invalid token'}), 401
    
    # Check if exam exists and is active
    exam = Exam.query.get_or_404(exam_id)
    if not exam.is_active:
        return jsonify({'error': 'Exam is not active'}), 400
    
    # Create exam attempt
    attempt = ExamAttempt(
        exam_id=exam_id,
        student_id=user_id
    )
    
    db.session.add(attempt)
    db.session.commit()
    
    # Get questions
    questions = Question.query.filter_by(exam_id=exam_id).order_by(Question.order).all()
    
    return jsonify({
        'attempt_id': attempt.id,
        'exam': {
            'id': exam.id,
            'title': exam.title,
            'duration_minutes': exam.duration_minutes
        },
        'questions': [{
            'id': q.id,
            'question_text': q.question_text,
            'points': q.points,
            'order': q.order
        } for q in questions]
    })
@app.route('/api/evaluate-answer', methods=['POST'])
def evaluate_answer_endpoint():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user_id = verify_token(token)

    if not user_id:
        return jsonify({'error': 'Invalid token'}), 401

    data = request.json
    attempt_id = data.get('attempt_id')
    question_id = data.get('question_id')
    spoken_text = data.get('spoken_text')

    if not attempt_id or not question_id or not spoken_text:
        return jsonify({'error': 'Missing data in request'}), 400

    # Check attempt ownership
    attempt = ExamAttempt.query.get(attempt_id)
    if not attempt or attempt.student_id != user_id:
        return jsonify({'error': 'Invalid attempt or access denied'}), 403

    # Get question
    question = Question.query.get(question_id)
    if not question:
        return jsonify({'error': 'Question not found'}), 404

    # Evaluate similarity score
    similarity_score = evaluate_answer(spoken_text, question.expected_answer)
    points_awarded = similarity_score * question.points

    # Save or update answer record
    answer = Answer.query.filter_by(attempt_id=attempt_id, question_id=question_id).first()
    if not answer:
        answer = Answer(
            attempt_id=attempt_id,
            question_id=question_id,
            spoken_text=spoken_text,
            similarity_score=similarity_score,
            points_awarded=points_awarded
        )
        db.session.add(answer)
    else:
        # Update existing answer if needed
        answer.spoken_text = spoken_text
        answer.similarity_score = similarity_score
        answer.points_awarded = points_awarded

    db.session.commit()

    return jsonify({
        'spoken_text': spoken_text,
        'similarity_score': similarity_score,
        'points_awarded': points_awarded,
        'max_points': question.points
    })

@app.route('/api/submit-answer', methods=['POST'])
def submit_answer():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user_id = verify_token(token)
    
    if not user_id:
        return jsonify({'error': 'Invalid token'}), 401
    
    # Handle file upload
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file provided'}), 400
    
    audio_file = request.files['audio']
    attempt_id = request.form['attempt_id']
    question_id = request.form['question_id']
    
    # Save audio file
    filename = secure_filename(f"answer_{attempt_id}_{question_id}.wav")
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    audio_file.save(filepath)
    
    # Convert speech to text
    spoken_text = speech_to_text(filepath)
    
    if not spoken_text:
        return jsonify({'error': 'Could not process audio'}), 400
    
    # Get expected answer
    question = Question.query.get(question_id)
    if not question:
        return jsonify({'error': 'Question not found'}), 404
    
    # Evaluate answer
    similarity_score = evaluate_answer(spoken_text, question.expected_answer)
    points_awarded = similarity_score * question.points
    
    # Save answer
    answer = Answer(
        attempt_id=attempt_id,
        question_id=question_id,
        spoken_text=spoken_text,
        audio_file_path=filepath,
        similarity_score=similarity_score,
        points_awarded=points_awarded
    )
    
    db.session.add(answer)
    db.session.commit()
    
    return jsonify({
        'spoken_text': spoken_text,
        'similarity_score': similarity_score,
        'points_awarded': points_awarded,
        'max_points': question.points
    })

@app.route('/api/complete-exam', methods=['POST'])
def complete_exam():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user_id = verify_token(token)
    
    if not user_id:
        return jsonify({'error': 'Invalid token'}), 401
    
    data = request.json
    attempt_id = data['attempt_id']
    
    # Get attempt
    attempt = ExamAttempt.query.get(attempt_id)
    if not attempt or attempt.student_id != user_id:
        return jsonify({'error': 'Attempt not found'}), 404
    
    # Calculate total score
    answers = Answer.query.filter_by(attempt_id=attempt_id).all()
    total_score = sum(answer.points_awarded for answer in answers)
    
    # Update attempt
    attempt.completed_at = datetime.utcnow()
    attempt.total_score = total_score
    attempt.status = 'completed'
    
    db.session.commit()
    
    return jsonify({
        'total_score': total_score,
        'status': 'completed'
    })
# Load the DNN face detector model once globally
modelFile = 'models/res10_300x300_ssd_iter_140000_fp16.caffemodel'
configFile = 'models/deploy.prototxt'
net = cv2.dnn.readNetFromCaffe(configFile, modelFile)

@app.route('/api/proctoring/face-check', methods=['POST'])
def proctor_face_check():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user_id = verify_token(token)

    if not user_id:
        return jsonify({'error': 'Invalid token'}), 401

    data = request.json
    frame_data = data.get('frame')

    if not frame_data:
        return jsonify({'error': 'No frame data provided'}), 400

    try:
        # Decode base64 image and convert to OpenCV format
        header, encoded = frame_data.split(',', 1)
        img_bytes = base64.b64decode(encoded)
        img = Image.open(BytesIO(img_bytes))
        frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

        (h, w) = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(cv2.resize(frame, (300, 300)), 1.0, (300, 300),
                                    (104.0, 177.0, 123.0))
        net.setInput(blob)
        detections = net.forward()

        faces = []
        for i in range(detections.shape[2]):
            confidence = detections[0, 0, i, 2]
            if confidence > 0.5:
                box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                (startX, startY, endX, endY) = box.astype("int")
                # Clip coordinates to frame size
                startX, startY = max(0, startX), max(0, startY)
                endX, endY = min(w - 1, endX), min(h - 1, endY)
                faces.append((startX, startY, endX, endY))

        face_detected = len(faces) > 0
        multiple_faces = len(faces) > 1

        # Eye detection with Haar cascade on face regions
        eye_movement_detected = False
        eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        for (startX, startY, endX, endY) in faces:
            roi_gray = gray[startY:endY, startX:endX]
            eyes = eye_cascade.detectMultiScale(roi_gray)
            # If number of eyes detected is not exactly 2, flag as suspicious
            if len(eyes) != 2:
                eye_movement_detected = True
                break

        return jsonify({
            'face_detected': face_detected,
            'multiple_faces': multiple_faces,
            'eye_movement_detected': eye_movement_detected,
            'timestamp': datetime.utcnow().isoformat()
        })

    except Exception as e:
        print(f"Proctoring error: {e}")
        return jsonify({'error': 'Internal server error'}), 500
        
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
