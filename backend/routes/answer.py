from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from model import ExamAttempt, Question, Answer
from service import verify_token
from service import semantic_similarity, award_points
from service import speech_to_text
from utils.database import db
from datetime import datetime, timezone
import os

answer_bp = Blueprint('answer', __name__)

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

# finalize an attempt and return result 
def end_exam_internal(attempt_id, user_id):
    attempt = db.session.get(ExamAttempt, attempt_id)
    if not attempt or attempt.student_id != user_id:
        return jsonify({'error': 'Invalid attempt or access denied'}), 403

    answers = Answer.query.filter_by(attempt_id=attempt_id).all()
    total_score = sum(int(a.points_awarded or 0) for a in answers if a.finalized)
    breakdown = [{
        'question_id': a.question_id,
        'spoken_text': a.spoken_text or '',
        'points_awarded': int(a.points_awarded or 0)
    } for a in answers if a.finalized]

    attempt.completed_at = datetime.now(timezone.utc)
    attempt.total_score = int(total_score)
    attempt.status = 'completed'
    db.session.commit()

    return jsonify({
        'total_score': int(total_score),
        'status': 'completed',
        'breakdown': breakdown
    }), 200

# evaluate answer using nlp
@answer_bp.route('/evaluate-answer', methods=['POST'])
def evaluate_answer():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user_id = verify_token(token)
    if not user_id:
        return jsonify({'error': 'Invalid token'}), 401

    data = request.json or {}
    attempt_id = data.get('attempt_id')
    question_id = data.get('question_id')
    spoken_text = data.get('spoken_text', '')

    if not attempt_id or not question_id or spoken_text is None:
        return jsonify({'error': 'Missing data in request'}), 400

    attempt = db.session.get(ExamAttempt, attempt_id)
    if not attempt or attempt.student_id != user_id:
        return jsonify({'error': 'Invalid attempt or access denied'}), 403

    question = db.session.get(Question, question_id)
    if not question:
        return jsonify({'error': 'Question not found'}), 404

    similarity = semantic_similarity(spoken_text, question.expected_answer)
    awarded = award_points(similarity, question.points)

    answer = Answer.query.filter_by(attempt_id=attempt_id, question_id=question_id).first()
    if not answer:
        answer = Answer(
            attempt_id=attempt_id,
            question_id=question_id,
            spoken_text=spoken_text,
            similarity_score=similarity,
            points_awarded=awarded,
            finalized=True
        )
        db.session.add(answer)
    else:
        answer.spoken_text = spoken_text
        answer.similarity_score = similarity
        answer.points_awarded = awarded
        answer.finalized = True

    db.session.commit()

    return jsonify({
        'spoken_text': spoken_text,
        'similarity_score': similarity,
        'points_awarded': int(awarded),
        'max_points': int(question.points),
        'is_correct': awarded == int(question.points)
    })

@answer_bp.route('/submit-answer', methods=['POST'])
def submit_answer():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user_id = verify_token(token)
    if not user_id:
        return jsonify({'error': 'Invalid token'}), 401

    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file provided'}), 400

    audio_file = request.files['audio']
    attempt_id = request.form.get('attempt_id')
    question_id = request.form.get('question_id')

    if not attempt_id or not question_id:
        return jsonify({'error': 'Missing attempt_id or question_id in form'}), 400

    attempt = db.session.get(ExamAttempt, attempt_id)
    if not attempt or attempt.student_id != user_id:
        return jsonify({'error': 'Invalid attempt or access denied'}), 403

    filename = secure_filename(f"answer_{attempt_id}_{question_id}.wav")
    filepath = os.path.join('uploads', filename)
    audio_file.save(filepath)

    spoken_text = speech_to_text(filepath)
    if not spoken_text:
        return jsonify({'error': 'Could not process audio'}), 400

    question = db.session.get(Question, question_id)
    if not question:
        return jsonify({'error': 'Question not found'}), 404

    similarity = semantic_similarity(spoken_text, question.expected_answer)
    awarded = award_points(similarity, question.points)

    answer = Answer.query.filter_by(attempt_id=attempt_id, question_id=question_id).first()
    if answer:
        answer.spoken_text = spoken_text
        answer.audio_file_path = filepath
        answer.similarity_score = similarity
        answer.points_awarded = awarded
        answer.finalized = True
    else:
        answer = Answer(
            attempt_id=attempt_id,
            question_id=question_id,
            spoken_text=spoken_text,
            audio_file_path=filepath,
            similarity_score=similarity,
            points_awarded=awarded,
            finalized=True
        )
        db.session.add(answer)

    db.session.commit()

    return jsonify({
        'spoken_text': spoken_text,
        'similarity_score': similarity,
        'points_awarded': int(awarded),
        'max_points': int(question.points),
        'is_correct': awarded == int(question.points)
    })

# finish and display result 
@answer_bp.route('/complete-exam', methods=['POST'])
def complete_exam():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user_id = verify_token(token)
    if not user_id:
        return jsonify({'error': 'Invalid token'}), 401

    data = request.json or {}
    attempt_id = data.get('attempt_id')
    if not attempt_id:
        return jsonify({'error': 'Missing attempt_id'}), 400

    attempt = db.session.get(ExamAttempt, attempt_id)
    if not attempt or attempt.student_id != user_id:
        return jsonify({'error': 'Attempt not found'}), 404

    answers = Answer.query.filter_by(attempt_id=attempt_id).all()
    total_score = sum(int(a.points_awarded or 0) for a in answers if a.finalized)

    attempt.completed_at = datetime.now(timezone.utc)
    attempt.total_score = int(total_score)
    attempt.status = 'completed'

    db.session.commit()

    return jsonify({
        'total_score': int(total_score),
        'status': 'completed'
    })

# skip the question grade - 0
@answer_bp.route('/skip-question', methods=['POST'])
def skip_question():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user_id = verify_token(token)
    if not user_id:
        return jsonify({'error': 'Invalid token'}), 401

    data = request.get_json() or {}
    attempt_id = data.get('attempt_id')
    question_id = data.get('question_id')
    if not attempt_id or not question_id:
        return jsonify({'error': 'Missing attempt_id or question_id'}), 400

    attempt = db.session.get(ExamAttempt, attempt_id)
    if not attempt or attempt.student_id != user_id:
        return jsonify({'error': 'Invalid attempt or access denied'}), 403

    question = db.session.get(Question, question_id)
    if not question:
        return jsonify({'error': 'Question not found'}), 404

    answer = get_or_create_draft_answer(attempt_id, question_id)
    answer.spoken_text = ''
    answer.similarity_score = 0.0
    answer.points_awarded = 0
    answer.finalized = True
    db.session.commit()

    next_q = (Question.query
              .filter(Question.exam_id == question.exam_id)
              .filter(Question.order > question.order)
              .order_by(Question.order)
              .first())

    return jsonify({
        'message': 'Question skipped',
        'points_awarded': 0,
        'next_question': {
            'id': next_q.id,
            'question_text': next_q.question_text,
            'points': next_q.points,
            'order': next_q.order
        } if next_q else None
    }), 200

# move to the next question after grading this 
@answer_bp.route('/move-next', methods=['POST'])
def move_next():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user_id = verify_token(token)
    if not user_id:
        return jsonify({'error': 'Invalid token'}), 401

    data = request.get_json() or {}
    attempt_id = data.get('attempt_id')
    question_id = data.get('question_id')
    provided_text = data.get('spoken_text', None)

    if not attempt_id or not question_id:
        return jsonify({'error': 'Missing attempt_id or question_id'}), 400

    attempt = db.session.get(ExamAttempt, attempt_id)
    if not attempt or attempt.student_id != user_id:
        return jsonify({'error': 'Invalid attempt or access denied'}), 403

    question = db.session.get(Question, question_id)
    if not question:
        return jsonify({'error': 'Question not found'}), 404

    answer = get_or_create_draft_answer(attempt_id, question_id)
    if answer.finalized:
        current_text = answer.spoken_text or ''
    else:
        current_text = (provided_text if provided_text is not None else (answer.spoken_text or '')).strip()

    similarity = semantic_similarity(current_text, question.expected_answer) if current_text else 0.0
    awarded = award_points(similarity, question.points)

    answer.spoken_text = current_text
    answer.similarity_score = similarity
    answer.points_awarded = int(awarded)
    answer.finalized = True
    db.session.commit()

    next_q = (Question.query
              .filter(Question.exam_id == question.exam_id)
              .filter(Question.order > question.order)
              .order_by(Question.order)
              .first())

    return jsonify({
        'spoken_text': current_text,
        'similarity_score': similarity,
        'points_awarded': int(awarded),
        'is_correct': awarded == int(question.points),
        'next_question': {
            'id': next_q.id,
            'question_text': next_q.question_text,
            'points': next_q.points,
            'order': next_q.order
        } if next_q else None
    }), 200

# voice commands to navigate the exam
@answer_bp.route('/voice-command', methods=['POST'])
def voice_command():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user_id = verify_token(token)
    if not user_id:
        return jsonify({'error': 'Invalid token'}), 401

    data = request.get_json() or {}
    attempt_id = data.get('attempt_id')
    question_id = data.get('question_id')
    command = (data.get('command') or '').strip().lower()
    spoken_text = data.get('spoken_text', None)

    if not attempt_id or not question_id or not command:
        return jsonify({'error': 'Missing attempt_id/question_id/command'}), 400

    if command in ['skip the question', 'skip this question', 'skip']:
        return skip_question()
    elif command in ['move to the next question', 'move next', 'next question', 'move to next question']:
        return move_next()
    elif command in ['end examination', 'end exam', 'finish exam', 'finish examination', 'end the exam']:
        return end_exam_internal(attempt_id, user_id)
    else:
        return jsonify({'error': 'Unknown command'}), 400

@answer_bp.route('/end-exam', methods=['POST'])
def end_exam():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user_id = verify_token(token)
    if not user_id:
        return jsonify({'error': 'Invalid token'}), 401

    data = request.json or {}
    attempt_id = data.get('attempt_id')
    if not attempt_id:
        return jsonify({'error': 'Missing attempt_id'}), 400

    return end_exam_internal(attempt_id, user_id)
