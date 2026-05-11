from sqlalchemy import text
from database import engine

def migrate():
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE team_members ADD COLUMN bxh_rank INTEGER"))
            conn.commit()
            print("Column bxh_rank added successfully")
        except Exception as e:
            # If column already exists, SQLAlchemy might raise an error
            print(f"Column might already exist or error occurred: {e}")

if __name__ == "__main__":
    migrate()
