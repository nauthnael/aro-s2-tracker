# Brief: Xử Lý Masked Username — Chuẩn Hóa & Disambiguation

**Gửi:** atigravity (AG)
**Từ:** Claude (PM)
**Ngày:** 05/05/2026
**Độ ưu tiên:** 🔴 High — ảnh hưởng tính đúng của toàn bộ HISTORY và TRACKER

---

## Bối Cảnh & Phân Tích Vấn Đề

ARO organizers mask tất cả email: `huntran@gmail.com` → `hun***@gmail.com`.  
Kết quả phân tích HISTORY hiện tại (05/05/2026) cho thấy **2 vấn đề riêng biệt**:

### Vấn Đề 1 — Format Split (88 cặp) 🔴

v24 import dùng format ngắn (`nau***`), JSON hàng ngày dùng format đầy đủ (`nau***@gmail.com`).  
Cùng một người, nhưng đang được lưu thành **2 dòng riêng** trong HISTORY.

```
nau***         max jade: 800,800   ← dữ liệu cũ từ v24
nau***@gmail.com  max jade: 867,690   ← dữ liệu mới từ JSON
```

**88 cặp** bị ảnh hưởng: nau***, pha***, ban***, dan***, thu***, vit***, hun***, ...

### Vấn Đề 2 — True Collision (trường hợp hiếm) 🟡

Đôi khi 2 người thật sự khác nhau có cùng prefix bị mask:
- `hun***@gmail.com` rank 20, jade ~69K = người lạ (không phải team)
- `hun***@gmail.com` rank 95, jade ~10K = hun[TEAM] (thành viên team của Adam)

Không thể phân biệt bằng username vì BXH chỉ trả về 1 mask cho cả 2.

---

## Giải Pháp Đề Xuất (3 cơ chế)

---

### Cơ Chế 1 — Chuẩn Hóa Username: Bỏ `@gmail.com`

**Quyết định:** Lưu tất cả username trong HISTORY và TRACKER theo format **không có `@gmail.com`**.

**Lý do:**
- Format ngắn (`nau***`) ngắn gọn hơn, ít lỗi hơn
- ARO BXH luôn mask thành `xxx***@gmail.com` — phần `@gmail.com` không thêm thông tin gì
- Dễ đọc hơn trong dashboard và báo cáo

**Thay đổi cần làm:**

**`ARO_update.py` — trong `parse_json_data()` hoặc khi ghi vào HISTORY:**
```python
def normalize_username(username: str) -> str:
    """Strip @gmail.com suffix for consistent storage."""
    return username.strip().replace("@gmail.com", "")
```

Gọi `normalize_username()` ở MỌI chỗ đọc username từ JSON trước khi lưu vào HISTORY.

**`ARO_create_master.py` — migration một lần:**

Chạy script migration (xem Cơ Chế 1b bên dưới) để fix 88 cặp trong HISTORY hiện tại.

---

### Cơ Chế 1b — Migration Script: Hợp Nhất 88 Cặp Format-Split

Viết script `fix_format_split.py` chạy 1 lần để:

1. Quét HISTORY, tìm tất cả cặp `xxx***` và `xxx***@gmail.com`
2. Với mỗi cặp, xác nhận chúng là cùng người bằng **jade trajectory check**:
   - Nếu max jade của format ngắn < max jade của format đầy đủ → **cùng người** (jade chỉ tăng theo thời gian)
   - Nếu jade của format ngắn > 0 VÀ jade của format đầy đủ cũng > 0 nhưng gap lớn bất thường → **flag để review thủ công**
3. Merge: đổi tên tất cả row `xxx***@gmail.com` thành `xxx***` (bỏ @gmail.com)
4. Update HISTORY KEY tương ứng: `20260429||xxx***@gmail.com` → `20260429||xxx***`
5. Delete các row duplicate nếu có (cùng Date + Username sau normalize)

**Logic merge:**
```python
for row in history_rows:
    if row.username.endswith('@gmail.com'):
        short = row.username.replace('@gmail.com', '')
        if short in all_usernames:
            # Verify same person: max jade of short < max jade of full (natural progression)
            max_short = max(jade for u, jade in history if u == short)
            max_full  = max(jade for u, jade in history if u == row.username)
            if max_short <= max_full * 1.05:  # tolerance 5%
                row.username = short  # rename to short format
                row.key = f"{row.date_str}||{short}"
            else:
                print(f"[WARNING] Possible collision: {short} vs {row.username} — review manually")
```

---

### Cơ Chế 2 — Team Member Identification: `(mask, jade_cap)` Tuple

**Vấn đề:** Khi 2 người khác nhau có cùng mask (`hun***`), cần phân biệt thành viên team.

**Giải pháp:** CONFIG sheet lưu team members theo format:
```
Username_Mask  |  Jade_Cap  |  Level  |  Ghi chú
hun***         |  30000     |  T2     |  Phân biệt với hun*** rank 20 (69K jade)
```

**Cơ chế hoạt động:**
- Khi update BXH hàng ngày, nếu gặp `hun***` với jade > jade_cap → đây là người lạ, không phải team
- Nếu gặp `hun***` với jade ≤ jade_cap → đây là thành viên team → gán IsTeam = True

**Thay đổi trong CONFIG sheet:**

Thêm 2 cột vào bảng TEAM_MEMBERS:
| Username | Level | Jade_Cap | Note |
|----------|-------|----------|------|
| nau***   | LEADER | 9999999 | Không collision |
| hun***   | T2     | 30000   | hun[TEAM], phân biệt với hun*** rank ~20 |

**Thay đổi trong `ARO_update.py` — hàm `compute_metrics()`:**
```python
def is_team_member(username: str, jade: float, team_config: dict) -> bool:
    """
    team_config = {mask: {"level": "T2", "jade_cap": 30000}}
    Returns True nếu username là team member với jade hợp lệ.
    """
    if username not in team_config:
        return False
    cap = team_config[username].get("jade_cap", float("inf"))
    return jade <= cap
```

---

### Cơ Chế 3 — Auto-Alias Cho True Collision Mới

**Vấn đề:** Khi update hàng ngày, nếu phát hiện cùng mask nhưng jade thấp hơn nhiều so với lịch sử → có thể là người mới.

**Giải pháp:** Khi gặp username đã tồn tại trong TRACKER nhưng jade ngày hôm nay thấp hơn **30% so với jade max lịch sử**, in cảnh báo và gán alias `[2]`:

```python
COLLISION_THRESHOLD = 0.30  # jade < 30% của max historical

def detect_collision(username, jade_today, history_max):
    if history_max > 0 and jade_today < history_max * COLLISION_THRESHOLD:
        alias = f"{username}[2]"
        print(f"[COLLISION] {username} jade today={jade_today:,.0f} << historical max={history_max:,.0f}")
        print(f"[COLLISION] Auto-aliasing to {alias} — review manually")
        return alias
    return username
```

**Lưu ý:** Cơ chế này chỉ là safety net. Trường hợp thực tế phải dùng Cơ Chế 2 (jade_cap) vì collision đã biết trước.

---

## Implementation Roadmap

### Bước 1 — Viết `fix_format_split.py` (ưu tiên cao nhất)

File standalone, chạy 1 lần, fix 88 cặp trong HISTORY + TRACKER:
1. Load `ARO_MASTER.xlsx`
2. Normalize tất cả username trong HISTORY: bỏ `@gmail.com`
3. Update HISTORY KEY
4. Delete duplicate rows (nếu sau normalize có 2 rows cùng Date + Username)
5. Rebuild TRACKER từ HISTORY đã clean
6. Save file

**Backup trước khi chạy:** `copy ARO_MASTER.xlsx ARO_MASTER_backup_05may.xlsx`

### Bước 2 — Update `ARO_update.py`

Thêm `normalize_username()`, gọi nó khi parse JSON. Thêm `is_team_member()` với jade_cap.

### Bước 3 — Update CONFIG Sheet

Thêm cột `Jade_Cap` vào bảng TEAM_MEMBERS trong CONFIG sheet.  
Giá trị ban đầu:
- `hun***`: jade_cap = 30,000 (hun[TEAM] ở rank 95 ngày 5/5 có jade ~10K)
- Tất cả thành viên team khác: jade_cap = 999,999 (không có collision)

### Bước 4 — Test

```bash
# Sau khi chạy fix_format_split.py:
python ARO_report.py --json bxh-05-05.json

# Kiểm tra:
# - nau*** trong HISTORY chỉ có 1 format (không có nau***@gmail.com nữa)
# - hun*** với jade < 30K được đánh IsTeam = True
# - hun*** với jade > 30K được đánh IsTeam = False
```

---

## Acceptance Criteria

- [ ] `fix_format_split.py` chạy thành công, log "Merged X pairs, deleted Y duplicates"
- [ ] HISTORY sau fix: chỉ còn `nau***`, không còn `nau***@gmail.com`
- [ ] `python ARO_report.py --json bxh-05-05.json` không tạo thêm `nau***@gmail.com` mới
- [ ] hun*** với jade ≤ 30K → IsTeam = True trong TRACKER
- [ ] hun*** với jade > 30K → IsTeam = False trong TRACKER
- [ ] Không mất bất kỳ ngày dữ liệu nào trong quá trình migration

---

## Dữ Liệu Thực Tế Để Tham Khảo

88 cặp format-split quan trọng nhất (theo jade):
```
nau***        : max 800,800 → nau***@gmail.com: max 867,690
pha***        : max 660,200 → pha***@gmail.com: max 716,510
ban***        : max 350,400 → ban***@gmail.com: max 367,370
dan***        : max 326,600 → dan***@gmail.com: max 348,420
hun***        : max 66,200  → hun***@gmail.com: max 69,080  ← ĐỒNG THỜI là collision case
```

**hun*** là case đặc biệt nhất:** sau khi normalize, `hun***` trong HISTORY = người rank ~20 (jade 66K-69K). hun[TEAM] ở rank 95 (~10K jade) cần được identify bằng jade_cap = 30,000.
