# Brief 8 — Fix Delta/W.Rate Sai Do Duplicate Masked Username
> PM: Adam | Dev: atigravity | Priority: P0  
> Root cause đã được phân tích hoàn toàn qua code review + data Excel

---

## 1. ROOT CAUSE — PHÂN TÍCH ĐẦY ĐỦ

### Vấn đề cốt lõi

ARO BXH mask email thành dạng `mal***@gmail.com`. Hai người dùng khác nhau có thể có cùng masked email. Hiện tại **cả hai được lưu với `username = "mal***@gmail.com"` trong DB**.

Các user bị ảnh hưởng (đã xác định từ Excel 18 ngày):
- `mal***` → mal[1]*** (572K jade, rank #3) + mal[2]*** (25K jade, rank #49)
- `tra***` → tra[1]*** + tra[2]***
- `qua***` → qua[1]*** + qua[2]*** + qua***
- `kha***` → kha[1]*** + kha[2]*** + kha***
- `rom***` → rom*** + rom[1]*** + rom[2]***
- `ben***` → ben*** + ben[1]*** + ben[2]***

### Tại sao Delta bị sai

Trong `routers/import_data.py` dòng 67 và 75:
```python
prev_rankings_map = {r.username: r for r in prev_rankings}
# ...
prev_r = prev_rankings_map.get(item["username"])
delta = calculate_delta(item["jade"], prev_r.jade if prev_r else None)
```

`prev_rankings_map` là dict, key = `username`. Nếu DB hôm qua có 2 record cùng `username = "mal***@gmail.com"`, dict chỉ giữ **1 cái** (cái sau cùng). 

Kết quả:
- Ngày hôm nay: mal[1]*** jade=572K, mal[2]*** jade=25K
- `prev_rankings_map["mal***@gmail.com"]` → chỉ có 1 record, ví dụ jade=555K (của mal[1]***)
- Delta cho mal[1]***: 572K − 555K = **+17K ✓ đúng**
- Delta cho mal[2]***: 25K − 555K = **−530K ✗ SAI HOÀN TOÀN**

### Tại sao W.Rate bị sai

Trong `import_data.py` dòng 80–83:
```python
history_rankings = db.query(Ranking, Snapshot.is_delayed)\
    .join(Snapshot, Ranking.snapshot_id == Snapshot.id)\
    .filter(Ranking.username == item["username"])\
    .order_by(Snapshot.date.desc()).limit(18).all()
```

Query này lấy history của tất cả record có `username = "mal***@gmail.com"` — tức là **lẫn lộn lịch sử của 2 người khác nhau**. W.Rate tính trên data hỗn hợp này → vô nghĩa.

---

## 2. GIẢI PHÁP — DÙNG `alias` LÀM PRIMARY KEY CHO DELTA/W.RATE

### Nguyên tắc

`alias` đã được `alias_resolver.py` tính toán đúng dựa trên jade threshold:
```python
"mal***": lambda j: "mal[1]***" if j > 400000 else "mal[2]***"
```

→ `alias` là unique identifier đúng cho từng người. **Dùng `alias` làm key cho delta lookup và W.Rate history**, không dùng `username`.

### Yêu cầu thêm: alias phải được lưu trước khi dùng

Trong flow hiện tại, alias được resolve tại thời điểm import, nhưng W.Rate history query vẫn dùng `username`. Cần sửa để query dùng `alias`.

---

## 3. CÁC THAY ĐỔI CẦN IMPLEMENT

### 3a. Sửa `routers/import_data.py` — delta lookup

**Thay đổi:** Build `prev_rankings_map` theo `alias` thay vì `username`:

```python
# HIỆN TẠI (dòng 66-67) — SAI:
prev_rankings = db.query(Ranking).filter(Ranking.snapshot_id == prev_snapshot.id).all()
prev_rankings_map = {r.username: r for r in prev_rankings}

# SỬA THÀNH — dùng alias làm key:
prev_rankings = db.query(Ranking).filter(Ranking.snapshot_id == prev_snapshot.id).all()
prev_rankings_map = {r.alias: r for r in prev_rankings}
```

**Và sửa delta lookup (dòng 75-76):**
```python
# HIỆN TẠI (dòng 72-76) — SAI:
alias, role, is_team = resolve_alias(item["username"], item["jade"], team_map)
prev_r = prev_rankings_map.get(item["username"])  # ← dùng username
delta = calculate_delta(item["jade"], prev_r.jade if prev_r else None)

# SỬA THÀNH:
alias, role, is_team = resolve_alias(item["username"], item["jade"], team_map)
prev_r = prev_rankings_map.get(alias)  # ← dùng alias
delta = calculate_delta(item["jade"], prev_r.jade if prev_r else None)
```

### 3b. Sửa `routers/import_data.py` — W.Rate history query

**Thay đổi:** Query history theo `alias` thay vì `username`:

```python
# HIỆN TẠI (dòng 80-83) — SAI:
history_rankings = db.query(Ranking, Snapshot.is_delayed)\
    .join(Snapshot, Ranking.snapshot_id == Snapshot.id)\
    .filter(Ranking.username == item["username"])\  # ← username
    .order_by(Snapshot.date.desc()).limit(18).all()

# SỬA THÀNH:
history_rankings = db.query(Ranking, Snapshot.is_delayed)\
    .join(Snapshot, Ranking.snapshot_id == Snapshot.id)\
    .filter(Ranking.alias == alias)\  # ← alias (đã resolve ở trên)
    .order_by(Snapshot.date.desc()).limit(18).all()
```

### 3c. Sửa `refresh_stats.py` — cùng vấn đề

`refresh_stats.py` cũng dùng `username` cho delta và W.Rate history. Phải sửa tương tự:

```python
# HIỆN TẠI (dòng 36-43) — SAI:
prev_r = prev_map.get(r.username)
r.delta = calculate_delta(r.jade, prev_r.jade if prev_r else None)

history = db.query(Ranking, Snapshot.is_delayed)\
    .join(Snapshot, Ranking.snapshot_id == Snapshot.id)\
    .filter(Ranking.username == r.username)\  # ← username
    .order_by(desc(Snapshot.date)).limit(18).all()

# SỬA THÀNH:
prev_r = prev_map.get(r.alias)  # ← alias
r.delta = calculate_delta(r.jade, prev_r.jade if prev_r else None)

history = db.query(Ranking, Snapshot.is_delayed)\
    .join(Snapshot, Ranking.snapshot_id == Snapshot.id)\
    .filter(Ranking.alias == r.alias)\  # ← alias
    .order_by(desc(Snapshot.date)).limit(18).all()
```

Và build `prev_map` cũng phải dùng alias:
```python
# Trong refresh_stats.py dòng 23-24:
# HIỆN TẠI:
prev_map = {r.username: r for r in prev_rankings}

# SỬA THÀNH:
prev_map = {r.alias: r for r in prev_rankings}
```

### 3d. Sửa `alias_resolver.py` — thêm các duplicate case còn thiếu

Hiện tại chỉ cover `mal***`, `qua***`, `tra***`, `kha***`. Cần thêm `rom***`, `ben***` và các case mới xuất hiện sau này:

```python
KNOWN_ALIASES = {
    # Phân biệt bằng jade threshold
    "mal***@gmail.com": lambda j: "mal[1]***" if j > 400000 else "mal[2]***",
    "tra***@gmail.com": lambda j: "tra[1]***" if j > 300000 else "tra[2]***",
    "qua***@gmail.com": lambda j: "qua[T2]***" if j > 25000 else "qua[farm]***",
    "kha***@gmail.com": lambda j: "kha[1]***" if j > 200000 else "kha[2]***",
    "rom***@gmail.com": lambda j: "rom[1]***" if j > 100000 else ("rom[2]***" if j > 30000 else "rom[3]***"),
    "ben***@gmail.com": lambda j: "ben[1]***" if j > 80000 else ("ben[2]***" if j > 30000 else "ben[3]***"),
    "hun***@gmail.com": lambda j: "hun[BXH]***" if j > 50000 else "hun[mới]***",
}
```

**Lưu ý quan trọng:** Key trong dict phải là **full username** như trong DB (ví dụ `"mal***@gmail.com"`), không phải prefix ngắn. Kiểm tra xem hiện tại code dùng prefix hay full email, sửa cho đúng.

---

## 4. SAU KHI SỬA CODE → CHẠY LẠI refresh_stats.py

```bash
python refresh_stats.py
```

Lệnh này recalculate delta và W.Rate cho **toàn bộ 19 snapshots** dựa trên logic mới (alias-based). Bắt buộc phải chạy.

---

## 5. VERIFY CHECKLIST

Sau khi chạy refresh_stats, chạy script sau và paste kết quả cho PM:

```python
# verify_duplicate_fix.py
import sqlite3

con = sqlite3.connect('data/aro_tracker.db')
cur = con.cursor()
cur.execute('SELECT id, date FROM snapshots ORDER BY date DESC LIMIT 1')
snap = cur.fetchone()
snap_id = snap[0]
print(f"Snapshot: {snap[1]}")

# Check mal[1]*** và mal[2]*** — delta phải dương và reasonable
cur.execute("""SELECT alias, rank, jade, delta, w_rate 
               FROM rankings WHERE snapshot_id=? 
               AND (alias LIKE 'mal%' OR alias LIKE 'tra%' OR alias LIKE 'qua%')
               ORDER BY rank""", (snap_id,))
for r in cur.fetchall():
    print(f"  alias={r[0]:<15} rank={r[1]:<5} jade={r[2]:<8} delta={r[3]:<10} w_rate={round(r[4] or 0)}")
con.close()
```

**Kết quả mong đợi:**
- `mal[1]***`: delta khoảng +15K–20K (không phải −500K)
- `mal[2]***`: delta nhỏ dương (khoảng +1K–2K)  
- W.Rate của cả 2 đều reasonable (không âm bất thường)

**UI check:**
- [ ] Tracker: mal[1]*** cột delta các ngày không có giá trị âm lớn bất thường
- [ ] Tracker: tra[1]***, tra[2]***, qua[1]***, qua[2]*** tương tự
- [ ] W.Rate của các user trên không còn negative hoặc 0 bất thường

**AG KHÔNG được báo "done" nếu chưa chạy verify script và confirm delta của mal[1]*** > 0.**

---

## 6. TÓM TẮT FILE CẦN SỬA

| File | Thay đổi |
|------|----------|
| `routers/import_data.py` | Build `prev_rankings_map` theo `alias`; delta lookup theo `alias`; W.Rate history query theo `alias` |
| `refresh_stats.py` | Build `prev_map` theo `alias`; delta lookup theo `alias`; W.Rate history query theo `alias` |
| `services/alias_resolver.py` | Thêm `rom***`, `ben***`; đảm bảo key là full username (với @gmail.com) |
| (sau khi sửa) | Chạy `python refresh_stats.py` để recalculate toàn bộ |

**Core principle:** `alias` là unique identity của mỗi người. `username` chỉ là masked email có thể trùng. Mọi thao tác liên quan đến continuity (delta, W.Rate history) phải dùng `alias`.

---

*Root cause đã được PM xác định bằng code review + data analysis. Implement đúng spec, verify đủ checklist rồi mới báo done.*
