from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from database import get_db, TeamMember, Snapshot, Ranking
from pydantic import BaseModel
from typing import List, Optional
from datetime import date

router = APIRouter(prefix="/api/team-members", tags=["team"])

class AliasUpdateSchema(BaseModel):
    username: str
    alias: str

@router.put("/alias")
async def update_alias(data: AliasUpdateSchema, db: Session = Depends(get_db)):
    # Tìm hoặc tạo mới team_member record
    member = db.query(TeamMember).filter(TeamMember.username == data.username).first()
    if member:
        old_alias = member.alias
        member.alias = data.alias  # Đồng bộ alias mới vào TeamMember (Brief 17)
    else:
        old_alias = None
        member = TeamMember(username=data.username, alias=data.alias, role="T2")
        db.add(member)
    db.flush()

    # Update alias trong rankings table (Brief 16)
    rankings_to_update = db.query(Ranking).filter(
        Ranking.username == data.username
    ).all()
    updated_count = 0
    for r in rankings_to_update:
        if '[?]' in (r.alias or '') or r.alias == old_alias or r.alias == data.username:
            r.alias = data.alias
            updated_count += 1

    db.commit()
    return {"status": "success", "updated_rankings": updated_count}

class SetTeamRequest(BaseModel):
    username: str       # full masked email, vd: dan***@gmail.com
    alias: str          # alias hiện tại từ rankings table — source of truth
    is_team: bool       # True = thêm vào team, False = loại khỏi team
    role: Optional[str] = None  # "T1" hoặc "T2" — chỉ cần khi is_team=True

@router.post("/set-team")
async def set_team_member(data: SetTeamRequest, db: Session = Depends(get_db)):
    """
    Thêm/loại/đổi role thành viên team.
    - Khi is_team=True:  upsert TeamMember, backfill is_team=True + team_role toàn bộ rankings theo alias
    - Khi is_team=False: xóa TeamMember, backfill is_team=False + team_role=None toàn bộ rankings theo alias
    """
    if data.is_team and not data.role:
        raise HTTPException(status_code=400, detail="Role (T1/T2) bắt buộc khi thêm vào team")
    if data.role and data.role not in ("T1", "T2"):
        raise HTTPException(status_code=400, detail="Role phải là T1 hoặc T2")

    if data.is_team:
        # Upsert TeamMember
        member = db.query(TeamMember).filter(TeamMember.username == data.username).first()
        if member:
            member.alias = data.alias   # đồng bộ alias từ tracker
            member.role = data.role
        else:
            member = TeamMember(
                username=data.username,
                alias=data.alias,
                role=data.role,
                bxh_rank=None,
                note=""
            )
            db.add(member)
        db.flush()

        # Backfill toàn bộ rankings theo alias — cập nhật is_team=True và team_role
        db.query(Ranking).filter(Ranking.alias == data.alias).update(
            {"is_team": True, "team_role": data.role},
            synchronize_session=False
        )

    else:
        # Xóa TeamMember nếu tồn tại
        member = db.query(TeamMember).filter(TeamMember.username == data.username).first()
        if member:
            db.delete(member)
        db.flush()

        # Backfill toàn bộ rankings theo alias — cập nhật is_team=False và team_role=None
        db.query(Ranking).filter(Ranking.alias == data.alias).update(
            {"is_team": False, "team_role": None},
            synchronize_session=False
        )

    db.commit()
    return {"status": "success"}

class TeamMemberSchema(BaseModel):
    id: Optional[int] = None
    username: str
    alias: str
    role: str
    bxh_rank: Optional[int] = None
    join_date: Optional[date] = None
    note: Optional[str] = None

    class Config:
        from_attributes = True

@router.get("", response_model=List[TeamMemberSchema])
async def get_team_members(db: Session = Depends(get_db)):
    return db.query(TeamMember).all()

@router.get("/with-stats")
async def get_team_with_stats(db: Session = Depends(get_db)):
    latest_snapshot = db.query(Snapshot).order_by(desc(Snapshot.date)).first()
    members = db.query(TeamMember).all()
    result = []

    for member in members:
        stats = None
        if latest_snapshot:
            ranking = None

            # Lookup bằng alias — alias là unique per person kể cả duplicate username
            if member.alias:
                ranking = db.query(Ranking).filter(
                    Ranking.snapshot_id == latest_snapshot.id,
                    Ranking.alias == member.alias
                ).first()

            if ranking:
                stats = {
                    "rank": ranking.rank,
                    "jade": ranking.jade,
                    "delta": ranking.delta,
                    "w_rate": ranking.w_rate,
                    "proj_may31": ranking.proj_may31,
                    "prize_est": ranking.prize_est,
                }

        result.append({
            "id": member.id,
            "username": member.username,
            "alias": member.alias,
            "role": member.role,
            "bxh_rank": member.bxh_rank,
            "note": member.note,
            "stats": stats
        })

    return result

@router.post("")
async def add_team_member(member: TeamMemberSchema, db: Session = Depends(get_db)):
    # Check duplicate username
    existing = db.query(TeamMember).filter(TeamMember.username == member.username).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Username '{member.username}' đã tồn tại trong team.")
        
    db_member = TeamMember(**member.dict(exclude={"id"}))
    db.add(db_member)
    db.commit()
    db.refresh(db_member)
    return {"status": "success", "id": db_member.id}

@router.put("/{member_id}")
async def update_team_member(member_id: int, member: TeamMemberSchema, db: Session = Depends(get_db)):
    db_member = db.query(TeamMember).filter(TeamMember.id == member_id).first()
    if not db_member:
        raise HTTPException(status_code=404, detail="Member not found")
    
    # Check if updated username conflicts with another user
    existing = db.query(TeamMember).filter(TeamMember.username == member.username, TeamMember.id != member_id).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Username '{member.username}' đã tồn tại ở thành viên khác.")

    for key, value in member.dict(exclude={"id"}).items():
        setattr(db_member, key, value)
    db.commit()
    return {"status": "success"}

@router.delete("/{member_id}")
async def delete_team_member(member_id: int, db: Session = Depends(get_db)):
    db_member = db.query(TeamMember).filter(TeamMember.id == member_id).first()
    if not db_member:
        raise HTTPException(status_code=404, detail="Member not found")
    
    db.delete(db_member)
    db.commit()
    return {"status": "success"}
