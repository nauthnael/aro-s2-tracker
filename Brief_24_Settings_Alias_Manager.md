# Brief 24 — Trang Settings: quản lý alias + xóa ghost entries
> PM: Adam | Dev: atigravity | Priority: P1  
> Tạo trang /settings với 2 chức năng: xem toàn bộ alias hệ thống + xóa ghost aliases (jade luôn = 0).

---

## BỐI CẢNH

Hiện Tracker có 150 users nhưng 51 trong số đó là "ghost" — alias tồn tại trong DB nhưng jade = 0 ở mọi snapshot (ví dụ: `qua[farm]***`, `qua[1]***`, `qua[2]***`, `qua[TEAM]`, `tra[1]***`...). Đây là rác từ các lần import lỗi cũ. PM cần:

1. Xem danh sách toàn bộ alias để phát hiện alias sai
2. Xóa ghost aliases bằng 1 click

---

## PHẦN 1 — API Backend (`routers/dashboard.py`)

Thêm 2 endpoints:

```python
@router.get("/aliases")
async def get_alias_summary(db: Session = Depends(get_db)):
    """
    Trả về toàn bộ aliases trong hệ thống với thống kê.
    Dùng cho trang Settings.
    """
    latest = db.query(Snapshot).order_by(desc(Snapshot.date)).first()
    latest_id = latest.id if latest else None

    rows = db.execute("""
        SELECT
            alias,
            username,
            COUNT(DISTINCT snapshot_id) AS days_present,
            MAX(jade) AS max_jade,
            MIN(jade) AS min_jade,
            MAX(rank) AS worst_rank,
            MIN(rank) AS best_rank,
            MAX(is_team) AS is_team,
            MAX(team_role) AS team_role
        FROM rankings
        GROUP BY alias, username
        ORDER BY max_jade DESC
    """).fetchall()

    result = []
    for r in rows:
        result.append({
            "alias": r[0],
            "username": r[1],
            "days_present": r[2],
            "max_jade": r[3],
            "min_jade": r[4],
            "worst_rank": r[5],
            "best_rank": r[6],
            "is_team": bool(r[7]),
            "team_role": r[8],
            "is_ghost": r[3] == 0,   # max_jade=0 → ghost
        })

    return result


@router.delete("/aliases/ghost")
async def delete_ghost_aliases(db: Session = Depends(get_db)):
    """
    Xóa tất cả rankings có alias mà max_jade = 0 across toàn bộ snapshots.
    Không xóa aliases đang có jade > 0 ở bất kỳ snapshot nào.
    """
    # Tìm ghost aliases
    ghost_rows = db.execute("""
        SELECT alias FROM rankings
        GROUP BY alias
        HAVING MAX(jade) = 0
    """).fetchall()
    ghost_aliases = [r[0] for r in ghost_rows]

    if not ghost_aliases:
        return {"status": "success", "deleted": 0, "message": "Không có ghost alias nào"}

    total_deleted = 0
    for alias in ghost_aliases:
        n = db.query(Ranking).filter(Ranking.alias == alias).delete(synchronize_session=False)
        total_deleted += n

    db.commit()
    return {
        "status": "success",
        "deleted_aliases": len(ghost_aliases),
        "deleted_records": total_deleted,
        "aliases": ghost_aliases
    }
```

---

## PHẦN 2 — Trang `/settings` mới

### `static/settings.html`

Tạo file mới `static/settings.html`, layout giống các trang khác (dùng style.css):

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>ARO Sprint 2 — Settings</title>
    <link rel="stylesheet" href="/static/style.css">
</head>
<body>
<div class="container-wide">
    <header>
        <div>
            <h1>ARO Sprint 2 Tracker</h1>
            <p style="color: var(--text-muted); font-size: 0.875rem;">Settings</p>
        </div>
        <nav class="nav-links">
            <a href="/">Dashboard</a>
            <a href="/tracker">Tracker</a>
            <a href="/team">Team</a>
            <a href="/charts">Charts</a>
            <a href="/settings" class="active">Settings</a>
            <button onclick="showImportModal()" class="btn btn-primary">Import BXH</button>
        </nav>
    </header>

    <div class="card">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1rem;">
            <h2>🏷️ Alias Manager</h2>
            <div style="display:flex; gap:0.75rem; align-items:center;">
                <span id="alias-stats" style="color:var(--text-muted); font-size:0.875rem;"></span>
                <button onclick="deleteGhosts()" id="delete-ghost-btn"
                    style="background:rgba(239,68,68,0.15); color:#ef4444; border:none;
                           padding:0.4rem 0.9rem; border-radius:0.375rem; cursor:pointer; font-size:0.875rem;">
                    🗑️ Xóa Ghost Aliases
                </button>
            </div>
        </div>

        <!-- Filter bar -->
        <div style="display:flex; gap:0.75rem; margin-bottom:1rem; flex-wrap:wrap;">
            <input type="text" id="alias-search" placeholder="🔍 Tìm alias hoặc username..."
                oninput="renderAliases()"
                style="padding:0.4rem 0.75rem; background:var(--background); color:white;
                       border:1px solid var(--surface); border-radius:0.375rem; width:260px;">
            <select id="alias-filter" onchange="renderAliases()"
                style="padding:0.4rem 0.75rem; background:var(--background); color:white;
                       border:1px solid var(--surface); border-radius:0.375rem;">
                <option value="all">Tất cả</option>
                <option value="ghost">👻 Ghost (jade=0)</option>
                <option value="team">⭐ Team members</option>
                <option value="active">✅ Active (jade>0)</option>
                <option value="known">🔑 KNOWN_ALIASES</option>
            </select>
        </div>

        <!-- Table -->
        <div style="overflow-x:auto;">
            <table>
                <thead>
                    <tr>
                        <th>Alias</th>
                        <th>Username</th>
                        <th>Max Jade</th>
                        <th>Best Rank</th>
                        <th>Days</th>
                        <th>Team</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody id="alias-table-body">
                    <tr><td colspan="7" style="text-align:center; color:var(--text-muted)">Loading...</td></tr>
                </tbody>
            </table>
        </div>
    </div>
</div>

<script src="/static/settings.js"></script>
</body>
</html>
```

### `static/settings.js`

Tạo file mới `static/settings.js`:

```javascript
// Known duplicate usernames (sync với alias_resolver.py)
const KNOWN_USERNAMES = [
    "mal***@gmail.com", "tra***@gmail.com", "qua***@gmail.com",
    "kha***@gmail.com", "rom***@gmail.com", "ben***@gmail.com",
    "hun***@gmail.com", "thu***@gmail.com"
];

let allAliases = [];

async function loadAliases() {
    try {
        const res = await fetch('/api/aliases');
        allAliases = await res.json();
        updateStats();
        renderAliases();
    } catch(err) {
        console.error('Error loading aliases:', err);
    }
}

function updateStats() {
    const ghost = allAliases.filter(a => a.is_ghost).length;
    const active = allAliases.filter(a => !a.is_ghost).length;
    document.getElementById('alias-stats').textContent =
        `${allAliases.length} tổng | ${active} active | ${ghost} ghost`;
}

function renderAliases() {
    const search = document.getElementById('alias-search').value.toLowerCase();
    const filter = document.getElementById('alias-filter').value;

    let filtered = allAliases.filter(a => {
        const matchSearch = !search ||
            a.alias.toLowerCase().includes(search) ||
            a.username.toLowerCase().includes(search);
        const matchFilter =
            filter === 'all' ? true :
            filter === 'ghost' ? a.is_ghost :
            filter === 'team' ? a.is_team :
            filter === 'active' ? !a.is_ghost :
            filter === 'known' ? KNOWN_USERNAMES.includes(a.username) : true;
        return matchSearch && matchFilter;
    });

    const body = document.getElementById('alias-table-body');

    if (filtered.length === 0) {
        body.innerHTML = '<tr><td colspan="7" style="text-align:center; color:var(--text-muted)">Không tìm thấy</td></tr>';
        return;
    }

    body.innerHTML = filtered.map(a => {
        const statusBadge = a.is_ghost
            ? '<span style="color:#6b7280; font-size:0.75rem;">👻 ghost</span>'
            : a.is_team
                ? `<span style="color:var(--accent); font-size:0.75rem;">⭐ ${a.team_role || 'team'}</span>`
                : '<span style="color:var(--success); font-size:0.75rem;">✅ active</span>';
        const isKnown = KNOWN_USERNAMES.includes(a.username);
        const aliasCell = isKnown
            ? `<span style="color:white; font-weight:500">${a.alias}</span> <span style="color:var(--accent); font-size:0.7rem;">🔑</span>`
            : `<span style="color:white">${a.alias}</span>`;
        const jadeStr = a.max_jade > 0
            ? a.max_jade.toLocaleString()
            : '<span style="color:#6b7280">—</span>';
        const rankStr = a.best_rank < 999
            ? '#' + a.best_rank
            : '<span style="color:#6b7280">—</span>';
        const rowStyle = a.is_ghost ? 'opacity:0.45;' : '';

        return `<tr style="${rowStyle}">
            <td>${aliasCell}</td>
            <td style="color:var(--text-muted); font-size:0.875rem;">${a.username}</td>
            <td>${jadeStr}</td>
            <td>${rankStr}</td>
            <td style="color:var(--text-muted)">${a.days_present}</td>
            <td>${a.is_team ? (a.team_role || '—') : '—'}</td>
            <td>${statusBadge}</td>
        </tr>`;
    }).join('');
}

async function deleteGhosts() {
    const ghost = allAliases.filter(a => a.is_ghost);
    if (ghost.length === 0) { alert('Không có ghost alias nào.'); return; }
    if (!confirm(`Xóa ${ghost.length} ghost aliases?\n\n${ghost.map(a=>a.alias).join(', ')}\n\nHành động này không thể hoàn tác.`)) return;

    const btn = document.getElementById('delete-ghost-btn');
    btn.disabled = true;
    btn.textContent = 'Đang xóa...';

    try {
        const res = await fetch('/api/aliases/ghost', { method: 'DELETE' });
        const data = await res.json();
        if (res.ok) {
            alert(`✅ Đã xóa ${data.deleted_aliases} ghost aliases (${data.deleted_records} records)`);
            await loadAliases();  // Refresh
        } else {
            alert('Lỗi: ' + (data.detail || 'Không thể xóa'));
        }
    } catch(err) {
        alert('Lỗi kết nối');
    } finally {
        btn.disabled = false;
        btn.textContent = '🗑️ Xóa Ghost Aliases';
    }
}

document.addEventListener('DOMContentLoaded', loadAliases);
```

---

## PHẦN 3 — Thêm link Settings vào nav tất cả trang

Thêm `<a href="/settings">Settings</a>` vào `<nav class="nav-links">` trong các file:
- `static/index.html`
- `static/tracker.html`
- `static/team.html`
- `static/charts.html`

---

## THỨ TỰ THỰC HIỆN

```
1. routers/dashboard.py — thêm GET /api/aliases và DELETE /api/aliases/ghost
2. static/settings.html — tạo mới
3. static/settings.js   — tạo mới
4. static/*.html        — thêm link Settings vào nav
5. Restart server
6. Verify
```

---

## VERIFY CHECKLIST

- [ ] `/settings` mở được, hiển thị bảng alias đầy đủ
- [ ] Filter "Ghost" → chỉ hiện aliases có jade=0
- [ ] Filter "KNOWN_ALIASES" → chỉ hiện `mal***`, `qua***`, `hun***`... với icon 🔑
- [ ] Nút "Xóa Ghost Aliases" → confirm dialog → xóa → table refresh, stats cập nhật
- [ ] Sau xóa: Tracker chỉ còn ~99-105 users (không còn ghost)
- [ ] Link "Settings" xuất hiện trên nav tất cả trang

---

## YÊU CẦU SAU KHI HOÀN THÀNH

AG tạo file `Review_Report_Brief_24.md` ghi rõ:
- Số ghost aliases đã xóa khi chạy lần đầu
- Screenshot hoặc mô tả giao diện /settings
- Kết quả verify checklist
