from flask import Blueprint, request, jsonify
from model import User, Exam, Question, ExamAttempt, Answer
from service import verify_token
from utils.database import db
from utils.decorators import token_required

exam_bp = Blueprint('exam', __name__)

# list of exams 
@exam_bp.route('/exams', methods=['GET', 'POST'])
def handle_exams():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user_id = verify_token(token)
    if not user_id:
        return jsonify({'error': 'Invalid token'}), 401

    if request.method == 'GET':
        user = db.session.get(User, user_id)
        if user.role == 'educator':
            exams = Exam.query.filter_by(educator_id=user_id).all()
        else:
            exams = Exam.query.filter_by(is_active=True).all()

        return jsonify([{
            'id': exam.id,
            'title': exam.title,
            'description': exam.description,
            'duration_minutes': exam.duration_minutes,
            'created_at': (exam.created_at.isoformat() if exam.created_at else None)
        } for exam in exams])

    elif request.method == 'POST':
        data = request.json
        if not data or 'title' not in data or 'duration_minutes' not in data or 'questions' not in data:
            return jsonify({'error': 'Missing exam fields'}), 400

        exam = Exam(
            title=data['title'],
            description=data.get('description', ''),
            educator_id=user_id,
            duration_minutes=data['duration_minutes']
        )

        db.session.add(exam)
        db.session.flush()

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

# take an exam 
@exam_bp.route('/exams/<int:exam_id>/start', methods=['POST'])
def start_exam(exam_id):
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user_id = verify_token(token)
    if not user_id:
        return jsonify({'error': 'Invalid token'}), 401

    exam = db.session.get(Exam, exam_id)
    if not exam:
        return jsonify({'error': 'Exam not found'}), 404
    if not exam.is_active:
        return jsonify({'error': 'Exam is not active'}), 400

    attempt = ExamAttempt(
        exam_id=exam_id,
        student_id=user_id
    )

    db.session.add(attempt)
    db.session.commit()

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

@exam_bp.route('/attempts/<int:attempt_id>/info', methods=['GET'])
def attempt_info(attempt_id):
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user_id = verify_token(token)
    if not user_id:
        return jsonify({'error': 'Invalid token'}), 401

    attempt = db.session.get(ExamAttempt, attempt_id)
    if not attempt or attempt.student_id != user_id:
        return jsonify({'error': 'Attempt not found or access denied'}), 404

    exam = db.session.get(Exam, attempt.exam_id)
    questions = Question.query.filter_by(exam_id=exam.id).order_by(Question.order).all()

    return jsonify({
        'attempt_id': attempt.id,
        'exam': {
            'id': exam.id,
            'title': exam.title,
            'duration_minutes': exam.duration_minutes,
            'description': exam.description
        },
        'questions': [{
            'id': q.id,
            'question_text': q.question_text,
            'points': q.points,
            'order': q.order
        } for q in questions],
        'started_at': attempt.started_at.isoformat() if attempt.started_at else None,
        'status': attempt.status
    }), 200

@exam_bp.route('/attempts/<int:attempt_id>/current', methods=['GET'])
def attempt_current(attempt_id):
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user_id = verify_token(token)
    if not user_id:
        return jsonify({'error': 'Invalid token'}), 401

    attempt = db.session.get(ExamAttempt, attempt_id)
    if not attempt or attempt.student_id != user_id:
        return jsonify({'error': 'Invalid attempt or access denied'}), 403

    answered_q_ids = [a.question_id for a in Answer.query.filter_by(attempt_id=attempt_id, finalized=True).all()]
    next_q = (Question.query
              .filter(Question.exam_id == attempt.exam_id)
              .filter(~Question.id.in_(answered_q_ids))
              .order_by(Question.order)
              .first())
    
    if not next_q:
        return jsonify({'next_question': None}), 200
    
    return jsonify({
        'next_question': {
            'id': next_q.id,
            'question_text': next_q.question_text,
            'points': next_q.points,
            'order': next_q.order
        }
    }), 200

@exam_bp.route('/attempts/<int:attempt_id>/results', methods=['GET'])
@token_required
def attempt_results(attempt_id):
    attempt = db.session.get(ExamAttempt, attempt_id)
    if not attempt or attempt.student_id != request.user_id:
        return jsonify({'error': 'Attempt not found or access denied'}), 404

    exam = db.session.get(Exam, attempt.exam_id)
    questions = Question.query.filter_by(exam_id=exam.id).order_by(Question.order).all()
    answers = Answer.query.filter_by(attempt_id=attempt_id).all()
    answer_map = {ans.question_id: ans for ans in answers}

    breakdown = []
    for q in questions:
        ans = answer_map.get(q.id)
        if ans and ans.finalized:
            breakdown.append({
                'question_id': q.id,
                'question_text': q.question_text,
                'spoken_text': ans.spoken_text or '',
                'points_awarded': int(ans.points_awarded or 0),
                'is_correct': int(ans.points_awarded or 0) == int(q.points),
                'similarity_score': float(ans.similarity_score or 0.0)
            })
        else:
            breakdown.append({
                'question_id': q.id,
                'question_text': q.question_text,
                'spoken_text': (ans.spoken_text if ans else '') if ans else '',
                'points_awarded': 0,
                'is_correct': False,
                'similarity_score': 0.0
            })

    return jsonify({
        'attempt_id': attempt.id,
        'exam_id': exam.id,
        'exam_title': exam.title,
        'total_score': int(attempt.total_score or 0),
        'breakdown': breakdown
    }), 200
