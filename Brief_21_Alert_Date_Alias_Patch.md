# Brief 21 — 3 fixes: Ngày cảnh báo + Alias DB patch + TeamMember format
> PM: Adam | Dev: atigravity | Priority: P1  
> 3 việc độc lập, làm theo thứ tự. Không cần restart server giữa các bước (trừ Bước 2 nếu có sửa Python).

---

## BƯỚC 1 — Thêm ngày vào Cảnh Báo trên Dashboard

### Vấn đề
Mục "Cảnh Báo" ở Dashboard chỉ hiển thị level + message, không có ngày. Khó biết cảnh báo này từ ngày nào.

### Fix — `static/app.js`

Tìm đoạn render alert (khoảng dòng 36-38):

```javascript
// HIỆN TẠI:
div.innerHTML = `<span class="badge ${badgeClass}">${alert.level}</span> <span style="font-size: 0.875rem">${alert.message}</span>`;
```

Sửa thành:

```javascript
// SỬA THÀNH — thêm ngày snapshot vào trước message:
const snapshotDate = data.snapshot?.date || '';
div.innerHTML = `<span class="badge ${badgeClass}">${alert.level}</span> <span style="color: var(--text-muted); font-size: 0.75rem; margin: 0 0.4rem;">${snapshotDate}</span><span style="font-size: 0.875rem">${alert.message}</span>`;
```

**Lưu ý:** `data.snapshot.date` đã có sẵn trong response của `/api/dashboard` (field `snapshot`). Không cần thay đổi backend.

---

## BƯỚC 2 — Patch alias sai trong DB (không cần re-import)

### Vấn đề
Snapshot 05/05 (id=25) có 2 alias sai được lưu từ trước khi Brief 16 fix:
- Rank 35: `qua***@gmail.com` → alias lưu là `qua[TEAM]` ← **sai**, đúng phải là `qua[T2]***` (jade=42,660 > 25,000)
- Rank 95: `hun***@gmail.com` → alias lưu là `hun[TEAM]` ← **sai**, đúng phải là `hun[moi]***` (rank=95 > 50)

Những alias sai này ảnh hưởng đến Tracker history (dùng alias làm key).

### Fix — Script SQL patch trực tiếp

Tạo file `patch_alias_05_05.py` trong thư mục project:

```python
"""
patch_alias_05_05.py — Patch alias sai trong snapshot 05/05 (id=25)
Chạy: python patch_alias_05_05.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal

db = SessionLocal()

try:
    # Patch 1: rank 35 — qua[TEAM] → qua[T2]***
    result1 = db.execute(
        """UPDATE rankings SET alias='qua[T2]***'
           WHERE snapshot_id=25 AND rank=35 AND username='qua***@gmail.com' AND alias='qua[TEAM]'""",
    )
    print(f"Patch 1 (rank 35 qua→qua[T2]***): {result1.rowcount} rows updated")

    # Patch 2: rank 95 — hun[TEAM] → hun[moi]***
    result2 = db.execute(
        """UPDATE rankings SET alias='hun[moi]***'
           WHERE snapshot_id=25 AND rank=95 AND username='hun***@gmail.com' AND alias='hun[TEAM]'""",
    )
    print(f"Patch 2 (rank 95 hun→hun[moi]***): {result2.rowcount} rows updated")

    # Verify
    rows = db.execute(
        """SELECT rank, username, alias, jade FROM rankings
           WHERE snapshot_id=25 AND rank IN (35, 95)"""
    ).fetchall()
    print("\nVerify sau patch:")
    for r in rows:
        print(f"  Rank {r[0]}: {r[1]} → alias={r[2]}, jade={r[3]:,}")

    db.commit()
    print("\nDone. Restart server sau khi chạy xong.")

except Exception as e:
    db.rollback()
    print(f"Error: {e}")
    raise
finally:
    db.close()
```

Chạy:
```
python patch_alias_05_05.py
```

---

## BƯỚC 3 — Fix TeamMember alias format (strip @gmail.com)

### Vấn đề
TeamMember hiện có alias sai format do Brief 20 fix code nhưng chưa sửa data cũ:
- `id=4`: alias = `nha***@gmail.com` ← sai, phải là `nha***`
- `id=5`: alias = `caf***@gmail.com` ← sai, phải là `caf***`
- `id=6`: alias = `kdl***@gmail.com` ← sai, phải là `kdl***`

Alias sai format làm `tm_alias_map` trong `get_tracker()` không match được với alias trong rankings (đã strip `@gmail.com`), dẫn đến `is_team=False` cho những user này trong Tracker.

### Fix — Script patch

Tạo file `patch_team_alias.py`:

```python
"""
patch_team_alias.py — Fix TeamMember alias: strip @gmail.com
Chạy: python patch_team_alias.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal, TeamMember, Ranking

db = SessionLocal()

try:
    members = db.query(TeamMember).all()
    for m in members:
        if m.alias and "@gmail.com" in m.alias:
            old_alias = m.alias
            new_alias = m.alias.replace("@gmail.com", "")
            
            # Update TeamMember alias
            m.alias = new_alias
            
            # Update tất cả rankings đang dùng alias cũ
            updated = db.query(Ranking).filter(Ranking.alias == old_alias).update(
                {"alias": new_alias}, synchronize_session=False
            )
            print(f"  {old_alias} → {new_alias} | rankings updated: {updated}")

    db.commit()
    print("\nDone.")

except Exception as e:
    db.rollback()
    print(f"Error: {e}")
    raise
finally:
    db.close()
```

Chạy:
```
python patch_team_alias.py
```

---

## THỨ TỰ THỰC HIỆN

```
1. Sửa static/app.js — thêm ngày vào alert render (không cần restart)
2. Chạy python patch_alias_05_05.py
3. Chạy python patch_team_alias.py  
4. Restart server
5. Verify checklist
```

---

## VERIFY CHECKLIST

**Bước 1 — Ngày cảnh báo:**
- [ ] Dashboard → mục "Cảnh Báo" → mỗi alert có ngày (vd: `2026-05-05`) hiển thị nhỏ giữa badge và message

**Bước 2 — Alias patch 05/05:**
- [ ] Dashboard rank 35: alias không còn là `qua[TEAM]` (phải là `qua[T2]***`)
- [ ] Dashboard rank 95: alias không còn là `hun[TEAM]` (phải là `hun[moi]***`)
- [ ] Tracker: `qua[T2]***` và `hun[moi]***` có history liên tục (không bị tạo entry mới)

**Bước 3 — TeamMember alias:**
- [ ] GET `/api/team-members` → không còn alias nào có `@gmail.com`
- [ ] Tracker: team members (`nha***`, `caf***`, `kdl***`) có checkbox Team đúng (ticked)
- [ ] Regression: is_team flag đúng trên Dashboard và Tracker

---

## YÊU CẦU SAU KHI HOÀN THÀNH

AG tạo file `Review_Report_Brief_21.md` trong thư mục project, ghi rõ:
- Output của từng script patch (số rows updated)
- Kết quả verify checklist (pass/fail từng item)
- Bất kỳ phát hiện nào ngoài scope brief
