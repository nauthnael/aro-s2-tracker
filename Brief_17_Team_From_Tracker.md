# Brief 17 — Quản lý Team từ màn hình Tracker
> PM: Adam | Dev: atigravity | Priority: P1  
> Thiết kế đã được PM chốt. Không tự ý thay đổi logic.

---

## TỔNG QUAN

Thay đổi cách PM quản lý team: thay vì nhập thủ công form ở `/team`, PM sẽ tick/bỏ tick trực tiếp trên từng row ở `/tracker`. Màn hình `/team` chuyển thành read-only (chỉ xem, không sửa).

**Không thay đổi schema DB.** Bảng `team_members` giữ nguyên. Chỉ thay đổi UI + thêm API endpoint mới.

---

## THAY ĐỔI 1 — Backend: API mới `POST /api/team-members/set-team`

Thêm endpoint mới vào `routers/team.py`. Đây là endpoint trung tâm xử lý toàn bộ logic thêm/bỏ/đổi role.

```python
from sqlalchemy import and_

class SetTeamRequest(BaseModel):
    username: str       # full masked email, vd: dan***@gmail.com
    alias: str          # alias hiện tại từ rankings table — source of truth
    is_team: bool       # True = thêm vào team, False = loại khỏi team
    role: Optional[str] = None  # "T1" hoặc "T2" — chỉ cần khi is_team=True

@router.post("/set-team")
async def set_team_member(data: SetTeamRequest, db: Session = Depends(get_db)):
    """
    Thêm/loại/đổi role thành viên team.
    - Khi is_team=True:  upsert TeamMember, backfill is_team=True + team_role toàn bộ rankings theo alias
    - Khi is_team=False: xóa TeamMember, backfill is_team=False + team_role=None toàn bộ rankings theo alias
    - Alias lấy từ rankings table (không tự nhập) — TeamMember.alias luôn đồng bộ với rankings.alias
    """
    if data.is_team and not data.role:
        raise HTTPException(status_code=400, detail="Role (T1/T2) bắt buộc khi thêm vào team")
    if data.role and data.role not in ("T1", "T2"):
        raise HTTPException(status_code=400, detail="Role phải là T1 hoặc T2")

    if data.is_team:
        # Upsert TeamMember
        member = db.query(TeamMember).filter(TeamMember.username == data.username).first()
        if member:
            member.alias = data.alias   # đồng bộ alias từ tracker
            member.role = data.role
        else:
            member = TeamMember(
                username=data.username,
                alias=data.alias,
                role=data.role,
                bxh_rank=None,
                note=""
            )
            db.add(member)
        db.flush()

        # Backfill toàn bộ rankings theo alias — cập nhật is_team=True và team_role
        db.query(Ranking).filter(Ranking.alias == data.alias).update(
            {"is_team": True, "team_role": data.role},
            synchronize_session=False
        )

    else:
        # Xóa TeamMember nếu tồn tại
        member = db.query(TeamMember).filter(TeamMember.username == data.username).first()
        if member:
            db.delete(member)
        db.flush()

        # Backfill toàn bộ rankings theo alias — cập nhật is_team=False và team_role=None
        db.query(Ranking).filter(Ranking.alias == data.alias).update(
            {"is_team": False, "team_role": None},
            synchronize_session=False
        )

    db.commit()
    return {"status": "success"}
```

> **Lưu ý:** Backfill dùng `alias` làm key (không phải `username`) vì alias là unique identity xuyên suốt hệ thống từ Brief 16. Một alias = một người thật dù username có bị mask trùng.

---

## THAY ĐỔI 2 — Backend: Cập nhật `PUT /api/team-members/alias`

Endpoint alias edit hiện tại (Brief 6/16) cần thêm bước đồng bộ alias vào `TeamMember` khi alias thay đổi. Sửa trong `routers/team.py`:

```python
@router.put("/alias")
async def update_alias(data: AliasUpdateSchema, db: Session = Depends(get_db)):
    member = db.query(TeamMember).filter(TeamMember.username == data.username).first()
    if member:
        old_alias = member.alias
        member.alias = data.alias  # ← đồng bộ alias mới vào TeamMember
    else:
        old_alias = None
        member = TeamMember(username=data.username, alias=data.alias, role="T2")
        db.add(member)
    db.flush()

    # Update alias trong rankings — giữ nguyên logic cũ
    rankings_to_update = db.query(Ranking).filter(Ranking.username == data.username).all()
    updated_count = 0
    for r in rankings_to_update:
        if '[?]' in (r.alias or '') or r.alias == old_alias or r.alias == data.username:
            r.alias = data.alias
            updated_count += 1

    db.commit()
    return {"status": "success", "updated_rankings": updated_count}
```

*(Endpoint này về cơ bản giữ nguyên — chỉ đảm bảo `member.alias = data.alias` được set đúng khi member đã tồn tại.)*

---

## THAY ĐỔI 3 — Frontend `/tracker`: Thêm cột Team controls

### 3a. `tracker.html` — Thêm modal role picker

Thêm vào cuối `<body>`, trước `<script>`:

```html
<!-- Modal chọn role khi tick Team -->
<div id="team-role-modal" style="
    display:none; position:fixed; inset:0;
    background:rgba(0,0,0,0.6); z-index:1000;
    align-items:center; justify-content:center;
">
    <div style="
        background:var(--surface); border-radius:0.75rem;
        padding:1.5rem; min-width:280px;
        border:1px solid rgba(255,255,255,0.1);
    ">
        <h3 style="margin:0 0 1rem 0; font-size:1rem">Thêm vào Team</h3>
        <p id="team-modal-alias" style="color:var(--text-muted);font-size:0.875rem;margin:0 0 1rem 0"></p>
        <div style="display:flex; gap:1rem; margin-bottom:1.5rem">
            <label style="display:flex;align-items:center;gap:0.5rem;cursor:pointer">
                <input type="radio" name="team-role" value="T1" checked
                    style="accent-color:#3b82f6">
                <span>T1</span>
            </label>
            <label style="display:flex;align-items:center;gap:0.5rem;cursor:pointer">
                <input type="radio" name="team-role" value="T2"
                    style="accent-color:#3b82f6">
                <span>T2</span>
            </label>
        </div>
        <div style="display:flex;gap:0.75rem">
            <button onclick="confirmSetTeam()" class="btn btn-primary" style="flex:1">Xác nhận</button>
            <button onclick="cancelSetTeam()" class="btn" style="background:var(--background);flex:1">Hủy</button>
        </div>
    </div>
</div>
```

### 3b. `tracker.html` — Thêm cột header "Team"

Trong `renderTable()` ở `tracker.js`, header hiện tại inject bằng JS. Cột Team là frozen column — thêm vào ngay sau cột Alias trong phần header inject:

```javascript
// Trong hàm renderTable(), đoạn render headerRow — THÊM th Team sau th Alias:
headerRow.innerHTML = `
    <th class="col-rank frozen">Rank</th>
    <th class="col-alias frozen">Alias</th>
    <th class="col-team frozen" style="text-align:center;min-width:90px">Team</th>
    <th class="col-wrate frozen">W.Rate</th>
    <th class="col-proj frozen">Proj 31/05</th>
    <th class="col-prize frozen">Prize</th>
`;
```

### 3c. `tracker.js` — Thêm cell Team vào mỗi row

Trong `renderTable()`, phần render frozen cells của mỗi user, thêm cell Team **sau cell alias**:

```javascript
// Sau cell col-alias, thêm:
const isTeam = user.is_team;
const role = user.team_role;  // "T1", "T2", hoặc null

cells += `
    <td class="col-team" style="text-align:center;vertical-align:middle">
        <div style="display:flex;align-items:center;justify-content:center;gap:0.4rem">
            <input type="checkbox"
                id="chk-team-${user.username.replace(/[^a-z0-9]/gi,'_')}"
                ${isTeam ? 'checked' : ''}
                onchange="handleTeamToggle(this, '${user.username}', '${user.alias.replace(/'/g, "\\'")}')"
                style="width:14px;height:14px;cursor:pointer;accent-color:#3b82f6">
            ${isTeam ? `<span style="font-size:0.7rem;color:${role === 'T1' ? '#3b82f6' : '#a78bfa'};font-weight:600">${role}</span>` : ''}
        </div>
    </td>
`;
```

### 3d. `tracker.js` — Các function xử lý Team toggle

Thêm vào cuối file (trước event listeners):

```javascript
// ─── TEAM MANAGEMENT ──────────────────────────────────────────────────────────

let pendingTeamAction = null; // { username, alias, checkbox }

function handleTeamToggle(checkbox, username, alias) {
    if (checkbox.checked) {
        // Tick → mở modal chọn role
        pendingTeamAction = { username, alias, checkbox };
        document.getElementById('team-modal-alias').textContent = `Alias: ${alias}`;
        // Reset radio về T1
        document.querySelector('input[name="team-role"][value="T1"]').checked = true;
        const modal = document.getElementById('team-role-modal');
        modal.style.display = 'flex';
    } else {
        // Bỏ tick → loại khỏi team ngay, không cần modal
        setTeamMember(username, alias, false, null, checkbox);
    }
}

function confirmSetTeam() {
    if (!pendingTeamAction) return;
    const role = document.querySelector('input[name="team-role"]:checked').value;
    const { username, alias, checkbox } = pendingTeamAction;
    document.getElementById('team-role-modal').style.display = 'none';
    setTeamMember(username, alias, true, role, checkbox);
    pendingTeamAction = null;
}

function cancelSetTeam() {
    if (pendingTeamAction) {
        // Revert checkbox về trạng thái cũ
        pendingTeamAction.checkbox.checked = false;
        pendingTeamAction = null;
    }
    document.getElementById('team-role-modal').style.display = 'none';
}

async function setTeamMember(username, alias, isTeam, role, checkbox) {
    try {
        const res = await fetch('/api/team-members/set-team', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, alias, is_team: isTeam, role })
        });

        if (res.ok) {
            // Cập nhật local data để re-render không cần reload
            if (trackerData) {
                const user = trackerData.users.find(u => u.username === username);
                if (user) {
                    user.is_team = isTeam;
                    user.team_role = isTeam ? role : null;
                }
            }
            renderTable();
        } else {
            // Revert checkbox nếu lỗi
            checkbox.checked = !isTeam;
            const err = await res.json();
            alert('Lỗi: ' + (err.detail || 'Không thể cập nhật team'));
        }
    } catch (err) {
        checkbox.checked = !isTeam;
        console.error(err);
        alert('Lỗi kết nối');
    }
}
```

> **Lưu ý `trackerData.users`:** Hiện tại `trackerData.users` là object `{0: {...}, 1: {...}, ...}` (không phải array). Hàm `.find()` sẽ lỗi. Phải dùng `Object.values(trackerData.users).find(...)`. AG kiểm tra kỹ chỗ này.

---

## THAY ĐỔI 4 — Frontend `/team`: Chuyển sang read-only

### 4a. `team.html` — Xóa modal và nút thêm thành viên

Xóa toàn bộ:
- Nút `+ Thêm Thành Viên`
- Toàn bộ `<div id="member-modal">...</div>`
- Cột "Hành động" trong `<thead>`

Header bảng sau khi sửa:
```html
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
</tr>
```

Tiêu đề card sửa lại:
```html
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
    <h2>Danh sách Team</h2>
    <a href="/tracker" style="font-size:0.8rem;color:var(--text-muted)">
        ← Quản lý team tại Tracker
    </a>
</div>
```

### 4b. `team.js` — Xóa các function không còn dùng

Xóa hoàn toàn các function:
- `editMember()`
- `showMemberModal()`
- `hideMemberModal()`
- `saveMember()`
- `deleteMember()`

Giữ lại toàn bộ: `fetchTeam()`, `renderTeam()`, `sortMembers()`, `attachSortListeners()`, `updateSortIcons()`, `updatePrizeBanner()`, `getRoleBadge()`, `formatNumber()`, `parsePrize()`.

Trong `renderTeam()`, xóa cell "Hành động" khỏi `row.innerHTML`. Đổi `colspan="10"` thành `colspan="9"` ở row "Chưa có thành viên".

---

## THỨ TỰ THỰC HIỆN

```
1. routers/team.py        — Thêm POST /api/team-members/set-team
2. tracker.html           — Thêm modal role picker
3. tracker.js             — Thêm col-team header, cell, và 4 functions
4. team.html              — Xóa nút/modal, đổi tiêu đề, xóa cột Hành động
5. team.js                — Xóa 5 functions, xóa cell Hành động, fix colspan
6. Restart server
7. Verify checklist
```

---

## VERIFY CHECKLIST

**Tracker — Thêm vào team:**
- [ ] Mỗi row có checkbox ở cột Team, member hiện tại đã tick sẵn, hiển thị badge T1/T2
- [ ] Tick checkbox người chưa có trong team → modal hiện ra với alias đúng, radio T1 checked mặc định
- [ ] Chọn T2 → Xác nhận → row đổi màu `row-team`, badge T2 xuất hiện
- [ ] Mở `/team` → thành viên mới xuất hiện đúng trong danh sách
- [ ] Hủy modal → checkbox revert về unchecked, không có gì thay đổi

**Tracker — Loại khỏi team:**
- [ ] Bỏ tick checkbox thành viên hiện tại → không có modal, xóa ngay
- [ ] Row đổi màu về bình thường, badge biến mất
- [ ] Mở `/team` → thành viên đó không còn trong danh sách
- [ ] Vào DB kiểm tra: toàn bộ `rankings` records theo alias đó có `is_team=false`

**Tracker — Đổi role:**
- [ ] Bỏ tick → tick lại → chọn role khác → badge cập nhật đúng
- [ ] Vào DB kiểm tra: toàn bộ `rankings` records theo alias đó có `team_role` đúng

**Backfill:**
- [ ] Thêm `dan***@gmail.com` vào team → query DB:
  `SELECT COUNT(*) FROM rankings WHERE alias='dan***' AND is_team=1`
  → phải bằng tổng số snapshot hiện có (26)
- [ ] Xóa `dan***@gmail.com` khỏi team → query DB:
  `SELECT COUNT(*) FROM rankings WHERE alias='dan***' AND is_team=0`
  → phải bằng 26

**Team page read-only:**
- [ ] Không có nút "+ Thêm Thành Viên"
- [ ] Không có cột "Hành động"
- [ ] Không có modal
- [ ] Có link "← Quản lý team tại Tracker"
- [ ] Sort, prize banner vẫn hoạt động bình thường

**Alias đồng bộ:**
- [ ] Sửa alias ✏️ trên tracker cho một user đang là team member
  → Vào `/team` → alias mới hiển thị đúng (TeamMember đã cập nhật)

**Regression:**
- [ ] Filter "Team nau***" trên tracker vẫn hoạt động đúng
- [ ] Dashboard vẫn hiển thị badge TEAM đúng người

---

## YÊU CẦU SAU KHI HOÀN THÀNH

AG tạo file `Review_Report_Brief_17.md` trong thư mục project, ghi rõ:
- Từng file đã sửa và thay đổi cụ thể
- Kết quả verify từng item trong checklist (pass/fail)
- Kết quả query DB backfill (số lượng records được update)
- Bất kỳ phát hiện hoặc thay đổi nào ngoài scope brief
