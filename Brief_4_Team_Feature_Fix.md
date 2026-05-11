# Brief 4 — Team Feature Fix
> PM: Adam | Dev: atigravity | Priority: P0  
> PM đã test trực tiếp, xác định 3 bug cụ thể sau

---

## 1. KẾT QUẢ TEST THỰC TẾ

PM đã test bằng Chrome, thêm `dangkhoa@gmail.com` / alias `dan***` / role `T1`.

**API `/api/team-members` sau khi lưu:**
```json
[
  {"username":"dangkhoa@gmail.com","alias":"dan***","role":"T1","join_date":null,"note":""},
  {"username":"dan***","alias":"dan***","role":"T1","join_date":null,"note":""}
]
```

Có 2 records — bị **duplicate** (1 từ lần test của Adam trước đó, 1 từ lần test của PM). Và **bảng Team Dashboard hiển thị trống** dù DB đã có data.

---

## 2. BA BUG CỤ THỂ

### Bug 1 — Team Dashboard load sai API

**File:** `static/team.js` dòng 3

```javascript
// HIỆN TẠI (sai):
const response = await fetch('/api/team');

// /api/team trả về Rankings (is_team=True) từ ngày mới nhất
// Nhưng is_team chưa được set đúng → trả về mảng rỗng []
// → Bảng hiển thị trống dù team_members đã có data
```

Team Dashboard phải fetch từ **2 nguồn** và merge:
1. `GET /api/team-members` → roster (danh sách thành viên đã đăng ký)  
2. `GET /api/team` → stats hôm nay (rank, jade, delta, w_rate từ ranking)

**Fix:** Sửa `fetchTeam()` để gọi cả 2 API và merge theo `username`:

```javascript
async function fetchTeam() {
    try {
        // Lấy roster từ team_members table
        const rosterRes = await fetch('/api/team-members');
        const roster = await rosterRes.json();

        // Lấy stats hôm nay từ rankings (is_team=True)
        const statsRes = await fetch('/api/team');
        const stats = await statsRes.json();

        // Build stats map: username -> stats
        const statsMap = {};
        stats.forEach(s => { statsMap[s.username] = s; });

        const teamBody = document.getElementById('team-body');
        teamBody.innerHTML = '';

        if (roster.length === 0) {
            teamBody.innerHTML = '<tr><td colspan="9" style="text-align:center;color:var(--text-muted)">Chưa có thành viên. Bấm "+ Thêm Thành Viên" để thêm.</td></tr>';
            return;
        }

        roster.forEach(member => {
            const s = statsMap[member.username] || {};
            const row = document.createElement('tr');
            if (member.role === 'LEADER') row.className = 'row-nau';
            else if (member.role === 'T1') row.className = 'row-team';

            row.innerHTML = `
                <td>${member.alias}</td>
                <td><span class="badge ${getRoleBadge(member.role)}">${member.role}</span></td>
                <td>${s.rank ? '#' + s.rank : '—'}</td>
                <td>${formatNumber(s.jade)}</td>
                <td class="${(s.delta || 0) >= 0 ? 'positive' : 'negative'}">
                    ${s.delta !== null && s.delta !== undefined ? (s.delta >= 0 ? '+' : '') + formatNumber(s.delta) : '—'}
                </td>
                <td>${s.w_rate !== null && s.w_rate !== undefined ? formatNumber(Math.round(s.w_rate)) : '—'}</td>
                <td>${formatNumber(s.proj_may31)}</td>
                <td style="color:var(--success)">${s.prize_est || '—'}</td>
                <td>
                    <button onclick="deleteMember('${member.username}')" 
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

---

### Bug 2 — Duplicate khi lưu thành viên (không check trùng)

**File:** `routers/team.py` — endpoint `POST /api/team-members`

```python
# HIỆN TẠI (sai) — không check trùng username:
@router.post("")
async def add_team_member(member: TeamMemberSchema, db: Session = Depends(get_db)):
    db_member = TeamMember(**member.dict())
    db.add(db_member)
    db.commit()
    return {"status": "success"}
```

**Fix:**
```python
@router.post("")
async def add_team_member(member: TeamMemberSchema, db: Session = Depends(get_db)):
    # Check duplicate username
    existing = db.query(TeamMember).filter(TeamMember.username == member.username).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Username '{member.username}' đã tồn tại trong team.")
    
    db_member = TeamMember(**member.dict())
    db.add(db_member)
    db.commit()
    db.refresh(db_member)
    return {"status": "success", "id": db_member.id}
```

**Và sửa `saveMember()` trong team.js để hiện lỗi rõ hơn:**
```javascript
if (response.ok) {
    hideMemberModal();
    fetchTeam();
} else {
    const err = await response.json();
    alert("Lỗi: " + (err.detail || "Không thể thêm thành viên"));
}
```

---

### Bug 3 — Team table thiếu cột header "Xóa" và thiếu delete function

**File:** `static/team.html` — thead thiếu cột Xóa  
**File:** `static/team.js` — không có function `deleteMember()`

**Fix team.html** — thêm `<th>` cuối:
```html
<thead>
    <tr>
        <th>Alias</th>
        <th>Role</th>
        <th>Rank</th>
        <th>Jade</th>
        <th>Δ Hôm Nay</th>
        <th>W.Rate</th>
        <th>Proj 31/05</th>
        <th>Prize</th>
        <th>Hành động</th>   <!-- THÊM CỘT NÀY -->
    </tr>
</thead>
```

**Fix team.js** — thêm function delete:
```javascript
async function deleteMember(username) {
    if (!confirm(`Xóa thành viên "${username}" khỏi team?`)) return;
    
    // Lấy ID thành viên trước
    const res = await fetch('/api/team-members');
    const members = await res.json();
    const member = members.find(m => m.username === username);
    if (!member) { alert("Không tìm thấy thành viên"); return; }
    
    const delRes = await fetch(`/api/team-members/${member.id}`, { method: 'DELETE' });
    if (delRes.ok) {
        fetchTeam();
    } else {
        alert("Lỗi khi xóa thành viên");
    }
}
```

**Lưu ý:** `GET /api/team-members` hiện tại **không trả về `id`** vì Pydantic schema `TeamMemberSchema` không có field `id`. Cần fix thêm:

```python
# routers/team.py — thêm id vào schema
class TeamMemberSchema(BaseModel):
    id: Optional[int] = None      # THÊM DÒNG NÀY
    username: str
    alias: str
    role: str
    join_date: Optional[date] = None
    note: Optional[str] = None

    class Config:
        from_attributes = True    # THÊM để đọc từ ORM object
```

---

## 3. DỌN DẸP DATA DUPLICATE HIỆN TẠI

Hiện DB có 2 record `dan***` bị trùng (do test nhiều lần). AG cần xóa bằng script trước khi test lại:

```python
# Chạy 1 lần để dọn dẹp:
# python -c "
# from database import SessionLocal, TeamMember
# db = SessionLocal()
# # Giữ lại record mới nhất, xóa các duplicate
# members = db.query(TeamMember).filter(TeamMember.alias == 'dan***').all()
# for m in members[:-1]:  # Xóa tất cả trừ cái cuối
#     db.delete(m)
# db.commit()
# print('Done')
# db.close()
# "
```

Hoặc đơn giản hơn: xóa toàn bộ `team_members` và thêm lại từ đầu qua UI sau khi fix:

```sql
DELETE FROM team_members;
```

---

## 4. TÓM TẮT FILE CẦN SỬA

| File | Bug | Thay đổi |
|------|-----|----------|
| `static/team.js` | Bug 1, 3 | Sửa `fetchTeam()` dùng 2 API + thêm `deleteMember()` |
| `static/team.html` | Bug 3 | Thêm `<th>Hành động</th>` vào thead |
| `routers/team.py` | Bug 2, 3 | Thêm duplicate check + thêm `id` vào schema |

---

## 5. ĐỊNH NGHĨA DONE

- [ ] Thêm `dangkhoa@gmail.com` / `dan***` / T1 → xuất hiện ngay trong bảng sau khi lưu
- [ ] Thêm cùng username lần 2 → hiện thông báo lỗi rõ ràng, không duplicate
- [ ] Bảng Team hiển thị đúng: alias, role, rank, jade, delta, w_rate, proj, prize
- [ ] Nút Xóa hoạt động → xóa khỏi bảng ngay lập tức
- [ ] Thành viên không có trong BXH hôm nay → hiển thị `—` thay vì crash

---

*Brief này do Adam (PM) soạn sau khi test trực tiếp và đọc code. Tất cả 3 bug đã được xác định chính xác — không cần debug thêm, chỉ cần implement fix theo spec trên.*
