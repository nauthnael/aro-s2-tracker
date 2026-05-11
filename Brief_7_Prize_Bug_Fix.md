# Brief 7 — Fix Prize Bug: Dùng Current Rank thay vì Projected Rank
> PM: Adam | Dev: atigravity | Priority: P0 — BUG ĐÃ XÁC ĐỊNH CHÍNH XÁC

---

## 1. ROOT CAUSE — ĐÃ XÁC ĐỊNH

**File:** `refresh_stats.py` dòng 51–58

```python
# HIỆN TẠI (SAI):
# Recalculate prizes based on projected rank for this snapshot
rankings_sorted = sorted(
    [r for r in rankings if r.proj_may31 is not None],
    key=lambda x: x.proj_may31,   # <-- Sort theo JADE DỰ BÁO 31/05
    reverse=True
)
for proj_rank, r in enumerate(rankings_sorted, start=1):
    r.prize_est = estimate_prize(proj_rank)  # <-- Prize theo PROJECTED RANK
```

**Hậu quả:** nau*** đang rank #1 thực tế, nhưng nếu `proj_may31` của nau*** thấp hơn một số người khác có w_rate cao hơn → `proj_rank` của nau*** có thể là #2, #3, #4 → prize bị tính là `$2,000` thay vì `$5,000`.

**Logic đúng phải là:** Prize = f(current_rank thực tế trong snapshot đó), không phải rank dự báo.

---

## 2. FIX

**File:** `refresh_stats.py`

Thay đoạn tính prize (dòng 51–62) bằng:

```python
# Recalculate prizes based on CURRENT RANK (not projected rank)
for r in rankings:
    if r.rank is not None:
        r.prize_est = estimate_prize(r.rank)
    else:
        r.prize_est = "$0"
```

**Xóa** đoạn code cũ:
```python
# XÓA TOÀN BỘ ĐOẠN NÀY:
rankings_sorted = sorted(
    [r for r in rankings if r.proj_may31 is not None],
    key=lambda x: x.proj_may31,
    reverse=True
)
for proj_rank, r in enumerate(rankings_sorted, start=1):
    r.prize_est = estimate_prize(proj_rank)
    
for r in rankings:
    if r.proj_may31 is None:
        r.prize_est = "N/A"
```

**Thay bằng:**
```python
# Assign prize based on current rank
for r in rankings:
    r.prize_est = estimate_prize(r.rank) if r.rank else "$0"
```

---

## 3. SAU KHI SỬA CODE → CHẠY LỆNH NÀY

```bash
python refresh_stats.py
```

Phải chạy lại để update `prize_est` trong DB cho tất cả snapshots hiện có.

---

## 4. VERIFY CHECKLIST

Chạy query sau và paste kết quả cho PM:

```python
# check_prize_fix.py
import sqlite3

con = sqlite3.connect('data/aro_tracker.db')
cur = con.cursor()
cur.execute('SELECT id, date FROM snapshots ORDER BY date DESC LIMIT 1')
snap = cur.fetchone()
print(f"Latest snapshot: {snap[1]}")

cur.execute('''SELECT rank, username, prize_est FROM rankings 
               WHERE snapshot_id=? ORDER BY rank LIMIT 15''', (snap[0],))
for r in cur.fetchall():
    print(f"  rank={r[0]} user={str(r[1])[:20]:<20} prize={r[2]}")
con.close()
```

**Kết quả mong đợi:**
- rank 1 → `$5,000`
- rank 2–5 → `$2,000`
- rank 6–10 → `$1,000`
- rank 11–50 → `$200`
- rank 51–100 → `$50`

**Dashboard UI:**
- [ ] nau*** (rank #1) hiển thị Prize = `$5,000`
- [ ] User rank #2–5 hiển thị `$2,000`

**AG KHÔNG được báo "done" nếu chưa chạy query verify và confirm nau*** = $5,000.**

---

## 5. TÓM TẮT

| File | Thay đổi |
|------|----------|
| `refresh_stats.py` | Sửa logic prize: dùng `r.rank` thay vì sort theo `proj_may31` |
| (sau khi sửa) | Chạy `python refresh_stats.py` để update DB |

**Chỉ sửa 1 chỗ, rất đơn giản. Không động vào file khác.**

---

*Root cause đã được PM xác định bằng code review. Không cần debug thêm — implement ngay.*
