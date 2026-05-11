
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from database import SessionLocal, Ranking
from sqlalchemy import func

db = SessionLocal()
try:
    # Tìm aliases chỉ có jade=0 xuyên suốt toàn bộ history
    result = db.execute("""
        SELECT alias, COUNT(*) as days, SUM(jade) as total_jade, MAX(jade) as max_jade
        FROM rankings
        GROUP BY alias
        HAVING max_jade = 0
        ORDER BY alias
    """).fetchall()
    
    print(f"Ghost aliases (max_jade=0 across ALL snapshots): {len(result)}")
    to_delete = []
    for row in result:
        print(f"  {row[0]}: {row[1]} days, total_jade={row[2]}")
        to_delete.append(row[0])
    
    if to_delete:
        confirm = input(f"\nXóa {len(to_delete)} ghost aliases? (yes/no): ").strip()
        if confirm == "yes":
            for alias in to_delete:
                n = db.query(Ranking).filter(Ranking.alias == alias).delete(synchronize_session=False)
                print(f"  Deleted {n} records for alias={alias}")
            db.commit()
            print("Done. Ghost aliases đã xóa.")
        else:
            print("Cancelled.")
    db.close()
except Exception as e:
    db.rollback()
    db.close()
    print(f"Error: {e}")
    raise
