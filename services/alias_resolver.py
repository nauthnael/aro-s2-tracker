"""
alias_resolver.py — Brief 16: Alias Disambiguation Overhaul (Sequential Matching)
Brief 20: Default alias strips @gmail.com for consistency with historical data.

Tang 1: Sequential matching (greedy cost-minimization) cho duplicate usernames.
Tang 2: KNOWN_ALIASES (jade/rank threshold da cau hinh).
Tang 3: Default — strip @gmail.com.
"""


def _compute_cost(new_jade, new_refs, prev_jade, prev_refs):
    """
    Cost function de ghep cap. Thap hon = tot hon.
    Refs chi dung lam tiebreaker khi khac nhau.
    """
    jade_diff = abs(new_jade - prev_jade)
    if new_refs != prev_refs:
        refs_diff = abs(new_refs - prev_refs) * 1000
    else:
        refs_diff = 0
    return jade_diff + refs_diff


def sequential_match(new_records, prev_records):
    """
    Ghep N new_records voi M prev_records bang greedy matching.

    new_records: list of dict {username, jade, refs, rank, ...}
    prev_records: list of dict {alias, jade, refs, ...} — tu prev snapshot cung username

    Return: list of (new_record, prev_record_or_None, confidence_ok: bool)
    """
    if not prev_records:
        return [(r, None, False) for r in new_records]

    results = []
    remaining_prev = list(prev_records)
    remaining_new = list(new_records)

    while remaining_new and remaining_prev:
        best_cost = float('inf')
        best_new_idx = 0
        best_prev_idx = 0

        for i, nr in enumerate(remaining_new):
            for j, pr in enumerate(remaining_prev):
                cost = _compute_cost(nr['jade'], nr['refs'], pr['jade'], pr['refs'])
                if cost < best_cost:
                    best_cost = cost
                    best_new_idx = i
                    best_prev_idx = j

        chosen_new = remaining_new.pop(best_new_idx)
        chosen_prev = remaining_prev.pop(best_prev_idx)

        # Confidence check: so sanh voi cap tot nhi con lai
        confidence_ok = True
        if remaining_prev:
            second_best_cost = min(
                _compute_cost(chosen_new['jade'], chosen_new['refs'], pr['jade'], pr['refs'])
                for pr in remaining_prev
            )
            diff_ratio = (second_best_cost - best_cost) / max(chosen_new['jade'], 1)
            if diff_ratio < 0.20:
                confidence_ok = False

        results.append((chosen_new, chosen_prev, confidence_ok))

    # New records khong co prev de ghep
    for nr in remaining_new:
        results.append((nr, None, False))

    return results


# KNOWN_ALIASES: jade/rank threshold cho duplicate da biet
# lambda nhan (jade, rank) de linh hoat dung ca 2
KNOWN_ALIASES = {
    "mal***@gmail.com": lambda j, r: "mal[1]***" if j > 400000 else "mal[2]***",
    "tra***@gmail.com": lambda j, r: "tra[1]***" if j > 300000 else ("tra[2]***" if j > 50000 else "tra[3]***"),
    "qua***@gmail.com": lambda j, r: "qua[T2]***" if j > 25000 else "qua[farm]***",
    "kha***@gmail.com": lambda j, r: "kha[1]***" if j > 200000 else "kha[2]***",
    "rom***@gmail.com": lambda j, r: "rom[1]***" if j > 100000 else ("rom[2]***" if j > 30000 else "rom[3]***"),
    "ben***@gmail.com": lambda j, r: "ben[1]***" if j > 80000 else ("ben[2]***" if j > 30000 else "ben[3]***"),
    "hun***@gmail.com": lambda j, r: "hun[BXH]***" if r < 50 else "hun[moi]***",
    "thu***@gmail.com": lambda j, r: "thu[1]***" if j > 200000 else "thu[2]***",
}


def resolve_alias(username, jade, rank, refs, team_members_map):
    """
    Resolve alias cho 1 user don le (khong phai duplicate).
    Dung cho Tang 2 va Tang 3.

    username: full masked email (vd: dan***@gmail.com)
    jade: int
    rank: int
    refs: int (t1_refs + t2_refs)
    team_members_map: {username: [{"alias": str, "role": str, "bxh_rank": int|None}]}

    Return: (alias, role, is_team)
    """
    # Tang 1 — Team member lookup (username exact match, KHONG dung rank)
    if username in team_members_map:
        members = team_members_map[username]
        if len(members) == 1:
            return members[0]["alias"], members[0]["role"], True
        else:
            # Nhieu entry cung username trong TeamMember
            sorted_members = sorted(members, key=lambda m: m.get("bxh_rank") or 999)
            for m in sorted_members:
                if m.get("bxh_rank") and rank <= m["bxh_rank"]:
                    return m["alias"], m["role"], True
            m = sorted_members[-1]
            return m["alias"], m["role"], True

    # Tang 2 — KNOWN_ALIASES (jade/rank threshold cho duplicate da biet)
    if username in KNOWN_ALIASES:
        return KNOWN_ALIASES[username](jade, rank), None, False

    # Tầng 3 — Default: strip @gmail.com để nhất quán với alias đã lưu trong DB
    alias = username.replace("@gmail.com", "") if "@gmail.com" in username else username
    return alias, None, False
