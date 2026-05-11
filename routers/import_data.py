from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from database import get_db, Snapshot, Ranking, TeamMember, Alert
from services.parser import parse_leaderboard_json, parse_leaderboard_html
from services.calculator import calculate_delta, calculate_w_rate, project_may31, estimate_prize
from services.alias_resolver import resolve_alias, sequential_match, KNOWN_ALIASES
from services.alerts import generate_alerts
from datetime import datetime, date
from typing import List, Optional
from pydantic import BaseModel
from collections import defaultdict

router = APIRouter(prefix="/api/import", tags=["import"])

def detect_and_parse(raw_input):
    """
    Tự động detect JSON hoặc HTML rồi parse.
    raw_input: string (JSON string hoặc HTML string)
    Trả về: list of parsed items
    """
    stripped = raw_input.strip()

    if stripped.startswith('<'):
        return parse_leaderboard_html(stripped)
    else:
        import json
        data = json.loads(stripped)
        return parse_leaderboard_json(data)

class RawImportRequest(BaseModel):
    raw_input: str
    import_date: str
    is_delayed: bool = False
    note: Optional[str] = None

def _process_import(parsed_items, import_date, is_delayed, note, db):
    dt = datetime.strptime(import_date, "%Y-%m-%d").date()
    snapshot = Snapshot(date=dt, is_delayed=is_delayed, note=note)
    db.add(snapshot)
    db.flush()

    # Build team map — username exact match only, KHÔNG dùng rank (Brief 16)
    team_members = db.query(TeamMember).all()
    team_map_by_username = {}
    for tm in team_members:
        key = tm.username
        if key not in team_map_by_username:
            team_map_by_username[key] = []
        team_map_by_username[key].append({
            "alias": tm.alias, "role": tm.role, "bxh_rank": tm.bxh_rank
        })
    # KHÔNG tạo team_map_by_rank — bxh_rank là số tĩnh, rank BXH thay đổi hàng ngày

    # Prev snapshot để tính delta và sequential matching
    prev_snapshot = db.query(Snapshot).filter(Snapshot.date < dt)\
        .order_by(Snapshot.date.desc()).first()
    prev_rankings_map = {}   # alias -> Ranking object
    prev_by_username = {}    # username -> [Ranking objects] — cho sequential matching
    if prev_snapshot:
        prev_rankings = db.query(Ranking)\
            .filter(Ranking.snapshot_id == prev_snapshot.id).all()
        prev_rankings_map = {r.alias: r for r in prev_rankings}
        for r in prev_rankings:
            if r.username not in prev_by_username:
                prev_by_username[r.username] = []
            prev_by_username[r.username].append(r)

    # Thêm refs vào mỗi item và group theo username để detect duplicate
    items_by_username = defaultdict(list)
    for item in parsed_items:
        item['refs'] = item.get('t1_refs', 0) + item.get('t2_refs', 0)
        items_by_username[item['username']].append(item)

    # Resolve alias cho từng nhóm username
    alias_assignments = {}  # id(item) -> (alias, role, is_team, confidence_ok)
    new_alerts = []         # Alert messages từ matching

    for username, items in items_by_username.items():
        if len(items) == 1:
            # Không có duplicate → resolve bình thường qua Tầng 1/2/3
            item = items[0]
            alias, role, is_team = resolve_alias(
                username, item['jade'], item['rank'], item['refs'], team_map_by_username
            )
            alias_assignments[id(item)] = (alias, role, is_team, True)

        else:
            # Duplicate username — chạy sequential matching (Tầng 1 Brief 16)
            prev_records_raw = prev_by_username.get(username, [])
            prev_records = [
                {"alias": r.alias, "jade": r.jade,
                 "refs": (r.t1_refs or 0) + (r.t2_refs or 0)}
                for r in prev_records_raw
            ]

            if len(prev_records) == len(items):
                # Đủ lịch sử — chạy sequential matching
                match_results = sequential_match(items, prev_records)
                for (new_item, prev_rec, confidence_ok) in match_results:
                    if prev_rec is not None:
                        matched_alias = prev_rec["alias"]

                        # Re-validate bằng KNOWN_ALIASES nếu username có rule
                        if username in KNOWN_ALIASES:
                            matched_alias = KNOWN_ALIASES[username](new_item['jade'], new_item['rank'])

                        # Kiểm tra alias có phải team member không
                        tm_entry = next(
                            (tm for tm in team_members if tm.alias == matched_alias), None
                        )
                        role = tm_entry.role if tm_entry else None
                        is_team = tm_entry is not None
                        alias_assignments[id(new_item)] = (matched_alias, role, is_team, confidence_ok)
                        if not confidence_ok:
                            new_alerts.append({
                                "level": "YELLOW",
                                "message": (
                                    f"Ghép cặp không chắc cho '{username}' rank {new_item['rank']} "
                                    f"(alias tạm: {matched_alias}). Vào /tracker để kiểm tra."
                                )
                            })
                    else:
                        # New record không có cặp trong prev → alias tạm
                        temp_alias = f"{username}[?]"
                        alias_assignments[id(new_item)] = (temp_alias, None, False, False)
                        new_alerts.append({
                            "level": "YELLOW",
                            "message": (
                                f"Username mới '{username}' rank {new_item['rank']} "
                                f"chưa xác định được alias. Vào /tracker để sửa alias thủ công."
                            )
                        })
            else:
                # Prev không có đủ record — Fallback Tầng 2: KNOWN_ALIASES / resolve_alias
                for item in items:
                    alias, role, is_team = resolve_alias(
                        username, item['jade'], item['rank'], item['refs'], team_map_by_username
                    )
                    if alias == username:
                        # Tầng 2 không có rule → Tầng 3: alias tạm + Alert
                        temp_alias = f"{username}[?]"
                        alias_assignments[id(item)] = (temp_alias, None, False, False)
                        new_alerts.append({
                            "level": "YELLOW",
                            "message": (
                                f"Duplicate username '{username}' rank {item['rank']} "
                                f"chưa có rule phân biệt. Vào /tracker để sửa alias thủ công."
                            )
                        })
                    else:
                        alias_assignments[id(item)] = (alias, role, is_team, True)

    # Build rankings với alias đã resolve
    rankings_to_save = []
    for item in parsed_items:
        alias, role, is_team, _ = alias_assignments[id(item)]

        prev_r = prev_rankings_map.get(alias)
        delta = calculate_delta(item["jade"], prev_r.jade if prev_r else None)

        history_rankings = db.query(Ranking, Snapshot.is_delayed)\
            .join(Snapshot, Ranking.snapshot_id == Snapshot.id)\
            .filter(Ranking.alias == alias)\
            .order_by(Snapshot.date.desc()).limit(18).all()

        history_deltas = [delta] + [r.Ranking.delta for r in history_rankings]
        is_delayed_list = [is_delayed] + [r.is_delayed for r in history_rankings]
        w_rate = calculate_w_rate(history_deltas, is_delayed_list)
        proj = project_may31(item["jade"], w_rate, dt)

        ranking = Ranking(
            snapshot_id=snapshot.id,
            rank=item["rank"],
            username=item["username"],
            alias=alias,
            jade=item["jade"],
            t1_refs=item["t1_refs"],
            t2_refs=item["t2_refs"],
            delta=delta,
            w_rate=w_rate,
            proj_may31=proj,
            prize_est="TBD",
            is_team=is_team,
            team_role=role
        )
        rankings_to_save.append(ranking)

    # Tính prize theo projected rank
    rankings_sorted_by_proj = sorted(
        [r for r in rankings_to_save if r.proj_may31 is not None],
        key=lambda r: r.proj_may31, reverse=True
    )
    for proj_rank, r in enumerate(rankings_sorted_by_proj, start=1):
        r.prize_est = estimate_prize(proj_rank)
    for r in rankings_to_save:
        if r.proj_may31 is None:
            r.prize_est = "N/A"

    db.add_all(rankings_to_save)
    db.flush()

    # Alerts từ matching + alerts thông thường
    all_alerts = new_alerts + generate_alerts(
        snapshot.id, rankings_to_save, prev_rankings_map, team_members
    )
    for alert_item in all_alerts:
        alert = Alert(
            snapshot_id=snapshot.id,
            level=alert_item["level"],
            message=alert_item["message"]
        )
        db.add(alert)

    db.commit()
    return {
        "status": "success",
        "message": f"Imported {len(rankings_to_save)} users for {import_date}",
        "snapshot_id": snapshot.id,
        "warnings": [a["message"] for a in new_alerts]
    }

@router.post("/preview")
async def preview_import(
    json_data: List[dict] = Body(...),
    import_date: str = Body(...),
    db: Session = Depends(get_db)
):
    dt = datetime.strptime(import_date, "%Y-%m-%d").date()
    existing_snapshot = db.query(Snapshot).filter(Snapshot.date == dt).first()
    if existing_snapshot:
        raise HTTPException(status_code=400, detail=f"Ngày {import_date} đã có dữ liệu.")

    parsed_items = parse_leaderboard_json(json_data)

    return {
        "date": import_date,
        "total_users": len(parsed_items),
        "preview_top5": parsed_items[:5],
        "preview_bottom3": parsed_items[-3:],
        "warning": "BXH có thể delay" if len(parsed_items) < 95 else None
    }

@router.post("")
async def import_data(
    json_data: List[dict] = Body(...),
    import_date: str = Body(...),
    is_delayed: bool = Body(False),
    note: Optional[str] = Body(None),
    db: Session = Depends(get_db)
):
    dt = datetime.strptime(import_date, "%Y-%m-%d").date()
    existing_snapshot = db.query(Snapshot).filter(Snapshot.date == dt).first()
    if existing_snapshot:
        raise HTTPException(status_code=400, detail=f"Data for {import_date} already exists.")

    parsed_items = parse_leaderboard_json(json_data)
    return _process_import(parsed_items, import_date, is_delayed, note, db)

@router.post("/preview-raw")
async def preview_import_raw(request: RawImportRequest, db: Session = Depends(get_db)):
    dt = datetime.strptime(request.import_date, "%Y-%m-%d").date()
    existing = db.query(Snapshot).filter(Snapshot.date == dt).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Ngày {request.import_date} đã có dữ liệu.")

    try:
        parsed_items = detect_and_parse(request.raw_input)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Parse lỗi: {str(e)}")

    return {
        "date": request.import_date,
        "total_users": len(parsed_items),
        "input_type": "html" if request.raw_input.strip().startswith('<') else "json",
        "preview_top5": parsed_items[:5],
        "warning": "BXH có thể thiếu data" if len(parsed_items) < 95 else None
    }

@router.post("/import-raw")
async def import_data_raw(request: RawImportRequest, db: Session = Depends(get_db)):
    dt = datetime.strptime(request.import_date, "%Y-%m-%d").date()
    existing = db.query(Snapshot).filter(Snapshot.date == dt).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Data for {request.import_date} already exists.")

    try:
        parsed_items = detect_and_parse(request.raw_input)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Parse lỗi: {str(e)}")

    return _process_import(parsed_items, request.import_date, request.is_delayed, request.note, db)

@router.get("/snapshots")
async def list_snapshots(db: Session = Depends(get_db)):
    """Trả về danh sách tất cả snapshots, sort theo date asc."""
    snapshots = db.query(Snapshot).order_by(Snapshot.date).all()
    return [
        {
            "id": s.id,
            "date": s.date.strftime("%Y-%m-%d"),
            "is_delayed": s.is_delayed,
            "note": s.note
        }
        for s in snapshots
    ]

@router.delete("/snapshot/{snapshot_id}")
async def delete_snapshot(snapshot_id: int, db: Session = Depends(get_db)):
    """
    Xóa 1 snapshot và toàn bộ rankings + alerts liên quan.
    Không cho phép xóa snapshot duy nhất còn lại trong DB.
    """
    # Kiểm tra snapshot tồn tại
    snapshot = db.query(Snapshot).filter(Snapshot.id == snapshot_id).first()
    if not snapshot:
        raise HTTPException(status_code=404, detail=f"Snapshot {snapshot_id} không tồn tại")

    # Không cho xóa nếu chỉ còn 1 snapshot
    total = db.query(Snapshot).count()
    if total <= 1:
        raise HTTPException(status_code=400, detail="Không thể xóa snapshot duy nhất còn lại")

    # Xóa rankings và alerts trước (foreign key), rồi xóa snapshot
    db.query(Ranking).filter(Ranking.snapshot_id == snapshot_id).delete(synchronize_session=False)
    db.query(Alert).filter(Alert.snapshot_id == snapshot_id).delete(synchronize_session=False)
    db.delete(snapshot)
    db.commit()

    return {
        "status": "success",
        "message": f"Đã xóa snapshot {snapshot.date} (id={snapshot_id})"
    }
