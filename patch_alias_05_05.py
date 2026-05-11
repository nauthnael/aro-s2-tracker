"""
patch_alias_05_05.py — Patch alias sai trong snapshot 05/05 (id=25)
Chạy: python patch_alias_05_05.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal
from sqlalchemy import text

db = SessionLocal()

try:
    # Patch 1: rank 35 — qua[TEAM] → qua[T2]***
    result1 = db.execute(
        text("UPDATE rankings SET alias='qua[T2]***' "
             "WHERE snapshot_id=25 AND rank=35 AND username='qua***@gmail.com' AND alias='qua[TEAM]'")
    )
    print(f"Patch 1 (rank 35 qua -> qua[T2]***): {result1.rowcount} rows updated")

    # Patch 2: rank 95 — hun[TEAM] → hun[moi]***
    result2 = db.execute(
        text("UPDATE rankings SET alias='hun[moi]***' "
             "WHERE snapshot_id=25 AND rank=95 AND username='hun***@gmail.com' AND alias='hun[TEAM]'")
    )
    print(f"Patch 2 (rank 95 hun -> hun[moi]***): {result2.rowcount} rows updated")

    # Verify
    rows = db.execute(
        text("SELECT rank, username, alias, jade FROM rankings "
             "WHERE snapshot_id=25 AND rank IN (35, 95)")
    ).fetchall()
    print("\nVerify sau patch:")
    for r in rows:
        print(f"  Rank {r[0]}: {r[1]} -> alias={r[2]}, jade={r[3]:,}")

    db.commit()
    print("\nDone. Restart server sau khi chay xong.")

except Exception as e:
    db.rollback()
    print(f"Error: {e}")
    raise
finally:
    db.close()
