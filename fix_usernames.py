from database import SessionLocal, Snapshot, Ranking
from datetime import date

def fix():
    db = SessionLocal()

    # Step 1: Build mapping from 29/04 snapshot
    snapshot_29 = db.query(Snapshot).filter(Snapshot.date == date(2026, 4, 29)).first()
    if not snapshot_29:
        print("ERROR: Snapshot 29/04 not found!")
        return

    json_rankings = db.query(Ranking).filter(Ranking.snapshot_id == snapshot_29.id).all()
    alias_to_correct = {}
    for r in json_rankings:
        if r.alias:
            alias_to_correct[r.alias] = r.username
        prefix = r.username.split('@')[0] if '@' in r.username else r.username
        alias_to_correct[prefix] = r.username
        alias_to_correct[r.username] = r.username

    print(f"Built map: {len(alias_to_correct)} entries")

    # Step 2: Update migrated rankings
    migrated = db.query(Ranking).filter(Ranking.snapshot_id != snapshot_29.id).all()
    print(f"Total migrated rankings to check: {len(migrated)}")

    fixed = 0
    no_map = []
    for r in migrated:
        correct = alias_to_correct.get(r.alias) or alias_to_correct.get(r.username)
        if correct and correct != r.username:
            r.username = correct
            fixed += 1
        elif not correct:
            no_map.append(r.alias or r.username)

    db.commit()
    print(f"Fixed: {fixed} usernames")

    # Step 3: Verify
    print("\n=== Verification ===")
    nau_count = db.query(Ranking).filter(Ranking.username == "nau***@gmail.com").count()
    print(f"nau***@gmail.com history count: {nau_count} (Expected: 19)")

    pha_count = db.query(Ranking).filter(Ranking.username == "pha***@gmail.com").count()
    print(f"pha***@gmail.com history count: {pha_count} (Expected: 19)")

    db.close()
    print("\nDone!")

if __name__ == "__main__":
    fix()
