# Brief 16 — Alias Disambiguation Overhaul: Sequential Matching
> PM: Adam | Dev: atigravity | Priority: P0  
> Thiết kế đã được PM chốt sau phân tích kỹ. Không tự ý thay đổi phương án.

---

## BỐI CẢNH & VẤN ĐỀ

### Lỗi phát hiện ngày 06/05

**Rank 35:** `thu***@gmail.com` (người lạ) bị gán alias `qua[TEAM]` vì `team_map_by_rank.get(35)` trả về team member `qua***` — người hôm qua ở rank 35, hôm nay trượt xuống rank 36.

**Rank 94–95:** `huy***@gmail.com` (người lạ) bị gán alias `hun[TEAM]` vì `team_map_by_rank.get(95)` trả về team member `hun***` — người hôm nay leo từ rank 95 lên rank 94.

### Root cause gốc rễ

`bxh_rank` trong TeamMember là **số tĩnh**, nhưng rank BXH thay đổi hàng ngày. Khi team member thay đổi rank, người lạ chiếm rank cũ → bị nhận nhầm. Không thể fix bằng cách update bxh_rank thủ công mỗi ngày — đây là thiết kế sai về bản chất.

### Vấn đề thứ hai: duplicate masked username

BXH mask email → nhiều người khác nhau có cùng `username` hiển thị (vd: 2 người cùng `thu***@gmail.com`). Hệ thống hiện dùng jade threshold cứng trong `KNOWN_ALIASES` — phải update thủ công mỗi khi phát hiện case mới, và ngưỡng có thể sai khi jade người thứ 2 tăng dần.

---

## PHƯƠNG ÁN ĐÃ CHỐT

### Core: Sequential matching (Phương án C)

Khi snapshot mới có N record cùng `username`, tìm N record cùng `username` đó trong prev snapshot, ghép cặp bằng **minimize cost function**:

```
cost(new_i, prev_j) = |new_i.jade - prev_j.jade|
                    + (|new_i.refs - prev_j.refs| nếu refs khác nhau, else 0)
```

Trong đó `refs = t1_refs + t2_refs`.

**Tiebreaker bằng refs:** Chỉ áp dụng khi 2 người có ref count **khác nhau**. Nếu ref count bằng nhau → bỏ qua, chỉ dùng jade. Ref count không bao giờ giảm nên là signal hợp lệ.

**Với 3+ người cùng username:** Dùng greedy matching — lặp lại: chọn cặp (new_i, prev_j) có cost thấp nhất, ghép và loại khỏi pool, tiếp tục đến hết.

### Fallback theo thứ tự

```
Tầng 1 — Sequential matching:   Có ≥ N record trong prev snapshot cùng username → chạy matching
Tầng 2 — KNOWN_ALIASES:         Không đủ lịch sử → dùng jade/rank threshold đã cấu hình
Tầng 3 — Alert + alias [?]:     Không có rule → gán alias tạm, tạo Alert YELLOW
```

### Confidence check & Alert

Sau khi ghép cặp ở Tầng 1, kiểm tra confidence:
- Tính `best_cost` (cặp được chọn) và `second_best_cost` (cặp tốt nhì)
- Nếu `(second_best_cost - best_cost) / max(new_i.jade, 1) < 0.20` → Alert YELLOW "Ghép cặp không chắc"

### Bỏ `team_map_by_rank` khỏi import pipeline

`bxh_rank` giữ trong DB và UI `/team` để PM tham khảo, nhưng **không dùng để match trong import**. Match team member chỉ bằng `username` exact match.

---

## IMPLEMENT

### 1. `services/alias_resolver.py` — Viết lại hoàn toàn

```python
def _compute_cost(new_jade, new_refs, prev_jade, prev_refs):
    """
    Cost function để ghép cặp. Thấp hơn = tốt hơn.
    Refs chỉ dùng làm tiebreaker khi khác nhau.
    """
    jade_diff = abs(new_jade - prev_jade)
    if new_refs != prev_refs:
        refs_diff = abs(new_refs - prev_refs) * 1000  # weight nhỏ, chỉ là tiebreaker
    else:
        refs_diff = 0
    return jade_diff + refs_diff


def sequential_match(new_records, prev_records):
    """
    Ghép N new_records với M prev_records bằng greedy matching.
    
    new_records: list of dict {username, jade, refs, rank, ...}
    prev_records: list of dict {alias, jade, refs, ...} — từ prev snapshot cùng username
    
    Return: list of (new_record, prev_record_or_None, confidence_ok: bool)
    """
    if not prev_records:
        return [(r, None, False) for r in new_records]

    results = []
    remaining_prev = list(prev_records)

    # Greedy: lặp cho đến khi hết new_records hoặc hết prev_records
    remaining_new = list(new_records)

    while remaining_new and remaining_prev:
        best_cost = float('inf')
        best_new_idx = 0
        best_prev_idx = 0

        for i, nr in enumerate(remaining_new):
            for j, pr in enumerate(remaining_prev):
                cost = _compute_cost(nr['jade'], nr['refs'], pr['jade'], pr['refs'])
                if cost < best_cost:
                    best_cost = cost
                    best_new_idx = i
                    best_prev_idx = j

        chosen_new = remaining_new.pop(best_new_idx)
        chosen_prev = remaining_prev.pop(best_prev_idx)

        # Confidence check: so với cặp tốt nhì còn lại
        confidence_ok = True
        if remaining_prev:
            second_best_cost = min(
                _compute_cost(chosen_new['jade'], chosen_new['refs'], pr['jade'], pr['refs'])
                for pr in remaining_prev
            )
            diff_ratio = (second_best_cost - best_cost) / max(chosen_new['jade'], 1)
            if diff_ratio < 0.20:
                confidence_ok = False

        results.append((chosen_new, chosen_prev, confidence_ok))

    # New records không có prev để ghép
    for nr in remaining_new:
        results.append((nr, None, False))

    return results


def resolve_alias(username, jade, rank, refs, team_members_map):
    """
    Resolve alias cho 1 user đơn lẻ (không phải duplicate).
    Dùng cho Tầng 2 và Tầng 3.

    username: full masked email (vd: dan***@gmail.com)
    jade: int
    rank: int
    refs: int (t1_refs + t2_refs)
    team_members_map: {username: [{"alias": str, "role": str, "bxh_rank": int|None}]}

    Return: (alias, role, is_team)
    """
    # Tầng 1 — Team member lookup (username exact match, không dùng rank)
    if username in team_members_map:
        members = team_members_map[username]
        if len(members) == 1:
            return members[0]["alias"], members[0]["role"], True
        else:
            # Nhiều entry cùng username trong TeamMember (ví dụ: 2 người cùng hun***@gmail.com)
            # Dùng bxh_rank làm rank threshold tĩnh — đây là trường hợp đặc biệt PM đã set
            sorted_members = sorted(members, key=lambda m: m.get("bxh_rank") or 999)
            for m in sorted_members:
                if m.get("bxh_rank") and rank <= m["bxh_rank"]:
                    return m["alias"], m["role"], True
            m = sorted_members[-1]
            return m["alias"], m["role"], True

    # Tầng 2 — KNOWN_ALIASES (jade/rank threshold cho duplicate đã biết)
    # lambda nhận (jade, rank) để linh hoạt dùng cả 2
    KNOWN_ALIASES = {
        "mal***@gmail.com": lambda j, r: "mal[1]***" if j > 400000 else "mal[2]***",
        "tra***@gmail.com": lambda j, r: "tra[1]***" if j > 300000 else ("tra[2]***" if j > 50000 else "tra[3]***"),
        "qua***@gmail.com": lambda j, r: "qua[T2]***" if j > 25000 else "qua[farm]***",
        "kha***@gmail.com": lambda j, r: "kha[1]***" if j > 200000 else "kha[2]***",
        "rom***@gmail.com": lambda j, r: "rom[1]***" if j > 100000 else ("rom[2]***" if j > 30000 else "rom[3]***"),
        "ben***@gmail.com": lambda j, r: "ben[1]***" if j > 80000 else ("ben[2]***" if j > 30000 else "ben[3]***"),
        "hun***@gmail.com": lambda j, r: "hun[BXH]***" if r < 50 else "hun[moi]***",
        "thu***@gmail.com": lambda j, r: "thu[1]***" if j > 200000 else "thu[2]***",
    }
    if username in KNOWN_ALIASES:
        return KNOWN_ALIASES[username](jade, rank), None, False

    # Tầng 3 — Default: giữ nguyên full username (có @gmail.com)
    return username, None, False
```

---

### 2. `routers/import_data.py` — Refactor `_process_import`

Thay toàn bộ logic resolve alias trong `_process_import`. Cấu trúc mới:

```python
def _process_import(parsed_items, import_date, is_delayed, note, db):
    dt = datetime.strptime(import_date, "%Y-%m-%d").date()
    snapshot = Snapshot(date=dt, is_delayed=is_delayed, note=note)
    db.add(snapshot)
    db.flush()

    # Build team map — username exact match only, KHÔNG dùng rank
    team_members = db.query(TeamMember).all()
    team_map_by_username = {}
    for tm in team_members:
        key = tm.username  # full masked email, vd: dan***@gmail.com
        if key not in team_map_by_username:
            team_map_by_username[key] = []
        team_map_by_username[key].append({
            "alias": tm.alias, "role": tm.role, "bxh_rank": tm.bxh_rank
        })
    # KHÔNG tạo team_map_by_rank nữa

    # Prev snapshot để tính delta và sequential matching
    prev_snapshot = db.query(Snapshot).filter(Snapshot.date < dt)\
        .order_by(Snapshot.date.desc()).first()
    prev_rankings_map = {}  # alias -> Ranking object
    prev_by_username = {}   # username -> [Ranking objects] — cho sequential matching
    if prev_snapshot:
        prev_rankings = db.query(Ranking)\
            .filter(Ranking.snapshot_id == prev_snapshot.id).all()
        prev_rankings_map = {r.alias: r for r in prev_rankings}
        for r in prev_rankings:
            if r.username not in prev_by_username:
                prev_by_username[r.username] = []
            prev_by_username[r.username].append(r)

    # Group parsed_items theo username để detect duplicate
    from collections import defaultdict
    items_by_username = defaultdict(list)
    for item in parsed_items:
        item['refs'] = item.get('t1_refs', 0) + item.get('t2_refs', 0)
        items_by_username[item['username']].append(item)

    # Resolve alias cho từng nhóm username
    alias_assignments = {}  # index trong parsed_items -> (alias, role, is_team, confidence_ok)
    new_alerts = []         # Alert messages từ matching

    for username, items in items_by_username.items():
        if len(items) == 1:
            # Không có duplicate → resolve bình thường
            item = items[0]
            alias, role, is_team = resolve_alias(
                username, item['jade'], item['rank'], item['refs'], team_map_by_username
            )
            alias_assignments[id(item)] = (alias, role, is_team, True)

        else:
            # Duplicate username — chạy sequential matching
            prev_records_raw = prev_by_username.get(username, [])
            prev_records = [
                {"alias": r.alias, "jade": r.jade,
                 "refs": (r.t1_refs or 0) + (r.t2_refs or 0)}
                for r in prev_records_raw
            ]

            if len(prev_records) == len(items):
                # Đủ lịch sử — chạy Tầng 1: sequential matching
                match_results = sequential_match(items, prev_records)
                for (new_item, prev_rec, confidence_ok) in match_results:
                    if prev_rec is not None:
                        # Giữ alias từ prev — người này là ai thì vẫn là người đó
                        matched_alias = prev_rec["alias"]
                        # Kiểm tra xem alias này có phải team member không
                        tm_entry = next(
                            (tm for tm in team_members if tm.alias == matched_alias), None
                        )
                        role = tm_entry.role if tm_entry else None
                        is_team = tm_entry is not None
                        alias_assignments[id(new_item)] = (matched_alias, role, is_team, confidence_ok)
                        if not confidence_ok:
                            new_alerts.append({
                                "level": "YELLOW",
                                "message": f"Ghép cặp không chắc cho '{username}' rank {new_item['rank']} "
                                           f"(alias tạm: {matched_alias}). Vào /tracker để kiểm tra."
                            })
                    else:
                        # New record không có cặp trong prev → alias tạm
                        temp_alias = f"{username}[?]"
                        alias_assignments[id(new_item)] = (temp_alias, None, False, False)
                        new_alerts.append({
                            "level": "YELLOW",
                            "message": f"Username mới '{username}' rank {new_item['rank']} chưa xác định được alias. "
                                       f"Vào /tracker để sửa alias thủ công."
                        })
            else:
                # Prev không có đủ record (lần đầu gặp duplicate, hoặc số lượng thay đổi)
                # Fallback Tầng 2: KNOWN_ALIASES
                for item in items:
                    alias, role, is_team = resolve_alias(
                        username, item['jade'], item['rank'], item['refs'], team_map_by_username
                    )
                    if alias == username:
                        # Tầng 2 cũng không có rule → Tầng 3: alias tạm + Alert
                        # Đánh số thứ tự theo rank
                        temp_alias = f"{username}[?]"
                        alias_assignments[id(item)] = (temp_alias, None, False, False)
                        new_alerts.append({
                            "level": "YELLOW",
                            "message": f"Duplicate username '{username}' rank {item['rank']} chưa có rule phân biệt. "
                                       f"Vào /tracker để sửa alias thủ công."
                        })
                    else:
                        alias_assignments[id(item)] = (alias, role, is_team, True)

    # Build rankings với alias đã resolve
    rankings_to_save = []
    for item in parsed_items:
        alias, role, is_team, _ = alias_assignments[id(item)]

        prev_r = prev_rankings_map.get(alias)
        delta = calculate_delta(item["jade"], prev_r.jade if prev_r else None)

        history_rankings = db.query(Ranking, Snapshot.is_delayed)\
            .join(Snapshot, Ranking.snapshot_id == Snapshot.id)\
            .filter(Ranking.alias == alias)\
            .order_by(Snapshot.date.desc()).limit(18).all()

        history_deltas = [delta] + [r.Ranking.delta for r in history_rankings]
        is_delayed_list = [is_delayed] + [r.is_delayed for r in history_rankings]
        w_rate = calculate_w_rate(history_deltas, is_delayed_list)

        proj = project_may31(item["jade"], w_rate, dt)

        ranking = Ranking(
            snapshot_id=snapshot.id,
            rank=item["rank"],
            username=item["username"],
            alias=alias,
            jade=item["jade"],
            t1_refs=item["t1_refs"],
            t2_refs=item["t2_refs"],
            delta=delta,
            w_rate=w_rate,
            proj_may31=proj,
            prize_est="TBD",
            is_team=is_team,
            team_role=role
        )
        rankings_to_save.append(ranking)

    # Tính prize theo projected rank
    rankings_sorted_by_proj = sorted(
        [r for r in rankings_to_save if r.proj_may31 is not None],
        key=lambda r: r.proj_may31, reverse=True
    )
    for proj_rank, r in enumerate(rankings_sorted_by_proj, start=1):
        r.prize_est = estimate_prize(proj_rank)
    for r in rankings_to_save:
        if r.proj_may31 is None:
            r.prize_est = "N/A"

    db.add_all(rankings_to_save)
    db.flush()

    # Alerts từ matching + alerts thông thường
    all_alerts = new_alerts + generate_alerts(
        snapshot.id, rankings_to_save, prev_rankings_map, team_members
    )
    for alert_item in all_alerts:
        alert = Alert(
            snapshot_id=snapshot.id,
            level=alert_item["level"],
            message=alert_item["message"]
        )
        db.add(alert)

    db.commit()
    return {
        "status": "success",
        "message": f"Imported {len(rankings_to_save)} users for {import_date}",
        "snapshot_id": snapshot.id,
        "warnings": [a["message"] for a in new_alerts]
    }
```

---

### 3. `refresh_stats.py` — Bỏ team_map_by_rank, dùng resolve_alias

Trong `refresh_stats.py`, tìm đoạn build `team_map` và set `is_team`. Sửa thành:

```python
from services.alias_resolver import resolve_alias

# Build team_map đúng format mới
team_members = db.query(TeamMember).all()
team_map_by_username = {}
for tm in team_members:
    key = tm.username
    if key not in team_map_by_username:
        team_map_by_username[key] = []
    team_map_by_username[key].append({
        "alias": tm.alias, "role": tm.role, "bxh_rank": tm.bxh_rank
    })

# Trong vòng loop set is_team — XÓA team_map_by_rank, thay bằng:
for r in rankings:
    refs = (r.t1_refs or 0) + (r.t2_refs or 0)
    new_alias, role, is_team = resolve_alias(
        r.username, r.jade, r.rank, refs, team_map_by_username
    )
    # Chỉ update is_team và team_role — KHÔNG overwrite alias đã có trong DB
    # (alias đã được set đúng lúc import, hoặc đã được PM chỉnh thủ công)
    r.is_team = is_team
    r.team_role = role
```

> ⚠️ **Quan trọng:** `refresh_stats.py` **KHÔNG overwrite alias** đã lưu trong DB. Chỉ recalculate delta, w_rate, prize và cập nhật is_team/team_role. Alias chỉ được set lúc import hoặc khi PM chỉnh thủ công qua `/tracker`.

---

### 4. `static/tracker.js` + `routers/team.py` — Alias edit cho record `[?]`

Brief 6 đã implement alias edit cơ bản (`PUT /api/team-members/alias` + icon ✏️ trên `/tracker`). Brief này **mở rộng** để handle alias `[?]`:

#### 4a. `static/tracker.js` — Highlight alias `[?]` và prompt rõ hơn

Tìm đoạn render cột alias trong `renderTable()`, sửa để highlight alias chứa `[?]`:

```javascript
// Thay đoạn render alias cell hiện tại bằng:
const isUnresolved = user.alias && user.alias.includes('[?]');
const aliasDisplay = isUnresolved
    ? `<span style="color:#f59e0b;font-weight:600">${user.alias}</span>`  // vàng = cần xử lý
    : user.alias;

// Thay đổi prompt message trong openAliasEdit:
function openAliasEdit(username, currentAlias) {
    const isUnresolved = currentAlias.includes('[?]');
    const msg = isUnresolved
        ? `⚠️ Username "${username}" chưa xác định được alias tự động.\nNhập alias đúng cho người này:`
        : `Sửa alias cho "${username}":\n(Hiện tại: ${currentAlias})`;
    const newAlias = prompt(msg, isUnresolved ? '' : currentAlias);
    if (newAlias === null || newAlias.trim() === '') return;
    if (newAlias.trim() === currentAlias) return;
    saveAlias(username, newAlias.trim());
}
```

#### 4b. `routers/team.py` — `PUT /api/team-members/alias` cập nhật rankings

Endpoint này (đã có từ Brief 6) cần thêm bước: sau khi update TeamMember, **update alias trong bảng rankings** cho tất cả record của username đó:

```python
@router.put("/alias")
async def update_alias(data: AliasUpdateSchema, db: Session = Depends(get_db)):
    # Update hoặc tạo TeamMember
    member = db.query(TeamMember).filter(TeamMember.username == data.username).first()
    if member:
        old_alias = member.alias
        member.alias = data.alias
    else:
        old_alias = None
        member = TeamMember(username=data.username, alias=data.alias, role="T2")
        db.add(member)
    db.flush()

    # THÊM: Update alias trong rankings table
    # Tìm tất cả rankings của username này có alias cũ (kể cả alias [?])
    rankings_to_update = db.query(Ranking).filter(
        Ranking.username == data.username
    ).all()
    for r in rankings_to_update:
        # Chỉ update nếu alias đang là [?] hoặc là alias cũ của người này
        if '[?]' in (r.alias or '') or r.alias == old_alias:
            r.alias = data.alias

    db.commit()
    return {"status": "success", "updated_rankings": len(rankings_to_update)}
```

---

### 5. Chuẩn hóa username trong TeamMember table

Kiểm tra và đảm bảo tất cả username trong `team_members` có đuôi `@gmail.com`:

```sql
-- Query kiểm tra
SELECT id, username, alias FROM team_members WHERE username NOT LIKE '%@gmail.com';
```

Nếu có record thiếu đuôi → update thủ công hoặc qua UI `/team`.

---

### 6. Fix data snapshot 06/05 sau khi sửa code

Snapshot 06/05 hiện có alias sai (rank 35 = `qua[TEAM]`, rank 95 = `hun[TEAM]`). Sau khi sửa code xong, **không chạy `refresh_stats.py`** (vì nó không overwrite alias). Thay vào đó PM tự fix thủ công qua `/tracker`:

1. Vào `/tracker`, filter ngày 06/05
2. Rank 35 (`thu***@gmail.com`): click ✏️ → đổi alias từ `qua[TEAM]` thành `thu[2]***`
3. Rank 95 (`huy***@gmail.com`): click ✏️ → đổi alias từ `hun[TEAM]` thành `huy***@gmail.com`
4. Sau khi sửa alias → delta và W.Rate của 2 người này sẽ được tính lại đúng trong lần import tiếp theo

> Nếu muốn recalculate delta/W.Rate ngay cho snapshot 06/05, chạy `refresh_stats.py` sau khi sửa alias thủ công (lúc này alias đã đúng, refresh_stats chỉ recalc số liệu, không đụng alias).

---

## THỨ TỰ THỰC HIỆN

```
1. services/alias_resolver.py   — Viết lại hoàn toàn theo spec trên
2. routers/import_data.py       — Refactor _process_import: sequential matching + alert
3. refresh_stats.py             — Bỏ team_map_by_rank, giữ alias trong DB
4. routers/team.py              — Mở rộng PUT /api/team-members/alias: update rankings table
5. static/tracker.js            — Highlight alias [?], sửa prompt message
6. Chuẩn hóa TeamMember username (kiểm tra @gmail.com)
7. Restart server
8. PM fix thủ công snapshot 06/05 qua /tracker
9. Verify checklist
```

---

## VERIFY CHECKLIST

**Sequential matching — import ngày mới (test với data thật):**
- [ ] Import snapshot tiếp theo → `thu***@gmail.com` rank ~35 có alias `thu[2]***` (không phải `qua[TEAM]`)
- [ ] `hun***@gmail.com` (team) và username khác cùng `hun***` được phân biệt đúng
- [ ] `mal***@gmail.com` 2 người vẫn đúng alias sau matching
- [ ] Response JSON của import có field `warnings: []` (mảng rỗng = không có alert mới)

**Fallback & Alert:**
- [ ] Thêm thử 1 duplicate username chưa có KNOWN_ALIASES rule → Alert YELLOW xuất hiện trên Dashboard
- [ ] Alert message có nội dung "Vào /tracker để sửa alias thủ công"

**Alias edit trên /tracker:**
- [ ] Alias chứa `[?]` hiển thị màu vàng (#f59e0b)
- [ ] Click ✏️ vào alias `[?]` → prompt nội dung "⚠️ chưa xác định được alias tự động"
- [ ] Nhập alias mới → alias trong rankings table được update (kiểm tra DB trực tiếp)
- [ ] Reload `/tracker` → alias mới vẫn còn

**Regression:**
- [ ] `nau***@gmail.com` rank 1: alias đúng, is_team=True
- [ ] `qua***@gmail.com` ở bất kỳ rank nào: is_team=True, alias=`qua[TEAM]`
- [ ] `thu***@gmail.com` rank <20 (jade ~264K): alias=`thu[1]***`
- [ ] `thu***@gmail.com` rank ~35 (jade ~45K): alias=`thu[2]***`
- [ ] Không có duplicate alias trong snapshot mới nhất

---

## YÊU CẦU SAU KHI HOÀN THÀNH

Sau khi implement và verify xong, AG tạo file `Review_Report_Brief_16.md` trong thư mục project, ghi rõ:
- Từng file đã sửa và thay đổi cụ thể
- Kết quả verify checklist (pass/fail từng item)
- Danh sách TeamMember username nào cần chuẩn hóa (nếu có)
- Bất kỳ phát hiện hoặc thay đổi nào ngoài scope brief
