
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

db = SQLAlchemy()

# check if a table has a specific column

def table_has_column(table_name: str, column_name: str) -> bool:
    res = db.session.execute(text(f"PRAGMA table_info('{table_name}')")).fetchall()
    cols = [row[1] for row in res]
    return column_name in cols

def ensure_answer_finalized_column():
    # Ensure the 'answer' table exists
    tables = db.session.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='answer'"
    )).fetchall()
    if not tables:
        return
    
    # Add 'finalized' if missing
    if not table_has_column('answer', 'finalized'):
        print("Adding missing 'finalized' column to 'answer' table...")
        db.session.execute(text("ALTER TABLE answer ADD COLUMN finalized BOOLEAN DEFAULT 0"))
        db.session.commit()
        print("'finalized' column added.")