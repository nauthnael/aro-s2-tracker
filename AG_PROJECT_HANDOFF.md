# ARO Sprint 2 Tracker — Project Handoff cho AG
> Cập nhật: 02/05/2026 (rev 2) | PM: Adam | Dev: atigravity  
> File này tóm tắt toàn bộ dự án để AG nắm tình hình và tiếp tục làm việc.

---

## 1. TỔNG QUAN DỰ ÁN

Web app theo dõi BXH ARO Sprint 2 Testnet (kết thúc 31/05/2026).  
Thay thế workflow Excel + Python thủ công trước đây.

**Stack:**
- Backend: FastAPI + SQLAlchemy + SQLite (`data/aro_tracker.db`)
- Frontend: Vanilla JS + HTML/CSS, Chart.js
- Chạy local: `python main.py` → http://localhost:8000

**Cấu trúc thư mục:**
```
main.py                  ← Entry point, FastAPI app
database.py              ← SQLAlchemy models: Snapshot, Ranking, TeamMember, Alert
requirements.txt
routers/
  import_data.py         ← POST /api/import, POST /api/import/preview
  dashboard.py           ← GET /api/dashboard, /api/tracker, /api/charts/*
  team.py                ← CRUD /api/team-members
  users.py
services/
  parser.py              ← Parse JSON từ BXH ARO
  calculator.py          ← delta, w_rate, proj_may31, estimate_prize
  alias_resolver.py      ← Phân biệt duplicate masked username
  alerts.py              ← Generate alerts
static/
  index.html + app.js    ← Dashboard (/)
  tracker.html + tracker.js  ← Pivot table (/tracker)
  team.html + team.js    ← Team management (/team)
  charts.html            ← Charts (/charts)
  style.css
data/
  aro_tracker.db         ← SQLite DB (19 snapshots, 100 users/snapshot)
refresh_stats.py         ← Recalculate delta/w_rate/prize cho toàn bộ DB
migrate_excel.py         ← One-time: import 18 ngày từ Excel vào DB
```

---

## 2. DB SCHEMA (QUAN TRỌNG)

```python
# Snapshot: 1 record per ngày import
Snapshot: id, date, is_delayed, note, created_at

# Ranking: 100 records per snapshot (1 per user)
Ranking: id, snapshot_id, rank, username, alias, jade, t1_refs, t2_refs,
         delta, w_rate, proj_may31, prize_est, is_team, team_role

# TeamMember: danh sách thành viên team nau***
TeamMember: id, username, alias, role (LEADER/T1/T2), bxh_rank, join_date, note

# Alert: cảnh báo tự động
Alert: id, snapshot_id, level (RED/YELLOW/INFO), message, created_at
```

**Lưu ý `bxh_rank` trong TeamMember:** Column này đã được thêm vào model `database.py` nhưng cần chạy migration:
```bash
python migrate_add_bxh_rank.py
```

---

## 3. BUSINESS LOGIC QUAN TRỌNG

### W.Rate (Weighted Rate)
```
W.Rate = Σ(delta_i × weight_i) / Σ(weight_i)
```
- Ngày mới nhất: weight = 15, giảm dần về 1 cho ngày xa nhất (tối đa 18 ngày)
- Ngày bị delay (is_delayed=True): weight = 2 (downweight)

### Prize
Dựa trên **current rank** (KHÔNG phải projected rank):
- #1 → $5,000 | #2–5 → $2,000 | #6–10 → $1,000 | #11–50 → $200 | #51–100 → $50

### Duplicate Masked Username
BXH mask email: `malicious123@gmail.com` → `mal***@gmail.com`. Hai người khác nhau có thể cùng hiển thị là `mal***@gmail.com`. Xử lý bằng `alias_resolver.py` — phân biệt bằng jade threshold.

---

## 4. BRIEF ĐÃ GIAO & TRẠNG THÁI

| # | File | Nội dung | Trạng thái |
|---|------|----------|------------|
| 1 | Brief_1_Master_Tracker_View.md | Pivot table /tracker với frozen columns, mode toggle Jade/Delta/Rank | ✅ Done |
| 2 | Brief_2_Charts_Dashboard_Fixes.md | Charts, top 100, import preview | ✅ Done |
| 3 | Brief_3_Historical_Data_Migration.md | Import 18 ngày từ Excel vào DB | ✅ Done |
| 4 | Brief_4_Team_Feature_Fix.md | Fix bảng Team: API đúng, delete, duplicate check | ✅ Done |
| **5** | **Brief_5_Team_Rank_Edit.md** | **Thêm `bxh_rank` + Edit button ở /team** | **⏳ CHƯA DONE** |
| **6** | **Brief_6_Tracker_Alias_Edit_Prize_Fix.md** | **Sửa alias ở /tracker + fix prize display** | **⏳ CHƯA DONE** |
| 7 | Brief_7_Prize_Bug_Fix.md | Fix prize dùng current_rank thay vì proj_rank | ✅ Done |
| **8** | **Brief_8_Duplicate_Username_Fix.md** | **Fix delta/W.Rate sai do duplicate username** | **⏳ CHƯA DONE** |

**AG cần implement Brief 5, 6, 8 — theo thứ tự ưu tiên: 8 → 5 → 6.**

---

## 5. CÁC BUG ĐÃ XÁC ĐỊNH — CẦN FIX NGAY

### ~~Bug P0-A: Prize tính sai (Brief 7)~~ ✅ ĐÃ FIX

Prize đã được sửa để dùng `current rank` thay vì projected rank. `refresh_stats.py` đã chạy lại.

---

### Bug P0-B: Delta và W.Rate sai do duplicate masked username (Brief 8)

**Files:** `routers/import_data.py`, `refresh_stats.py`, `services/alias_resolver.py`

**Root cause:** `prev_rankings_map` và W.Rate history query đều dùng `username` làm key. Khi 2 người cùng `mal***@gmail.com`, dict chỉ giữ 1 record → delta user thứ 2 bị tính sai hoàn toàn (ví dụ: mal[2]*** jade 25K bị so với jade 555K của mal[1]*** → delta = −530K).

**Fix:** Dùng `alias` làm key thay vì `username` ở 3 chỗ:

```python
# 1. import_data.py — build prev_map:
prev_rankings_map = {r.alias: r for r in prev_rankings}  # ← alias, không phải username

# 2. import_data.py — delta lookup:
prev_r = prev_rankings_map.get(alias)  # ← alias (đã resolve trước đó)

# 3. import_data.py — W.Rate history:
.filter(Ranking.alias == alias)  # ← alias, không phải username

# 4. refresh_stats.py — build prev_map:
prev_map = {r.alias: r for r in prev_rankings}  # ← alias

# 5. refresh_stats.py — delta + W.Rate:
prev_r = prev_map.get(r.alias)
.filter(Ranking.alias == r.alias)
```

Sau khi sửa: `python refresh_stats.py`

**Thêm vào `alias_resolver.py`** các case còn thiếu:
```python
KNOWN_ALIASES = {
    "mal***@gmail.com": lambda j: "mal[1]***" if j > 400000 else "mal[2]***",
    "tra***@gmail.com": lambda j: "tra[1]***" if j > 300000 else "tra[2]***",
    "qua***@gmail.com": lambda j: "qua[T2]***" if j > 25000 else "qua[farm]***",
    "kha***@gmail.com": lambda j: "kha[1]***" if j > 200000 else "kha[2]***",
    "rom***@gmail.com": lambda j: "rom[1]***" if j > 100000 else ("rom[2]***" if j > 30000 else "rom[3]***"),
    "ben***@gmail.com": lambda j: "ben[1]***" if j > 80000 else ("ben[2]***" if j > 30000 else "ben[3]***"),
    "hun***@gmail.com": lambda j: "hun[BXH]***" if j > 50000 else "hun[mới]***",
}
```
⚠️ Đảm bảo key là **full username** (có `@gmail.com`), không phải prefix ngắn.

---

### Feature: Thêm bxh_rank + Edit ở /team (Brief 5)

**Mục đích:** Khi 2 thành viên team cùng masked username, phân biệt bằng rank BXH.

**Các thay đổi:**
1. Chạy `python migrate_add_bxh_rank.py` (migration đã có sẵn)
2. `routers/team.py` — thêm `bxh_rank: Optional[int] = None` vào `TeamMemberSchema` (đã có trong `database.py`)
3. `static/team.js` — sửa `fetchTeam()`: build `statsMap` theo rank (`statsMap[r.rank] = r`), lookup bằng `member.bxh_rank`
4. `static/team.js` — thêm `editMember(id)` function, update `saveMember()` để handle cả create và update
5. `static/team.html` — thêm input `member-rank` vào modal form

Chi tiết đầy đủ trong Brief_5_Team_Rank_Edit.md.

---

### Feature: Edit alias ở /tracker + Fix prize display (Brief 6)

**Mục đích:** PM muốn tự đặt alias cho user từ UI Tracker.

**Các thay đổi:**
1. `routers/team.py` — thêm endpoint `PUT /api/team-members/alias` (upsert alias vào team_members)
2. `routers/dashboard.py` — trong `get_tracker()`, override alias từ team_members lên rankings
3. `static/tracker.js` — thêm icon ✏️ vào cột alias, thêm `openAliasEdit()` + `saveAlias()` functions

Chi tiết đầy đủ trong Brief_6_Tracker_Alias_Edit_Prize_Fix.md.

---

## 6. THỨ TỰ IMPLEMENT ĐỀ NGHỊ

```
1. ✅ Fix Prize (Brief 7)          → DONE
2. Fix Duplicate Username (Brief 8) → 3 files + chạy refresh_stats.py
3. Team bxh_rank + Edit (Brief 5)  → DB migration + 2 files
4. Tracker Alias Edit (Brief 6)    → 3 files
```

Sau mỗi bước: **restart server, test UI, confirm với PM trước khi sang bước tiếp theo.**

---

## 7. QUY TRÌNH IMPORT DATA HÀNG NGÀY

1. Lấy JSON từ BXH ARO lúc 12:00 trưa GMT+7
2. Vào http://localhost:8000 → bấm **Import BXH**
3. Chọn ngày, paste JSON, bấm **Parse & Preview**
4. Kiểm tra preview (số user = 100, top 5 đúng)
5. Bấm **Confirm Import**
6. Nếu ngày hôm đó BXH bị delay → tick checkbox "Đánh dấu có delay"

---

## 8. CÁC FILE QUAN TRỌNG ĐỂ ĐỌC THÊM

| File | Mục đích |
|------|----------|
| `ARO_context.md` | Cơ chế jade, milestone, prize pool, team roster, W.Rate |
| `ARO_Tracker_App_Spec.md` | Spec đầy đủ ban đầu của app |
| `Brief_5_Team_Rank_Edit.md` | Spec đầy đủ cho tính năng team edit |
| `Brief_6_Tracker_Alias_Edit_Prize_Fix.md` | Spec đầy đủ cho alias edit |
| `Brief_7_Prize_Bug_Fix.md` | Root cause + fix prize |
| `Brief_8_Duplicate_Username_Fix.md` | Root cause + fix delta/W.Rate |

---

## 9. VERIFY SAU KHI IMPLEMENT

Sau khi implement Brief 7 và 8, chạy:

```python
# Paste vào python shell từ thư mục project:
import sqlite3
con = sqlite3.connect('data/aro_tracker.db')
cur = con.cursor()
cur.execute('SELECT id, date FROM snapshots ORDER BY date DESC LIMIT 1')
snap = cur.fetchone()
snap_id = snap[0]
print(f"Snapshot: {snap[1]}")

# Check prize nau***
cur.execute("SELECT rank, alias, prize_est FROM rankings WHERE snapshot_id=? AND alias LIKE 'nau%'", (snap_id,))
print("nau***:", cur.fetchone())  # Phải là rank=1, prize=$5,000

# Check delta mal[1]*** và mal[2]***
cur.execute("SELECT alias, delta, w_rate FROM rankings WHERE snapshot_id=? AND alias LIKE 'mal%' ORDER BY rank", (snap_id,))
for r in cur.fetchall():
    print(f"  {r[0]}: delta={r[1]}, w_rate={round(r[2] or 0)}")
# mal[1]*** delta phải ~+17K (không phải -500K)
con.close()
```

---

*Mọi câu hỏi về spec và priority: hỏi PM Adam trực tiếp.*  
*Mọi bug mới phát sinh: report cho PM, không tự sửa ngoài scope brief.*
