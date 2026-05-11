# Brief 6 — Tracker: Sửa Alias + Fix Prize Logic
> PM: Adam | Dev: atigravity | Priority: P0  
> 2 task độc lập, implement cả 2 trong cùng 1 lần.

---

## TASK 1 — Thêm nút "Sửa Alias" ở màn hình Tracker

### Bối cảnh

Màn hình `/tracker` hiển thị cột `Alias` (frozen column thứ 2). Hiện không có cách nào sửa alias từ UI — người dùng muốn tự đặt tên alias theo ý mình cho từng user.

### Cơ chế lưu alias

Alias cần được lưu vào **`team_members` table** (không phải `rankings`). Lý do:
- `rankings` table có hàng trăm record cho mỗi user (mỗi snapshot 1 record) — không thể sửa alias ở đó
- `team_members` là single source of truth cho metadata user
- Trong `GET /api/tracker`, alias đã được lấy từ `r.alias` — cần thêm logic lấy alias từ `team_members` nếu có

### Các thay đổi cần làm

#### 1a. Thêm endpoint `PUT /api/alias` trong backend

**File:** `routers/team.py` (hoặc tạo `routers/alias.py` mới nếu muốn tách)

```python
from pydantic import BaseModel

class AliasUpdateSchema(BaseModel):
    username: str
    alias: str

@router.put("/alias")  # full path: /api/team-members/alias
async def update_alias(data: AliasUpdateSchema, db: Session = Depends(get_db)):
    # Tìm hoặc tạo mới team_member record
    member = db.query(TeamMember).filter(TeamMember.username == data.username).first()
    if member:
        member.alias = data.alias
    else:
        # Tạo record mới với role T2 (observer, không có trong team chính)
        member = TeamMember(username=data.username, alias=data.alias, role="T2")
        db.add(member)
    db.commit()
    return {"status": "success"}
```

**Lưu ý về routing:** Nếu đặt trong `routers/team.py` có prefix `/api/team-members`, endpoint sẽ là `PUT /api/team-members/alias`. Đảm bảo không conflict với `PUT /api/team-members/{member_id}` (int vs string path).

#### 1b. Cập nhật `GET /api/tracker` để dùng alias từ `team_members`

**File:** `routers/dashboard.py` — hàm `get_tracker()`

Thêm logic override alias từ `team_members` (ưu tiên alias từ team_members hơn alias trong rankings):

```python
@router.get("/tracker")
async def get_tracker(db: Session = Depends(get_db)):
    # ... code hiện tại giữ nguyên ...
    
    # THÊM: Build alias override map từ team_members
    team_members = db.query(TeamMember).all()
    alias_override = {tm.username: tm.alias for tm in team_members if tm.alias}
    
    # Sau khi build user_data, áp dụng alias override:
    for username, data in user_data.items():
        if username in alias_override:
            data["alias"] = alias_override[username]
    
    # ... phần sort và return giữ nguyên ...
```

#### 1c. Thêm nút Sửa vào cột Alias trong `tracker.js`

**File:** `static/tracker.js` — trong hàm `renderTable()`, phần render frozen cells

Sửa cell alias để có icon sửa inline:

```javascript
// Thay dòng:
<td class="col-alias">${user.alias}</td>

// Bằng:
<td class="col-alias">
    <span style="display:flex;align-items:center;gap:0.375rem">
        <span class="alias-text">${user.alias}</span>
        <button onclick="openAliasEdit('${user.username}', '${user.alias.replace(/'/g, "\\'")}')"
            title="Sửa alias"
            style="background:none;border:none;cursor:pointer;color:var(--text-muted);font-size:0.75rem;padding:0;line-height:1;opacity:0.6" 
            onmouseover="this.style.opacity='1'" 
            onmouseout="this.style.opacity='0.6'">
            ✏️
        </button>
    </span>
</td>
```

#### 1d. Thêm modal sửa alias + function vào `tracker.js`

**File:** `static/tracker.js` — thêm vào cuối file:

```javascript
function openAliasEdit(username, currentAlias) {
    const newAlias = prompt(`Sửa alias cho "${username}":\n(Hiện tại: ${currentAlias})`, currentAlias);
    if (newAlias === null || newAlias.trim() === '') return; // Cancelled or empty
    if (newAlias.trim() === currentAlias) return; // No change
    
    saveAlias(username, newAlias.trim());
}

async function saveAlias(username, alias) {
    try {
        const res = await fetch('/api/team-members/alias', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, alias })
        });
        if (res.ok) {
            // Update local data và re-render (không cần full reload)
            if (trackerData) {
                const user = trackerData.users.find(u => u.username === username);
                if (user) user.alias = alias;
                renderTable();
            }
        } else {
            alert("Lỗi khi lưu alias");
        }
    } catch (err) {
        console.error(err);
        alert("Lỗi kết nối");
    }
}
```

**Lưu ý:** Dùng `prompt()` (browser native dialog) cho đơn giản — không cần tạo thêm modal HTML.

#### 1e. Thêm HTML modal (không cần — dùng native `prompt()`)

Không cần sửa `tracker.html` cho tính năng này.

---

## TASK 2 — Fix Prize Logic

### Bối cảnh

Prize hiện tại đã đúng về logic (trong `services/calculator.py`). **Vấn đề thực tế:** prize được tính dựa trên `proj_rank` (rank dự kiến 31/05) chứ không phải `current_rank`. Tuy nhiên, prize **hiển thị trên Dashboard** lấy từ cột `prize_est` trong DB — được tính bởi `refresh_stats.py`.

Kiểm tra `estimate_prize()` trong `services/calculator.py`:

```python
def estimate_prize(rank):
    if rank == 1:
        return "$5,000"
    elif 2 <= rank <= 5:
        return "$2,000"
    elif 6 <= rank <= 10:
        return "$1,000"
    elif 11 <= rank <= 50:
        return "$200"
    elif 51 <= rank <= 100:
        return "$50"
    else:
        return "$0"
```

**Kết luận: Logic đã đúng 100%** theo bảng prize của Adam. Không cần sửa `calculator.py`.

### Vấn đề có thể xảy ra: Prize hiển thị "$0" hoặc sai

Nguyên nhân thường gặp:
1. `refresh_stats.py` chưa được chạy sau khi import data → `prize_est` = NULL trong DB
2. Frontend Dashboard hiển thị `prize_est` từ API nhưng format sai

### Fix cần làm

#### 2a. Kiểm tra DB xem prize_est có đúng không

Chạy query này và paste kết quả vào chat để PM verify:

```python
# check_prize.py — chạy 1 lần để verify
from database import SessionLocal, Snapshot, Ranking
from sqlalchemy import desc

db = SessionLocal()
latest = db.query(Snapshot).order_by(desc(Snapshot.date)).first()
print(f"Latest snapshot: {latest.date}")

rankings = db.query(Ranking).filter(Ranking.snapshot_id == latest.id).order_by(Ranking.rank).limit(15).all()
for r in rankings:
    print(f"  rank={r.rank} username={r.username[:15]:<15} proj={r.proj_may31} prize={r.prize_est}")
db.close()
```

#### 2b. Nếu prize_est NULL hoặc sai → chạy lại refresh_stats.py

```bash
python refresh_stats.py
```

#### 2c. Fix Dashboard frontend hiển thị prize

**File:** `static/dashboard.js` hoặc `static/index.html` — kiểm tra chỗ hiển thị prize cho từng user trong top 100.

Đảm bảo dùng đúng field: `r.prize_est` (không phải `r.prize` hay field nào khác).

Format hiển thị cần có màu xanh (success color):
```javascript
// Trong cell prize của bảng top 100:
`<td style="color:var(--success)">${r.prize_est || '—'}</td>`
```

---

## 3. THỨ TỰ THỰC HIỆN

1. **Task 2 trước** (nhanh hơn):
   - Chạy `check_prize.py` để verify data
   - Nếu cần: chạy `refresh_stats.py`
   - Fix frontend nếu display sai

2. **Task 1 sau**:
   - Thêm `PUT /api/team-members/alias` endpoint
   - Cập nhật `GET /api/tracker` để dùng alias override
   - Sửa `tracker.js` thêm ✏️ button và functions

3. Restart server
4. Verify checklist bên dưới

---

## 4. VERIFY CHECKLIST (bắt buộc trước khi báo done)

**Task 1 — Alias Edit:**
- [ ] Vào `/tracker`, hover vào cột Alias bất kỳ → thấy icon ✏️
- [ ] Bấm ✏️ → prompt hiện ra với alias hiện tại pre-filled
- [ ] Nhập alias mới → bảng update ngay không cần reload trang
- [ ] Reload trang → alias mới vẫn còn (đã lưu vào DB)
- [ ] Bấm Cancel → không có gì thay đổi

**Task 2 — Prize:**
- [ ] `GET /api/dashboard` → `top10` array, mỗi item có `prize_est` không null
- [ ] Rank #1 → `$5,000`
- [ ] Rank #2–5 → `$2,000`
- [ ] Rank #6–10 → `$1,000`
- [ ] Rank #11–50 → `$200`
- [ ] Rank #51–100 → `$50`
- [ ] Dashboard hiển thị prize đúng màu xanh

**AG KHÔNG được báo "done" nếu chưa chạy xong checklist.**

---

## 5. TÓM TẮT FILE CẦN SỬA

| File | Task | Thay đổi |
|------|------|----------|
| `routers/team.py` | 1 | Thêm `PUT /api/team-members/alias` endpoint |
| `routers/dashboard.py` | 1 | Thêm alias override từ team_members trong `get_tracker()` |
| `static/tracker.js` | 1 | Thêm ✏️ button vào cột alias, thêm `openAliasEdit()` + `saveAlias()` |
| `services/calculator.py` | 2 | **KHÔNG CẦN SỬA** — logic đã đúng |
| `refresh_stats.py` | 2 | Chạy lại nếu prize_est NULL trong DB |
| Dashboard frontend | 2 | Verify `prize_est` field được hiển thị đúng |

---

*Brief này do Adam (PM) soạn. Implement đúng spec, verify đủ checklist rồi mới báo done.*
