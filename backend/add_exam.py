from app import app, db, Exam, Question, User

def add_sample_exam():
    with app.app_context():
        educator = User.query.filter_by(email='educator@example.com').first()
        if not educator:
            print("Educator user not found")
            return
        
        exam = Exam(
            title='Sample Exam 1',
            description='This is a test exam',
            educator_id=educator.id,
            duration_minutes=30
        )
        db.session.add(exam)
        db.session.commit()

        q1 = Question(
            exam_id=exam.id,
            question_text='What is the capital of France?',
            expected_answer='Paris',
            points=10,
            order=1
        )
        q2 = Question(
            exam_id=exam.id,
            question_text='Name the largest planet in our solar system.',
            expected_answer='Jupiter',
            points=10,
            order=2
        )

        db.session.add_all([q1, q2])
        db.session.commit()
        print("Sample exam and questions added!")

if __name__ == '__main__':
    add_sample_exam()
