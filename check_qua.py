from database import SessionLocal, Ranking
from sqlalchemy import text
db = SessionLocal()
results = db.execute(text("SELECT alias, COUNT(*) FROM rankings WHERE username='qua***@gmail.com' GROUP BY alias")).fetchall()
for r in results:
    print(f'Alias {r[0]}: {r[1]} records')
db.close()
