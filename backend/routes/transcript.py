from flask import Blueprint, request, jsonify
from model import ExamAttempt, Answer
from service import verify_token
from utils.database import db

transcript_bp = Blueprint('transcript', __name__)

def get_or_create_draft_answer(attempt_id: int, question_id: int) -> Answer:
    ans = Answer.query.filter_by(attempt_id=attempt_id, question_id=question_id).first()
    if ans is None:
        ans = Answer(
            attempt_id=attempt_id,
            question_id=question_id,
            spoken_text='',
            similarity_score=None,
            points_awarded=None,
            finalized=False
        )
        db.session.add(ans)
        db.session.commit()
    return ans

@transcript_bp.route('/transcript/append', methods=['POST'])
def append_transcript():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user_id = verify_token(token)
    if not user_id:
        return jsonify({'error': 'Invalid token'}), 401

    data = request.json or {}
    attempt_id = data.get('attempt_id')
    question_id = data.get('question_id')
    text_part = (data.get('text') or '').strip()

    if not attempt_id or not question_id or text_part == '':
        return jsonify({'error': 'Missing attempt_id/question_id/text'}), 400

    attempt = db.session.get(ExamAttempt, attempt_id)
    if not attempt or attempt.student_id != user_id:
        return jsonify({'error': 'Invalid attempt or access denied'}), 403

    ans = get_or_create_draft_answer(attempt_id, question_id)
    if ans.finalized:
        return jsonify({'error': 'Answer already finalized for this question'}), 400

    ans.spoken_text = (ans.spoken_text + (' ' if ans.spoken_text else '') + text_part).strip()
    db.session.commit()

    return jsonify({
        'message': 'Transcript appended',
        'current_transcript': ans.spoken_text
    }), 200