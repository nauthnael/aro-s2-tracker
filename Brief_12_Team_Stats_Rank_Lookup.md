# Brief 12 — Fix Team Stats Lookup: Dùng bxh_rank thay vì alias
> PM: Adam | Dev: atigravity | Priority: P0 — Bug đã xác định qua Chrome debug
> Chỉ sửa 1 hàm, 1 file.

---

## ROOT CAUSE ĐÃ XÁC NHẬN

`GET /api/team-members/with-stats` đang JOIN bằng `Ranking.alias == member.alias`:

```python
# HIỆN TẠI (SAI):
ranking = db.query(Ranking).filter(
    Ranking.snapshot_id == latest_snapshot.id,
    Ranking.alias == member.alias        # ← "hun[TEAM]"
).first()
```

Vấn đề: `member.alias` là tên PM tự đặt (`"hun[TEAM]"`), còn `ranking.alias` là tên do `alias_resolver.py` tự tính (`"hun[moi]***"`). Hai giá trị **không bao giờ khớp** → `stats = null` mãi mãi dù `bxh_rank = 95` đã được set đúng.

---

## FIX — File: `routers/team.py`

Sửa hàm `get_team_with_stats()` — thay toàn bộ logic lookup bên trong vòng `for member in members`:

```python
@router.get("/with-stats")
async def get_team_with_stats(db: Session = Depends(get_db)):
    latest_snapshot = db.query(Snapshot).order_by(desc(Snapshot.date)).first()
    members = db.query(TeamMember).all()
    result = []

    for member in members:
        stats = None
        if latest_snapshot:
            ranking = None

            # Ưu tiên lookup bằng bxh_rank (chính xác tuyệt đối, không nhầm người)
            if member.bxh_rank:
                ranking = db.query(Ranking).filter(
                    Ranking.snapshot_id == latest_snapshot.id,
                    Ranking.rank == member.bxh_rank          # ← dùng rank
                ).first()

            # Fallback: lookup bằng username nếu không có bxh_rank
            # (chỉ an toàn khi username là unique trên BXH hôm đó)
            if not ranking and member.username:
                ranking = db.query(Ranking).filter(
                    Ranking.snapshot_id == latest_snapshot.id,
                    Ranking.username == member.username
                ).first()

            if ranking:
                stats = {
                    "rank": ranking.rank,
                    "jade": ranking.jade,
                    "delta": ranking.delta,
                    "w_rate": ranking.w_rate,
                    "proj_may31": ranking.proj_may31,
                    "prize_est": ranking.prize_est,
                }

        result.append({
            "id": member.id,
            "username": member.username,
            "alias": member.alias,
            "role": member.role,
            "bxh_rank": member.bxh_rank,
            "note": member.note,
            "stats": stats
        })

    return result
```

---

## LOGIC SAU KHI FIX

| Trường hợp | Lookup bằng | Kết quả |
|---|---|---|
| `bxh_rank = 95` (hun[TEAM]) | `rank == 95` | ✅ Tìm đúng người |
| `bxh_rank = 35` (qua[TEAM]) | `rank == 35` | ✅ Tìm đúng người |
| `bxh_rank = null`, username unique | `username` | ✅ Tìm đúng |
| Rớt khỏi top 100 | không tìm thấy | → `stats = null` → hiện "Ngoài top 100" ✅ |

---

## VERIFY

Restart server, vào `/team`, kiểm tra:

- [ ] `hun[TEAM]` (bxh_rank=95) → hiển thị rank, jade, delta đúng của rank #95
- [ ] `qua[TEAM]` (bxh_rank=35) → hiển thị stats đúng của rank #35
- [ ] Thành viên không có bxh_rank và không trong top 100 → hiển thị "Ngoài top 100"
- [ ] `GET /api/team-members/with-stats` → `hun[TEAM].stats` không còn `null`

**Chỉ sửa 1 hàm, restart, kiểm tra xong báo PM.**
