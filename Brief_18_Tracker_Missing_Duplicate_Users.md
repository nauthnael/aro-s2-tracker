# Brief 18 — Fix Tracker thiếu user do duplicate username keyed by username
> PM: Adam | Dev: atigravity | Priority: P0  
> Root cause đã xác định qua Chrome debug + đọc source code. Chỉ sửa 1 file: `routers/dashboard.py`.

---

## ROOT CAUSE

Hàm `get_tracker()` trong `routers/dashboard.py` build `user_data` dict với key là **`username`**:

```python
user_data = {}  # username -> {meta, history}

for r in all_rankings:
    if r.username not in user_data:
        user_data[r.username] = { ... }
```

Khi 2 người khác nhau có cùng `username` (vd: `mal***@gmail.com` → `mal[1]***` jade 661K và `mal[2]***` jade 31K), dict chỉ giữ **1 entry** cho key `mal***@gmail.com`. Người nào được insert trước giữ slot, người kia bị ghi đè hoàn toàn — mất hẳn khỏi Tracker.

**Đã xác nhận qua Chrome:**
- `mal[1]***` (rank 3, jade 661K) — **không tồn tại** trong tracker response
- `thu[1]***` (rank 7, jade ~264K) — **không tồn tại** trong tracker response  
- Thay vào đó `mal***@gmail.com` chỉ có 1 entry với alias `mal[2]***` (rank 51)
- `thu***@gmail.com` chỉ có 1 entry với alias `qua[TEAM]` (rank 35, người lạ bị gán nhầm từ bug cũ)
- Dashboard (`/api/dashboard`) đọc thẳng từ rankings table theo rank → vẫn thấy rank 3 và rank 7 đúng

**Vấn đề thứ hai:** Alias override ở cuối hàm cũng dùng username làm key:
```python
alias_override = {tm.username: tm.alias for tm in team_members if tm.alias}
for username, data in user_data.items():
    if username in alias_override:
        data["alias"] = alias_override[username]
```
Cùng vấn đề — nếu TeamMember có `mal***@gmail.com` thì chỉ override được 1 trong 2 người.

---

## FIX — `routers/dashboard.py`, hàm `get_tracker()`

**Đổi key của `user_data` từ `username` sang `alias`.**

Alias là unique identity của từng người thật (được đảm bảo bởi `alias_resolver.py` từ Brief 16). Hai người cùng `username` luôn có alias khác nhau (`mal[1]***` vs `mal[2]***`).

### Thay toàn bộ đoạn build `user_data` (Pass 1):

```python
# HIỆN TẠI — key bằng username (SAI khi duplicate):
user_data = {}
for r in all_rankings:
    date_str = snap_id_to_date.get(r.snapshot_id)
    if date_str is None:
        continue
    if r.username not in user_data:
        user_data[r.username] = {
            "username": r.username,
            "alias": r.alias or r.username,
            ...
        }
    user_data[r.username]["history"][date_str] = { ... }
    if r.snapshot_id == latest_snapshot_id:
        user_data[r.username]["current_rank"] = r.rank ...

# SỬA THÀNH — key bằng alias (ĐÚNG):
user_data = {}
for r in all_rankings:
    date_str = snap_id_to_date.get(r.snapshot_id)
    if date_str is None:
        continue

    # Dùng alias làm key — unique per person kể cả khi username trùng
    # Fallback: nếu alias null thì dùng username (không nên xảy ra sau Brief 16)
    key = r.alias if r.alias else r.username

    if key not in user_data:
        user_data[key] = {
            "username": r.username,
            "alias": key,
            "is_team": False,
            "team_role": None,
            "current_rank": 999,
            "current_jade": 0,
            "w_rate": 0.0,
            "proj_may31": 0,
            "prize_est": "$0",
            "history": {}
        }

    # Add history entry
    user_data[key]["history"][date_str] = {
        "rank": r.rank,
        "jade": r.jade,
        "delta": r.delta,
        "t1_refs": r.t1_refs or 0,
        "t2_refs": r.t2_refs or 0,
        "delta_t1": None,
        "delta_t2": None,
        "is_delayed": snap_id_to_delayed.get(r.snapshot_id, False)
    }

    # Update alias/team info từ data mới nhất (alias có thể thay đổi qua các snapshot)
    if r.alias:
        user_data[key]["alias"] = r.alias
    if r.is_team:
        user_data[key]["is_team"] = True
        user_data[key]["team_role"] = r.team_role

    # Current metrics từ latest snapshot
    if r.snapshot_id == latest_snapshot_id:
        user_data[key]["current_rank"] = r.rank if r.rank else 999
        user_data[key]["current_jade"] = r.jade or 0
        user_data[key]["w_rate"] = r.w_rate or 0.0
        user_data[key]["proj_may31"] = r.proj_may31 or 0
        user_data[key]["prize_est"] = r.prize_est or "$0"
```

### Thay đoạn alias override (Pass 4 — sau Pass 2 delta_t1/t2):

```python
# HIỆN TẠI — override bằng username key (SAI):
alias_override = {tm.username: tm.alias for tm in team_members if tm.alias}
for username, data in user_data.items():
    if username in alias_override:
        data["alias"] = alias_override[username]

# SỬA THÀNH — override bằng alias key (không cần nữa vì alias đã đúng từ rankings):
# Alias override từ TeamMember chỉ cần cho trường hợp alias trong rankings bị null
# Với key-by-alias, alias đã được set đúng từ rankings rồi
# Chỉ cần update is_team/team_role nếu TeamMember có thông tin mới hơn rankings:
team_members = db.query(TeamMember).all()
tm_alias_map = {tm.alias: tm for tm in team_members if tm.alias}

for key, data in user_data.items():
    if key in tm_alias_map:
        tm = tm_alias_map[key]
        # Nếu rankings chưa set is_team (do snapshot cũ chưa backfill), set từ TeamMember
        if not data["is_team"]:
            data["is_team"] = True
            data["team_role"] = tm.role
```

### Pass 2 (delta_t1/t2) và Pass 5 (sort) — giữ nguyên logic, chỉ đổi variable name:

```python
# Pass 2 — đổi `username` thành `key` cho nhất quán:
for key, data in user_data.items():
    sorted_dates = sorted(data["history"].keys())
    for i, date_str in enumerate(sorted_dates):
        if i == 0:
            data["history"][date_str]["delta_t1"] = None
            data["history"][date_str]["delta_t2"] = None
        else:
            prev_date = sorted_dates[i - 1]
            prev = data["history"][prev_date]
            curr = data["history"][date_str]
            curr["delta_t1"] = curr["t1_refs"] - prev["t1_refs"]
            curr["delta_t2"] = curr["t2_refs"] - prev["t2_refs"]

# Sort và return — giữ nguyên:
users_list = list(user_data.values())
users_list.sort(key=lambda x: x["current_rank"])
return { "dates": dates, "snapshots": snapshots_out, "users": users_list }
```

---

## LƯU Ý QUAN TRỌNG

**`tracker.js` không cần sửa** — frontend dùng `user.username` để gọi API alias edit và team toggle. Các field `username`, `alias` vẫn có đủ trong mỗi user object, chỉ là key của dict thay đổi ở backend, không ảnh hưởng JSON trả về.

**`saveAlias()` trong `tracker.js`** gọi `PUT /api/team-members/alias` với `username` — vẫn đúng vì endpoint đó nhận username.

**`setTeamMember()` trong `tracker.js`** gọi `POST /api/team-members/set-team` với `username` và `alias` — vẫn đúng.

---

## THỨ TỰ THỰC HIỆN

```
1. Sửa routers/dashboard.py — get_tracker() theo spec trên
2. Restart server
3. Verify checklist
```

---

## VERIFY CHECKLIST

**Rank 3 và Rank 7 xuất hiện lại:**
- [ ] Mở `/tracker` → thấy `mal[1]***` ở rank 3 (jade ~661K)
- [ ] Mở `/tracker` → thấy `thu[1]***` ở rank 7 (jade ~264K)
- [ ] Tổng số users trong tracker ≈ đúng (không tăng vô lý do duplicate entry)

**Duplicate username được tách đúng:**
- [ ] `mal[1]***` và `mal[2]***` là 2 row riêng biệt, jade khác nhau rõ ràng
- [ ] `thu[1]***` và `thu[2]***` là 2 row riêng biệt
- [ ] `hun[BXH]***` và `hun[moi]***` là 2 row riêng biệt (nếu cả 2 đang trong top 100)

**Data đúng:**
- [ ] `mal[1]***`: rank 3, jade ~661K, history đầy đủ từ ngày đầu
- [ ] `mal[2]***`: rank ~51, jade ~31K, history riêng không bị lẫn
- [ ] Filter "Team nau***" vẫn hiển thị đúng team members

**Regression:**
- [ ] Search theo alias vẫn hoạt động
- [ ] Alias edit ✏️ vẫn hoạt động
- [ ] Team checkbox vẫn hoạt động
- [ ] Dashboard không bị ảnh hưởng (đọc từ rankings trực tiếp, không qua get_tracker)

---

## YÊU CẦU SAU KHI HOÀN THÀNH

AG tạo file `Review_Report_Brief_18.md` trong thư mục project, ghi rõ:
- Xác nhận đã sửa `get_tracker()` đổi key từ `username` sang `alias`
- Kết quả verify checklist (pass/fail từng item)
- Tổng số users trong tracker trước và sau fix
- Bất kỳ phát hiện hoặc thay đổi nào ngoài scope brief
