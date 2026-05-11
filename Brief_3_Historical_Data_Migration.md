# Brief 3 — Historical Data Migration (Top 100, 18 ngày)
> PM: Adam | Dev: atigravity | Priority: P0 — làm ngay  
> Mục tiêu: Import đủ lịch sử 18 ngày (10/04–28/04) cho toàn bộ top 100 vào DB

---

## 1. VẤN ĐỀ HIỆN TẠI

**Triệu chứng:** Màn hình `/tracker` chỉ hiển thị lịch sử của nau***, 99 user còn lại toàn `—`.

**Root cause đã xác định (PM đã inspect code + API):**

### Lỗi 1 — `migrate_excel.py` mapping username sai

```python
# HIỆN TẠI (sai):
username = alias
if alias == "nau***": username = "nau***@gmail.com"
elif "***" not in alias: username = f"{alias}***@gmail.com"  # guess mù
```

Kết quả: username được lưu trong DB từ migrate là dạng `nau***` (không có @gmail.com), còn data từ JSON import ngày 29/04 lưu là `nau***@gmail.com`. **Hai bảng không join được với nhau** → tracker thấy nau*** có lịch sử (vì script đặc biệt xử lý đúng case này), còn 99 user kia username không match.

### Lỗi 2 — Cột Excel bị map sai

Script hiện dùng:
```python
rank_col = 2 + i   # col 2-19 = rank
jade_col = 20 + i  # col 20-37 = jade
```

Nhưng thực tế cấu trúc Excel (đã verify qua excel_dump.txt):
- **Cột 1**: Username/alias
- **Cột 2–19**: Rank 18 ngày (10/04 → 28/04) ✓ đúng
- **Cột 20–37**: Jade 18 ngày (10/04 → 28/04) ✓ đúng

Mapping cột đúng nhưng **giá trị jade trong Excel là dạng `60.6K`**, `parse_jade()` xử lý được. Vấn đề chính vẫn là username mapping.

### Lỗi 3 — Thiếu T1/T2 refs trong migrated data

Script set `t1_refs=0, t2_refs=0` cho tất cả user migrate từ Excel vì Excel không có cột refs. Điều này OK (không có data thì để 0), nhưng cần ghi chú rõ.

---

## 2. GIẢI PHÁP

### Bước A — Xóa toàn bộ data migrate cũ (sai) giữ lại ngày 29/04

Snapshots ID 2-19 (10/04–28/04) được migrate từ Excel, cần xóa hết và re-migrate đúng.  
Snapshot ID 1 (29/04) là import từ JSON thật — **giữ lại, không xóa**.

```python
# Xóa snapshots cũ migrate sai
db.query(Snapshot).filter(Snapshot.id != 1).delete()
# (cascade delete sẽ tự xóa rankings và alerts liên quan)
db.commit()
```

### Bước B — Viết lại `migrate_excel.py` đúng

File Excel: `ARO_Sprint2_v24_28Apr.xlsx`, sheet `📊 Master Tracker`

**Cấu trúc sheet (đã verify):**
- Row 1-3: Header title rows (bỏ qua)
- Row 4: Date headers — cột 2 = "10-04", cột 3 = "11-04", ..., cột 19 = "28-04" (rank section) | cột 20-37 = jade same dates
- Row 5 trở đi: Data users — cột 1 = alias, cột 2-19 = rank, cột 20-37 = jade

**Username mapping — đây là phần quan trọng nhất:**

AG cần build `USERNAME_MAP` từ hai nguồn:
1. Bảng `team_members` trong DB (đã có)
2. Match với data ngày 29/04 (snapshot ID 1) trong bảng `rankings` — đây là nguồn username chính xác

```python
def build_username_map(db, alias_list):
    """
    Map alias từ Excel → username thật trong DB.
    Ưu tiên: match với data ngày 29/04 bằng alias.
    """
    # Lấy tất cả rankings ngày 29/04 (snapshot ID 1)
    latest_rankings = db.query(Ranking).filter(Ranking.snapshot_id == 1).all()
    
    # Build map: alias → username
    alias_to_username = {}
    for r in latest_rankings:
        if r.alias:
            alias_to_username[r.alias] = r.username
        # Also try matching by username prefix if alias not set
        alias_to_username[r.username] = r.username
    
    # Also check team_members
    team_members = db.query(TeamMember).all()
    for tm in team_members:
        if tm.alias:
            alias_to_username[tm.alias] = tm.username
    
    return alias_to_username
```

**Logic migrate đúng:**

```python
def migrate():
    wb = openpyxl.load_workbook('ARO_Sprint2_v24_28Apr.xlsx', data_only=True)
    sheet = wb['📊 Master Tracker']
    db = SessionLocal()
    
    # BƯỚC 1: Xóa snapshots migrate cũ (giữ lại snapshot ID=1 là ngày 29/04)
    old_snapshots = db.query(Snapshot).filter(Snapshot.note.like("Migrated%")).all()
    for s in old_snapshots:
        db.delete(s)
    db.commit()
    print(f"Deleted {len(old_snapshots)} old migrated snapshots")
    
    # BƯỚC 2: Parse dates từ row 4
    dates = []
    for col in range(2, 20):
        val = sheet.cell(row=4, column=col).value
        if val is None:
            dates.append(None)
            continue
        val = str(val).replace('*', '').strip()
        try:
            d = datetime.strptime(f"{val}-2026", "%d-%m-%Y").date()
            dates.append(d)
        except:
            dates.append(None)
    print(f"Dates: {[str(d) for d in dates if d]}")
    
    # BƯỚC 3: Collect tất cả alias từ cột 1 (row 5 trở đi)
    all_aliases = []
    for row in range(5, 150):  # buffer lớn hơn
        alias = sheet.cell(row=row, column=1).value
        if alias and str(alias).strip():
            all_aliases.append((row, str(alias).strip()))
    print(f"Found {len(all_aliases)} users in Excel")
    
    # BƯỚC 4: Build username map từ data ngày 29/04
    alias_to_username = build_username_map(db, [a for _, a in all_aliases])
    print(f"Username map has {len(alias_to_username)} entries")
    
    # Log các alias chưa map được để debug
    unmapped = []
    for _, alias in all_aliases:
        if alias not in alias_to_username:
            unmapped.append(alias)
    if unmapped:
        print(f"WARNING - Unmapped aliases ({len(unmapped)}): {unmapped[:10]}...")
    
    # BƯỚC 5: Migrate từng ngày
    for i, d in enumerate(dates):
        if d is None:
            continue
            
        rank_col = 2 + i
        jade_col = 20 + i
        
        # Tạo snapshot
        snapshot = db.query(Snapshot).filter(Snapshot.date == d).first()
        if not snapshot:
            snapshot = Snapshot(
                date=d,
                is_delayed=(str(d) == '2026-04-25'),  # 25/04 bị delay (có dấu * trong Excel)
                note="Migrated from Master Tracker"
            )
            db.add(snapshot)
            db.flush()
        
        rankings_to_add = []
        for row, alias in all_aliases:
            rank_val = sheet.cell(row=row, column=rank_col).value
            jade_val = sheet.cell(row=row, column=jade_col).value
            
            rank = parse_rank(rank_val)
            jade = parse_jade(jade_val)
            
            # Skip nếu không có data ngày đó (user chưa xuất hiện)
            if rank is None and jade is None:
                continue
            
            # Map alias → username
            username = alias_to_username.get(alias)
            if username is None:
                # Fallback: dùng alias làm username tạm
                username = alias
                
            # Check duplicate
            existing = db.query(Ranking).filter(
                Ranking.snapshot_id == snapshot.id,
                Ranking.username == username
            ).first()
            if existing:
                continue
                
            ranking = Ranking(
                snapshot_id=snapshot.id,
                rank=rank,
                username=username,
                alias=alias,
                jade=jade or 0,
                t1_refs=0,   # Excel không có cột này
                t2_refs=0,   # Excel không có cột này
                is_team=False,  # refresh_stats.py sẽ set sau
                team_role=None,
                delta=None,   # refresh_stats.py sẽ tính sau
                w_rate=None,
                proj_may31=None,
                prize_est=None
            )
            rankings_to_add.append(ranking)
        
        if rankings_to_add:
            db.add_all(rankings_to_add)
            db.flush()
            print(f"  {d}: {len(rankings_to_add)} users")
    
    db.commit()
    db.close()
    print("Migration complete. Now run refresh_stats.py")
```

### Bước C — Cập nhật `refresh_stats.py` để set `is_team`

Sau khi migrate, `refresh_stats.py` cần set `is_team` + `team_role` cho các user là team members:

```python
# Thêm vào đầu vòng lặp trong refresh():
team_members = db.query(TeamMember).all()
team_map = {tm.username: tm for tm in team_members}

for r in rankings:
    tm = team_map.get(r.username)
    if tm:
        r.is_team = True
        r.team_role = tm.role
    else:
        r.is_team = False
        r.team_role = None
    # ... (phần delta, w_rate, proj giữ nguyên)
```

---

## 3. THỨ TỰ THỰC HIỆN

AG chạy theo đúng thứ tự này:

```bash
# 1. Chạy migrate (sẽ tự xóa data cũ sai và import lại đúng)
python migrate_excel.py

# 2. Chạy refresh để tính delta, w_rate, proj, prize, is_team
python refresh_stats.py

# 3. Verify kết quả qua API
curl http://localhost:8000/api/tracker | python -m json.tool | head -100
```

---

## 4. VERIFICATION SAU KHI CHẠY

AG kiểm tra các điều sau trước khi báo cáo xong:

### Check 1 — Số snapshots
```
GET /api/snapshots → phải có 19 entries (10/04 → 29/04)
```

### Check 2 — Số users mỗi ngày
```python
# Chạy trong python shell:
from database import SessionLocal, Snapshot, Ranking
db = SessionLocal()
for s in db.query(Snapshot).order_by(Snapshot.date).all():
    count = db.query(Ranking).filter(Ranking.snapshot_id == s.id).count()
    print(f"{s.date}: {count} users")
```
**Kết quả kỳ vọng:** mỗi ngày có 50–100 users (không phải chỉ 1).

### Check 3 — Tracker view
```
GET /api/tracker → pha***, mal[1]***, ban*** phải có history trong nhiều ngày, không phải chỉ 1 ngày
```

### Check 4 — W.Rate của top users
Sau refresh, pha*** phải có w_rate ≈ 50,000–55,000 (theo context đã biết là ~54K).  
Nếu w_rate = 0 → migrate hoặc refresh vẫn còn lỗi.

---

## 5. ĐẶC BIỆT — Xử lý ngày 25/04 bị delay

Trong Excel, ngày 25/04 có dấu `*` trong header (đã thấy trong excel_dump: `25-04*`).  
Script cần set `is_delayed=True` cho snapshot ngày 25/04.

```python
# Khi parse date, check dấu *:
raw_val = str(sheet.cell(row=4, column=col).value)
is_delayed_date = '*' in raw_val
val_clean = raw_val.replace('*', '').strip()
d = datetime.strptime(f"{val_clean}-2026", "%d-%m-%Y").date()
dates.append((d, is_delayed_date))
```

---

## 6. ĐỊNH NGHĨA DONE

- [ ] Chạy `python migrate_excel.py` không có lỗi exception
- [ ] Log output hiển thị mỗi ngày có > 50 users (không phải 1)
- [ ] Chạy `python refresh_stats.py` không có lỗi
- [ ] `/api/tracker` → pha***, mal[1]***, ban*** có lịch sử ít nhất 10+ ngày
- [ ] Tracker UI tại `http://localhost:8000/tracker` hiển thị đủ data nhiều ngày cho nhiều user
- [ ] pha*** w_rate ≈ 40,000–60,000 (không phải 0)
- [ ] Ngày 25/04 header cột có icon ⚠️ trong tracker UI

---

*Brief này do Adam (PM) soạn sau khi inspect trực tiếp code migrate_excel.py và API response. Root cause đã xác định rõ — không phải lỗi thiếu data mà là lỗi username mapping.*
