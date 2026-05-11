# Brief 14 — Team Page: STT Column + Sort Headers + Total Prize Banner
> PM: Adam | Dev: atigravity | Priority: P1  
> Chỉ sửa 2 file: `static/team.html` và `static/team.js`. Không đụng backend.

---

## TỔNG QUAN

3 cải tiến UI cho trang `/team`:

1. **Cột STT** — số thứ tự thứ tự hiển thị (1, 2, 3…) ở đầu bảng
2. **Click-to-sort headers** — click vào header để sort tăng/giảm, click lại để đảo chiều
3. **Banner tổng prize** — hiển thị tổng prize dự kiến của cả team phía trên bảng

---

## THAY ĐỔI 1 — Cột STT (`team.html` + `team.js`)

### `team.html` — thêm `<th>` đầu tiên:

```html
<!-- HIỆN TẠI: -->
<tr>
    <th>Alias</th>
    <th>Role</th>
    ...
</tr>

<!-- SỬA THÀNH: -->
<tr>
    <th>#</th>
    <th data-col="alias">Alias <span class="sort-icon">↕</span></th>
    <th data-col="role">Role <span class="sort-icon">↕</span></th>
    <th data-col="rank">Rank <span class="sort-icon">↕</span></th>
    <th data-col="jade">Jade <span class="sort-icon">↕</span></th>
    <th data-col="delta">Δ Hôm Nay <span class="sort-icon">↕</span></th>
    <th data-col="w_rate">W.Rate <span class="sort-icon">↕</span></th>
    <th data-col="proj">Proj 31/05 <span class="sort-icon">↕</span></th>
    <th data-col="prize">Prize <span class="sort-icon">↕</span></th>
    <th>Hành động</th>
</tr>
```

### `team.js` — thêm số thứ tự vào `row.innerHTML`:

```javascript
// Trong vòng forEach, thêm biến index (đổi forEach thành forEach với index):
members.forEach((member, index) => {
    // ... (giữ nguyên logic hiện tại)
    row.innerHTML = `
        <td style="color:var(--text-muted);font-size:0.85rem;text-align:center">${index + 1}</td>
        <td>${member.alias}</td>
        ...
    `;
});
```

> **Lưu ý:** STT là số thứ tự hiển thị sau khi sort (không phải ID cố định). Tức là sau khi sort, STT luôn hiển thị 1, 2, 3… theo thứ tự mới.

---

## THAY ĐỔI 2 — Click-to-sort Headers (`team.js`)

### Logic sort

Thêm state sort ở đầu file:

```javascript
let sortState = { col: null, dir: 'asc' };
```

Thêm function `sortMembers(members, col, dir)` — nhận array members và trả về array đã sort:

```javascript
function sortMembers(members, col, dir) {
    const sorted = [...members];
    sorted.sort((a, b) => {
        const sa = a.stats || {};
        const sb = b.stats || {};
        let va, vb;

        switch (col) {
            case 'alias': va = a.alias || ''; vb = b.alias || ''; break;
            case 'role':  va = a.role || '';  vb = b.role || '';  break;
            case 'rank':  va = sa.rank  ?? 999; vb = sb.rank  ?? 999; break;
            case 'jade':  va = sa.jade  ?? -1;  vb = sb.jade  ?? -1;  break;
            case 'delta': va = sa.delta ?? -Infinity; vb = sb.delta ?? -Infinity; break;
            case 'w_rate':va = sa.w_rate ?? -1; vb = sb.w_rate ?? -1; break;
            case 'proj':  va = sa.proj_may31 ?? -1; vb = sb.proj_may31 ?? -1; break;
            case 'prize': va = parsePrize(sa.prize_est); vb = parsePrize(sb.prize_est); break;
            default: return 0;
        }

        if (typeof va === 'string') {
            return dir === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va);
        }
        return dir === 'asc' ? va - vb : vb - va;
    });
    return sorted;
}

// Helper: parse "$2,000" → 2000
function parsePrize(str) {
    if (!str || str === '—') return -1;
    return parseInt(str.replace(/[^0-9]/g, '')) || -1;
}
```

### Gắn event listener vào headers

Sau khi render bảng xong (ở cuối `fetchTeam` hoặc trong `DOMContentLoaded`), gắn click handler vào các `<th>` có `data-col`:

```javascript
function attachSortListeners(members) {
    document.querySelectorAll('thead th[data-col]').forEach(th => {
        // Clone để remove listener cũ
        const newTh = th.cloneNode(true);
        th.parentNode.replaceChild(newTh, th);
        
        newTh.style.cursor = 'pointer';
        newTh.style.userSelect = 'none';
        
        newTh.addEventListener('click', () => {
            const col = newTh.getAttribute('data-col');
            if (sortState.col === col) {
                sortState.dir = sortState.dir === 'asc' ? 'desc' : 'asc';
            } else {
                sortState.col = col;
                sortState.dir = 'asc';
            }
            renderTeam(cachedMembers);
        });
    });
}
```

### Refactor `fetchTeam` để tách fetch và render

```javascript
let cachedMembers = [];

async function fetchTeam() {
    try {
        const res = await fetch('/api/team-members/with-stats');
        cachedMembers = await res.json();
        renderTeam(cachedMembers);
    } catch (err) {
        console.error("Error fetching team:", err);
    }
}

function renderTeam(members) {
    // Sort nếu có sortState
    const toRender = sortState.col ? sortMembers(members, sortState.col, sortState.dir) : members;

    const teamBody = document.getElementById('team-body');
    teamBody.innerHTML = '';

    if (toRender.length === 0) {
        teamBody.innerHTML = '<tr><td colspan="10" style="text-align:center;color:var(--text-muted)">Chưa có thành viên.</td></tr>';
        updatePrizeBanner(toRender);
        return;
    }

    toRender.forEach((member, index) => {
        // ... (giữ nguyên logic render row hiện tại, thêm <td> STT ở đầu)
    });

    updateSortIcons();
    attachSortListeners(members);  // pass members gốc (chưa sort) để re-sort lại từ đầu
    updatePrizeBanner(toRender);
}
```

### Cập nhật sort icon sau khi render

```javascript
function updateSortIcons() {
    document.querySelectorAll('thead th[data-col]').forEach(th => {
        const icon = th.querySelector('.sort-icon');
        if (!icon) return;
        const col = th.getAttribute('data-col');
        if (sortState.col === col) {
            icon.textContent = sortState.dir === 'asc' ? '↑' : '↓';
            icon.style.color = 'var(--accent, #3b82f6)';
        } else {
            icon.textContent = '↕';
            icon.style.color = 'var(--text-muted)';
        }
    });
}
```

---

## THAY ĐỔI 3 — Banner tổng prize (`team.html` + `team.js`)

### `team.html` — thêm banner giữa tiêu đề và bảng:

```html
<!-- HIỆN TẠI: -->
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
    <h2>Danh sách Team</h2>
    <button ...>+ Thêm Thành Viên</button>
</div>
<table>

<!-- SỬA THÀNH: -->
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
    <h2>Danh sách Team</h2>
    <button onclick="showMemberModal()" class="btn btn-primary">+ Thêm Thành Viên</button>
</div>

<!-- Banner tổng prize -->
<div id="prize-banner" style="
    background: rgba(34,197,94,0.1);
    border: 1px solid rgba(34,197,94,0.3);
    border-radius: 0.5rem;
    padding: 0.75rem 1.25rem;
    margin-bottom: 1rem;
    display: flex;
    align-items: center;
    gap: 0.75rem;
">
    <span style="color:var(--text-muted);font-size:0.875rem">💰 Tổng prize dự kiến cả team:</span>
    <span id="prize-total" style="font-size:1.125rem;font-weight:700;color:#22c55e">—</span>
    <span style="color:var(--text-muted);font-size:0.75rem" id="prize-members-note"></span>
</div>

<table>
```

### `team.js` — function `updatePrizeBanner`:

```javascript
function updatePrizeBanner(members) {
    let total = 0;
    let countInTop100 = 0;

    members.forEach(m => {
        const prize = parsePrize((m.stats || {}).prize_est);
        if (prize > 0) {
            total += prize;
            countInTop100++;
        }
    });

    document.getElementById('prize-total').textContent =
        total > 0 ? '$' + total.toLocaleString() : '—';

    const note = document.getElementById('prize-members-note');
    if (total > 0) {
        const outCount = members.length - countInTop100;
        note.textContent = `(${countInTop100} thành viên trong top 100${outCount > 0 ? `, ${outCount} ngoài top` : ''})`;
    } else {
        note.textContent = '';
    }
}
```

---

## THỨ TỰ THỰC HIỆN

```
1. Sửa team.html — thêm th "#", thêm data-col vào headers, thêm prize-banner HTML
2. Sửa team.js   — refactor fetchTeam → fetchTeam + renderTeam, thêm sort logic, thêm updatePrizeBanner
3. Restart server (hoặc hard refresh Ctrl+Shift+R)
4. Verify theo checklist bên dưới
```

---

## VERIFY CHECKLIST

**STT:**
- [ ] Cột đầu tiên hiển thị 1, 2, 3… cho tất cả rows
- [ ] Sau khi sort, STT cập nhật theo thứ tự mới (1, 2, 3… lại từ đầu)

**Sort:**
- [ ] Click header "Rank" → sort tăng dần (rank thấp lên trên), click lại → giảm dần
- [ ] Click header "Jade" → sort theo jade giảm dần (mặc định desc hợp lý hơn, nhưng follow spec asc-first)
- [ ] Click header "Prize" → sort theo prize value (không phải string)
- [ ] Members "Ngoài top 100" (stats=null) xếp cuối khi sort theo các cột số
- [ ] Icon ↕ đổi thành ↑/↓ đúng với chiều sort, trở về ↕ khi sort cột khác
- [ ] Click "Alias" → sort alphabetical

**Prize Banner:**
- [ ] Banner hiển thị tổng $USD đúng (cộng tất cả prize_est của members có stats)
- [ ] Note trong ngoặc hiển thị số thành viên trong/ngoài top 100
- [ ] Banner không bị ảnh hưởng bởi thứ tự sort (tổng không đổi khi sort)
- [ ] Nếu không ai có prize → hiển thị "—"

**Regression:**
- [ ] Nút Sửa / Xóa vẫn hoạt động bình thường sau khi sort
- [ ] colspan trong row "Chưa có thành viên" đổi thành `10` (thêm cột STT)

---

## YÊU CẦU SAU KHI HOÀN THÀNH

Sau khi implement và verify xong, AG tạo file `Review_Report_Brief_14.md` trong thư mục project, ghi rõ:
- Từng file đã sửa và thay đổi cụ thể là gì
- Kết quả chạy verify checklist (từng item pass/fail)
- Bất kỳ phát hiện hoặc thay đổi nào ngoài scope brief (nếu có)
