"""
patch_team_alias.py — Fix TeamMember alias: strip @gmail.com
Chạy: python patch_team_alias.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal, TeamMember, Ranking

db = SessionLocal()

try:
    members = db.query(TeamMember).all()
    print("Patching TeamMember aliases...")
    for m in members:
        if m.alias and "@gmail.com" in m.alias:
            old_alias = m.alias
            new_alias = m.alias.replace("@gmail.com", "")
            
            # Update TeamMember alias
            m.alias = new_alias
            
            # Update tất cả rankings đang dùng alias cũ
            updated = db.query(Ranking).filter(Ranking.alias == old_alias).update(
                {"alias": new_alias}, synchronize_session=False
            )
            print(f"  {old_alias} -> {new_alias} | rankings updated: {updated}")

    db.commit()
    print("\nDone.")

except Exception as e:
    db.rollback()
    print(f"Error: {e}")
    raise
finally:
    db.close()
