# Brief 23 — Fix alias kế thừa sai + dọn DB garbage + xóa snapshot 27 nhầm ngày
> PM: Adam | Dev: atigravity | Priority: P0  
> Root cause đã xác định. 3 việc cần làm theo thứ tự.

---

## ROOT CAUSE

### Vấn đề 1 — Sequential match kế thừa alias sai vô điều kiện

`routers/import_data.py` dòng 101-108:

```python
# HIỆN TẠI — kế thừa alias cũ dù alias đó sai:
if prev_rec is not None:
    matched_alias = prev_rec["alias"]   # ← lấy alias từ prev, không validate
    alias_assignments[id(new_item)] = (matched_alias, role, is_team, confidence_ok)
```

Khi import 06/05 lần 1, `qua***@gmail.com` rank 36 bị gán alias `qua[TEAM]` (sai từ import cũ). Khi import 06/05 lần 2 (snapshot 27), sequential match tìm prev record của `qua***@gmail.com` → thấy alias `qua[TEAM]***` → kế thừa → alias sai tiếp tục.

**Fix đúng:** Sau khi sequential match cho ra alias từ prev, nếu username có rule trong KNOWN_ALIASES thì **bỏ alias cũ, dùng KNOWN_ALIASES** — vì KNOWN_ALIASES là source of truth cho duplicate usernames đã biết.

### Vấn đề 2 — Snapshot 27 bị gán sai ngày (07/05 nhưng data là 06/05)

PM nhập nhầm: paste data 06/05 nhưng chọn ngày 07/05. Cần xóa snapshot 27.

### Vấn đề 3 — Garbage aliases trong DB

Tracker hiện có nhiều alias rác từ các lần import lỗi cũ:
- `qua[TEAM]` (không có ***) — alias không valid
- `qua[TEAM]***` — alias kế thừa sai từ sequential match  
- `qua[1]***`, `qua[2]***` — alias không rõ nguồn gốc, jade=0

---

## PHẦN 1 — Fix `routers/import_data.py`

Tìm đoạn trong `_process_import()` (khoảng dòng 96-116), phần xử lý sequential match khi `len(prev_records) == len(items)`:

```python
# HIỆN TẠI (SAI):
match_results = sequential_match(items, prev_records)
for (new_item, prev_rec, confidence_ok) in match_results:
    if prev_rec is not None:
        matched_alias = prev_rec["alias"]
        tm_entry = next(
            (tm for tm in team_members if tm.alias == matched_alias), None
        )
        role = tm_entry.role if tm_entry else None
        is_team = tm_entry is not None
        alias_assignments[id(new_item)] = (matched_alias, role, is_team, confidence_ok)
```

```python
# SỬA THÀNH — validate alias sau khi match:
match_results = sequential_match(items, prev_records)
for (new_item, prev_rec, confidence_ok) in match_results:
    if prev_rec is not None:
        matched_alias = prev_rec["alias"]

        # --- THÊM: Re-validate bằng KNOWN_ALIASES ---
        # Nếu username có rule KNOWN_ALIASES, dùng rule đó thay vì alias cũ.
        # KNOWN_ALIASES là source of truth cho duplicate usernames đã biết.
        from services.alias_resolver import KNOWN_ALIASES
        if username in KNOWN_ALIASES:
            matched_alias = KNOWN_ALIASES[username](new_item['jade'], new_item['rank'])
        # --- END THÊM ---

        tm_entry = next(
            (tm for tm in team_members if tm.alias == matched_alias), None
        )
        role = tm_entry.role if tm_entry else None
        is_team = tm_entry is not None
        alias_assignments[id(new_item)] = (matched_alias, role, is_team, confidence_ok)
```

**Lưu ý:** Import `KNOWN_ALIASES` nên được đưa lên đầu file (dòng 6) cùng với các import khác từ `alias_resolver`:

```python
# Dòng 6 — sửa thành:
from services.alias_resolver import resolve_alias, sequential_match, KNOWN_ALIASES
```

Và xóa dòng `from services.alias_resolver import KNOWN_ALIASES` trong thân hàm.

---

## PHẦN 2 — Script xóa snapshot 27 và dọn garbage aliases

Tạo file `patch_cleanup_db.py`:

```python
"""
patch_cleanup_db.py — Xóa snapshot 27 (sai ngày) + dọn garbage aliases
Chạy: python patch_cleanup_db.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal, Snapshot, Ranking, Alert

db = SessionLocal()

try:
    # ── Bước 1: Xóa snapshot 27 (data 06/05 nhập nhầm ngày 07/05) ──
    snap27 = db.query(Snapshot).filter(Snapshot.id == 27).first()
    if snap27:
        print(f"Xóa snapshot id=27, date={snap27.date}")
        db.query(Ranking).filter(Ranking.snapshot_id == 27).delete(synchronize_session=False)
        db.query(Alert).filter(Alert.snapshot_id == 27).delete(synchronize_session=False)
        db.delete(snap27)
        print("  → Đã xóa")
    else:
        print("Snapshot 27 không tồn tại (đã xóa trước?)")

    # ── Bước 2: Dọn garbage aliases — users có jade=0 và alias không hợp lệ ──
    # Các alias rác cần xóa khỏi rankings (jade=0 = không có trong top 100 ngày đó)
    # Nhưng KHÔNG xóa records trong snapshots đã import — chỉ xóa nếu TOÀN BỘ history = 0
    
    # Tìm aliases chỉ xuất hiện với jade=0 (ghost entries)
    from sqlalchemy import func
    ghost_check = db.execute("""
        SELECT alias, COUNT(*) as cnt, SUM(jade) as total_jade
        FROM rankings
        GROUP BY alias
        HAVING total_jade = 0 AND alias NOT LIKE '%[?]%'
        ORDER BY alias
    """).fetchall()
    
    print(f"\nGhost aliases (jade luôn = 0): {len(ghost_check)}")
    for row in ghost_check:
        print(f"  alias={row[0]}, count={row[1]}, total_jade={row[2]}")
    
    # Xóa ghost rankings (không có trong bất kỳ snapshot nào với jade > 0)
    deleted_total = 0
    for row in ghost_check:
        alias = row[0]
        n = db.execute(
            f"DELETE FROM rankings WHERE alias='{alias}' AND jade=0"
        ).rowcount
        deleted_total += n
        print(f"  Xóa {n} records cho alias={alias}")
    
    db.commit()
    print(f"\nTổng records xóa: {deleted_total}")
    print("Done. Restart server.")

except Exception as e:
    db.rollback()
    print(f"Error: {e}")
    raise
finally:
    db.close()
```

Chạy:
```
python patch_cleanup_db.py
```

---

## PHẦN 3 — Re-import 06/05 đúng ngày

Sau khi xóa snapshot 27 và fix code (Phần 1), **PM re-import 06/05**:

1. Vào Dashboard → Import BXH
2. Chọn ngày **2026-05-06** (chú ý chọn đúng ngày)
3. Paste data BXH 06/05
4. Parse & Preview → kiểm tra:
   - Rank 35: `thu***@gmail.com` jade ~45,080
   - Rank 36: `qua***@gmail.com` jade ~43,440
   - Rank 94: `hun***@gmail.com` jade ~16,149
   - Rank 95: `huy***@gmail.com` jade ~16,149
5. Confirm Import

---

## THỨ TỰ THỰC HIỆN

```
1. Sửa routers/import_data.py — thêm KNOWN_ALIASES re-validation (Phần 1)
2. Restart server
3. Chạy python patch_cleanup_db.py (xóa snapshot 27 + dọn garbage)
4. PM re-import BXH 06/05 qua UI (chọn đúng ngày 2026-05-06)
5. Verify checklist
```

---

## VERIFY CHECKLIST

**Alias logic:**
- [ ] Import bất kỳ ngày nào có `qua***@gmail.com` jade > 25K → alias tự động = `qua[T2]***` (không phải `qua[TEAM]***`)
- [ ] Import bất kỳ ngày nào có `hun***@gmail.com` rank > 50 → alias = `hun[moi]***`
- [ ] Import bất kỳ ngày nào có `hun***@gmail.com` rank ≤ 50 → alias = `hun[BXH]***`
- [ ] Import bất kỳ ngày nào có `mal***@gmail.com` jade > 400K → alias = `mal[1]***`

**Data 06/05 sau re-import:**
- [ ] Rank 35: alias = `thu[2]***`, jade = 45,080
- [ ] Rank 36: alias = `qua[T2]***`, jade = 43,440 (KHÔNG phải `qua[TEAM]***`)
- [ ] Rank 94: alias = `hun[moi]***` hoặc `hun[BXH]***` (tùy rank)
- [ ] Rank 95: alias = `huy***`, jade = 16,149
- [ ] Delta 06/05 tính đúng so với 05/05

**DB sạch:**
- [ ] Không còn alias nào có jade = 0 tồn tại trong rankings (ghost entries đã xóa)
- [ ] Tracker không còn hiện `qua[TEAM]`, `qua[1]***`, `qua[2]***` với jade = 0

**Regression:**
- [ ] Các alias KNOWN_ALIASES khác (`mal`, `tra`, `kha`, `rom`, `ben`, `thu`) vẫn đúng
- [ ] Team members vẫn đúng alias và is_team sau re-import

---

## YÊU CẦU SAU KHI HOÀN THÀNH

AG tạo file `Review_Report_Brief_23.md` trong thư mục project, ghi rõ:
- Output của `patch_cleanup_db.py` (số ghost records xóa)
- Alias của rank 35, 36, 94, 95 trong snapshot 06/05 sau re-import
- Kết quả verify checklist (pass/fail từng item)
- Bất kỳ phát hiện nào ngoài scope brief
