# Brief 13 — Fix thu*** Alias Collision + hun[TEAM] Badge
> PM: Adam | Dev: atigravity | Priority: P0  
> 2 bug độc lập, root cause đã xác định qua Chrome debug. Implement xong chạy refresh_stats.py.

---

## BUG 1 — thu*** delta/W.Rate sai do alias collision

### Root cause

`alias_resolver.py` **chưa có rule cho `thu***`**. Cả 2 người khác nhau đều được gán alias `"thu***"` → `prev_map["thu***"]` bị collision → delta tính nhầm người.

Bằng chứng từ DB:
- Snapshot 05/05: có **2 record** `thu***@gmail.com` — rank 7 jade=264K và rank 44 jade=35K
- Snapshot 04/05: `prev_map["thu***"]` chỉ giữ 1 record (jade 31K của rank 44)
- Delta rank 7 = 264K − 31K = **+233K** (sai — thực ra người jade cao tăng ~4K/ngày)
- W.Rate rank 7 = **121,012** (vô nghĩa)
- Proj 31/05 rank 7 = **3,411,310** (vô nghĩa → prize hiển thị $5,000 sai)

### Fix — `services/alias_resolver.py`

Thêm rule `thu***` vào `KNOWN_ALIASES`. Ngưỡng: jade > 200K là người cũ (rank 6-7), ≤ 200K là người mới (rank 40-60):

```python
KNOWN_ALIASES = {
    "mal***@gmail.com": lambda j: "mal[1]***" if j > 400000 else "mal[2]***",
    "tra***@gmail.com": lambda j: "tra[1]***" if j > 300000 else ("tra[2]***" if j > 50000 else "tra[3]***"),
    "qua***@gmail.com": lambda j: "qua[T2]***" if j > 25000 else "qua[farm]***",
    "kha***@gmail.com": lambda j: "kha[1]***" if j > 200000 else "kha[2]***",
    "rom***@gmail.com": lambda j: "rom[1]***" if j > 100000 else ("rom[2]***" if j > 30000 else "rom[3]***"),
    "ben***@gmail.com": lambda j: "ben[1]***" if j > 80000 else ("ben[2]***" if j > 30000 else "ben[3]***"),
    "hun***@gmail.com": lambda j: "hun[BXH]***" if j > 50000 else "hun[moi]***",
    "thu***@gmail.com": lambda j: "thu[1]***" if j > 200000 else "thu[2]***",  # THÊM DÒNG NÀY
}
```

### Sau khi sửa → chạy bắt buộc:

```bash
python refresh_stats.py
```

Lệnh này recalculate delta và W.Rate cho toàn bộ 25 snapshots với alias mới. Bắt buộc — không chạy thì data vẫn sai.

---

## BUG 2 — hun[TEAM] không có badge TEAM trên Dashboard

### Root cause

Dashboard hiển thị badge TEAM dựa trên field `is_team` trong bảng `rankings`. Field này được set bởi `refresh_stats.py` và `import_data.py` qua:

```python
team_map = {tm.username: tm for tm in team_members}
# ...
tm = team_map.get(r.username)
if tm:
    r.is_team = True
```

Vấn đề: `team_map` key bằng `username`. `hun***@gmail.com` có **2 người** trên BXH (rank 22 và rank 95). `team_map.get("hun***@gmail.com")` chỉ match được 1 trong 2 record rankings — không đảm bảo đúng người.

Cần lookup `is_team` theo **`bxh_rank`** khi thành viên có `bxh_rank` set, giống cách Brief 12 đã làm cho `/with-stats`.

### Fix — `refresh_stats.py` và `routers/import_data.py`

Sửa logic build `team_map` và set `is_team` trong **cả 2 file**:

#### Trong `refresh_stats.py` — tìm đoạn set is_team (khoảng dòng 13–20):

```python
# HIỆN TẠI:
team_members = db.query(TeamMember).all()
team_map = {tm.username: tm for tm in team_members}
# ...
for r in rankings:
    tm = team_map.get(r.username)
    if tm:
        r.is_team = True
        r.team_role = tm.role

# SỬA THÀNH:
team_members = db.query(TeamMember).all()
team_map_by_username = {tm.username: tm for tm in team_members}
team_map_by_rank = {tm.bxh_rank: tm for tm in team_members if tm.bxh_rank}

for r in rankings:
    # Ưu tiên match bằng bxh_rank (chính xác, không nhầm người)
    tm = team_map_by_rank.get(r.rank) or team_map_by_username.get(r.username)
    if tm:
        r.is_team = True
        r.team_role = tm.role
    else:
        r.is_team = False
        r.team_role = None
```

#### Trong `routers/import_data.py` — tìm đoạn build team_map và resolve (khoảng dòng 59–72):

```python
# HIỆN TẠI:
team_members = db.query(TeamMember).all()
team_map = {tm.username: {"alias": tm.alias, "role": tm.role} for tm in team_members}
# ...
alias, role, is_team = resolve_alias(item["username"], item["jade"], team_map)

# SỬA THÀNH:
team_members = db.query(TeamMember).all()
team_map_by_username = {tm.username: {"alias": tm.alias, "role": tm.role, "bxh_rank": tm.bxh_rank} for tm in team_members}
team_map_by_rank = {tm.bxh_rank: {"alias": tm.alias, "role": tm.role} for tm in team_members if tm.bxh_rank}

# Và trong vòng loop xử lý từng item, sau khi có item["rank"]:
# Check bằng rank trước
tm_by_rank = team_map_by_rank.get(item["rank"])
if tm_by_rank:
    alias = tm_by_rank["alias"]
    role = tm_by_rank["role"]
    is_team = True
else:
    alias, role, is_team = resolve_alias(item["username"], item["jade"], team_map_by_username)
```

---

## THỨ TỰ THỰC HIỆN

```
1. Sửa alias_resolver.py — thêm "thu***@gmail.com" rule
2. Sửa refresh_stats.py — team_map dùng bxh_rank
3. Sửa import_data.py — team_map dùng bxh_rank
4. python refresh_stats.py   ← BẮT BUỘC
5. Restart server
6. Verify
```

---

## VERIFY CHECKLIST

**Bug 1 — thu***:**
- [ ] `GET /api/dashboard` → rank 7 (`thu[1]***`): delta ~+4K (không phải +233K)
- [ ] rank 7 W.Rate ~5,000–8,000 (không phải 121,012)
- [ ] rank 7 proj_may31 hợp lý (~400K–500K, không phải 3.4M)
- [ ] rank 7 prize_est = `$1,000` (rank 6–10), không phải `$5,000`
- [ ] rank 44 (`thu[2]***`): delta và W.Rate độc lập, không bị ảnh hưởng bởi rank 7

**Bug 2 — hun[TEAM]:**
- [ ] Dashboard rank 95: có badge `TEAM`, highlight màu đúng
- [ ] `GET /api/dashboard` → rank 95 record có `is_team=true`, `team_role="T1"`
- [ ] Rank 22 (`hun[BXH]***`, không phải team): `is_team=false`, không có badge TEAM

**AG KHÔNG được báo "done" nếu chưa confirm delta rank 7 thu*** < 10,000 và rank 95 có is_team=true.**

---

## YÊU CẦU SAU KHI HOÀN THÀNH

Sau khi implement và verify xong, AG tạo file `Review_Report_Brief_13.md` trong thư mục project, ghi rõ:
- Từng file đã sửa và thay đổi cụ thể là gì
- Kết quả chạy verify checklist (từng item pass/fail)
- Bất kỳ phát hiện hoặc thay đổi nào ngoài scope brief (nếu có)
