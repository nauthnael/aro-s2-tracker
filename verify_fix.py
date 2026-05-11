import sqlite3
con = sqlite3.connect('data/aro_tracker.db')
cur = con.cursor()
cur.execute('SELECT id, date FROM snapshots ORDER BY date DESC LIMIT 1')
snap = cur.fetchone()
snap_id = snap[0]
print(f"Snapshot: {snap[1]}")

cur.execute("""SELECT alias, rank, jade, delta, w_rate 
               FROM rankings WHERE snapshot_id=? 
               AND (alias LIKE 'mal%' OR alias LIKE 'tra%' OR alias LIKE 'qua%')
               ORDER BY rank""", (snap_id,))
for r in cur.fetchall():
    print(f"  alias={str(r[0]):<15} rank={str(r[1]):<5} jade={str(r[2]):<8} delta={str(r[3]):<10} w_rate={round(r[4] or 0)}")
con.close()
