from database import SessionLocal, Ranking
from sqlalchemy import text
db = SessionLocal()
for username in ['hun***@gmail.com', 'mal***@gmail.com']:
    print(f'\nUsername: {username}')
    results = db.execute(text(f"SELECT alias, COUNT(*) FROM rankings WHERE username='{username}' GROUP BY alias")).fetchall()
    for r in results:
        print(f'  Alias {r[0]}: {r[1]} records')
db.close()
