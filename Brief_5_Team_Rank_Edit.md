# Brief 5 — Team: Thêm bxh_rank + Tính năng Edit
> PM: Adam | Dev: atigravity | Priority: P0  
> Mục tiêu: Xử lý trường hợp 2 thành viên có cùng masked username (vd: `qua***@gmail.com`),  
> đồng thời thêm khả năng chỉnh sửa thành viên trong bảng Team.

---

## 1. BỐI CẢNH

Hiện tại stats lookup trong `team.js` match theo `username`. Vấn đề: BXH dùng masked email
(`qua***@gmail.com`), nên 2 người khác nhau có thể cùng hiện thị là `qua***@gmail.com`.  
→ Không thể phân biệt bằng username.

**Giải pháp đã được PM duyệt:** Thêm field `bxh_rank` (rank hiện tại trên BXH) vào `team_members`.
Khi fetch stats, lookup bằng **rank** thay vì username — rank là duy nhất trong mỗi snapshot.

---

## 2. THAY ĐỔI CẦN IMPLEMENT

### 2.1 — DB: Thêm cột `bxh_rank`

**File:** `database.py`

Thêm column vào model `TeamMember`:
```python
bxh_rank = Column(Integer, nullable=True)
```

**Migration:** Vì dùng SQLite + SQLAlchemy không có Alembic, chạy SQL trực tiếp:
```python
# Thêm vào cuối file database.py, trong block if __name__ == "__main__":
# HOẶC tạo script migrate_add_bxh_rank.py riêng:

from database import engine
with engine.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE team_members ADD COLUMN bxh_rank INTEGER"))
        conn.commit()
        print("Column bxh_rank added successfully")
    except Exception as e:
        print(f"Already exists or error: {e}")
```

Tạo file `migrate_add_bxh_rank.py` và chạy 1 lần: `python migrate_add_bxh_rank.py`

---

### 2.2 — Backend: Cập nhật Pydantic Schema và API

**File:** `routers/team.py`

Cập nhật `TeamMemberSchema` để include `bxh_rank`:
```python
class TeamMemberSchema(BaseModel):
    id: Optional[int] = None
    username: str
    alias: str
    role: str
    bxh_rank: Optional[int] = None    # THÊM DÒNG NÀY
    join_date: Optional[date] = None
    note: Optional[str] = None

    class Config:
        from_attributes = True
```

Không cần sửa gì thêm ở các endpoint — schema đã handle tất cả.

---

### 2.3 — Frontend: Sửa `fetchTeam()` để lookup bằng rank

**File:** `static/team.js`

Thay toàn bộ hàm `fetchTeam()` bằng version mới dưới đây:

```javascript
async function fetchTeam() {
    try {
        // Lấy roster từ team_members table
        const rosterRes = await fetch('/api/team-members');
        const roster = await rosterRes.json();

        // Lấy toàn bộ leaderboard hôm nay để lấy stats
        const dashRes = await fetch('/api/dashboard');
        const dash = await dashRes.json();
        const allRankings = dash.top10 || []; // top10 key thực ra là top 100

        // Build stats map theo RANK (không phải username) để xử lý duplicate masked email
        const statsMap = {};
        allRankings.forEach(r => { statsMap[r.rank] = r; });

        const teamBody = document.getElementById('team-body');
        teamBody.innerHTML = '';

        if (roster.length === 0) {
            teamBody.innerHTML = '<tr><td colspan="10" style="text-align:center;color:var(--text-muted)">Chưa có thành viên. Bấm "+ Thêm Thành Viên" để thêm.</td></tr>';
            return;
        }

        roster.forEach(member => {
            // Lookup bằng bxh_rank nếu có, fallback về username
            const s = (member.bxh_rank ? statsMap[member.bxh_rank] : null) 
                      || statsMap[member.username] 
                      || {};
            const row = document.createElement('tr');
            if (member.role === 'LEADER') row.className = 'row-nau';
            else if (member.role === 'T1') row.className = 'row-team';

            row.innerHTML = `
                <td>${member.alias}</td>
                <td><span class="badge ${getRoleBadge(member.role)}">${member.role}</span></td>
                <td>${s.rank ? '#' + s.rank : (member.bxh_rank ? '#' + member.bxh_rank : '—')}</td>
                <td>${formatNumber(s.jade)}</td>
                <td class="${(s.delta || 0) >= 0 ? 'positive' : 'negative'}">
                    ${s.delta !== null && s.delta !== undefined ? (s.delta >= 0 ? '+' : '') + formatNumber(s.delta) : '—'}
                </td>
                <td>${s.w_rate !== null && s.w_rate !== undefined ? formatNumber(Math.round(s.w_rate)) : '—'}</td>
                <td>${formatNumber(s.proj_may31)}</td>
                <td style="color:var(--success)">${s.prize_est || '—'}</td>
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

---

### 2.4 — Frontend: Thêm Edit functions vào `team.js`

**File:** `static/team.js`

Thêm biến global và các hàm sau (đặt sau `fetchTeam()`):

```javascript
// Track edit mode
let editingMemberId = null;

async function editMember(memberId) {
    // Lấy data member hiện tại
    const res = await fetch('/api/team-members');
    const members = await res.json();
    const member = members.find(m => m.id === memberId);
    if (!member) { alert("Không tìm thấy thành viên"); return; }

    // Pre-fill modal
    document.getElementById('member-username').value = member.username;
    document.getElementById('member-alias').value = member.alias;
    document.getElementById('member-role').value = member.role;
    document.getElementById('member-rank').value = member.bxh_rank || '';
    document.getElementById('member-note').value = member.note || '';

    // Đổi sang edit mode
    editingMemberId = memberId;
    document.getElementById('modal-title').textContent = 'Sửa Thành Viên';
    document.getElementById('save-member-btn').textContent = 'Cập Nhật';
    
    showMemberModal();
}

function showMemberModal() {
    document.getElementById('member-modal').style.display = 'flex';
}

function hideMemberModal() {
    document.getElementById('member-modal').style.display = 'none';
    // Reset về add mode
    editingMemberId = null;
    document.getElementById('modal-title').textContent = 'Thêm Thành Viên';
    document.getElementById('save-member-btn').textContent = 'Lưu';
    // Clear fields
    document.getElementById('member-username').value = '';
    document.getElementById('member-alias').value = '';
    document.getElementById('member-role').value = 'T1';
    document.getElementById('member-rank').value = '';
    document.getElementById('member-note').value = '';
}

async function saveMember() {
    const username = document.getElementById('member-username').value.trim();
    const alias = document.getElementById('member-alias').value.trim();
    const role = document.getElementById('member-role').value;
    const bxh_rank = document.getElementById('member-rank').value 
                     ? parseInt(document.getElementById('member-rank').value) 
                     : null;
    const note = document.getElementById('member-note').value.trim();

    if (!username || !alias) {
        alert("Vui lòng điền đủ Username và Alias");
        return;
    }

    try {
        let response;
        if (editingMemberId) {
            // UPDATE
            response = await fetch(`/api/team-members/${editingMemberId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, alias, role, bxh_rank, note })
            });
        } else {
            // CREATE
            response = await fetch('/api/team-members', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, alias, role, bxh_rank, note })
            });
        }

        if (response.ok) {
            hideMemberModal();
            fetchTeam();
        } else {
            const err = await response.json();
            alert("Lỗi: " + (err.detail || "Không thể lưu thành viên"));
        }
    } catch (err) {
        console.error(err);
    }
}
```

**Lưu ý:** Xóa hàm `showMemberModal()` và `hideMemberModal()` cũ (nếu có) để tránh duplicate — version mới đã include reset logic.

---

### 2.5 — Frontend: Thêm field Rank vào Modal

**File:** `static/team.html`

Thêm field `bxh_rank` vào form (đặt sau field Role):

```html
<div>
    <label>Role:</label>
    <select id="member-role" class="btn" style="width: 100%; text-align: left; background: var(--background); color: white; border: 1px solid var(--surface)">
        <option value="LEADER">LEADER</option>
        <option value="T1">T1</option>
        <option value="T2">T2</option>
    </select>
</div>
<div>
    <label>Rank trên BXH:</label>
    <input type="number" id="member-rank" placeholder="Vd: 37" min="1" max="100"
        class="btn" style="width: 100%; text-align: left; background: var(--background); color: white; border: 1px solid var(--surface)">
    <small style="color:var(--text-muted);font-size:0.75rem;display:block;margin-top:0.25rem">
        ⚠️ Bắt buộc nếu có 2 người cùng hiển thị giống nhau trên BXH
    </small>
</div>
```

Cũng update label username cho rõ hơn:
```html
<label>Username ARO (từ BXH, vd: dan***@gmail.com):</label>
```

Và thêm cột header "Hành động" đã có đủ 10 cột (có thêm cột Sửa):
```html
<!-- thead giữ nguyên, không cần sửa — đã có cột "Hành động" từ Brief 4 -->
```

---

## 3. THỨ TỰ THỰC HIỆN

1. Tạo và chạy `migrate_add_bxh_rank.py`
2. Sửa `database.py` — thêm column vào model
3. Sửa `routers/team.py` — thêm `bxh_rank` vào schema
4. Sửa `static/team.js` — replace `fetchTeam()`, thêm `editMember()`, update `saveMember()`, update `hideMemberModal()`
5. Sửa `static/team.html` — thêm field rank vào modal
6. Restart server
7. **Verify bắt buộc trước khi báo done:**

---

## 4. VERIFY CHECKLIST (AG phải test từng cái trước khi báo done)

```
GET /api/team-members → response có field "bxh_rank" không?
```

Test UI:
- [ ] Thêm `dan***@gmail.com` / alias `dan***` / T1 / rank `5` → xuất hiện trong bảng với rank #5
- [ ] Thêm cùng username lần 2 → hiện lỗi "đã tồn tại", không duplicate
- [ ] Bấm "Sửa" → modal mở với data pre-filled đầy đủ (kể cả rank)
- [ ] Sửa rank → lưu → bảng reload với rank mới
- [ ] Thêm 2 thành viên cùng masked username khác rank (vd: rank 37 và rank 95) → cả 2 hiện đúng stats riêng
- [ ] Thành viên không có `bxh_rank` (null) → fallback lookup bằng username, không crash

**AG KHÔNG được báo "done" nếu chưa chạy xong checklist này.**

---

## 5. TÓM TẮT FILE CẦN SỬA

| File | Thay đổi |
|------|----------|
| `migrate_add_bxh_rank.py` | TẠO MỚI — chạy 1 lần để ALTER TABLE |
| `database.py` | Thêm `bxh_rank = Column(Integer, nullable=True)` vào model TeamMember |
| `routers/team.py` | Thêm `bxh_rank: Optional[int] = None` vào TeamMemberSchema |
| `static/team.js` | Replace `fetchTeam()` (lookup by rank), thêm `editMember()`, update `saveMember()` + `hideMemberModal()` |
| `static/team.html` | Thêm input field `member-rank` vào modal form |

---

*Brief này do Adam (PM) soạn. Implement đúng spec, verify đủ checklist rồi mới báo done.*
