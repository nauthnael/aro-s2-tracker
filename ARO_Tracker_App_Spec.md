# ARO Sprint 2 Tracker — Project Spec v1.0
> PM: Adam | Dev: atigravity (AG) | Date: 01/05/2026  
> Target: Done hôm nay, deploy local + accessible qua browser

---

## 1. TÓM TẮT DỰ ÁN

Xây dựng một **web app** thay thế hoàn toàn workflow Excel + Python script hiện tại.  
Mỗi ngày Adam paste JSON từ BXH ARO vào app → app tự parse, lưu DB, tính toán, hiển thị dashboard.

**Vấn đề hiện tại cần giải quyết:**
- Excel cồng kềnh, phải nhập tay nhiều bước
- Cần chạy script Python riêng để tính W.Rate, dự báo, xuất báo cáo
- Không có dashboard trực quan, không xem được trend theo thời gian

---

## 2. TECH STACK ĐỀ XUẤT

| Layer | Công nghệ | Lý do |
|-------|-----------|-------|
| **Backend** | **Python + FastAPI** | AG quen Python, codebase hiện tại đã có Python scripts xử lý ARO data. Tái dụng logic tính W.Rate, parse JSON ngay. |
| **Database** | **SQLite** | File-based, zero config, đủ mạnh cho ~100 users × 60 ngày. Không cần cài MySQL/Postgres. File DB nằm trong project folder. |
| **Frontend** | **Vanilla JS + HTML/CSS** (hoặc Vue 3 CDN) | Không cần build step, AG chạy ngay. Chart.js cho biểu đồ. |
| **Server** | FastAPI uvicorn, chạy `localhost:8000` | Truy cập từ bất kỳ thiết bị cùng mạng LAN (kể cả điện thoại). |

**Không cần:** Docker, NPM build, deployment phức tạp.  
**Chạy bằng:** `python main.py` → mở `http://localhost:8000`

---

## 3. CẤU TRÚC DATABASE

### Bảng `snapshots` — Mỗi ngày 1 lần import
```sql
CREATE TABLE snapshots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        DATE NOT NULL UNIQUE,   -- '2026-04-28'
    is_delayed  BOOLEAN DEFAULT FALSE,  -- BXH bị delay hôm đó
    note        TEXT,                   -- ghi chú tự do
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Bảng `rankings` — 1 dòng = 1 user 1 ngày
```sql
CREATE TABLE rankings (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id  INTEGER REFERENCES snapshots(id),
    rank         INTEGER,
    username     TEXT,       -- email gốc từ BXH, ví dụ "nau***@gmail.com"
    alias        TEXT,       -- alias xử lý trùng tên, ví dụ "qua[T]***"
    jade         INTEGER,
    t1_refs      INTEGER,
    t2_refs      INTEGER,
    delta        INTEGER,    -- jade hôm nay - hôm qua (NULL nếu ngày đầu tiên)
    w_rate       REAL,       -- weighted rate tính tại ngày này
    proj_may31   INTEGER,    -- dự báo jade ngày 31/05
    prize_est    TEXT,       -- "$5,000", "$2,000", etc.
    is_team      BOOLEAN DEFAULT FALSE,
    team_role    TEXT        -- "LEADER", "T1", "T2"
);
```

### Bảng `team_members` — Roster team nau***
```sql
CREATE TABLE team_members (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    username    TEXT UNIQUE,
    alias       TEXT,
    role        TEXT,        -- "LEADER", "T1", "T2"
    join_date   DATE,
    note        TEXT         -- ghi chú trùng tên, cảnh báo, etc.
);
```

### Bảng `alerts` — Cảnh báo tự động
```sql
CREATE TABLE alerts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER REFERENCES snapshots(id),
    level       TEXT,        -- "RED", "YELLOW", "INFO"
    message     TEXT,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## 4. API ENDPOINTS (FastAPI)

### Import Data
| Method | Path | Mô tả |
|--------|------|-------|
| `POST` | `/api/import` | Nhận JSON BXH, parse, lưu DB, trả về summary |
| `GET`  | `/api/snapshots` | Danh sách các ngày đã import |
| `DELETE` | `/api/snapshots/{date}` | Xóa 1 ngày nếu nhập sai |

### Dashboard & Stats
| Method | Path | Mô tả |
|--------|------|-------|
| `GET` | `/api/dashboard` | Tổng hợp ngày mới nhất: top10, team, alerts |
| `GET` | `/api/users/{username}/history` | Lịch sử jade + rank theo ngày |
| `GET` | `/api/top10` | Top 10 BXH ngày mới nhất |
| `GET` | `/api/team` | Team nau*** — jade, delta, proj, prize |
| `GET` | `/api/alerts` | Cảnh báo mới nhất |

### Quản lý Team
| Method | Path | Mô tả |
|--------|------|-------|
| `GET`  | `/api/team-members` | Danh sách roster |
| `POST` | `/api/team-members` | Thêm thành viên mới |
| `PUT`  | `/api/team-members/{id}` | Cập nhật alias, role, note |
| `DELETE` | `/api/team-members/{id}` | Xóa thành viên |

### Export
| Method | Path | Mô tả |
|--------|------|-------|
| `GET` | `/api/export/report/{date}` | Xuất báo cáo markdown ngày đó |
| `GET` | `/api/export/csv` | Export toàn bộ data ra CSV |

---

## 5. TÍNH NĂNG & UI SCREENS

### Screen 1: Dashboard (Trang chủ)
**URL:** `/`

Layout 3 khu vực:
- **Header**: Ngày cập nhật mới nhất | Nút "Import BXH hôm nay" | Cảnh báo nếu có
- **Khu A — nau*** Status Card**:
  - Rank hiện tại | Jade | Delta hôm nay | W.Rate | Dự báo 31/05 | Prize dự kiến
  - Gap vs #2 (thu hẹp hay nới rộng?)
- **Khu B — Top 10 Table**:
  - Cột: Rank | User | Jade | Δ hôm nay | W.Rate | T1+T2 | Verdict (Farm/Thật)
  - Highlight nau*** = xanh đậm, team = xanh nhạt
- **Khu C — Alerts Panel**:
  - Danh sách cảnh báo 🔴🟡ℹ️ theo mức độ

### Screen 2: Import BXH
**URL:** `/import` hoặc Modal overlay

- Textarea lớn: "Paste JSON từ BXH ARO vào đây"
- Checkbox: "⚠️ Đánh dấu ngày này có delay"
- Ghi chú tùy ý
- Nút "Parse & Preview" → hiện preview 5 dòng đầu để xác nhận
- Nút "Confirm Import" → lưu DB
- Sau import: redirect về Dashboard, hiển thị summary "✅ Đã import 100 users, 28/04/2026"

### Screen 3: Team Dashboard
**URL:** `/team`

- Bảng team members: Alias | Role | Rank | Jade | Δ | W.Rate | Proj 31/05 | Prize | Status
- Badge trạng thái: 🟢 Active / 🟡 Chưa lên BXH / 🔴 Rate giảm bất thường
- Nút "Quản lý Team" → CRUD thành viên

### Screen 4: Biểu đồ Lịch sử
**URL:** `/charts`

- **Chart 1**: Line chart — Jade theo ngày (top 5 users, có thể toggle on/off từng user)
- **Chart 2**: Line chart — Rank theo ngày (nau*** + đối thủ chính)
- **Chart 3**: Bar chart — Delta hàng ngày của nau***
- **Chart 4**: Line chart — Gap nau*** vs #2 theo ngày
- Dùng **Chart.js** (CDN, không cần install)

### Screen 5: User Detail
**URL:** `/users/:username`

- Thông tin summary: username, alias, team role
- Bảng lịch sử 18+ ngày: ngày | rank | jade | delta | w.rate
- Mini line chart jade theo ngày
- Verdict: Farm / Thật / Team (với lý do)

---

## 6. LOGIC NGHIỆP VỤ (Business Logic)

AG cần implement các hàm sau (có thể tái dùng từ scripts Python hiện tại):

### 6.1 Parse JSON BXH
```python
# Input: JSON string từ ARO leaderboard
# Format: [{"#":"1","username":"nau***@gmail.com","jades earned from campaign":"800.84K","referral count":"46 (19 Tier 1 + 27 Tier 2)"}]
# Xử lý:
# - Lọc bỏ dòng separator ({"#":"s",...})
# - Convert jade "800.84K" → 800840
# - Parse refs "46 (19 Tier 1 + 27 Tier 2)" → t1=19, t2=27
# - Xử lý trùng tên: đọc bảng team_members để assign alias đúng
```

### 6.2 Tính Delta
```python
delta = jade_today - jade_yesterday
# Nếu user mới xuất hiện: delta = NULL (không phải 0)
# Nếu BXH delay: ghi chú, không dùng delta này để tính W.Rate
```

### 6.3 Tính W.Rate (Weighted Rate)
```python
# Lấy 18 ngày gần nhất của user
# weight[0] = 15 (mới nhất), weight[1] = 14, ..., weight[17] = 1 (xa nhất)  
# Nếu ngày i bị đánh dấu is_delayed=True: weight[i] = 2 (thay vì theo thứ tự)
# W.Rate = sum(delta[i] * weight[i]) / sum(weight[i])
# Chỉ tính trên các ngày có delta hợp lệ (không NULL)
```

### 6.4 Dự báo 31/05
```python
days_left = (date(2026, 5, 31) - today).days
proj_may31 = jade_today + w_rate * days_left
```

### 6.5 Prize Estimation
```python
# Dựa trên projected rank (so sánh proj_may31 của tất cả users)
prizes = {1: 5000, 2: 2000, 3: 2000, 4: 2000, 5: 2000,
          6: 1000, 7: 1000, 8: 1000, 9: 1000, 10: 1000}
# rank 11-50: $200, rank 51-100: $50
```

### 6.6 Auto Alerts
Sau mỗi lần import, tự động kiểm tra và tạo alerts:

| Điều kiện | Level | Message |
|-----------|-------|---------|
| nau*** delta < 70% W.Rate | RED | "⚠️ Rate nau*** giảm bất thường hôm nay" |
| Gap nau*** vs #2 < 100K | YELLOW | "🟡 [User] đang thu hẹp gap, còn [X] jade" |
| Team member delta = 0 lần 2 | RED | "🔴 [Alias] rate = 0 hai ngày liên tiếp" |
| Ngưỡng #50 tăng > 2000/ngày | YELLOW | "🟡 Ngưỡng top50 hôm nay: [X] jade (+[Y])" |
| User mới có T1 > 100 | INFO | "ℹ️ [User] xuất hiện với [N] T1 refs" |
| Toàn bộ top10 delta < 20% bình thường | INFO | "ℹ️ BXH có thể delay hôm nay" |

### 6.7 Trùng Tên — Alias Rules
Đây là logic quan trọng, phải implement cẩn thận:

```python
# Khi parse user mới, lookup team_members table trước
# Nếu username match → dùng alias đã thiết lập
# Nếu username trùng với user đã có → compare jade để phân biệt

KNOWN_ALIASES = {
    # username_prefix: {jade_range: alias}
    "qua***": {"high": "qua[T]***", "low": "qua[F]***"},  # team vs farm
    "hun***": {"high": "hun[BXH]***", "low": "hun[mới]***"},
    "tra***": {"first": "tra[1]***", "second": "tra[2]***"},
    "mal***": {"top": "mal[1]***", "other": "mal[2]***"},
    "kha***": {"28T1": "kha[28T1]***", "2T1": "kha[2T1]***"},
}
```

---

## 7. CẤU TRÚC PROJECT

```
aro-tracker/
├── main.py              # FastAPI app entry point
├── database.py          # SQLite setup, models
├── routers/
│   ├── import_data.py   # POST /api/import
│   ├── dashboard.py     # GET /api/dashboard, top10, team
│   ├── users.py         # user history, detail
│   ├── team.py          # team CRUD
│   └── export.py        # markdown, CSV export
├── services/
│   ├── parser.py        # Parse JSON BXH
│   ├── calculator.py    # W.Rate, delta, proj, prize
│   ├── alerts.py        # Auto alert generation
│   └── alias_resolver.py # Xử lý trùng tên
├── static/
│   ├── index.html       # Dashboard (Screen 1)
│   ├── import.html      # Import screen (Screen 2)
│   ├── team.html        # Team dashboard (Screen 3)
│   ├── charts.html      # Charts (Screen 4)
│   ├── user.html        # User detail (Screen 5)
│   ├── app.js           # Shared JS logic
│   └── style.css        # Styling
├── data/
│   └── aro_tracker.db   # SQLite database (auto-created)
├── requirements.txt
└── README.md
```

---

## 8. TASK BREAKDOWN CHO AG

Ước tính 1 ngày làm việc (~8h). Thứ tự ưu tiên:

### Phase 1 — Core Backend (3h)
- [ ] **Task 1** (30'): Setup FastAPI project, SQLite, tạo tables
- [ ] **Task 2** (45'): Viết `parser.py` — parse JSON ARO → objects Python
- [ ] **Task 3** (30'): Viết `calculator.py` — delta, W.Rate, proj, prize
- [ ] **Task 4** (30'): Viết `alias_resolver.py` — xử lý trùng tên
- [ ] **Task 5** (45'): `POST /api/import` — nhận JSON, gọi parser, lưu DB
- [ ] **Task 6** (30'): `GET /api/dashboard` + `GET /api/top10` + `GET /api/team`

### Phase 2 — Frontend MVP (2.5h)
- [ ] **Task 7** (45'): Dashboard HTML — nau*** card, top10 table, alerts
- [ ] **Task 8** (30'): Import page — textarea paste JSON, preview, confirm
- [ ] **Task 9** (45'): Team dashboard page
- [ ] **Task 10** (30'): CSS styling — highlight màu, responsive basic

### Phase 3 — Charts & Polish (1.5h)
- [ ] **Task 11** (45'): Charts page — Chart.js, jade trend, rank trend
- [ ] **Task 12** (30'): User detail page — history table + mini chart
- [ ] **Task 13** (15'): `GET /api/export/report` — trả về markdown báo cáo

### Phase 4 — Migration & Testing (1h)
- [ ] **Task 14** (30'): Import data từ Excel hiện tại (`ARO_Sprint2_v24_28Apr.xlsx`) → DB
- [ ] **Task 15** (30'): Test toàn bộ flow, fix bugs

---

## 9. REQUIREMENTS.TXT

```
fastapi>=0.110.0
uvicorn[standard]>=0.27.0
python-multipart>=0.0.9
aiofiles>=23.2.1
```

Chạy bằng:
```bash
pip install -r requirements.txt
python main.py
# → App chạy tại http://localhost:8000
```

---

## 10. DATA MIGRATION TỪ EXCEL

Để không mất dữ liệu 18 ngày hiện có, AG cần viết 1 script migration:

```python
# migrate_excel.py
# Đọc ARO_Sprint2_v24_28Apr.xlsx
# Sheet "📊 Master Tracker": parse từng cột ngày
# Insert vào bảng snapshots + rankings
# Chạy 1 lần duy nhất
```

---

## 11. CÁC QUY TẮC QUAN TRỌNG CẦN NHỚ

AG đọc thêm `ARO_context.md` để nắm các rule sau:

1. **Node bản thân KHÔNG tính jade BXH** — chỉ refs T1/T2 mới tính
2. **Milestone Bonus là one-time, cộng dồn** — xem bảng milestone trong context
3. **Delay handling** — nếu `is_delayed=True`, weight = 2 thay vì mặc định trong W.Rate
4. **Alias nhất quán** — luôn dùng alias đã thiết lập, không tạo alias mới tùy tiện
5. **Ngưỡng quan trọng** — #50 và #100 cần monitor riêng

---

## 12. ĐỊNH NGHĨA DONE

App được coi là **done** khi:
- [ ] Adam paste JSON → bấm import → data hiện trên dashboard trong < 3 giây
- [ ] Dashboard hiển thị đúng: rank, jade, delta, W.Rate, proj 31/05 cho nau***
- [ ] Alerts tự động xuất hiện nếu có bất thường
- [ ] Biểu đồ jade trend top 5 load được
- [ ] Data 18 ngày cũ từ Excel đã được migrate vào DB
- [ ] Chạy được từ điện thoại cùng mạng WiFi (LAN access)

---

*Spec này do Adam (PM) soạn. Mọi thắc mắc về nghiệp vụ hỏi Adam, mọi thắc mắc về tech AG tự quyết.*
