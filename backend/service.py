"""
Unified service utilities:
- Auth (JWT): generate_token, verify_token
- Evaluation (SBERT similarity + scoring): semantic_similarity, award_points
- Proctoring (face/eye detection): analyze_frame
- Speech (speech-to-text): speech_to_text
"""

from __future__ import annotations

import speech_recognition as sr
import cv2, os, base64
import numpy as np
from io import BytesIO
from PIL import Image
from pathlib import Path
import jwt
from datetime import datetime, timedelta, timezone
from flask import current_app
from sklearn.metrics.pairwise import cosine_similarity

# create jwt token 
def generate_token(user_id):
    payload = {
        'user_id': user_id,
        'exp': datetime.now(timezone.utc) + timedelta(days=1)
    }
    token = jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256')
    if isinstance(token, bytes):
        token = token.decode('utf-8')
    return token

# verify jwt token
def verify_token(token):
    if not token:
        return None
    try:
        payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
        return payload.get('user_id')
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


# Evaluation (SBERT similarity + scoring)

_sbert_model = None
def _get_sbert():
    global _sbert_model
    if _sbert_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _sbert_model = SentenceTransformer('all-MiniLM-L6-v2')
        except Exception as e:
            print(f"SBERT load error: {e}")
            _sbert_model = None
    return _sbert_model

def semantic_similarity(student_answer: str, expected_answer: str) -> float:
    try:
        if not student_answer:
            return 0.0
        model = _get_sbert()
        if model is None:
            return 0.0
        student_embedding = model.encode([student_answer])
        expected_embedding = model.encode([expected_answer])
        similarity = cosine_similarity(student_embedding, expected_embedding)[0][0]
        return float(similarity)
    except Exception as e:
        print(f"Answer evaluation error: {e}")
        return 0.0
# scoring rule: full points if similarity >= threshold, else 0
def award_points(similarity: float, max_points: int) -> int:
    
    threshold = current_app.config['EVAL_SIMILARITY_THRESHOLD']
    return int(max_points) if similarity >= threshold else 0

# Proctoring (face/eye detection)
def _resolve_model_path(filename: str) -> str:
    candidates = []
    here = Path(__file__).resolve().parent
    candidates.append(here / "models" / filename)

    try:
        from flask import current_app
        if current_app:
            candidates.append(Path(current_app.root_path) / "models" / filename)
    except Exception:
        pass

    candidates.append(Path.cwd() / "models" / filename)

    for p in candidates:
        if p.exists():
            return str(p)

    return str(candidates[0])

_modelFile = _resolve_model_path("res10_300x300_ssd_iter_140000_fp16.caffemodel")
_configFile = _resolve_model_path("deploy.prototxt")

_net = None
def _get_face_net():
    global _net
    if _net is None:
        try:
            _net = cv2.dnn.readNetFromCaffe(_configFile, _modelFile)
        except Exception as e:
            print(f"Warning: Could not load DNN model files:\n  prototxt={_configFile}\n  caffemodel={_modelFile}\n  error={e}")
            _net = None
    return _net

def analyze_frame(frame_data):
    try:
        header, encoded = frame_data.split(',', 1)
        img_bytes = base64.b64decode(encoded)
        img = Image.open(BytesIO(img_bytes))
        frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

        net = _get_face_net()
        if net is None:
            return {'error': 'Face detection model not loaded'}

        (h, w) = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(cv2.resize(frame, (300, 300)), 1.0, (300, 300),
                                     (104.0, 177.0, 123.0))
        net.setInput(blob)
        detections = net.forward()

        faces = []
        for i in range(detections.shape[2]):
            confidence = float(detections[0, 0, i, 2])
            if confidence > 0.5:
                box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                (startX, startY, endX, endY) = box.astype("int")
                startX, startY = max(0, startX), max(0, startY)
                endX, endY = min(w - 1, endX), min(h - 1, endY)
                faces.append((startX, startY, endX, endY))

        face_detected = len(faces) > 0
        multiple_faces = len(faces) > 1

        eye_movement_detected = False
        eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        for (sx1, sy1, sx2, sy2) in faces:
            sy, ey = max(0, sy1), min(gray.shape[0], sy2)
            sx, ex = max(0, sx1), min(gray.shape[1], sx2)
            if sy >= ey or sx >= ex:
                continue
            roi_gray = gray[sy:ey, sx:ex]
            eyes = eye_cascade.detectMultiScale(roi_gray)
            if len(eyes) != 2:
                eye_movement_detected = True
                break

        return {
            'face_detected': face_detected,
            'multiple_faces': multiple_faces,
            'eye_movement_detected': eye_movement_detected,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        print(f"Proctoring error: {e}")
        return {'error': 'Frame analysis failed'}

# Speech (speech-to-text)

def speech_to_text(audio_file_path):
    """Convert audio file to text using speech_recognition (Google API)."""
    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(audio_file_path) as source:
            audio = recognizer.record(source)
            text = recognizer.recognize_google(audio)
            return text
    except Exception as e:
        print(f"Speech recognition error: {e}")
        return None

__all__ = [
    'generate_token', 'verify_token',
    'semantic_similarity', 'award_points',
    'analyze_frame',
    'speech_to_text'
]
