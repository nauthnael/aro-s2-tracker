from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db, Snapshot, Ranking, Alert, TeamMember
from sqlalchemy import desc

router = APIRouter(prefix="/api", tags=["dashboard"])

@router.get("/dashboard")
async def get_dashboard(db: Session = Depends(get_db)):
    # Get latest snapshot
    snapshot = db.query(Snapshot).order_by(desc(Snapshot.date)).first()
    if not snapshot:
        return {"message": "No data available"}
        
    # Get nau*** data
    nau = db.query(Ranking).filter(Ranking.snapshot_id == snapshot.id, Ranking.username == "nau***@gmail.com").first()
    
    # Get latest alerts
    alerts = db.query(Alert).filter(Alert.snapshot_id == snapshot.id).all()
    
    # Top rankings (all)
    top_rankings = db.query(Ranking).filter(Ranking.snapshot_id == snapshot.id).order_by(Ranking.rank).all()
    
    return {
        "snapshot": snapshot,
        "nau": nau,
        "top10": top_rankings, # Keeping the key name for frontend compatibility or rename if preferred
        "alerts": alerts
    }

@router.get("/tracker")
async def get_tracker(db: Session = Depends(get_db)):
    # 1. Get all snapshots, sorted by date asc
    snapshots = db.query(Snapshot).order_by(Snapshot.date).all()
    if not snapshots:
        return {"dates": [], "snapshots": [], "users": []}

    # Build snapshot lookup map: id -> date_str (YYYY-MM-DD)
    snap_id_to_date = {s.id: s.date.strftime("%Y-%m-%d") for s in snapshots}
    snap_id_to_delayed = {s.id: s.is_delayed for s in snapshots}
    dates = [s.date.strftime("%Y-%m-%d") for s in snapshots]

    # Serializable snapshot list for frontend delayed flag detection
    snapshots_out = [
        {"id": s.id, "date": s.date.strftime("%Y-%m-%d"), "is_delayed": s.is_delayed}
        for s in snapshots
    ]

    # 2. Latest snapshot id for current metrics
    latest_snapshot_id = snapshots[-1].id

    # 3. Fetch ALL rankings in one query (avoid N+1)
    all_rankings = db.query(Ranking).all()

    user_data = {}  # alias -> {meta, history}

    for r in all_rankings:
        date_str = snap_id_to_date.get(r.snapshot_id)
        if date_str is None:
            continue  # orphaned ranking, skip

        # Dùng alias làm key — unique per person kể cả khi username trùng
        # Fallback: nếu alias null thì dùng username (không nên xảy ra sau Brief 16)
        key = r.alias if r.alias else r.username

        if key not in user_data:
            user_data[key] = {
                "username": r.username,
                "alias": key,
                "is_team": False,
                "team_role": None,
                "current_rank": 999,
                "current_jade": 0,
                "w_rate": 0.0,
                "proj_may31": 0,
                "prize_est": "$0",
                "history": {}
            }

        # Add history entry for this date
        user_data[key]["history"][date_str] = {
            "rank": r.rank,
            "jade": r.jade,
            "delta": r.delta,
            "t1_refs": r.t1_refs or 0,
            "t2_refs": r.t2_refs or 0,
            "delta_t1": None,
            "delta_t2": None,
            "is_delayed": snap_id_to_delayed.get(r.snapshot_id, False)
        }

        # Update alias/team info from data mới nhất (alias có thể thay đổi qua các snapshot)
        if r.alias:
            user_data[key]["alias"] = r.alias
        if r.is_team:
            user_data[key]["is_team"] = True
            user_data[key]["team_role"] = r.team_role

        # Current metrics from latest snapshot only
        if r.snapshot_id == latest_snapshot_id:
            user_data[key]["current_rank"] = r.rank if r.rank else 999
            user_data[key]["current_jade"] = r.jade or 0
            user_data[key]["w_rate"] = r.w_rate or 0.0
            user_data[key]["proj_may31"] = r.proj_may31 or 0
            user_data[key]["prize_est"] = r.prize_est or "$0"

    # Pass 2: tính delta_t1, delta_t2 cho từng user
    for key, data in user_data.items():
        sorted_dates = sorted(data["history"].keys())
        for i, date_str in enumerate(sorted_dates):
            if i == 0:
                data["history"][date_str]["delta_t1"] = None
                data["history"][date_str]["delta_t2"] = None
            else:
                prev_date = sorted_dates[i - 1]
                prev = data["history"][prev_date]
                curr = data["history"][date_str]
                curr["delta_t1"] = curr["t1_refs"] - prev["t1_refs"]
                curr["delta_t2"] = curr["t2_refs"] - prev["t2_refs"]

    # 4. Alias/Team Override from TeamMember
    # Đảm bảo is_team/team_role luôn chính xác nhất kể cả snapshot cũ chưa backfill
    team_members = db.query(TeamMember).all()
    tm_alias_map = {tm.alias: tm for tm in team_members if tm.alias}
    
    for key, data in user_data.items():
        if key in tm_alias_map:
            tm = tm_alias_map[key]
            if not data["is_team"]:
                data["is_team"] = True
                data["team_role"] = tm.role

    # 5. Sort by current_rank, users not in latest snapshot go to bottom
    users_list = list(user_data.values())
    users_list.sort(key=lambda x: x["current_rank"])

    return {
        "dates": dates,
        "snapshots": snapshots_out,
        "users": users_list
    }

from sqlalchemy import text

@router.get("/aliases")
async def get_alias_summary(db: Session = Depends(get_db)):
    """
    Tr\u1ea3 v\u1ec1 to\u00e0n b\u1ed9 aliases trong h\u1ec7 th\u1ed1ng v\u1edbi th\u1ed1ng k\u00ea.
    D\u00f9ng cho trang Settings.
    """
    rows = db.execute(text("""
        SELECT
            alias,
            username,
            COUNT(DISTINCT snapshot_id) AS days_present,
            MAX(jade) AS max_jade,
            MIN(jade) AS min_jade,
            MAX(rank) AS worst_rank,
            MIN(rank) AS best_rank,
            MAX(CAST(is_team AS INTEGER)) AS is_team,
            MAX(team_role) AS team_role
        FROM rankings
        GROUP BY alias, username
        ORDER BY max_jade DESC
    """)).fetchall()

    result = []
    for r in rows:
        result.append({
            "alias": r[0],
            "username": r[1],
            "days_present": r[2],
            "max_jade": r[3],
            "min_jade": r[4],
            "worst_rank": r[5],
            "best_rank": r[6],
            "is_team": bool(r[7]),
            "team_role": r[8],
            "is_ghost": r[3] == 0,   # max_jade=0 \u2192 ghost
        })

    return result

@router.delete("/aliases/ghost")
async def delete_ghost_aliases(db: Session = Depends(get_db)):
    """
    X\u00f3a t\u1ea5t c\u1ea3 rankings c\u00f3 alias m\u00e0 max_jade = 0 across to\u00e0n b\u1ed9 snapshots.
    Kh\u00f4ng x\u00f3a aliases \u0111ang c\u00f3 jade > 0 \u1edf b\u1ea5t k\u1ef3 snapshot n\u00e0o.
    """
    # T\u00ecm ghost aliases
    ghost_rows = db.execute(text("""
        SELECT alias FROM rankings
        GROUP BY alias
        HAVING MAX(jade) = 0
    """)).fetchall()
    ghost_aliases = [r[0] for r in ghost_rows]

    if not ghost_aliases:
        return {"status": "success", "deleted": 0, "message": "Kh\u00f4ng c\u00f3 ghost alias n\u00e0o"}

    total_deleted = 0
    for alias in ghost_aliases:
        n = db.query(Ranking).filter(Ranking.alias == alias).delete(synchronize_session=False)
        total_deleted += n

    db.commit()
    return {
        "status": "success",
        "deleted_aliases": len(ghost_aliases),
        "deleted_records": total_deleted,
        "aliases": ghost_aliases
    }

@router.get("/charts/jade-history")
async def get_jade_history(usernames: str = None, db: Session = Depends(get_db)):
    snapshots = db.query(Snapshot).order_by(Snapshot.date).all()
    dates = [str(s.date) for s in snapshots]
    
    if usernames:
        user_list = usernames.split(',')
    else:
        # Default to top 5 users from the latest snapshot
        latest = snapshots[-1] if snapshots else None
        if not latest: return {"dates": dates, "series": []}
        top5 = db.query(Ranking).filter(Ranking.snapshot_id == latest.id).order_by(Ranking.rank).limit(5).all()
        user_list = [r.username for r in top5]
        
    series = []
    for uname in user_list:
        rankings = db.query(Ranking, Snapshot.date)\
            .join(Snapshot, Ranking.snapshot_id == Snapshot.id)\
            .filter(Ranking.username == uname)\
            .order_by(Snapshot.date).all()
            
        jade_map = {str(r.date): r.Ranking.jade for r in rankings}
        rank_map = {str(r.date): r.Ranking.rank for r in rankings}
        
        series.append({
            "username": uname,
            "alias": rankings[0].Ranking.alias if rankings else uname,
            "jade_history": [jade_map.get(d) for d in dates],
            "rank_history": [rank_map.get(d) for d in dates]
        })
        
    return {"dates": dates, "series": series}

@router.get("/charts/nau-daily")
async def get_nau_daily(db: Session = Depends(get_db)):
    snapshots = db.query(Snapshot).order_by(Snapshot.date).all()
    dates = [str(s.date) for s in snapshots]
    
    nau_rankings = db.query(Ranking, Snapshot.date)\
        .join(Snapshot, Ranking.snapshot_id == Snapshot.id)\
        .filter(Ranking.username == "nau***@gmail.com")\
        .order_by(Snapshot.date).all()
        
    delta_map = {str(r.date): r.Ranking.delta for r in nau_rankings}
    wrate_map = {str(r.date): r.Ranking.w_rate for r in nau_rankings}
    jade_map = {str(r.date): r.Ranking.jade for r in nau_rankings}
    
    # Gap vs #2
    gap_vs_2 = []
    for s in snapshots:
        top2 = db.query(Ranking).filter(Ranking.snapshot_id == s.id).order_by(Ranking.rank).limit(2).all()
        if len(top2) >= 2:
            # Find nau in these top 2 or just assume nau is top 1
            nau = next((r for r in top2 if r.username == "nau***@gmail.com"), None)
            other = next((r for r in top2 if r.username != "nau***@gmail.com"), None)
            if nau and other:
                gap_vs_2.append(nau.jade - other.jade)
            else:
                gap_vs_2.append(None)
        else:
            gap_vs_2.append(None)
            
    return {
        "dates": dates,
        "nau_delta": [delta_map.get(d) for d in dates],
        "gap_vs_2": gap_vs_2,
        "w_rate_line": [wrate_map.get(d) for d in dates]
    }

@router.get("/snapshots")
async def get_snapshots(db: Session = Depends(get_db)):
    return db.query(Snapshot).order_by(desc(Snapshot.date)).all()

@router.delete("/snapshots/{date_str}")
async def delete_snapshot(date_str: str, db: Session = Depends(get_db)):
    snapshot = db.query(Snapshot).filter(Snapshot.date == date_str).first()
    if snapshot:
        db.delete(snapshot)
        db.commit()
        return {"status": "success"}
    return {"status": "not found"}

@router.get("/top10")
async def get_top10(db: Session = Depends(get_db)):
    snapshot = db.query(Snapshot).order_by(desc(Snapshot.date)).first()
    if not snapshot: return []
    return db.query(Ranking).filter(Ranking.snapshot_id == snapshot.id).order_by(Ranking.rank).limit(10).all()

@router.get("/team")
async def get_team_stats(db: Session = Depends(get_db)):
    snapshot = db.query(Snapshot).order_by(desc(Snapshot.date)).first()
    if not snapshot: return []
    return db.query(Ranking).filter(Ranking.snapshot_id == snapshot.id, Ranking.is_team == True).order_by(Ranking.rank).all()

@router.get("/alerts")
async def get_latest_alerts(db: Session = Depends(get_db)):
    snapshot = db.query(Snapshot).order_by(desc(Snapshot.date)).first()
    if not snapshot: return []
    return db.query(Alert).filter(Alert.snapshot_id == snapshot.id).all()
