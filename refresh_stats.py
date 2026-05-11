from sqlalchemy import desc
from database import SessionLocal, Snapshot, Ranking, TeamMember
from services.calculator import calculate_delta, calculate_w_rate, project_may31, estimate_prize
from services.alias_resolver import resolve_alias

def refresh():
    db = SessionLocal()

    # Get all snapshots in chronological order
    snapshots = db.query(Snapshot).order_by(Snapshot.date).all()

    # Build team map — username exact match only, KHÔNG dùng bxh_rank (Brief 16)
    team_members = db.query(TeamMember).all()
    team_map_by_username = {}
    for tm in team_members:
        key = tm.username
        if key not in team_map_by_username:
            team_map_by_username[key] = []
        team_map_by_username[key].append({
            "alias": tm.alias, "role": tm.role, "bxh_rank": tm.bxh_rank
        })

    for snapshot in snapshots:
        print(f"Refreshing {snapshot.date}...")
        rankings = db.query(Ranking).filter(Ranking.snapshot_id == snapshot.id).all()

        # Get previous rankings (lookup by alias — unique per person)
        prev_snapshot = db.query(Snapshot).filter(Snapshot.date < snapshot.date).order_by(desc(Snapshot.date)).first()
        prev_map = {}
        if prev_snapshot:
            prev_rankings = db.query(Ranking).filter(Ranking.snapshot_id == prev_snapshot.id).all()
            prev_map = {r.alias: r for r in prev_rankings}

        for r in rankings:
            refs = (r.t1_refs or 0) + (r.t2_refs or 0)

            # Update is_team và team_role dựa trên alias đã có trong DB
            # ⚠️ KHÔNG overwrite r.alias — alias chỉ được set lúc import hoặc PM sửa thủ công
            _, role, is_team = resolve_alias(
                r.username, r.jade, r.rank, refs, team_map_by_username
            )
            # Nhưng nếu alias đang là [?] hoặc là full username, thử resolve lại
            # (trường hợp PM đã thêm rule KNOWN_ALIASES mới sau khi import)
            if r.alias == r.username or (r.alias and '[?]' in r.alias):
                resolved_alias, role, is_team = resolve_alias(
                    r.username, r.jade, r.rank, refs, team_map_by_username
                )
                if resolved_alias != r.username and '[?]' not in resolved_alias:
                    r.alias = resolved_alias
            else:
                # Alias đã đúng — chỉ cập nhật is_team/team_role từ resolve_alias
                _, role, is_team = resolve_alias(
                    r.username, r.jade, r.rank, refs, team_map_by_username
                )

            r.is_team = is_team
            r.team_role = role

            # Recalculate delta, w_rate, proj
            prev_r = prev_map.get(r.alias)
            r.delta = calculate_delta(r.jade, prev_r.jade if prev_r else None)

            history = db.query(Ranking, Snapshot.is_delayed)\
                .join(Snapshot, Ranking.snapshot_id == Snapshot.id)\
                .filter(Ranking.alias == r.alias, Snapshot.date <= snapshot.date)\
                .order_by(desc(Snapshot.date)).limit(18).all()

            history_deltas = [item.Ranking.delta for item in history]
            is_delayed_list = [item.is_delayed for item in history]

            r.w_rate = calculate_w_rate(history_deltas, is_delayed_list)
            r.proj_may31 = project_may31(r.jade, r.w_rate or 0, snapshot.date)

        # Recalculate prizes based on projected rank for this snapshot
        rankings_sorted = sorted(
            [r for r in rankings if r.proj_may31 is not None],
            key=lambda x: x.proj_may31,
            reverse=True
        )
        for proj_rank, r in enumerate(rankings_sorted, start=1):
            r.prize_est = estimate_prize(proj_rank)

        for r in rankings:
            if r.proj_may31 is None:
                r.prize_est = "N/A"

        db.commit()

    db.close()
    print("Refresh complete.")

if __name__ == "__main__":
    refresh()
