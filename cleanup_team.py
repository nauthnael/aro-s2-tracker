"""
cleanup_team.py — Dọn dẹp team_members table:
1. Xóa record username không có @gmail.com (format sai)
2. In danh sách còn lại để verify

Chạy: python cleanup_team.py
"""
from database import SessionLocal, TeamMember

def cleanup():
    db = SessionLocal()

    # Xóa tất cả records mà username không chứa @ (format sai)
    bad = db.query(TeamMember).filter(~TeamMember.username.contains('@')).all()
    print(f"Found {len(bad)} records with invalid username (no @):")
    for m in bad:
        print(f"  DELETE id={m.id} username='{m.username}' alias='{m.alias}'")
        db.delete(m)

    db.commit()

    # Verify còn lại
    remaining = db.query(TeamMember).all()
    print(f"\nRemaining {len(remaining)} team members:")
    for m in remaining:
        print(f"  id={m.id} username='{m.username}' alias='{m.alias}' role={m.role}")

    db.close()
    print("\nDone!")

if __name__ == "__main__":
    cleanup()
