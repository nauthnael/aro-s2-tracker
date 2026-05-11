# Brief 2 — Charts + Dashboard Fixes
> PM: Adam | Dev: atigravity | Priority: P1 — sau khi Brief 1 xong  
> Context: Fix 4 vấn đề còn tồn đọng sau lần build đầu

---

## 1. TỔNG QUAN

Brief này gồm 4 fix độc lập, AG có thể làm theo thứ tự hoặc song song:

| # | Fix | Impact | Effort |
|---|-----|--------|--------|
| A | Charts.html — implement thực sự | Cao | ~2h |
| B | Dashboard top 10 → top 100 | Trung bình | ~30' |
| C | Prize logic dùng projected rank | Trung bình | ~30' |
| D | Import — thêm bước Preview | Trung bình | ~45' |

---

## 2. FIX A — Charts.html

### Vấn đề

`charts.html` hiện chỉ có 2 `<canvas>` trống với comment `"Charts implementation would go here"`. Không có chart nào thực sự hoạt động.

### API cần thêm

#### `GET /api/charts/jade-history?usernames=nau,pha,mal,sdt,cry&limit=5`

Trả về lịch sử jade cho một số users cụ thể, dùng cho Chart 1 và Chart 2.

```json
{
  "dates": ["2026-04-10", "2026-04-11", ..., "2026-04-29"],
  "series": [
    {
      "username": "nau***@gmail.com",
      "alias": "nau***",
      "color": "#3b82f6",
      "jade_history": [320000, 365000, ..., 850000],
      "rank_history": [3, 2, ..., 1]
    },
    ...
  ]
}
```

Nếu không truyền `usernames`, trả về top 5 users hiện tại theo jade.

**File sửa:** Thêm vào `routers/dashboard.py`.

#### `GET /api/charts/nau-daily`

Trả về delta hằng ngày + gap vs #2 của nau***, dùng cho Chart 3 và Chart 4.

```json
{
  "dates": ["2026-04-10", ..., "2026-04-29"],
  "nau_delta": [null, 45000, 38000, ..., 63340],
  "gap_vs_2": [null, null, ..., 140650],
  "w_rate_line": [null, null, ..., 51280]
}
```

**File sửa:** Thêm vào `routers/dashboard.py`.

### Frontend — 4 charts thực sự

**File sửa:** `static/charts.html` — xóa placeholder comment, implement Chart.js đầy đủ.

#### Chart 1 — Jade Trend (Top 5)

```javascript
// Line chart: x = ngày, y = jade
// Mỗi user 1 line với màu riêng
// Tooltip hiện: alias, jade, rank ngày đó
// Legend có thể click để toggle từng user
const COLORS = ['#3b82f6', '#f59e0b', '#10b981', '#8b5cf6', '#ef4444'];
```

#### Chart 2 — Rank Trend

```javascript
// Line chart: x = ngày, y = rank
// Y-axis inverted (rank #1 ở trên cùng)
// options: { scales: { y: { reverse: true } } }
// Chỉ show: nau***, pha***, mal*** (top 3 đối thủ chính)
```

#### Chart 3 — nau*** Daily Delta (Bar chart)

```javascript
// Bar chart: x = ngày, y = delta jade hôm đó
// Bar màu xanh, ngày delayed màu cam
// Đường W.Rate dạng line overlay (type: 'line') trên cùng chart
// Dùng Chart.js mixed chart
```

#### Chart 4 — Gap vs #2

```javascript
// Line chart: x = ngày, y = jade gap (nau*** - #2)
// Fill area dưới đường (fill: true, backgroundColor: rgba xanh nhạt)
// Đường ngang threshold 100K màu đỏ đứt (warning line):
// { type: 'line', yMin: 100000, yMax: 100000, borderColor: '#ef4444', borderDash: [5,5] }
// Dùng plugin annotation của Chart.js
```

### User selector cho Chart 1 & 2

Thêm UI cho phép Adam chọn user muốn xem:

```html
<div class="user-selector">
  <span>Hiển thị:</span>
  <!-- Dynamically populated từ API -->
  <button class="chip active" data-username="nau***@gmail.com">nau***</button>
  <button class="chip active" data-username="pha***@gmail.com">pha***</button>
  <!-- ... top 5 mặc định -->
  <button class="chip-add" onclick="showUserPicker()">+ Thêm</button>
</div>
```

Khi click chip → toggle user đó on/off trên Chart 1 & 2. Không re-fetch API, dùng `chart.data.datasets[i].hidden = !hidden`.

---

## 3. FIX B — Dashboard Top 10 → Top 100

### Vấn đề

`dashboard.py` dòng 22: `limit(10)` hard-coded.  
`index.html` bảng chỉ có tiêu đề "Top 10 Leaderboard".

### Thay đổi cần làm

**File: `routers/dashboard.py`**

```python
# Dòng 22 — XÓA limit(10)
# TRƯỚC:
top10 = db.query(Ranking).filter(...).order_by(Ranking.rank).limit(10).all()

# SAU:
top_rankings = db.query(Ranking).filter(
    Ranking.snapshot_id == snapshot.id
).order_by(Ranking.rank).all()  # bỏ limit, lấy hết
```

**File: `static/index.html`**

```html
<!-- Đổi tiêu đề -->
<h2>Top 100 Leaderboard</h2>

<!-- Thêm search bar ngay dưới h2 -->
<div style="margin: 0.75rem 0;">
  <input type="text" id="leaderboard-search" 
    placeholder="🔍 Tìm user..." 
    oninput="filterLeaderboard(this.value)"
    style="width: 280px; padding: 0.4rem 0.75rem; background: var(--background); 
           color: white; border: 1px solid var(--surface); border-radius: 0.375rem;">
</div>

<!-- Thêm cột Verdict vào thead -->
<th>Verdict</th>
```

**File: `static/app.js`**

Thêm cột Verdict và search function:

```javascript
// Trong vòng lặp render rows — thêm Verdict badge
const verdict = getVerdict(user);
row.innerHTML = `
    <td>${user.rank}</td>
    <td>${user.alias || user.username}</td>
    <td>${formatNumber(user.jade)}</td>
    <td class="${(user.delta || 0) >= 0 ? 'positive' : 'negative'}">
        ${user.delta !== null ? (user.delta >= 0 ? '+' : '') + formatNumber(user.delta) : '—'}
    </td>
    <td>${user.w_rate !== null ? formatNumber(Math.round(user.w_rate)) : '—'}</td>
    <td>${user.t1_refs}+${user.t2_refs}</td>
    <td>${verdict}</td>
`;

function getVerdict(user) {
    if (user.is_team) return '<span class="badge badge-team">TEAM</span>';
    // Farm heuristic: nhiều T1 refs nhưng delta thấp bất thường
    const totalRefs = user.t1_refs + user.t2_refs;
    if (totalRefs > 50 && user.w_rate !== null && user.w_rate < 5000) {
        return '<span class="badge badge-red">Farm</span>';
    }
    return '<span class="badge badge-info">—</span>';
}

// Search filter
let allRankings = []; // cache toàn bộ list

function filterLeaderboard(searchText) {
    const filtered = allRankings.filter(u => 
        (u.alias || u.username).toLowerCase().includes(searchText.toLowerCase())
    );
    renderLeaderboardRows(filtered);
}
```

**`static/style.css`** — thêm:

```css
.badge-team { background: rgba(16, 185, 129, 0.2); color: #10b981; }
.positive   { color: #10b981; }
.negative   { color: #ef4444; }
```

---

## 4. FIX C — Prize Logic: Projected Rank

### Vấn đề

`import_data.py` dòng 70:
```python
prize = estimate_prize(item["rank"])  # Comment của AG: "prize might depend on projected rank"
```
Dùng rank **hôm nay** thay vì rank **dự báo 31/05** — sai spec.

### Thay đổi cần làm

Logic đúng: sau khi tính `proj_may31` cho tất cả users, so sánh cross-user để ra `projected_rank`, rồi mới tính prize.

**File: `routers/import_data.py`**

```python
# BƯỚC 6 hiện tại: tính proj_may31 cho từng user riêng lẻ ✓
# Thêm BƯỚC 6B sau khi có đủ rankings_to_save:

# 6B. Tính projected rank dựa trên proj_may31
# Sort theo proj_may31 desc → assign projected_rank → estimate_prize(projected_rank)
rankings_sorted_by_proj = sorted(
    [r for r in rankings_to_save if r.proj_may31 is not None],
    key=lambda r: r.proj_may31,
    reverse=True
)
for proj_rank, r in enumerate(rankings_sorted_by_proj, start=1):
    r.prize_est = estimate_prize(proj_rank)

# Users không có proj (null w_rate) → prize_est = "N/A"
for r in rankings_to_save:
    if r.proj_may31 is None:
        r.prize_est = "N/A"
```

**Lưu ý:** Cũng cần chạy lại `refresh_stats.py` để cập nhật prize cho 18 ngày data cũ sau khi fix.

---

## 5. FIX D — Import Preview Step

### Vấn đề

Spec yêu cầu "Parse & Preview trước khi Confirm" nhưng hiện tại bấm "Confirm Import" là import thẳng, không có bước xác nhận với preview data.

### Thay đổi cần làm

**Thêm API endpoint:** `POST /api/import/preview`

Endpoint này parse JSON nhưng **không lưu DB**, chỉ trả về summary để user xem trước.

```python
# routers/import_data.py — thêm endpoint mới

@router.post("/preview")
async def preview_import(
    json_data: List[dict] = Body(...),
    import_date: str = Body(...),
    db: Session = Depends(get_db)
):
    dt = datetime.strptime(import_date, "%Y-%m-%d").date()
    
    # Check duplicate
    existing = db.query(Snapshot).filter(Snapshot.date == dt).first()
    if existing:
        raise HTTPException(400, detail=f"Ngày {import_date} đã có dữ liệu.")
    
    # Parse only, không lưu
    parsed_items = parse_leaderboard_json(json_data)
    
    return {
        "date": import_date,
        "total_users": len(parsed_items),
        "preview_top5": parsed_items[:5],  # 5 dòng đầu
        "preview_bottom3": parsed_items[-3:],  # 3 dòng cuối
        "warning": "BXH có thể delay" if len(parsed_items) < 95 else None
    }
```

**File: `static/index.html`** — sửa Import Modal thành 2 bước:

```html
<!-- Bước 1: Input -->
<div id="import-step-1">
  <label>Ngày:</label>
  <input type="date" id="import-date">
  <textarea id="json-input" placeholder="Paste JSON từ BXH ARO vào đây..."></textarea>
  <label>
    <input type="checkbox" id="import-delayed"> ⚠️ Đánh dấu ngày này có delay
  </label>
  <div style="display: flex; gap: 1rem;">
    <button onclick="previewImport()" class="btn btn-primary" id="preview-btn">
      🔍 Parse & Preview
    </button>
    <button onclick="hideImportModal()" class="btn">Hủy</button>
  </div>
</div>

<!-- Bước 2: Preview (ẩn mặc định) -->
<div id="import-step-2" style="display: none;">
  <div id="import-preview-content"></div>
  <div style="display: flex; gap: 1rem; margin-top: 1rem;">
    <button onclick="confirmImport()" class="btn btn-primary" id="import-btn">
      ✅ Confirm Import
    </button>
    <button onclick="backToStep1()" class="btn">← Sửa lại</button>
  </div>
</div>
```

**File: `static/app.js`** — thêm flow:

```javascript
async function previewImport() {
    const date = document.getElementById('import-date').value;
    const jsonStr = document.getElementById('json-input').value;
    if (!date || !jsonStr) { alert("Vui lòng nhập đủ ngày và JSON"); return; }
    
    const btn = document.getElementById('preview-btn');
    btn.innerText = "Đang parse...";
    btn.disabled = true;
    
    try {
        const jsonData = JSON.parse(jsonStr);
        const res = await fetch('/api/import/preview', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ json_data: jsonData, import_date: date })
        });
        const preview = await res.json();
        if (!res.ok) { alert("Error: " + preview.detail); return; }
        
        // Render preview
        const content = document.getElementById('import-preview-content');
        content.innerHTML = `
            <div class="preview-summary">
                <h3>✅ Parse thành công</h3>
                <p>📅 Ngày: <strong>${preview.date}</strong></p>
                <p>👥 Tổng users: <strong>${preview.total_users}</strong></p>
                ${preview.warning ? `<p style="color:#f97316">⚠️ ${preview.warning}</p>` : ''}
            </div>
            <h4 style="margin-top:1rem">5 dòng đầu:</h4>
            <table>
                <thead><tr><th>Rank</th><th>Username</th><th>Jade</th><th>T1</th><th>T2</th></tr></thead>
                <tbody>
                    ${preview.preview_top5.map(u => `
                        <tr><td>${u.rank}</td><td>${u.username}</td>
                        <td>${formatNumber(u.jade)}</td>
                        <td>${u.t1_refs}</td><td>${u.t2_refs}</td></tr>
                    `).join('')}
                </tbody>
            </table>
        `;
        
        // Switch to step 2
        document.getElementById('import-step-1').style.display = 'none';
        document.getElementById('import-step-2').style.display = 'block';
        
    } catch(e) {
        alert("Invalid JSON format");
    } finally {
        btn.innerText = "🔍 Parse & Preview";
        btn.disabled = false;
    }
}

function backToStep1() {
    document.getElementById('import-step-1').style.display = 'block';
    document.getElementById('import-step-2').style.display = 'none';
}
```

---

## 6. TÓM TẮT FILE CẦN SỬA

| File | Fix | Ghi chú |
|------|-----|---------|
| `routers/dashboard.py` | A | Thêm 2 endpoints `/api/charts/jade-history` và `/api/charts/nau-daily` |
| `routers/import_data.py` | C, D | Fix prize logic + thêm `/api/import/preview` |
| `static/charts.html` | A | Implement 4 charts thực sự bằng Chart.js |
| `static/index.html` | B, D | Top 100 + search + import 2 bước |
| `static/app.js` | B, D | Render 100 rows + verdict + search + preview flow |
| `static/style.css` | A, B | Badge styles + chart container styles |
| `refresh_stats.py` | C | Chạy lại sau khi fix prize logic |

---

## 7. THỨ TỰ LÀM KHUYẾN NGHỊ

```
Fix C (prize logic) → 30' — fix backend trước, đơn giản nhất
Fix B (top 100)    → 30' — nâng limit, thêm search
Fix D (preview)    → 45' — thêm endpoint + sửa modal 2 bước
Fix A (charts)     → 2h  — làm cuối vì phức tạp nhất
```

---

## 8. ĐỊNH NGHĨA DONE

- [ ] **Fix A:** 4 charts load được với data thực từ DB, không phải placeholder
- [ ] **Fix A:** User có thể toggle từng user on/off trên Chart 1 (Jade Trend)
- [ ] **Fix A:** Chart 4 (Gap vs #2) có đường cảnh báo 100K màu đỏ
- [ ] **Fix B:** Dashboard hiện 100 users, search real-time hoạt động
- [ ] **Fix B:** Cột Verdict hiện TEAM / Farm / — đúng logic
- [ ] **Fix C:** Prize estimate dựa trên projected rank 31/05, không phải rank hôm nay
- [ ] **Fix D:** Import modal có 2 bước: Preview → Confirm
- [ ] **Fix D:** Bước Preview hiện tổng users + 5 dòng mẫu + cảnh báo delay nếu có

---

*Brief này do Adam (PM) soạn. Fix B + D là UI, Fix C là business logic — cần test kỹ sau khi fix C.*
