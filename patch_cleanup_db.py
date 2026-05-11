"""
patch_cleanup_db.py — Xóa snapshot 27 (sai ngày) + dọn garbage aliases
Chạy: python patch_cleanup_db.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal, Snapshot, Ranking, Alert
from sqlalchemy import text

db = SessionLocal()

try:
    # ── Bước 1: Xóa snapshot 27 (data 06/05 nhập nhầm ngày 07/05) ──
    # Check id first
    snap27 = db.query(Snapshot).filter(Snapshot.id == 27).first()
    if snap27:
        print(f"Xoa snapshot id=27, date={snap27.date}")
        db.query(Ranking).filter(Ranking.snapshot_id == 27).delete(synchronize_session=False)
        db.query(Alert).filter(Alert.snapshot_id == 27).delete(synchronize_session=False)
        db.delete(snap27)
        print("  -> Da xoa")
    else:
        print("Snapshot 27 khong ton tai")

    # ── Bước 2: Don garbage aliases — users co jade=0 va alias khong hop le ──
    ghost_check = db.execute(text("""
        SELECT alias, COUNT(*) as cnt, SUM(jade) as total_jade
        FROM rankings
        GROUP BY alias
        HAVING total_jade = 0 AND alias NOT LIKE '%[?]%'
    """)).fetchall()
    
    print(f"\nGhost aliases (jade luon = 0): {len(ghost_check)}")
    deleted_total = 0
    for row in ghost_check:
        alias = row[0]
        n = db.execute(
            text(f"DELETE FROM rankings WHERE alias=:alias AND jade=0"),
            {"alias": alias}
        ).rowcount
        deleted_total += n
        print(f"  Xoa {n} records cho alias={alias}")
    
    db.commit()
    print(f"\nTong records xoa: {deleted_total}")
    print("Done. Restart server.")

except Exception as e:
    db.rollback()
    print(f"Error: {e}")
    raise
finally:
    db.close()
