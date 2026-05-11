from database import SessionLocal, TeamMember
from datetime import date

def init_team():
    db = SessionLocal()
    # Check if leader exists
    leader = db.query(TeamMember).filter(TeamMember.username == "nau***@gmail.com").first()
    if not leader:
        leader = TeamMember(
            username="nau***@gmail.com",
            alias="nau***",
            role="LEADER",
            join_date=date(2026, 4, 1),
            note="Team Leader"
        )
        db.add(leader)
        
    # Add some other known team members from previous context or common patterns
    # (This can be updated later by the user via the UI)
    
    db.commit()
    db.close()
    print("Team initialized.")

if __name__ == "__main__":
    init_team()
