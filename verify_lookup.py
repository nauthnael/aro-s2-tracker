import requests, json

try:
    r = requests.get('http://localhost:8000/api/team-members/with-stats')
    data = r.json()
    print(f"Total members: {len(data)}")
    
    targets = ["hun[TEAM]", "qua[TEAM]"]
    for m in data:
        alias = m.get("alias")
        if alias in targets:
            stats_status = "FOUND" if m.get("stats") else "NULL"
            print(f"User: {alias}, Stats: {stats_status}, BXH Rank: {m.get('bxh_rank')}")
            if m.get("stats"):
                print(f"   Details: Rank {m['stats']['rank']}, Jade {m['stats']['jade']}")
except Exception as e:
    print(f"Error: {e}")
