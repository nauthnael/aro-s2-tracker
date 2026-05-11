# Brief 9 — Team: Fix Lookup Bằng Alias + Dashboard Layout
> PM: Adam | Dev: atigravity | Priority: P0  
> 2 task độc lập, implement cùng lúc.

---

## TASK 1 — Fix Team Stats Lookup Bằng Alias (Backend)

### Bối cảnh & Vấn đề

Hiện tại `team.js` lookup stats theo `bxh_rank` (nếu có), fallback về `username`. Vấn đề:

- `hun***` (team member) chưa được gán `bxh_rank` → fallback về `username = "hun***@gmail.com"`
- BXH hôm nay có `hun***` lạ (rank #21, không phải team) cùng masked email
- Kết quả: bảng Team hiển thị stats của người lạ rank #21 cho hun*** của team

**Giải pháp (Cách 3 — PM đã duyệt):** Backend trả về stats trực tiếp bằng cách JOIN `team_members` với `rankings` theo `alias`. Không cần frontend tự lookup, không cần fallback logic dễ sai.

### Logic đúng

```
alias trong team_members === alias trong rankings (đã được alias_resolver.py đảm bảo)

Nếu thành viên hôm nay có trong top 100 → alias khớp → lấy stats
Nếu thành viên rớt khỏi top 100 → không có ranking record → stats = null → hiển thị "—"
Không bao giờ nhầm sang người khác vì alias là unique
```

### Thay đổi cần làm

#### 1a. Thêm endpoint mới `GET /api/team-with-stats`

**File:** `routers/team.py`

Thêm endpoint trả về team roster đã kèm stats từ snapshot mới nhất, join theo `alias`:

```python
from sqlalchemy import desc

@router.get("/with-stats")  # full path: /api/team-members/with-stats
async def get_team_with_stats(db: Session = Depends(get_db)):
    # Lấy snapshot mới nhất
    latest_snapshot = db.query(Snapshot).order_by(desc(Snapshot.date)).first()
    
    members = db.query(TeamMember).all()
    result = []
    
    for member in members:
        stats = None
        if latest_snapshot:
            # Lookup bằng ALIAS — không bao giờ nhầm người
            ranking = db.query(Ranking).filter(
                Ranking.snapshot_id == latest_snapshot.id,
                Ranking.alias == member.alias
            ).first()
            if ranking:
                stats = {
                    "rank": ranking.rank,
                    "jade": ranking.jade,
                    "delta": ranking.delta,
                    "w_rate": ranking.w_rate,
                    "proj_may31": ranking.proj_may31,
                    "prize_est": ranking.prize_est,
                }
        
        result.append({
            "id": member.id,
            "username": member.username,
            "alias": member.alias,
            "role": member.role,
            "bxh_rank": member.bxh_rank,
            "note": member.note,
            "stats": stats  # None nếu không có trong top 100 hôm nay
        })
    
    return result
```

**Lưu ý import:** Cần import `Snapshot`, `Ranking` từ `database` vào `routers/team.py` nếu chưa có.

#### 1b. Sửa `fetchTeam()` trong `team.js` để dùng endpoint mới

**File:** `static/team.js`

Thay toàn bộ hàm `fetchTeam()`:

```javascript
async function fetchTeam() {
    try {
        const res = await fetch('/api/team-members/with-stats');
        const members = await res.json();

        const teamBody = document.getElementById('team-body');
        teamBody.innerHTML = '';

        if (members.length === 0) {
            teamBody.innerHTML = '<tr><td colspan="9" style="text-align:center;color:var(--text-muted)">Chưa có thành viên. Bấm "+ Thêm Thành Viên" để thêm.</td></tr>';
            return;
        }

        members.forEach(member => {
            const s = member.stats || {};
            const inTop100 = member.stats !== null;

            const row = document.createElement('tr');
            if (member.role === 'LEADER') row.className = 'row-nau';
            else if (member.role === 'T1') row.className = 'row-team';

            // Hiển thị rank: nếu có stats → rank thực hôm nay, không có → "Ngoài top 100"
            const rankDisplay = inTop100
                ? '#' + s.rank
                : '<span style="color:var(--text-muted);font-size:0.75rem">Ngoài top 100</span>';

            row.innerHTML = `
                <td>${member.alias}</td>
                <td><span class="badge ${getRoleBadge(member.role)}">${member.role}</span></td>
                <td>${rankDisplay}</td>
                <td>${inTop100 ? formatNumber(s.jade) : '—'}</td>
                <td class="${(s.delta || 0) >= 0 ? 'positive' : 'negative'}">
                    ${inTop100 && s.delta !== null && s.delta !== undefined
                        ? (s.delta >= 0 ? '+' : '') + formatNumber(s.delta)
                        : '—'}
                </td>
                <td>${inTop100 && s.w_rate !== null ? formatNumber(Math.round(s.w_rate)) : '—'}</td>
                <td>${inTop100 ? formatNumber(s.proj_may31) : '—'}</td>
                <td style="color:var(--success)">${inTop100 ? (s.prize_est || '—') : '—'}</td>
                <td>
                    <button onclick="editMember(${member.id})"
                        style="background:rgba(59,130,246,0.2);color:#3b82f6;border:none;padding:0.25rem 0.5rem;border-radius:0.25rem;cursor:pointer;font-size:0.75rem;margin-right:0.25rem">
                        Sửa
                    </button>
                    <button onclick="deleteMember(${member.id}, '${member.alias}')"
                        style="background:rgba(239,68,68,0.2);color:#ef4444;border:none;padding:0.25rem 0.5rem;border-radius:0.25rem;cursor:pointer;font-size:0.75rem">
                        Xóa
                    </button>
                </td>
            `;
            teamBody.appendChild(row);
        });
    } catch (err) {
        console.error("Error fetching team:", err);
    }
}
```

**Xóa** đoạn `usernameMap` và logic fallback cũ bên trong forEach — không cần nữa.

---

## TASK 2 — Fix Dashboard Layout: Bảng Top 100 Bị Tràn

### Bối cảnh & Vấn đề

Nhìn screenshot: bảng Top 100 và box Cảnh Báo đang nằm cạnh nhau theo grid 2 cột (`grid-column: span 2` cho bảng, box cảnh báo chiếm cột còn lại). Vì `max-width: 1200px` của `.container`, bảng bị cứng về chiều ngang → cột Prize bị cắt đứt ở rìa phải.

### Fix

**File:** `static/index.html` — sửa layout section B + C

Đổi từ grid ngang sang **layout dọc**: bảng Top 100 full width, Cảnh Báo nằm dưới (hoặc thu gọn vào sidebar nhỏ hơn).

**Phương án A — Stack dọc (đơn giản nhất):**

```html
<!-- Xóa div.grid bọc ngoài, để 2 card xếp dọc tự nhiên -->

<!-- Section B: Top 100 — full width -->
<div class="card">
    <h2>Top 100 Leaderboard</h2>
    <!-- ... giữ nguyên nội dung ... -->
    <div style="overflow-x: auto;">  <!-- thêm scroll ngang nếu cần -->
        <table>
            <!-- ... -->
        </table>
    </div>
</div>

<!-- Section C: Cảnh Báo — full width bên dưới -->
<div class="card">
    <h2>Cảnh Báo</h2>
    <div id="alerts-list" style="margin-top: 1rem; display: flex; flex-wrap: wrap; gap: 0.75rem;">
        <!-- alerts hiển thị ngang hàng thay vì xếp dọc -->
    </div>
</div>
```

**Phương án B — Sidebar nhỏ hơn (giữ layout ngang nhưng cân đúng tỉ lệ):**

```html
<!-- Sửa div.grid thành grid 3:1 -->
<div style="display: grid; grid-template-columns: 3fr 1fr; gap: 1.5rem; align-items: start;">
    <!-- Section B: Top 100 -->
    <div class="card" style="overflow-x: auto;">
        <h2>Top 100 Leaderboard</h2>
        <!-- ... -->
    </div>

    <!-- Section C: Cảnh Báo -->
    <div class="card">
        <h2>Cảnh Báo</h2>
        <div id="alerts-list" style="margin-top: 1rem;"></div>
    </div>
</div>
```

**PM chọn Phương án B** (giữ layout ngang, sidebar cảnh báo hẹp lại, bảng rộng ra).

Ngoài ra, thêm `overflow-x: auto` cho table wrapper để khi màn hình nhỏ hơn, bảng có thể scroll ngang thay vì bị cắt:

```html
<div style="overflow-x: auto; margin-top: 0.75rem;">
    <table>...</table>
</div>
```

**File:** `static/style.css` — mở rộng max-width container cho Dashboard

Hiện tại `.container { max-width: 1200px }` áp dụng cho tất cả trang. Chỉ cần tăng cho index.html:

```css
/* Thêm vào cuối style.css */
.container-wide {
    max-width: 1600px;
    margin: 0 auto;
    padding: 2rem;
}
```

Và sửa `index.html`: đổi `<div class="container">` thành `<div class="container-wide">`.

---

## 3. THỨ TỰ THỰC HIỆN

1. Task 2 trước (CSS, không ảnh hưởng backend):
   - Sửa `index.html`: layout grid 3:1, thêm `overflow-x: auto`
   - Sửa `style.css`: thêm `.container-wide`

2. Task 1 sau:
   - Sửa `routers/team.py`: thêm endpoint `/api/team-members/with-stats`
   - Sửa `static/team.js`: replace `fetchTeam()` dùng endpoint mới

3. Restart server → verify

---

## 4. VERIFY CHECKLIST

**Task 2 — Layout:**
- [ ] Bảng Top 100 hiển thị đủ cột Prize không bị cắt
- [ ] Cảnh Báo vẫn hiện đúng bên phải, không che bảng
- [ ] Trên màn hình nhỏ hơn: bảng có thể scroll ngang

**Task 1 — Team Lookup:**
- [ ] `GET /api/team-members/with-stats` trả về array có field `stats` (object hoặc null)
- [ ] hun*** (chưa có bxh_rank, rớt khỏi top 100): hiển thị "Ngoài top 100", **không** hiện stats của hun*** lạ
- [ ] dan*** (trong top 100, alias khớp): hiển thị đúng rank, jade, delta
- [ ] Thành viên bất kỳ đang trong top 100 với alias đúng → stats hiện đúng

**AG KHÔNG được báo "done" nếu chưa verify hun*** hiển thị "Ngoài top 100" thay vì rank #21.**

---

## 5. TÓM TẮT FILE CẦN SỬA

| File | Task | Thay đổi |
|------|------|----------|
| `routers/team.py` | 1 | Thêm `GET /api/team-members/with-stats` endpoint |
| `static/team.js` | 1 | Replace `fetchTeam()` dùng endpoint mới, bỏ fallback logic |
| `static/index.html` | 2 | Đổi grid 3:1, bọc table trong `overflow-x: auto`, đổi `container-wide` |
| `static/style.css` | 2 | Thêm `.container-wide { max-width: 1600px }` |

---

*Brief này do Adam (PM) soạn. Implement đúng spec, verify đủ checklist rồi mới báo done.*
