from functools import wraps
from flask import request, jsonify
from service import verify_token

def token_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        user_id = verify_token(token)
        if not user_id:
            return jsonify({'error': 'Invalid token'}), 401
        request.user_id = user_id
        return f(*args, **kwargs)
    return decorated_function