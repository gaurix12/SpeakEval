from app import app, db, User
from werkzeug.security import generate_password_hash

def add_educator():
    with app.app_context():
        if User.query.filter_by(email='educator@example.com').first():
            print("Educator already exists")
            return
        
        educator = User(
            email='educator@example.com',
            password_hash=generate_password_hash('password123'),
            role='educator',
            name='Educator User'
        )
        db.session.add(educator)
        db.session.commit()
        print("Educator user added!")

if __name__ == '__main__':
    add_educator()
