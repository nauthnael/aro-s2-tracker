# Brief 10 — Referral Tab + Dashboard T1/T2 Detail
> PM: Adam | Dev: atigravity | Priority: P1  
> 3 task: (A) Dashboard T1+T2 chi tiết, (B) Backend thêm ref history, (C) Tab Referral ở Tracker

---

## TASK A — Dashboard: Sửa cột T1+T2 hiển thị chi tiết

### File: `static/app.js`

Trong hàm `renderLeaderboardRows()`, tìm dòng render cột T1+T2:

```javascript
// HIỆN TẠI:
<td>${user.t1_refs + user.t2_refs}</td>

// SỬA THÀNH:
<td title="${user.t1_refs} T1 + ${user.t2_refs} T2">
    ${user.t1_refs + user.t2_refs}
    <span style="color:var(--text-muted);font-size:0.75rem;display:block">
        ${user.t1_refs}T1 + ${user.t2_refs}T2
    </span>
</td>
```

Không cần sửa backend. Đây là thay đổi nhỏ nhất trong brief, làm trước.

---

## TASK B — Backend: Thêm ref history vào `/api/tracker`

### Bối cảnh

API `/api/tracker` trả về `user.history[date]` hiện chỉ có `{rank, jade, delta, is_delayed}`. Cần thêm `t1_refs`, `t2_refs`, `delta_t1`, `delta_t2` vào mỗi history entry.

`delta_t1` = t1_refs hôm nay − t1_refs hôm qua (Δ đơn giản, không weighted).  
`delta_t2` = t2_refs hôm nay − t2_refs hôm qua.

### File: `routers/dashboard.py` — hàm `get_tracker()`

#### B1. Thêm t1_refs, t2_refs vào history entry

Tìm đoạn build history (hiện tại khoảng dòng 77–82):

```python
# HIỆN TẠI:
user_data[r.username]["history"][date_str] = {
    "rank": r.rank,
    "jade": r.jade,
    "delta": r.delta,
    "is_delayed": snap_id_to_delayed.get(r.snapshot_id, False)
}

# SỬA THÀNH:
user_data[r.username]["history"][date_str] = {
    "rank": r.rank,
    "jade": r.jade,
    "delta": r.delta,
    "t1_refs": r.t1_refs or 0,
    "t2_refs": r.t2_refs or 0,
    "delta_t1": None,   # sẽ tính ở pass thứ 2
    "delta_t2": None,
    "is_delayed": snap_id_to_delayed.get(r.snapshot_id, False)
}
```

#### B2. Tính delta_t1 và delta_t2 — pass thứ 2 sau khi build xong toàn bộ history

Thêm đoạn này **sau vòng loop `for r in all_rankings`**, trước phần sort:

```python
# Pass 2: tính delta_t1, delta_t2 cho từng user
for username, data in user_data.items():
    sorted_dates = sorted(data["history"].keys())  # dates đã là YYYY-MM-DD, sort alpha = sort chrono
    for i, date_str in enumerate(sorted_dates):
        if i == 0:
            # Ngày đầu tiên: không có prev → delta = None
            data["history"][date_str]["delta_t1"] = None
            data["history"][date_str]["delta_t2"] = None
        else:
            prev_date = sorted_dates[i - 1]
            prev = data["history"][prev_date]
            curr = data["history"][date_str]
            curr["delta_t1"] = curr["t1_refs"] - prev["t1_refs"]
            curr["delta_t2"] = curr["t2_refs"] - prev["t2_refs"]
```

**Lưu ý:** Không cần thêm column mới vào DB — tính on-the-fly khi serve API là đủ, vì delta_refs không cần lưu lịch sử.

---

## TASK C — Frontend: Tab Referral ở Tracker

### C1. Thêm button "Refs" vào toggle group

**File:** `static/tracker.html`

Thêm button vào `.toggle-group`:

```html
<div class="toggle-group">
    <button class="active" data-mode="jade" onclick="switchMode('jade')">Jade</button>
    <button data-mode="delta" onclick="switchMode('delta')">Δ Delta</button>
    <button data-mode="rank" onclick="switchMode('rank')">Rank</button>
    <button data-mode="refs" onclick="switchMode('refs')">Refs</button>  <!-- THÊM -->
</div>
```

### C2. Thêm sort state và sửa render trong `tracker.js`

**File:** `static/tracker.js`

#### Thêm biến sort state (đầu file, cạnh `currentMode`):

```javascript
let currentMode = 'jade';
let sortState = { col: null, dir: 0 };
// dir: 0 = default (by current_rank), 1 = desc (nhiều nhất lên trên), -1 = asc
```

#### Sửa render header — thêm click sort cho cột ngày khi mode = refs:

Trong phần render header `dates.forEach(...)`, sửa để khi mode là `refs` thì header có thể click để sort:

```javascript
dates.forEach(dateStr => {
    const snap = snapshots.find(s => s.date === dateStr);
    const dateObj = new Date(dateStr);
    const displayDate = `${dateObj.getDate()}/${dateObj.getMonth() + 1}`;
    const isDelayed = snap && snap.is_delayed;

    const th = document.createElement('th');
    if (isDelayed) th.className = 'delayed';

    if (currentMode === 'refs') {
        // Hiện sort indicator nếu đang sort theo cột này
        const isSorted = sortState.col === dateStr;
        const arrow = isSorted ? (sortState.dir === 1 ? ' ▼' : ' ▲') : '';
        th.innerHTML = `<span style="cursor:pointer;user-select:none" onclick="sortByRefDate('${dateStr}')">${displayDate}${isDelayed ? ' ⚠️' : ''}${arrow}</span>`;
    } else {
        th.innerHTML = `${displayDate} ${isDelayed ? '⚠️' : ''}`;
    }

    headerRow.appendChild(th);
});
```

#### Thêm hàm `sortByRefDate()`:

```javascript
function sortByRefDate(dateStr) {
    if (sortState.col === dateStr) {
        // Toggle: desc → asc → default
        sortState.dir = sortState.dir === 1 ? -1 : (sortState.dir === -1 ? 0 : 1);
        if (sortState.dir === 0) sortState.col = null;
    } else {
        sortState.col = dateStr;
        sortState.dir = 1; // Bắt đầu bằng desc (nhiều nhất lên trên)
    }
    renderTable();
}
```

#### Sửa phần filter + sort users trong `renderTable()`:

Tìm đoạn filter users (hiện tại `const filteredUsers = users.filter(...)`), sửa thành:

```javascript
// Filter
let filteredUsers = users.filter(u => {
    const matchSearch = !searchText || u.alias.toLowerCase().includes(searchText);
    const matchFilter = filterMode === 'all' ||
                       (filterMode === 'team' && u.is_team) ||
                       (filterMode === 'top10' && u.current_rank <= 10);
    return matchSearch && matchFilter;
});

// Sort: nếu mode refs và đang sort theo ngày cụ thể
if (currentMode === 'refs' && sortState.col && sortState.dir !== 0) {
    filteredUsers = [...filteredUsers].sort((a, b) => {
        const histA = a.history[sortState.col];
        const histB = b.history[sortState.col];
        // Sort theo delta_t1 (T1 quan trọng hơn T2)
        const valA = histA ? (histA.delta_t1 ?? -9999) : -9999;
        const valB = histB ? (histB.delta_t1 ?? -9999) : -9999;
        return sortState.dir === 1 ? valB - valA : valA - valB;
    });
} else if (currentMode !== 'refs' || sortState.dir === 0) {
    // Reset về sort mặc định (theo current_rank) khi đổi mode
    // (users đã được sort theo rank từ API)
}
```

#### Thêm render mode `refs` vào phần render cell:

Trong `dates.forEach(dateStr => {...})` bên trong render body, thêm case `refs`:

```javascript
if (hist) {
    if (currentMode === 'jade') {
        content = formatNumber(hist.jade);
        className = 'mode-jade';
    } else if (currentMode === 'delta') {
        if (hist.delta !== null) {
            content = (hist.delta >= 0 ? '+' : '') + formatNumber(hist.delta);
            className = hist.delta >= 0 ? 'mode-delta-pos' : 'mode-delta-neg';
        }
    } else if (currentMode === 'rank') {
        content = '#' + hist.rank;
        className = 'mode-jade';
    } else if (currentMode === 'refs') {
        // Format: "19(+3) / 27(+5)"
        const dt1 = hist.delta_t1;
        const dt2 = hist.delta_t2;
        const t1str = `${hist.t1_refs}${dt1 !== null && dt1 !== undefined ? '(<span style="color:' + (dt1 >= 0 ? 'var(--success)' : 'var(--danger)') + '">' + (dt1 >= 0 ? '+' : '') + dt1 + '</span>)' : ''}`;
        const t2str = `${hist.t2_refs}${dt2 !== null && dt2 !== undefined ? '(<span style="color:' + (dt2 >= 0 ? 'var(--success)' : 'var(--danger)') + '">' + (dt2 >= 0 ? '+' : '') + dt2 + '</span>)' : ''}`;
        content = `${t1str} / ${t2str}`;
        className = 'mode-jade';
    }
}
```

#### Reset sort khi đổi mode:

Trong hàm `switchMode()`, thêm reset sort:

```javascript
function switchMode(mode) {
    currentMode = mode;
    // Reset sort khi đổi mode
    if (mode !== 'refs') {
        sortState = { col: null, dir: 0 };
    }
    document.querySelectorAll('.toggle-group button').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.mode === mode);
    });
    renderTable();
}
```

### C3. CSS: tăng min-width cột ngày khi mode refs (vì content rộng hơn)

**File:** `static/style.css`

```css
/* Cột ngày ở mode refs cần rộng hơn */
.tracker-table td.mode-refs-cell {
    min-width: 120px;
    font-size: 0.8rem;
}
```

Và trong render, thêm class `mode-refs-cell` vào td khi mode = refs:

```javascript
cells += `<td class="${className}${currentMode === 'refs' ? ' mode-refs-cell' : ''}">${content}</td>`;
```

---

## 4. THỨ TỰ THỰC HIỆN

```
1. Task A — app.js (1 dòng, làm ngay)
2. Task B — dashboard.py (backend, cần test API response trước)
3. Task C — tracker.js + tracker.html + style.css (sau khi B xong)
4. Restart → verify
```

---

## 5. VERIFY CHECKLIST

**Task A:**
- [ ] Dashboard cột T1+T2: nau*** hiển thị `46` với dòng nhỏ `19T1 + 27T2`

**Task B:**
- [ ] `GET /api/tracker` → `users[0].history["2026-04-28"]` có field `t1_refs`, `t2_refs`, `delta_t1`, `delta_t2`
- [ ] `delta_t1` của ngày đầu tiên = null (không có prev)
- [ ] `delta_t1` của ngày thứ 2 trở đi = t1_today - t1_yesterday (số dương nếu tăng)

**Task C:**
- [ ] Tab Refs xuất hiện trong toggle group
- [ ] Chuyển sang tab Refs: mỗi ô hiện `19(+3) / 27(+5)` với delta màu xanh/đỏ
- [ ] Click header ngày → sort theo delta_t1 desc (nhiều nhất lên trên), arrow ▼ xuất hiện
- [ ] Click lần 2 → sort asc, arrow ▲
- [ ] Click lần 3 → về default (sort theo rank), không có arrow
- [ ] Chuyển sang tab Jade/Delta/Rank → sort tự reset về default

**AG KHÔNG được báo "done" nếu chưa verify format ô `19(+3) / 27(+5)` và sort hoạt động đúng 3 trạng thái.**

---

## 6. TÓM TẮT FILE CẦN SỬA

| File | Task | Thay đổi |
|------|------|----------|
| `static/app.js` | A | Sửa render cột T1+T2 thêm breakdown |
| `routers/dashboard.py` | B | Thêm t1_refs/t2_refs/delta_t1/delta_t2 vào history entry; thêm pass-2 tính delta |
| `static/tracker.html` | C | Thêm button "Refs" vào toggle group |
| `static/tracker.js` | C | Thêm sort state, sortByRefDate(), render mode refs, reset sort khi đổi mode |
| `static/style.css` | C | Thêm `.mode-refs-cell` min-width |

---

*Brief này do Adam (PM) soạn. Implement đúng spec, verify đủ checklist rồi mới báo done.*
