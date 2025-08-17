from flask import Blueprint, request, jsonify
from service import verify_token, analyze_frame

proctoring_bp = Blueprint('proctoring', __name__)

# face-check for no face, excessive eye movements away from screen and more than one face in the frame
@proctoring_bp.route('/proctoring/face-check', methods=['POST'])
def face_check():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user_id = verify_token(token)
    if not user_id:
        return jsonify({'error': 'Invalid token'}), 401

    data = request.json or {}
    frame_data = data.get('frame')

    if not frame_data:
        return jsonify({'error': 'No frame data provided'}), 400

    result = analyze_frame(frame_data)
    
    if 'error' in result:
        return jsonify({'error': result['error']}), 500
    
    return jsonify(result)