# ARO Sprint 2 Tracker — Claude Code Handoff
> Ngày viết: 2026-05-11 | Viết bởi: Claude (Cowork mode) → Chuyển giao cho Claude Code

---

## 1. TỔNG QUAN DỰ ÁN

Web app theo dõi bảng xếp hạng ARO Sprint 2 Testnet cho team nau***. PM (Adam) import BXH ARO mỗi ngày, app tính toán delta/W.Rate/projection và hiển thị dashboard.

- **Event:** ARO Sprint 2 Testnet, kết thúc 31/05/2026
- **Account chính theo dõi:** `nau***@gmail.com` (đang #1 BXH)
- **Stack:** FastAPI + SQLAlchemy + SQLite + Vanilla JS
- **Server:** chạy local trên Windows, `uvicorn main:app --port 8000`
- **DB:** `data/aro_tracker.db` (SQLite)
- **Data hiện tại:** 27 snapshots (10/04 → 07/05/2026), ~150 aliases trong tracker (trong đó ~51 ghost)

---

## 2. CẤU TRÚC PROJECT

```
project/
├── main.py                    # FastAPI app entry point
├── database.py                # SQLAlchemy models + DB init
├── requirements.txt
├── data/
│   └── aro_tracker.db         # SQLite DB (server đang dùng)
├── routers/
│   ├── dashboard.py           # GET /api/dashboard, /api/tracker, /api/aliases, charts
│   ├── import_data.py         # POST /api/import/import-raw, DELETE /api/import/snapshot/{id}
│   ├── team.py                # GET/POST /api/team-members, POST /api/team-members/set-team
│   └── users.py               # PUT /api/team-members/alias
├── services/
│   ├── alias_resolver.py      # Core alias logic — QUAN TRỌNG NHẤT
│   ├── parser.py              # Parse JSON/HTML từ BXH ARO
│   ├── calculator.py          # delta, w_rate, proj_may31, estimate_prize
│   └── alerts.py              # Generate alerts (RED/YELLOW/INFO)
└── static/
    ├── index.html + app.js    # Dashboard
    ├── tracker.html + tracker.js   # Tracker (bảng lịch sử tất cả users)
    ├── team.html + team.js    # Team page (read-only)
    ├── settings.html + settings.js # Settings — alias manager (mới nhất)
    ├── charts.html            # Charts
    └── style.css
```

---

## 3. DATABASE MODELS

```python
Snapshot: id, date, is_delayed, note, created_at
Ranking:  id, snapshot_id, rank, username, alias, jade, t1_refs, t2_refs,
          delta, w_rate, proj_may31, prize_est, is_team, team_role
TeamMember: id, username, alias, role, bxh_rank (deprecated), join_date, note
Alert:    id, snapshot_id, level (RED/YELLOW/INFO), message, created_at
```

---

## 4. KHÁI NIỆM QUAN TRỌNG

### Alias
- **Username** = masked email từ BXH ARO (vd: `nau***@gmail.com`) — có thể trùng giữa 2 người thật
- **Alias** = unique identity per person thật (vd: `mal[1]***`, `mal[2]***`)
- Alias là **key duy nhất** để track lịch sử 1 người qua nhiều ngày
- Default alias: strip `@gmail.com` → `nau***@gmail.com` thành `nau***`
- **TeamMember alias KHÔNG có @gmail.com** — đây là constraint quan trọng

### Alias Resolution (3 tầng)
```
Tầng 1: TeamMember lookup (username exact match) → alias từ TeamMember table
Tầng 2: KNOWN_ALIASES — lambda(jade, rank) cho duplicate usernames đã biết
Tầng 3: Default strip @gmail.com
```

### KNOWN_ALIASES (8 usernames đã biết là duplicate)
```python
"mal***@gmail.com": j > 400K → "mal[1]***" else "mal[2]***"
"tra***@gmail.com": j > 300K → "tra[1]***", j > 50K → "tra[2]***", else "tra[3]***"
"qua***@gmail.com": j > 25K → "qua[T2]***" else "qua[farm]***"
"kha***@gmail.com": j > 200K → "kha[1]***" else "kha[2]***"
"rom***@gmail.com": j > 100K → "rom[1]***", j > 30K → "rom[2]***", else "rom[3]***"
"ben***@gmail.com": j > 80K → "ben[1]***", j > 30K → "ben[2]***", else "ben[3]***"
"hun***@gmail.com": rank < 50 → "hun[BXH]***" else "hun[moi]***"
"thu***@gmail.com": j > 200K → "thu[1]***" else "thu[2]***"
```

### Sequential Matching
Khi import ngày mới, nếu 1 username xuất hiện N lần → greedy cost matching với N records cùng username ngày hôm trước. Cost = `|delta_jade| + |delta_refs|*1000`.

### W.Rate
Weighted average delta, weights 15→1 mới→cũ, delayed snapshot weight=2.

### Prize
Ước tính theo projected rank tại 31/05 (không phải rank hiện tại):
- #1: $5,000 | #2: $3,000 | #3: $2,000 | #4-5: $1,000 | #6-10: $500 | #11-20: $200 | #21-50: $50

---

## 5. BRIEFS ĐÃ IMPLEMENT (Brief 1-24)

| Brief | Nội dung | Trạng thái |
|-------|----------|------------|
| 1-9 | Tính năng cơ bản: tracker, charts, team, alias edit, prize | ✅ Done |
| 10 | T1/T2 refs tab trên Dashboard | ✅ Done |
| 11 | HTML import (parse table từ ARO website) | ✅ Done |
| 12 | Team stats + rank lookup | ✅ Done |
| 13 | Thu alias + hun team fix | ✅ Done |
| 14 | Team page: STT column, sort, prize banner | ✅ Done |
| 15 | team.js rewrite (file bị truncate) | ✅ Done |
| 16 | **Alias Disambiguation Overhaul**: sequential matching, KNOWN_ALIASES với `lambda j, r:` | ✅ Done |
| 17 | Team từ Tracker: checkbox UI, `/team` read-only, `POST /api/team-members/set-team` với backfill | ✅ Done |
| 18 | Fix `get_tracker()` key by alias (thay vì username) | ✅ Done |
| 19 | Delete snapshot API + UI (nút Xóa trong Import Modal) | ✅ Done |
| 20 | Fix default alias strip `@gmail.com` | ✅ Done |
| 21 | Alert date, patch alias 05/05, patch TeamMember alias format | ✅ Done |
| 22 | Fix `get_team_with_stats()` lookup by alias (không phải username) | ✅ Done |
| 23 | **CHƯA IMPLEMENT** — Fix sequential match kế thừa alias sai | ⏳ Pending |
| 24 | **CHƯA IMPLEMENT** — Trang /settings alias manager + xóa ghost aliases | ⏳ Pending |

---

## 6. BUGS PENDING (CẦN FIX TRƯỚC TIÊN)

### Bug 1 — Brief 23: Sequential match kế thừa alias sai (P0)

**File:** `routers/import_data.py`, hàm `_process_import()`, khoảng dòng 96-116

**Vấn đề:** Khi sequential match tìm được prev record, nó kế thừa alias cũ vô điều kiện. Nếu alias cũ sai (ví dụ `qua[TEAM]***` từ import lỗi trước), alias sai lan truyền sang ngày mới mãi mãi.

**Triệu chứng hiện tại:** `qua***@gmail.com` rank 39, jade 44,490 đang hiển thị alias `qua[TEAM]***` thay vì `qua[T2]***` (vì j > 25K).

**Fix cần làm:**
```python
# Trong vòng lặp match_results, sau khi lấy matched_alias từ prev_rec:
# THÊM re-validation bằng KNOWN_ALIASES:
from services.alias_resolver import KNOWN_ALIASES
if username in KNOWN_ALIASES:
    matched_alias = KNOWN_ALIASES[username](new_item['jade'], new_item['rank'])
```

Cũng cần update import ở đầu file:
```python
from services.alias_resolver import resolve_alias, sequential_match, KNOWN_ALIASES
```

### Bug 2 — Brief 24: Ghost aliases + trang Settings (P1)

**Vấn đề:** ~51 aliases có jade=0 mọi ngày tồn tại trong DB, làm Tracker hiển thị 150 users thay vì ~99-105.

**Fix cần làm:**
1. Thêm `GET /api/aliases` và `DELETE /api/aliases/ghost` vào `routers/dashboard.py`
2. Tạo `static/settings.html` và `static/settings.js`
3. Thêm link Settings vào nav tất cả trang

Chi tiết đầy đủ trong `Brief_24_Settings_Alias_Manager.md`.

---

## 7. WORKFLOW HÀNG NGÀY CỦA PM

1. Vào `http://localhost:8000/` → click **Import BXH**
2. Paste HTML source của bảng BXH ARO (Ctrl+U → Ctrl+A → Ctrl+C từ ARO website)
3. Chọn đúng ngày → Parse & Preview → kiểm tra top 5 và các rank có duplicate username
4. Confirm Import
5. Kiểm tra Dashboard: delta, W.Rate, Cảnh Báo
6. Nếu thấy alias sai → vào Tracker → click ✏️ để sửa alias thủ công

---

## 8. KNOWN ISSUES / CẦN CHÚ Ý

### File truncation
AG (developer cũ) có pattern ghi file không hoàn chỉnh. Khi sửa file, luôn verify bằng:
```python
python3 -c "
with open('file.py','rb') as f: d=f.read()
print(len(d), 'bytes', '| ends with newline:', d.endswith(b'\n'))
"
```

### DB path
Server chạy từ thư mục project trên Windows, DB nằm ở `data/aro_tracker.db` (relative path). Không phải file nào trong mount sandbox cũng reflect đúng — dùng API để query khi cần.

### alias_resolver.py — file bị restore
File hiện tại đã được Cowork restore đầy đủ (4,787 bytes). Nếu thấy file nhỏ hơn nhiều, cần ghi lại từ spec.

### TeamMember alias format
TeamMember.alias **không có** `@gmail.com`. Nếu thấy alias dạng `xxx***@gmail.com` trong TeamMember → chạy `patch_team_alias.py`.

### Sequential matching gotcha
Với N người cùng username, code chỉ chạy sequential match khi `len(prev_records) == len(items)`. Nếu số lượng không khớp → fallback Tầng 2/3. Đây là behavior đúng.

---

## 9. API ENDPOINTS CHÍNH

```
GET  /api/dashboard          → snapshot, nau stats, top100, alerts
GET  /api/tracker            → {dates, snapshots, users[]} với full history
GET  /api/team-members       → list TeamMember
GET  /api/team-members/with-stats → TeamMember + latest ranking stats (lookup by alias)
POST /api/team-members/set-team  → add/remove/change role + backfill all rankings by alias
PUT  /api/team-members/alias     → sửa alias 1 user (update TeamMember + all rankings)
GET  /api/import/snapshots   → list tất cả snapshots
DELETE /api/import/snapshot/{id} → xóa 1 snapshot (không cho xóa nếu chỉ còn 1)
POST /api/import/import-raw  → import BXH (JSON hoặc HTML)
POST /api/import/preview-raw → preview trước khi import
GET  /api/aliases            → [Brief 24 — chưa implement] alias summary
DELETE /api/aliases/ghost    → [Brief 24 — chưa implement] xóa ghost aliases
```

---

## 10. CÁCH VIẾT BRIEF (QUY TRÌNH LÀM VIỆC)

PM không code trực tiếp. Workflow:
1. **Claude phân tích** lỗi/yêu cầu → đọc source code → xác định root cause
2. **Claude viết Brief** (file Markdown trong thư mục project) với spec code cụ thể, đủ chi tiết để AG implement
3. **AG implement** theo brief → tạo `Review_Report_Brief_X.md` sau khi xong
4. **PM verify** trên browser → báo lỗi nếu còn → Claude viết brief tiếp

Brief format chuẩn:
- Root cause rõ ràng với code snippet hiện tại vs code cần sửa
- Thứ tự thực hiện (numbered steps)
- Verify checklist (checkbox)
- Yêu cầu Review_Report sau khi done

---

## 11. CONTEXT ĐẶC BIỆT

- **`qua[TEAM]`** trong BXH ARO là username thật của 1 người (không phải alias do app gán). App đã từng nhầm lẫn giữa alias nội bộ và username ARO.
- **`hun[TEAM]***@gmail.com`** là username thật trên ARO (người này đặt username kiểu đó). Khi parse BXH, đây là username thô, không phải alias.
- **Delay days**: BXH ARO đôi khi không update (cuối tuần, maintenance). Delta=0 cho toàn bộ là bình thường, không phải bug.
- **Prize pool**: $13,500 tổng (xem `services/calculator.py → estimate_prize()`).
