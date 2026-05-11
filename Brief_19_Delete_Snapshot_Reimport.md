# Brief 19 — Thêm chức năng xóa snapshot + hướng dẫn re-import 06/05
> PM: Adam | Dev: atigravity | Priority: P0  
> 2 việc: (1) thêm API + UI xóa snapshot theo ngày, (2) PM xóa và re-import snapshot 06/05 bị sai data.

---

## BỐI CẢNH

Snapshot 06/05 được import trước khi Brief 16 fix code → data sai ở 2 chỗ:
- Rank 35: DB lưu `username=qua***@gmail.com` nhưng BXH gốc là `thu***@gmail.com`
- Rank 95: DB lưu `username=hun***@gmail.com` nhưng BXH gốc là `huy***@gmail.com`

Giải pháp: xóa snapshot 06/05 khỏi DB, re-import lại từ file JSON gốc. Code Brief 16 hiện tại sẽ xử lý đúng.

Hiện app chưa có tính năng xóa snapshot → cần implement trước.

---

## PHẦN 1 — API xóa snapshot

### `routers/import_data.py` — Thêm endpoint DELETE

```python
@router.delete("/snapshot/{snapshot_id}")
async def delete_snapshot(snapshot_id: int, db: Session = Depends(get_db)):
    """
    Xóa 1 snapshot và toàn bộ rankings + alerts liên quan.
    Không cho phép xóa snapshot duy nhất còn lại trong DB.
    """
    # Kiểm tra snapshot tồn tại
    snapshot = db.query(Snapshot).filter(Snapshot.id == snapshot_id).first()
    if not snapshot:
        raise HTTPException(status_code=404, detail=f"Snapshot {snapshot_id} không tồn tại")

    # Không cho xóa nếu chỉ còn 1 snapshot
    total = db.query(Snapshot).count()
    if total <= 1:
        raise HTTPException(status_code=400, detail="Không thể xóa snapshot duy nhất còn lại")

    # Xóa rankings và alerts trước (foreign key), rồi xóa snapshot
    db.query(Ranking).filter(Ranking.snapshot_id == snapshot_id).delete(synchronize_session=False)
    db.query(Alert).filter(Alert.snapshot_id == snapshot_id).delete(synchronize_session=False)
    db.delete(snapshot)
    db.commit()

    return {
        "status": "success",
        "message": f"Đã xóa snapshot {snapshot.date} (id={snapshot_id})"
    }
```

---

## PHẦN 2 — UI xóa snapshot trên Dashboard

### `static/index.html` — Thêm section quản lý snapshots

Thêm vào **trong Import Modal** (modal đã có sẵn), ngay sau phần import form, một section nhỏ liệt kê các snapshot gần nhất với nút xóa:

Tìm đoạn đóng của Import Modal (`</div>` cuối cùng của modal content), thêm vào trước đó:

```html
<!-- Quản lý snapshots -->
<div style="margin-top: 1.5rem; padding-top: 1.5rem; border-top: 1px solid var(--surface)">
    <h3 style="font-size: 0.875rem; color: var(--text-muted); margin-bottom: 0.75rem;">
        📅 Snapshots đã import (5 gần nhất)
    </h3>
    <div id="snapshot-list" style="display:flex; flex-direction:column; gap:0.5rem;">
        <!-- Injected by JS -->
    </div>
</div>
```

### `static/app.js` (hoặc file JS của Dashboard) — Thêm logic

**Thêm function load snapshot list** (gọi khi mở Import Modal):

```javascript
async function loadSnapshotList() {
    try {
        const res = await fetch('/api/import/snapshots');
        const snapshots = await res.json();
        const container = document.getElementById('snapshot-list');
        if (!container) return;

        // Hiển thị 5 snapshot gần nhất, mới nhất lên trên
        const recent = [...snapshots].reverse().slice(0, 5);

        container.innerHTML = recent.map(s => `
            <div style="display:flex; justify-content:space-between; align-items:center;
                        background:var(--background); padding:0.5rem 0.75rem;
                        border-radius:0.375rem; font-size:0.875rem;">
                <span>
                    <span style="color:white; font-weight:500">${s.date}</span>
                    ${s.is_delayed ? '<span style="color:#f59e0b; font-size:0.75rem; margin-left:0.5rem">⚠️ delay</span>' : ''}
                    <span style="color:var(--text-muted); margin-left:0.5rem; font-size:0.75rem">
                        (id: ${s.id})
                    </span>
                </span>
                <button onclick="deleteSnapshot(${s.id}, '${s.date}')"
                    style="background:rgba(239,68,68,0.15); color:#ef4444; border:none;
                           padding:0.25rem 0.6rem; border-radius:0.25rem; cursor:pointer;
                           font-size:0.75rem;">
                    Xóa
                </button>
            </div>
        `).join('');
    } catch(err) {
        console.error('Error loading snapshots:', err);
    }
}

async function deleteSnapshot(snapshotId, dateStr) {
    if (!confirm(
        `Xóa snapshot ngày ${dateStr}?\n\n` +
        `Toàn bộ dữ liệu BXH ngày này sẽ bị xóa khỏi DB.\n` +
        `Sau đó import lại nếu cần.`
    )) return;

    try {
        const res = await fetch(`/api/import/snapshot/${snapshotId}`, { method: 'DELETE' });
        if (res.ok) {
            const data = await res.json();
            alert(`✅ ${data.message}`);
            loadSnapshotList();   // Refresh list
            loadDashboard();      // Refresh dashboard data
        } else {
            const err = await res.json();
            alert('Lỗi: ' + (err.detail || 'Không thể xóa'));
        }
    } catch(err) {
        console.error(err);
        alert('Lỗi kết nối');
    }
}
```

**Sửa `showImportModal()`** — thêm gọi `loadSnapshotList()` khi mở modal:

```javascript
function showImportModal() {
    document.getElementById('import-modal').style.display = 'flex';
    loadSnapshotList();  // Thêm dòng này
}
```

---

## PHẦN 3 — API GET danh sách snapshots

Cần thêm endpoint để frontend lấy danh sách snapshot. Thêm vào `routers/import_data.py`:

```python
@router.get("/snapshots")
async def list_snapshots(db: Session = Depends(get_db)):
    """Trả về danh sách tất cả snapshots, sort theo date asc."""
    snapshots = db.query(Snapshot).order_by(Snapshot.date).all()
    return [
        {
            "id": s.id,
            "date": s.date.strftime("%Y-%m-%d"),
            "is_delayed": s.is_delayed,
            "note": s.note
        }
        for s in snapshots
    ]
```

---

## PHẦN 4 — Sau khi implement: PM thực hiện fix data 06/05

Sau khi AG implement và restart server, **PM thực hiện các bước sau**:

```
1. Vào Dashboard → bấm "Import BXH"
2. Trong modal, phần "Snapshots đã import" → tìm ngày 2026-05-06
3. Bấm nút "Xóa" → confirm
4. Snapshot 06/05 bị xóa khỏi DB
5. Import lại: paste JSON file bxh-06-05.json vào ô import
6. Chọn ngày 2026-05-06, bấm Parse & Preview
7. Kiểm tra preview: rank 35 phải là thu***@gmail.com, rank 95 phải là huy***@gmail.com
8. Bấm Confirm Import
```

Sau khi re-import, code Brief 16 (sequential matching) sẽ tự động gán đúng alias cho tất cả duplicate username.

---

## THỨ TỰ THỰC HIỆN

```
1. routers/import_data.py  — Thêm GET /api/import/snapshots
2. routers/import_data.py  — Thêm DELETE /api/import/snapshot/{id}
3. static/index.html       — Thêm snapshot list section vào Import Modal
4. static/app.js           — Thêm loadSnapshotList() + deleteSnapshot() + sửa showImportModal()
5. Restart server
6. Verify UI hoạt động (xem list, xóa test với snapshot khác trước)
7. PM thực hiện Phần 4: xóa + re-import 06/05
8. Verify data sau re-import
```

> ⚠️ **Bước 6:** AG test xóa một snapshot cũ (không phải 06/05) để xác nhận chức năng hoạt động trước khi PM dùng thật. Restore lại bằng cách re-import nếu cần.

---

## VERIFY CHECKLIST

**UI xóa snapshot:**
- [ ] Mở Import Modal → thấy list 5 snapshot gần nhất với ngày và id
- [ ] Snapshot bị delay có badge ⚠️
- [ ] Bấm Xóa → confirm dialog hiện đúng ngày
- [ ] Sau xóa: list refresh, dashboard refresh
- [ ] Không thể xóa nếu chỉ còn 1 snapshot (API trả lỗi 400)

**Data sau re-import 06/05:**
- [ ] Tracker rank 35: `username=thu***@gmail.com`, `alias=thu[2]***` (jade ~45K)
- [ ] Tracker rank 36: `username=qua***@gmail.com`, `alias=qua[T2]***` (jade ~43K)
- [ ] Tracker rank 94: `username=hun***@gmail.com`, alias đúng (jade ~16K)
- [ ] Tracker rank 95: `username=huy***@gmail.com`, alias khác với rank 94 (jade ~16K)
- [ ] Không còn duplicate alias nào trong snapshot 06/05
- [ ] Delta và W.Rate của các user trên hợp lý (không bị vô nghĩa)

---

## YÊU CẦU SAU KHI HOÀN THÀNH

AG tạo file `Review_Report_Brief_19.md` trong thư mục project, ghi rõ:
- Các file đã sửa và thay đổi cụ thể
- Kết quả verify checklist (pass/fail từng item)
- Kết quả data sau khi PM re-import 06/05 (rank 35 và 95 đúng chưa)
- Bất kỳ phát hiện hoặc thay đổi nào ngoài scope brief
