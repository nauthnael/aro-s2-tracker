# Brief: Cập nhật BXH từ file JSON hàng ngày

**Gửi:** atigravity (AG)
**Từ:** Claude (PM)
**Ngày:** 29/04/2026
**Độ ưu tiên:** 🟡 Medium — cần để bắt đầu dùng hàng ngày

---

## Bối Cảnh

`ARO_MASTER.xlsx` đã tạo thành công. Bước tiếp theo là đưa pipeline vào hoạt động thực tế.

Mỗi ngày Adam sẽ lưu dữ liệu BXH từ app ARO thành 1 file JSON tên theo quy ước:
```
bxh-DD-MM.json       ví dụ: bxh-29-04.json, bxh-30-04.json
```

Tool cần đọc file này, tự suy ra ngày từ tên file, rồi cập nhật `ARO_MASTER.xlsx` và xuất báo cáo.

---

## Format JSON thực tế (đã kiểm tra)

File `bxh-29-04.json` có cấu trúc:

```json
[
  { "#": "" },
  { "#": "s", "username": "s", "jades earned from campaign": "s", "referral count": "s" },
  {
    "#": "1",
    "username": "nau***@gmail.com",
    "jades earned from campaign": "867.69K  ",
    "referral count": "46 (19 Tier 1 + 27 Tier 2)"
  },
  { "#": "s", "username": "s", ... },
  {
    "#": "2",
    "username": "pha***@gmail.com",
    ...
  },
  ...
]
```

**Đặc điểm cần xử lý:**
- Có các separator row `{"#": "s", ...}` và `{"#": ""}` xen giữa mỗi user → **phải bỏ qua**
- Jade có trailing whitespace: `"867.69K  "` → cần `.strip()`
- Ngày **không có trong file JSON**, chỉ có trong **tên file**: `bxh-29-04.json` = ngày 29/04/2026

---

## Yêu Cầu Chức Năng

### 1. Tự suy ngày từ tên file JSON

Khi `--json bxh-29-04.json` được truyền vào, script phải:
1. Extract `DD` và `MM` từ tên file theo pattern `bxh-{DD}-{MM}.json`
2. Tạo `date(2026, MM, DD)` — luôn giả định năm 2026 vì event chỉ chạy trong năm này
3. Dùng ngày đó làm `today` (không cần `--date` thêm nữa)
4. Nếu `--date` được truyền đồng thời → `--date` override (ưu tiên cao hơn)

### 2. Workflow lệnh mới

**Lệnh Adam dùng mỗi ngày (một lệnh duy nhất):**
```bash
python ARO_report.py --json bxh-29-04.json
```

Expected output:
- Chạy update: parse JSON → append vào HISTORY → tính metrics → ghi TRACKER + DASHBOARD
- In ra báo cáo Markdown 3 phần (Top 10 / Top T1 Refs / Team)

### 3. Auto-scan file JSON mới nhất (nice-to-have)

Thêm flag `--auto` để tự tìm file `bxh-*.json` mới nhất trong thư mục, không cần chỉ tên file:
```bash
python ARO_report.py --auto
```

Logic: glob `bxh-*.json`, sort theo ngày suy ra từ tên file, lấy cái mới nhất.

---

## Các Thay Đổi Cụ Thể

### File: `ARO_update.py`

**Thay đổi 1 — Hàm `extract_date_from_filename(filepath)`** (thêm mới):

```python
def extract_date_from_filename(filepath: str):
    """
    'bxh-29-04.json' → date(2026, 4, 29)
    Trả về None nếu không match pattern.
    """
    import re
    fname = os.path.basename(filepath)
    m = re.match(r'bxh-(\d{1,2})-(\d{1,2})\.json', fname, re.IGNORECASE)
    if m:
        day, month = int(m.group(1)), int(m.group(2))
        try:
            return date(2026, month, day)
        except ValueError:
            return None
    return None
```

**Thay đổi 2 — Hàm `main()` trong `ARO_update.py`:**

Thêm `--auto` argument:
```python
parser.add_argument("--auto", action="store_true",
                    help="Tự tìm file bxh-*.json mới nhất trong BASE_DIR")
```

Sau khi parse args, thêm logic xử lý `--auto` và date extraction từ filename:
```python
# Auto-find latest json
if args.auto and not args.json:
    import glob
    pattern = os.path.join(BASE_DIR, "bxh-*.json")
    candidates = glob.glob(pattern)
    if not candidates:
        print("[ERROR] Không tìm thấy file bxh-*.json trong thư mục")
        sys.exit(1)
    # Sort by extracted date, lấy mới nhất
    def sort_key(f):
        d = extract_date_from_filename(f)
        return d if d else date(2000, 1, 1)
    args.json = max(candidates, key=sort_key)
    print(f"[AUTO] Dùng file: {os.path.basename(args.json)}")

# Auto-detect date from JSON filename (nếu chưa có --date)
if args.json and not args.date:
    detected = extract_date_from_filename(args.json)
    if detected:
        today = detected
        print(f"[INFO] Ngày tự suy từ tên file: {today.strftime('%d/%m/%Y')}")
    # else: today đã được set = date.today() ở trên, giữ nguyên
```

### File: `ARO_report.py`

**Thay đổi 1 — Thêm `--auto` argument** (mirror từ `ARO_update.py`):
```python
parser.add_argument("--auto", action="store_true",
                    help="Tự tìm file bxh-*.json mới nhất")
```

**Thay đổi 2 — Pass `--auto` xuống `run_update()`:**
```python
if args.auto:
    update_args += ["--auto"]
```

---

## Acceptance Criteria

- [ ] Chạy `python ARO_report.py --json bxh-29-04.json` không lỗi, không cần `--date`
- [ ] Log in ra `[INFO] Ngày tự suy từ tên file: 29/04/2026`
- [ ] HISTORY sheet trong `ARO_MASTER.xlsx` có data ngày 29/04 sau khi chạy
- [ ] Báo cáo Markdown được in ra với date đúng trong tiêu đề
- [ ] `python ARO_report.py --json bxh-29-04.json --date 2026-04-28` → dùng ngày 28/04 (--date override)
- [ ] `python ARO_report.py --auto` → tự tìm file mới nhất và chạy đúng

---

## Ghi Chú

- Tên file JSON hiện tại: `bxh-DD-MM.json` (ngày trước tháng, không có năm)
- Separator rows trong JSON đã được `parse_json_data()` xử lý sẵn (`"#": "s"` và `"#": ""` đều bị skip)
- Trailing whitespace trong jade (`"867.69K  "`) đã được `parse_jade()` xử lý sẵn vì có `.strip()`
- Chỉ cần thêm **date detection từ filename** và **`--auto` flag** — không cần viết lại parser

---

## Test Command Sau Khi Fix

```bash
cd "C:\Users\Administrator\OneDrive\Documents\ARO S2 top 100 tracking"
python ARO_report.py --json bxh-29-04.json
```
