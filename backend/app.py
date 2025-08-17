from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from config import Config
from utils.database import db
import os

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    db.init_app(app)
    
    # Configure CORS to connect frontend and backend 
    CORS(
        app,
        origins=[
            'http://localhost:5173',
            'http://127.0.0.1:5173',
            'http://localhost:3000'
        ],
        methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
        allow_headers=['Content-Type', 'Authorization', 'X-Requested-With'],
        supports_credentials=True,
        max_age=86400
    )
    
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # register blueprints
    from routes import auth_bp, exam_bp, answer_bp, proctoring_bp, transcript_bp
    app.register_blueprint(auth_bp, url_prefix='/api')
    app.register_blueprint(exam_bp, url_prefix='/api')
    app.register_blueprint(answer_bp, url_prefix='/api')
    app.register_blueprint(proctoring_bp, url_prefix='/api')
    app.register_blueprint(transcript_bp, url_prefix='/api')
    
    # create database tables and run migrations
    with app.app_context():
        db.create_all()
        from utils.database import ensure_answer_finalized_column
        try:
            ensure_answer_finalized_column()
        except Exception as e:
            print(f"Startup migration helper error: {e}")
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)