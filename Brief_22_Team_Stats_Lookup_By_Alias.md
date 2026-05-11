# Brief 22 — Fix Team page: lookup stats bằng alias thay vì username
> PM: Adam | Dev: atigravity | Priority: P0  
> Root cause đã xác định. Sửa 1 chỗ trong `routers/team.py`.

---

## ROOT CAUSE

`get_team_with_stats()` trong `routers/team.py` lookup ranking bằng `username`:

```python
# Fallback hiện tại — SAI khi duplicate username:
if not ranking and member.username:
    ranking = db.query(Ranking).filter(
        Ranking.snapshot_id == latest_snapshot.id,
        Ranking.username == member.username   # ← lấy nhầm người đầu tiên có cùng username
    ).first()
```

Với `hun***@gmail.com` có 2 người trong top 100:
- Rank 22: alias `hun[BXH]***`, jade 69,730 — **không phải team**
- Rank 94: alias `hun[moi]***`, jade 16,149 — **team T1** (PM vừa tick)

TeamMember lưu `alias = "hun[moi]***"`. Nhưng query bằng `username` → SQLAlchemy trả về rank 22 trước (id thấp hơn) → Team page hiển thị `hun[moi]***` ở #22 — **sai hoàn toàn**.

**Alias là unique per person** (đảm bảo bởi alias_resolver từ Brief 16). Lookup bằng alias luôn cho kết quả chính xác.

---

## FIX — `routers/team.py`, hàm `get_team_with_stats()`

Thay toàn bộ logic lookup ranking bên trong vòng lặp `for member in members`:

```python
# HIỆN TẠI (SAI — lookup username, nhầm người khi duplicate):
ranking = None

# Ưu tiên lookup bằng bxh_rank
if member.bxh_rank:
    ranking = db.query(Ranking).filter(
        Ranking.snapshot_id == latest_snapshot.id,
        Ranking.rank == member.bxh_rank
    ).first()

# Fallback: lookup bằng username
if not ranking and member.username:
    ranking = db.query(Ranking).filter(
        Ranking.snapshot_id == latest_snapshot.id,
        Ranking.username == member.username
    ).first()
```

```python
# SỬA THÀNH (ĐÚNG — lookup alias, luôn chính xác):
ranking = None

# Lookup bằng alias — alias là unique per person kể cả duplicate username
if member.alias:
    ranking = db.query(Ranking).filter(
        Ranking.snapshot_id == latest_snapshot.id,
        Ranking.alias == member.alias
    ).first()
```

Xóa hoàn toàn phần `bxh_rank` lookup (đã xác định là không đáng tin từ Brief 16 — rank thay đổi hàng ngày). Chỉ giữ lookup bằng alias.

---

## THỨ TỰ THỰC HIỆN

```
1. Sửa routers/team.py — get_team_with_stats() theo spec trên
2. Restart server
3. Verify checklist
```

---

## VERIFY CHECKLIST

- [ ] Team page → `hun[moi]***` hiển thị rank 94, jade ~16,149 (KHÔNG phải rank 22)
- [ ] Team page → các thành viên khác (`nau***`, `caf***`, `nha***`, `kdl***`) rank và jade vẫn đúng
- [ ] Tracker → tick team cho một user bình thường → Team page cập nhật đúng rank/jade ngay
- [ ] Nếu team member không có trong top 100 ngày đó → stats = null, không crash

---

## YÊU CẦU SAU KHI HOÀN THÀNH

AG tạo file `Review_Report_Brief_22.md` trong thư mục project, ghi rõ:
- Xác nhận đã thay lookup từ `username` sang `alias` trong `get_team_with_stats()`
- Kết quả verify checklist (pass/fail từng item)
- Rank và jade của `hun[moi]***` trên Team page sau fix
