from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db, Ranking, Snapshot
from sqlalchemy import desc

router = APIRouter(prefix="/api/users", tags=["users"])

@router.get("/{username}/history")
async def get_user_history(username: str, db: Session = Depends(get_db)):
    history = db.query(Ranking, Snapshot.date, Snapshot.is_delayed)\
        .join(Snapshot, Ranking.snapshot_id == Snapshot.id)\
        .filter(Ranking.username == username)\
        .order_by(desc(Snapshot.date)).all()
        
    results = []
    for r, date, delayed in history:
        results.append({
            "date": date,
            "rank": r.rank,
            "jade": r.jade,
            "delta": r.delta,
            "w_rate": r.w_rate,
            "is_delayed": delayed
        })
    return results
