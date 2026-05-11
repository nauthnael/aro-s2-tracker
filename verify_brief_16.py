from services.alias_resolver import resolve_alias, sequential_match

team_map = {
    'qua***@gmail.com': [{'alias': 'qua[TEAM]', 'role': 'T1', 'bxh_rank': 35}],
    'hun***@gmail.com': [{'alias': 'hun[TEAM]', 'role': 'T1', 'bxh_rank': 95}],
}

print("=== Test resolve_alias (single) ===")
# qua[TEAM] - rank đã lệch sang 36, vẫn phải match vì username exact match
r = resolve_alias('qua***@gmail.com', 45000, 36, 10, team_map)
print(f"qua@ rank=36 jade=45k  -> {r}")

# thu[1]*** - jade > 200K
r = resolve_alias('thu***@gmail.com', 264000, 7, 5, {})
print(f"thu@ rank=7  jade=264k -> {r}")

# thu[2]*** - jade < 200K
r = resolve_alias('thu***@gmail.com', 45000, 35, 3, {})
print(f"thu@ rank=35 jade=45k  -> {r}")

# hun[TEAM] - rank 94, bxh_rank=95, 94 <= 95 so matches
r = resolve_alias('hun***@gmail.com', 15000, 94, 2, team_map)
print(f"hun@ rank=94 jade=15k  -> {r}")

# huy*** - not in team_map at all
r = resolve_alias('huy***@gmail.com', 15200, 95, 0, {})
print(f"huy@ rank=95 jade=15k  -> {r}")

print()
print("=== Test sequential_match (thu*** 2 people) ===")
new_records = [
    {'username': 'thu***@gmail.com', 'jade': 45000, 'refs': 3, 'rank': 35},
    {'username': 'thu***@gmail.com', 'jade': 264000, 'refs': 10, 'rank': 7},
]
prev_records = [
    {'alias': 'thu[2]***', 'jade': 42000, 'refs': 3},
    {'alias': 'thu[1]***', 'jade': 260000, 'refs': 10},
]
results = sequential_match(new_records, prev_records)
for new_r, prev_r, ok in results:
    alias = prev_r['alias'] if prev_r else None
    print(f"  rank={new_r['rank']} jade={new_r['jade']} -> alias={alias} confidence_ok={ok}")

print()
print("=== Test qua[TEAM] being wrongly matched — should be prevented ===")
# Scenario: thu***@gmail.com at rank 35 used to be wrongly matched to qua[TEAM]
# With sequential_match, prev would have thu[2]*** at rank 35, not qua[TEAM]
# This shows the sequential_match returns correct alias from prev snapshot
new_records2 = [
    {'username': 'thu***@gmail.com', 'jade': 45000, 'refs': 3, 'rank': 35},
]
prev_records2 = [
    {'alias': 'thu[2]***', 'jade': 42000, 'refs': 3},  # prev snapshot had correct alias
]
results2 = sequential_match(new_records2, prev_records2)
for new_r, prev_r, ok in results2:
    alias = prev_r['alias'] if prev_r else None
    print(f"  rank={new_r['rank']} jade={new_r['jade']} -> alias={alias} confidence_ok={ok}")
    assert alias == 'thu[2]***', f"FAIL: expected thu[2]***, got {alias}"
    print("  PASS: thu***@gmail.com rank 35 correctly matched to thu[2]***")
