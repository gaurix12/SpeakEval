from .auth import auth_bp
from .exam import exam_bp
from .answer import answer_bp
from .proctoring import proctoring_bp
from .transcript import transcript_bp

__all__ = ['auth_bp', 'exam_bp', 'answer_bp', 'proctoring_bp', 'transcript_bp']
