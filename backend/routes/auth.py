from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from model import User
from service import generate_token, verify_token
from utils.database import db
from utils.decorators import token_required

auth_bp = Blueprint('auth', __name__)

# register user
@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.json
    if not data or 'email' not in data or 'password' not in data or 'role' not in data or 'name' not in data:
        return jsonify({'error': 'Missing registration fields'}), 400

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

# login user
@auth_bp.route('/login', methods=['POST'])
def login():
    try:
        data = request.json
        if not data or 'email' not in data or 'password' not in data:
            return jsonify({'error': 'Email and password required'}), 400

        user = User.query.filter_by(email=data['email']).first()
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

@auth_bp.route('/validate-token', methods=['GET'])
def validate_token():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user_id = verify_token(token)
    if not user_id:
        return jsonify({'valid': False, 'error': 'invalid_or_expired_token'}), 401
    
    user = db.session.get(User, user_id)
    return jsonify({
        'valid': True, 
        'user': {
            'id': user.id, 
            'email': user.email, 
            'name': user.name, 
            'role': user.role
        }
    }), 200

