import requests, json

def verify():
    try:
        r = requests.get('http://localhost:8000/api/dashboard')
        data = r.json()
        rankings = data.get("top10", [])
        print(f"Total rankings in dashboard: {len(rankings)}")
        
        # Verify Bug 1: thu***
        thu1 = next((r for r in rankings if r["rank"] == 7), None)
        if thu1:
            print(f"Rank 7 (thu***):")
            print(f"  Alias: {thu1['alias']}")
            print(f"  Delta: {thu1['delta']}")
            print(f"  W.Rate: {thu1['w_rate']}")
            print(f"  Proj: {thu1['proj_may31']}")
            print(f"  Prize: {thu1['prize_est']}")
        else:
            print("Rank 7 not found in dashboard")

        thu2 = next((r for r in rankings if r["rank"] == 44), None)
        if thu2:
            print(f"Rank 44 (thu***):")
            print(f"  Alias: {thu2['alias']}")
            print(f"  Delta: {thu2['delta']}")
        
        # Verify Bug 2: hun[TEAM]
        hun_team = next((r for r in rankings if r["rank"] == 95), None)
        if hun_team:
            print(f"Rank 95 (hun[TEAM]):")
            print(f"  Is Team: {hun_team['is_team']}")
            print(f"  Role: {hun_team['team_role']}")
        else:
            print("Rank 95 not found in dashboard")
            
        hun_bxh = next((r for r in rankings if r["rank"] == 22), None)
        if hun_bxh:
            print(f"Rank 22 (hun[BXH]):")
            print(f"  Is Team: {hun_bxh['is_team']}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    verify()
