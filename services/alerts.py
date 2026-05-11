def generate_alerts(snapshot_id, current_rankings, previous_rankings_map, team_members_list):
    """
    current_rankings: list of Ranking objects
    previous_rankings_map: dict of {username: Ranking object}
    team_members_list: list of TeamMember objects
    """
    alerts = []
    
    # 1. Check nau*** (Leader)
    nau = next((r for r in current_rankings if r.username == "nau***@gmail.com"), None)
    if nau and nau.delta is not None and nau.w_rate:
        if nau.delta < 0.7 * nau.w_rate:
            alerts.append({
                "level": "RED",
                "message": f"⚠️ Rate nau*** giảm bất thường hôm nay ({nau.delta} < 70% of {int(nau.w_rate)})"
            })
            
    # 2. Gap vs #2
    if len(current_rankings) >= 2:
        top1 = current_rankings[0]
        top2 = current_rankings[1]
        if top1.username == "nau***@gmail.com":
            gap = top1.jade - top2.jade
            if gap < 100000:
                alerts.append({
                    "level": "YELLOW",
                    "message": f"🟡 {top2.alias} đang thu hẹp gap, còn {gap:,} jade"
                })
                
    # 3. Team members delta = 0
    team_usernames = [tm.username for tm in team_members_list]
    for r in current_rankings:
        if r.username in team_usernames and r.username != "nau***@gmail.com":
            if r.delta == 0:
                # Check previous delta if possible (simplified: just check current)
                # Spec says "delta = 0 lần 2"
                prev = previous_rankings_map.get(r.username)
                if prev and prev.delta == 0:
                    alerts.append({
                        "level": "RED",
                        "message": f"🔴 {r.alias} rate = 0 hai ngày liên tiếp"
                    })
                    
    # 4. Top 50 threshold
    rank50 = next((r for r in current_rankings if r.rank == 50), None)
    prev_rank50 = next((r for r in previous_rankings_map.values() if r.rank == 50), None)
    if rank50 and prev_rank50:
        increase = rank50.jade - prev_rank50.jade
        if increase > 2000:
            alerts.append({
                "level": "YELLOW",
                "message": f"🟡 Ngưỡng top 50 hôm nay: {rank50.jade:,} jade (+{increase:,})"
            })
            
    # 5. New users with many T1
    for r in current_rankings:
        prev = previous_rankings_map.get(r.username)
        if not prev and r.t1_refs > 100:
            alerts.append({
                "level": "INFO",
                "message": f"ℹ️ {r.username} xuất hiện với {r.t1_refs} T1 refs"
            })
            
    # 6. Overall delay check
    if current_rankings:
        avg_delta = sum(r.delta for r in current_rankings if r.delta is not None) / len([r for r in current_rankings if r.delta is not None]) if any(r.delta is not None for r in current_rankings) else 0
        # This is a bit complex without full history. Simplified:
        # If too many top users have 0 or very low delta
        low_delta_count = sum(1 for r in current_rankings[:10] if r.delta is not None and r.delta < 100)
        if low_delta_count > 5:
            alerts.append({
                "level": "INFO",
                "message": "ℹ️ BXH có thể delay hôm nay (nhiều user top có delta thấp)"
            })
            
    return alerts
