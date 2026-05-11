# Brief 11 — Thêm Import HTML (giữ tương thích JSON cũ)
> PM: Adam | Dev: atigravity | Priority: P1  
> Mục tiêu: Paste HTML table thẳng từ BXH ARO vào import modal, không cần convert JSON nữa.

---

## 1. PHÂN TÍCH HTML ĐÃ XÁC NHẬN

PM đã parse thực tế file HTML BXH ngày 02/05. Cấu trúc cố định:

```html
<table>
  <thead>
    <tr>
      <th>#</th>
      <th>Username</th>
      <th>Jades Earned From Campaign</th>
      <th>Referral Count</th>
    </tr>
  </thead>
  <tbody>
    <!-- Mỗi user có 2 row: 1 row 's' (separator/spacer) + 1 row data thật -->
    <tr><td>s</td><td>s</td><td>s</td><td>s</td></tr>   ← BỎ QUA
    <tr>
      <td>1</td>
      <td>nau***@gmail.com</td>
      <td>972.71K</td>
      <td>46 (19 Tier 1 + 27 Tier 2)</td>
    </tr>
    ...
  </tbody>
</table>
```

**Đặc điểm quan trọng:**
- Tổng 202 rows = 100 user rows + 100 separator rows (`#` = `"s"`) + 2 header rows
- Filter separator: bỏ row nếu `cells[0].text == "s"`
- Jade format: `"972.71K"` → cùng format với JSON cũ → **tái dụng `parse_jade()` hiện có**
- Referral format: `"46 (19 Tier 1 + 27 Tier 2)"` → cùng format với JSON cũ → **tái dụng `parse_refs()` hiện có**
- Mỗi cell có 1 `<span>` bên trong, `cell.get_text(strip=True)` lấy text đúng

---

## 2. THAY ĐỔI CẦN IMPLEMENT

### 2a. Thêm `parse_leaderboard_html()` vào `services/parser.py`

Thêm function mới vào cuối file, **không sửa** `parse_leaderboard_json()` cũ:

```python
from bs4 import BeautifulSoup

def parse_leaderboard_html(html_str):
    """
    Parse HTML table từ BXH ARO.
    Cấu trúc: <table> với 4 cột: #, Username, Jades Earned From Campaign, Referral Count
    Mỗi user có 2 row: 1 separator (# = "s") + 1 data row thật.
    """
    soup = BeautifulSoup(html_str, 'html.parser')
    table = soup.find('table')
    if not table:
        raise ValueError("Không tìm thấy thẻ <table> trong HTML")

    parsed_results = []
    for row in table.find_all('tr'):
        cells = row.find_all('td')
        if not cells:
            continue  # skip header row (th)
        
        rank_text = cells[0].get_text(strip=True)
        
        # Bỏ qua separator rows
        if rank_text == 's' or not rank_text.isdigit():
            continue
        
        rank = int(rank_text)
        username = cells[1].get_text(strip=True)
        jade_str = cells[2].get_text(strip=True)
        refs_str = cells[3].get_text(strip=True)
        
        jade = parse_jade(jade_str)
        t1, t2 = parse_refs(refs_str)
        
        parsed_results.append({
            "rank": rank,
            "username": username,
            "jade": jade,
            "t1_refs": t1,
            "t2_refs": t2
        })

    if len(parsed_results) == 0:
        raise ValueError("Parse HTML không tìm thấy dữ liệu. Kiểm tra lại HTML.")
    
    return parsed_results
```

**Cài thêm dependency:**
```bash
pip install beautifulsoup4
```

Thêm vào `requirements.txt`:
```
beautifulsoup4>=4.12.0
```

### 2b. Thêm auto-detect và endpoint hỗ trợ HTML trong `routers/import_data.py`

Thêm import ở đầu file:
```python
from services.parser import parse_leaderboard_json, parse_leaderboard_html
```

Thêm helper function detect loại input:
```python
def detect_and_parse(raw_input):
    """
    Tự động detect JSON hoặc HTML rồi parse.
    raw_input: string (JSON string hoặc HTML string)
    Trả về: list of parsed items
    """
    stripped = raw_input.strip()
    
    if stripped.startswith('<'):
        # HTML input
        return parse_leaderboard_html(stripped)
    else:
        # JSON input (giữ tương thích cũ)
        import json
        data = json.loads(stripped)
        return parse_leaderboard_json(data)
```

### 2c. Thêm 2 endpoint mới nhận raw string (cho HTML paste)

Hiện tại `/api/import/preview` và `/api/import` nhận `json_data: List[dict]` — không thể nhận HTML string. Cần thêm endpoint mới song song:

**File:** `routers/import_data.py`

```python
class RawImportRequest(BaseModel):
    raw_input: str          # HTML string hoặc JSON string
    import_date: str        # "YYYY-MM-DD"
    is_delayed: bool = False
    note: Optional[str] = None

@router.post("/preview-raw")
async def preview_import_raw(request: RawImportRequest, db: Session = Depends(get_db)):
    dt = datetime.strptime(request.import_date, "%Y-%m-%d").date()
    existing = db.query(Snapshot).filter(Snapshot.date == dt).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Ngày {request.import_date} đã có dữ liệu.")
    
    try:
        parsed_items = detect_and_parse(request.raw_input)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Parse lỗi: {str(e)}")
    
    return {
        "date": request.import_date,
        "total_users": len(parsed_items),
        "input_type": "html" if request.raw_input.strip().startswith('<') else "json",
        "preview_top5": parsed_items[:5],
        "warning": "BXH có thể thiếu data" if len(parsed_items) < 95 else None
    }

@router.post("/import-raw")
async def import_data_raw(request: RawImportRequest, db: Session = Depends(get_db)):
    dt = datetime.strptime(request.import_date, "%Y-%m-%d").date()
    existing = db.query(Snapshot).filter(Snapshot.date == dt).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Data for {request.import_date} already exists.")
    
    try:
        parsed_items = detect_and_parse(request.raw_input)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Parse lỗi: {str(e)}")
    
    # Từ đây xử lý giống hệt endpoint /api/import hiện tại
    # (copy toàn bộ logic từ dòng "# 2. Create Snapshot" trở xuống)
    # ... [copy logic từ import_data() hiện tại] ...
```

**Lưu ý:** Phần xử lý sau khi có `parsed_items` là **giống hệt** endpoint cũ. AG nên extract thành hàm `_process_import(parsed_items, dt, is_delayed, note, db)` để tái dụng cho cả 2 endpoint, tránh duplicate code.

### 2d. Sửa Frontend: textarea nhận cả HTML + JSON

**File:** `static/index.html`

Sửa label và placeholder của textarea:
```html
<!-- HIỆN TẠI: -->
<textarea id="json-input" placeholder="Paste JSON từ BXH ARO vào đây..."></textarea>

<!-- SỬA THÀNH: -->
<textarea id="json-input" placeholder="Paste HTML table hoặc JSON từ BXH ARO vào đây...&#10;&#10;HTML: Copy toàn bộ source của bảng BXH (Ctrl+U → Ctrl+A → Ctrl+C)&#10;JSON: Paste JSON như cũ"></textarea>
```

**File:** `static/app.js` — sửa `previewImport()` để gọi endpoint mới:

```javascript
async function previewImport() {
    const date = document.getElementById('import-date').value;
    const rawInput = document.getElementById('json-input').value.trim();
    if (!date || !rawInput) { alert("Vui lòng nhập đủ ngày và data"); return; }
    
    const btn = document.getElementById('preview-btn');
    btn.innerText = "Đang parse...";
    btn.disabled = true;
    
    try {
        const response = await fetch('/api/import/preview-raw', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                raw_input: rawInput,
                import_date: date 
            })
        });
        
        const preview = await response.json();
        if (!response.ok) { alert("Error: " + preview.detail); return; }
        
        // Hiện input type để user biết đã detect đúng
        const inputTypeLabel = preview.input_type === 'html' ? '🌐 HTML table' : '📋 JSON';
        
        const content = document.getElementById('import-preview-content');
        content.innerHTML = `
            <div class="preview-summary" style="background: rgba(255,255,255,0.05); padding: 1rem; border-radius: 0.5rem; margin-bottom: 1rem;">
                <h3 style="color: var(--success)">✅ Parse thành công</h3>
                <p>📅 Ngày: <strong>${preview.date}</strong></p>
                <p>📥 Định dạng: <strong>${inputTypeLabel}</strong></p>
                <p>👥 Tổng users: <strong>${preview.total_users}</strong></p>
                ${preview.warning ? `<p style="color: var(--warning)">⚠️ ${preview.warning}</p>` : ''}
            </div>
            <h4>Xem trước 5 dòng đầu:</h4>
            <table style="font-size: 0.8rem; margin-top: 0.5rem;">
                <thead><tr><th>Rank</th><th>User</th><th>Jade</th><th>T1</th><th>T2</th></tr></thead>
                <tbody>
                    ${preview.preview_top5.map(u => `
                        <tr><td>${u.rank}</td><td>${u.username}</td><td>${formatNumber(u.jade)}</td><td>${u.t1_refs}</td><td>${u.t2_refs}</td></tr>
                    `).join('')}
                </tbody>
            </table>
        `;
        
        document.getElementById('import-step-1').style.display = 'none';
        document.getElementById('import-step-2').style.display = 'block';
        
        // Lưu rawInput để dùng khi confirmImport
        window._pendingRawInput = rawInput;
        
    } catch (err) {
        alert("Lỗi parse: " + err.message);
    } finally {
        btn.innerText = "🔍 Parse & Preview";
        btn.disabled = false;
    }
}

async function confirmImport() {
    const btn = document.getElementById('import-btn');
    const date = document.getElementById('import-date').value;
    const rawInput = window._pendingRawInput || document.getElementById('json-input').value.trim();
    const isDelayed = document.getElementById('import-delayed').checked;
    
    try {
        btn.innerText = "Importing...";
        btn.disabled = true;
        
        const response = await fetch('/api/import/import-raw', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                raw_input: rawInput,
                import_date: date,
                is_delayed: isDelayed,
                note: ""
            })
        });
        
        const result = await response.json();
        if (response.ok) {
            alert(result.message);
            hideImportModal();
            window._pendingRawInput = null;
            fetchDashboard();
        } else {
            alert("Error: " + result.detail);
        }
    } catch (err) {
        alert("Error during import");
    } finally {
        btn.innerText = "✅ Confirm Import";
        btn.disabled = false;
    }
}
```

---

## 3. CÁCH LẤY HTML TỪ BXH ARO (hướng dẫn cho Adam)

Có 2 cách:

**Cách 1 — Copy page source (toàn trang):**
1. Vào trang BXH ARO trên trình duyệt
2. Nhấn `Ctrl+U` (View Page Source) → cửa sổ mới mở ra
3. `Ctrl+A` → `Ctrl+C` để copy toàn bộ
4. Paste vào ô import

→ Parser sẽ tự tìm `<table>` trong đó, bỏ qua tất cả HTML khác.

**Cách 2 — Copy chỉ table element (Inspector):**
1. `F12` → Elements tab
2. Tìm và click vào thẻ `<table id="react-aria...">`
3. Right-click → **Copy → Copy outerHTML**
4. Paste vào ô import

→ Nhỏ gọn hơn Cách 1, cùng kết quả.

**Cách 1 tiện hơn** vì không cần mở DevTools.

---

## 4. THỨ TỰ THỰC HIỆN

```
1. pip install beautifulsoup4 → thêm vào requirements.txt
2. Thêm parse_leaderboard_html() vào services/parser.py
3. Thêm detect_and_parse() + 2 endpoint mới vào routers/import_data.py
   (extract _process_import() để tái dụng logic)
4. Sửa static/app.js: previewImport() + confirmImport() gọi endpoint mới
5. Sửa static/index.html: cập nhật placeholder textarea
6. Restart → test
```

---

## 5. VERIFY CHECKLIST

```
[ ] GET /api/import/preview-raw với HTML string → trả về total_users=100, input_type="html"
[ ] GET /api/import/preview-raw với JSON string → trả về total_users=100, input_type="json"
[ ] Preview hiện đúng: rank 1 = nau***, jade ~972K, t1=19, t2=27
[ ] Confirm import HTML → snapshot được tạo, dashboard reload có data mới
[ ] Import JSON cũ vẫn hoạt động bình thường (không bị break)
[ ] HTML có < 95 users → hiện warning "BXH có thể thiếu data"
[ ] HTML không có <table> → hiện lỗi rõ ràng "Không tìm thấy thẻ <table>"
```

**AG KHÔNG được báo "done" nếu chưa test cả HTML lẫn JSON đều import thành công.**

---

## 6. TÓM TẮT FILE CẦN SỬA

| File | Thay đổi |
|------|----------|
| `requirements.txt` | Thêm `beautifulsoup4>=4.12.0` |
| `services/parser.py` | Thêm `parse_leaderboard_html()`, import BeautifulSoup |
| `routers/import_data.py` | Thêm `detect_and_parse()`, `RawImportRequest`, 2 endpoint `/preview-raw` và `/import-raw`; extract `_process_import()` |
| `static/app.js` | Sửa `previewImport()` và `confirmImport()` gọi endpoint mới |
| `static/index.html` | Cập nhật placeholder textarea |

---

*Root cause đã được PM xác nhận qua parse thực tế: 100 users parse đúng, format khớp 100% với parser hiện có. Implement đúng spec, verify đủ checklist rồi mới báo done.*
