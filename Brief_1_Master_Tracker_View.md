# Brief 1 — Master Tracker View (`/tracker`)
> PM: Adam | Dev: atigravity | Priority: P0 — làm trước  
> Context: Thay thế hoàn toàn sheet "📊 Master Tracker" trong file Excel hiện tại

---

## 1. MỤC TIÊU

Tạo một màn hình mới `/tracker` hiển thị **toàn bộ 100 users × tất cả ngày đã import** dưới dạng bảng pivot — giống hệt sheet Excel nhưng trong browser, không cần mở file.

Đây là tính năng **cốt lõi nhất** thay thế workflow Excel hằng ngày.

---

## 2. API CẦN THÊM

### `GET /api/tracker`

Trả về toàn bộ data dưới dạng matrix để frontend render pivot table.

**Response shape:**
```json
{
  "dates": ["2026-04-10", "2026-04-11", ..., "2026-04-29"],
  "users": [
    {
      "username": "nau***@gmail.com",
      "alias": "nau***",
      "is_team": true,
      "team_role": "LEADER",
      "current_rank": 1,
      "current_jade": 850000,
      "w_rate": 51280,
      "proj_may31": 2493000,
      "prize_est": "$5,000",
      "history": {
        "2026-04-10": { "rank": 3, "jade": 320000, "delta": null, "is_delayed": false },
        "2026-04-11": { "rank": 2, "jade": 365000, "delta": 45000, "is_delayed": false },
        ...
      }
    },
    ...
  ]
}
```

**Sắp xếp users:** theo `current_rank` tăng dần (rank hôm nay).  
**Lưu ý:** user chưa xuất hiện ngày đó → `history[date] = null`.

**File cần sửa:** `routers/dashboard.py` — thêm endpoint `/api/tracker`.

```python
@router.get("/tracker")
async def get_tracker(db: Session = Depends(get_db)):
    # 1. Lấy tất cả snapshots, sort by date asc
    snapshots = db.query(Snapshot).order_by(Snapshot.date).all()
    dates = [str(s.date) for s in snapshots]
    snapshot_map = {s.id: str(s.date) for s in snapshots}
    delayed_map = {s.id: s.is_delayed for s in snapshots}

    # 2. Lấy tất cả rankings
    all_rankings = db.query(Ranking).all()

    # 3. Build user dict: username → {meta, history}
    # 4. Lấy current_rank từ snapshot mới nhất
    # 5. Sort by current_rank
    # 6. Return
```

---

## 3. FRONTEND — `static/tracker.html`

### 3.1 Layout tổng thể

```
┌─────────────────────────────────────────────────────────────────┐
│  HEADER: Nav + "Import BXH" button                              │
├─────────────────────────────────────────────────────────────────┤
│  TOOLBAR: [Mode toggle] [Search] [Filter: All/Team/Top10]       │
├────────┬────────────────┬──────────────────────────────────────┤
│ FROZEN │  FROZEN cols   │  SCROLLABLE: ngày 1 | ngày 2 | ... │
│ Rank   │  Alias | W.Rate│  jade/Δ/rank per day                │
│        │  Proj | Prize  │                                      │
│   1    │  nau***  51K   │  800K  | 760K  | 720K | ...         │
│   2    │  pha***  54K   │  660K  | 606K  | 550K | ...         │
└────────┴────────────────┴──────────────────────────────────────┘
```

### 3.2 Cột FROZEN (luôn hiển thị, không scroll ngang)

| Cột | Nội dung | Width |
|-----|----------|-------|
| Rank | Rank hôm nay | 60px |
| Alias | Username display | 130px |
| W.Rate | Weighted rate | 80px |
| Proj 31/05 | Jade dự báo | 100px |
| Prize | $5,000 etc | 70px |

### 3.3 Cột ngày (SCROLLABLE, mỗi ngày 1 cột)

Header cột: `28/04` (format DD/MM)  
Nếu ngày đó bị delayed: header có icon ⚠️ màu cam.

Mỗi ô trong cột ngày hiển thị theo **mode** đang chọn (xem 3.4).

### 3.4 Mode Toggle — 3 chế độ xem

Nút toggle ở toolbar, mặc định là **Jade**:

| Mode | Hiển thị trong ô | Format |
|------|-----------------|--------|
| **Jade** | Jade tuyệt đối | `800,840` |
| **Delta (Δ)** | Chênh lệch so hôm trước | `+45,000` (xanh) / `-1,200` (đỏ) / `—` (null) |
| **Rank** | Rank ngày đó | `#1` |

### 3.5 Màu sắc highlight rows

```css
/* nau*** leader */
.row-nau    { background: rgba(59, 130, 246, 0.20); }
/* team members */
.row-team   { background: rgba(16, 185, 129, 0.10); }
/* top 10 còn lại */
.row-top10  { background: rgba(255, 255, 255, 0.03); }
/* ngày delayed */
th.delayed  { color: #f97316; }  /* cam */
```

### 3.6 Màu giá trị trong ô

- Jade mode: trắng bình thường, ô trống (user chưa có) → `—` màu muted
- Delta mode:
  - `> 0` → xanh lá (`#10b981`)
  - `< 0` → đỏ (`#ef4444`)
  - `null` → `—` màu muted
- Rank mode: rank cải thiện (nhỏ hơn hôm qua) → xanh, tệ hơn → đỏ

### 3.7 Toolbar controls

```html
<!-- Mode toggle -->
<div class="toggle-group">
  <button class="active" data-mode="jade">Jade</button>
  <button data-mode="delta">Δ Delta</button>
  <button data-mode="rank">Rank</button>
</div>

<!-- Search -->
<input type="text" placeholder="Tìm user..." id="search-input">

<!-- Filter -->
<select id="filter-select">
  <option value="all">Tất cả (100)</option>
  <option value="top10">Top 10</option>
  <option value="team">Team nau***</option>
</select>
```

### 3.8 Sticky behavior

- Header row (chứa ngày) phải sticky khi scroll dọc: `position: sticky; top: 0`
- Các cột frozen phải sticky khi scroll ngang: `position: sticky; left: 0` (dùng CSS sticky cho multiple columns)

---

## 4. FILE CẦN TẠO / SỬA

| File | Hành động | Mô tả |
|------|-----------|-------|
| `routers/dashboard.py` | Thêm | endpoint `GET /api/tracker` |
| `static/tracker.html` | Tạo mới | HTML skeleton + toolbar |
| `static/tracker.js` | Tạo mới | Fetch API + render pivot table + mode toggle + search/filter |
| `static/style.css` | Sửa | Thêm CSS cho `.tracker-table`, `.frozen-col`, `.toggle-group` |
| `static/index.html` | Sửa | Thêm nav link "Tracker" |
| `static/team.html` | Sửa | Thêm nav link "Tracker" |
| `static/charts.html` | Sửa | Thêm nav link "Tracker" |

---

## 5. IMPLEMENTATION NOTES CHO AG

### CSS sticky multi-column (quan trọng)

Sticky nhiều cột đòi hỏi set `left` offset chính xác cho từng cột:

```css
.col-rank   { position: sticky; left: 0;     z-index: 2; background: var(--surface); }
.col-alias  { position: sticky; left: 60px;  z-index: 2; background: var(--surface); }
.col-wrate  { position: sticky; left: 190px; z-index: 2; background: var(--surface); }
.col-proj   { position: sticky; left: 270px; z-index: 2; background: var(--surface); }
.col-prize  { position: sticky; left: 370px; z-index: 2; background: var(--surface); }
/* Header sticky cả 2 chiều */
thead th { position: sticky; top: 0; z-index: 3; }
thead th.frozen { z-index: 4; } /* frozen + header = highest z-index */
```

### Performance — render 100 rows × 20 cột

100 × 20 = 2,000 ô — không cần virtual scroll, render thẳng DOM là đủ.  
Nhưng dùng `DocumentFragment` để batch insert, tránh reflow nhiều lần:

```javascript
const fragment = document.createDocumentFragment();
users.forEach(user => {
    const tr = buildRow(user, dates, mode);
    fragment.appendChild(tr);
});
tbody.appendChild(fragment);
```

### Mode switch — không re-fetch API

Khi user click toggle Jade/Delta/Rank, **không gọi API lại**.  
Giữ `window.trackerData` trong memory, chỉ re-render tbody.

```javascript
let trackerData = null; // cache từ lần fetch đầu

async function loadTracker() {
    const res = await fetch('/api/tracker');
    trackerData = await res.json();
    renderTable(trackerData, currentMode);
}

function switchMode(mode) {
    currentMode = mode;
    renderTable(trackerData, mode); // dùng cached data
}
```

### Search/Filter

```javascript
function filterUsers(users, searchText, filterMode) {
    return users.filter(u => {
        const matchSearch = !searchText || 
            u.alias.toLowerCase().includes(searchText.toLowerCase());
        const matchFilter = filterMode === 'all' ||
            (filterMode === 'team' && u.is_team) ||
            (filterMode === 'top10' && u.current_rank <= 10);
        return matchSearch && matchFilter;
    });
}
```

---

## 6. ĐỊNH NGHĨA DONE

Brief này hoàn thành khi:

- [ ] Truy cập `http://localhost:8000/tracker` không lỗi
- [ ] Hiện đủ 100 users (hoặc bao nhiêu user có trong DB)
- [ ] Cột frozen (Rank, Alias, W.Rate, Proj, Prize) không di chuyển khi scroll ngang
- [ ] Header row không di chuyển khi scroll dọc
- [ ] 3 mode toggle hoạt động: Jade / Δ / Rank — không gọi API lại
- [ ] Search theo alias hoạt động real-time
- [ ] Filter All / Top 10 / Team hoạt động
- [ ] nau*** highlight xanh đậm, team members highlight xanh nhạt
- [ ] Ngày delayed hiện icon ⚠️ và màu cam trên header cột
- [ ] Nav link "Tracker" xuất hiện trên tất cả các trang

---

*Brief này do Adam (PM) soạn dựa trên yêu cầu: "dashboard hiển thị đủ top 100, và có lịch sử từng ngày theo cột, giống giao diện file Excel"*
