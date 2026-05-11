# Brief 20 — Fix alias default: khôi phục strip @gmail.com để đồng bộ data cũ
> PM: Adam | Dev: atigravity | Priority: P0 — KHẨN  
> Root cause đã xác định. Sửa 1 dòng trong alias_resolver.py + xóa re-import snapshot 06/05 bị lỗi.

---

## ROOT CAUSE

Brief 16 đổi default alias từ `strip @gmail.com` → **giữ nguyên full email**:

```python
# Dòng 123 alias_resolver.py hiện tại:
return username, None, False   # alias = "nau***@gmail.com"
```

Toàn bộ 25 snapshot cũ (10/04 → 05/05) đã lưu alias = `nau***` (không có `@gmail.com`).  
Snapshot 06/05 mới import lưu alias = `nau***@gmail.com`.

Tracker key-by-alias (Brief 18) tạo **2 entry riêng biệt** cho cùng 1 người:
- `alias = "nau***"` → 25 ngày lịch sử
- `alias = "nau***@gmail.com"` → 1 ngày (06/05)

Hậu quả: **90 users mất toàn bộ lịch sử**, chỉ giữ được ngày 06/05.

---

## FIX

### Bước 1 — Sửa `services/alias_resolver.py` dòng 122-123

```python
# HIỆN TẠI (SAI — tạo alias không nhất quán với data cũ):
# Tầng 3 — Default: giữ nguyên full username (có @gmail.com)
return username, None, False

# SỬA THÀNH (đồng bộ với toàn bộ data cũ):
# Tầng 3 — Default: strip @gmail.com để nhất quán với alias đã lưu trong DB
alias = username.replace("@gmail.com", "") if "@gmail.com" in username else username
return alias, None, False
```

Chỉ sửa đúng 2 dòng này, không đụng gì khác trong file.

---

### Bước 2 — Xóa snapshot 06/05 bị sai và re-import lại

Snapshot 06/05 hiện có 2 vấn đề:
1. Alias của các user thông thường bị lưu dạng `@gmail.com` (sai format)
2. Data rank 35 và rank 95 vẫn sai từ trước (lý do ban đầu cần re-import)

Cần xóa và import lại sau khi đã fix code Bước 1.

**Cách xóa:** Vào Dashboard → Import BXH → phần "Snapshots đã import" → tìm 2026-05-06 → bấm Xóa.

**Sau đó import lại** file `bxh-06-05.json` qua UI như bình thường.

---

### Bước 3 — KHÔNG cần sửa gì khác

- `routers/dashboard.py` (`get_tracker`): giữ nguyên key-by-alias — đúng rồi
- DB data cũ (25 snapshots): không cần migration — alias format đã đúng (`nau***` không có `@gmail.com`)
- `refresh_stats.py`: không cần chạy lại (alias trong snapshot cũ vẫn đúng, không bị thay đổi)

---

## THỨ TỰ THỰC HIỆN

```
1. Sửa services/alias_resolver.py — dòng 122-123 (strip @gmail.com)
2. Restart server
3. Xóa snapshot 06/05 qua UI Dashboard → Import BXH
4. Re-import bxh-06-05.json cho ngày 2026-05-06
5. Verify
```

---

## VERIFY CHECKLIST

**Tracker lịch sử khôi phục:**
- [ ] `nau***` có đúng 26 ngày history (từ 10/04 đến 06/05) trong 1 row duy nhất
- [ ] Tổng số users trong tracker ≈ 144 (không phải 229 như hiện tại)
- [ ] Không còn user nào có alias dạng `xxx***@gmail.com` (trừ các username không phải gmail)

**Data 06/05 đúng:**
- [ ] Rank 35: `username=thu***@gmail.com`, `alias=thu[2]***`
- [ ] Rank 36: `username=qua***@gmail.com`, `alias=qua[T2]***`
- [ ] Rank 94: `username=hun***@gmail.com`, alias đúng
- [ ] Rank 95: `username=huy***@gmail.com`, alias = `huy***`

**Alias format nhất quán:**
- [ ] `nau***@gmail.com` → alias `nau***` (không có @gmail.com)
- [ ] `dan***@gmail.com` → alias `dan***`
- [ ] User có email không phải gmail (vd: `tug***@outlook.com.tr`) → alias giữ nguyên (không strip)

**Regression:**
- [ ] KNOWN_ALIASES vẫn hoạt động: `mal***@gmail.com` → `mal[1]***` hoặc `mal[2]***`
- [ ] Team members vẫn đúng alias và is_team
- [ ] Dashboard top 100 hiển thị đúng

---

## YÊU CẦU SAU KHI HOÀN THÀNH

AG tạo file `Review_Report_Brief_20.md` trong thư mục project, ghi rõ:
- Xác nhận dòng đã sửa trong `alias_resolver.py`
- Tổng số users trong tracker trước và sau fix (phải giảm từ 229 về ~144)
- Kết quả verify checklist (pass/fail từng item)
- Bất kỳ phát hiện hoặc thay đổi nào ngoài scope brief
