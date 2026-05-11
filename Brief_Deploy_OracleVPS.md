# Brief Deploy — ARO Tracker lên Oracle Cloud VPS
> PM: Adam | Thực hiện: Adam hoặc AG  
> Mục tiêu: App chạy 24/7 tại `http://YOUR_IP` hoặc domain riêng, bảo mật cơ bản.

---

## TỔNG QUAN

```
Local Windows PC  →  Git/SCP upload code  →  Oracle VPS (Ubuntu)
                                               ├── Python + virtualenv
                                               ├── uvicorn (FastAPI app)
                                               ├── systemd (auto-restart)
                                               └── nginx (reverse proxy port 80)
```

App chạy trên port **8000** bên trong VPS, nginx proxy từ port **80** ra ngoài.  
DB file `data/aro_tracker.db` nằm trên disk VPS — persistent, không mất khi restart.

---

## BƯỚC 1 — Chuẩn bị VPS Oracle

### 1.1 Mở port trên Oracle Security List

Oracle mặc định chặn tất cả port ngoài 22. Phải mở port 80 (HTTP) và 443 (HTTPS nếu dùng sau):

1. Vào Oracle Cloud Console → **Networking → Virtual Cloud Networks**
2. Chọn VCN của instance → **Security Lists → Default Security List**
3. Thêm **Ingress Rule**:
   - Source CIDR: `0.0.0.0/0`
   - IP Protocol: TCP
   - Destination Port: `80`
4. (Tùy chọn) Thêm rule tương tự cho port `443`

### 1.2 Mở port trên firewall Ubuntu

```bash
sudo iptables -I INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save   # lưu để không mất sau reboot
```

Nếu không có `netfilter-persistent`:
```bash
sudo apt install iptables-persistent -y
```

---

## BƯỚC 2 — Setup môi trường trên VPS

SSH vào VPS:
```bash
ssh ubuntu@YOUR_ORACLE_IP
```

### 2.1 Cài Python và dependencies

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3 python3-pip python3-venv nginx git -y
```

### 2.2 Tạo thư mục app

```bash
sudo mkdir -p /opt/aro-tracker
sudo chown ubuntu:ubuntu /opt/aro-tracker
```

---

## BƯỚC 3 — Upload code lên VPS

**Chọn 1 trong 2 cách:**

### Cách A — SCP (upload thẳng từ Windows, không cần GitHub)

Chạy lệnh sau trên **Windows PowerShell** (thay đường dẫn và IP thực):

```powershell
scp -r "C:\Users\Administrator\OneDrive\Documents\ARO S2 top 100 tracking\*" ubuntu@YOUR_ORACLE_IP:/opt/aro-tracker/
```

**Lưu ý:** Bỏ qua các file không cần thiết. Tạo file `.scpignore` không được hỗ trợ natively — tốt hơn nên dùng cách B.

### Cách B — rsync (khuyến nghị, chỉ upload file cần thiết)

```powershell
# Trên Windows PowerShell (cần cài rsync hoặc dùng Git Bash):
rsync -avz --exclude='__pycache__' --exclude='*.pyc' --exclude='.git' --exclude='scratch' --exclude='ARO_*.xlsx' --exclude='ARO_*.py' --exclude='Brief_*.md' --exclude='data/' "C:\Users\Administrator\OneDrive\Documents\ARO S2 top 100 tracking/" ubuntu@YOUR_ORACLE_IP:/opt/aro-tracker/
```

**Giải thích exclude:**
- `data/` — **KHÔNG upload DB local**. Trên VPS sẽ tạo DB mới từ đầu (xem Bước 5 về migrate data)
- `*.xlsx`, `ARO_*.py` — file Excel và script Python cũ không cần cho web app
- `Brief_*.md` — brief chỉ dùng nội bộ
- `scratch/` — thư mục tạm

---

## BƯỚC 4 — Setup Python virtualenv và cài packages

```bash
cd /opt/aro-tracker
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Verify:
```bash
python3 -c "import fastapi, uvicorn, sqlalchemy; print('OK')"
```

---

## BƯỚC 5 — Migrate DB từ local lên VPS

**Quan trọng:** DB có 19 snapshots dữ liệu lịch sử cần giữ lại.

### Option A — Upload DB file trực tiếp (nhanh nhất)

```powershell
# Trên Windows PowerShell:
scp "C:\Users\Administrator\OneDrive\Documents\ARO S2 top 100 tracking\data\aro_tracker.db" ubuntu@YOUR_ORACLE_IP:/opt/aro-tracker/data/aro_tracker.db
```

Trước tiên tạo thư mục data trên VPS:
```bash
mkdir -p /opt/aro-tracker/data
```

### Option B — Khởi tạo DB mới trên VPS (nếu muốn bắt đầu clean)

```bash
cd /opt/aro-tracker
source venv/bin/activate
python3 -c "from database import init_db; init_db(); print('DB initialized')"
```

**Khuyến nghị: Option A** — giữ nguyên toàn bộ lịch sử 19 ngày.

---

## BƯỚC 6 — Test app chạy được

```bash
cd /opt/aro-tracker
source venv/bin/activate
python3 main.py
```

Mở trình duyệt vào `http://YOUR_ORACLE_IP:8000` — nếu thấy Dashboard là OK.

Dừng bằng `Ctrl+C`, sang bước tiếp.

---

## BƯỚC 7 — Tạo systemd service (auto-start, auto-restart)

### 7.1 Tạo file service

```bash
sudo nano /etc/systemd/system/aro-tracker.service
```

Nội dung:
```ini
[Unit]
Description=ARO Sprint 2 Tracker
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/aro-tracker
Environment="PATH=/opt/aro-tracker/venv/bin"
ExecStart=/opt/aro-tracker/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Lưu ý quan trọng:**
- `WorkingDirectory=/opt/aro-tracker` — bắt buộc, vì DB path dùng relative `./data/aro_tracker.db`
- `host=127.0.0.1` — chỉ bind localhost, nginx sẽ proxy ra ngoài (bảo mật hơn `0.0.0.0`)

### 7.2 Enable và start service

```bash
sudo systemctl daemon-reload
sudo systemctl enable aro-tracker    # auto-start khi VPS reboot
sudo systemctl start aro-tracker
sudo systemctl status aro-tracker    # kiểm tra đang chạy
```

Xem log real-time:
```bash
sudo journalctl -u aro-tracker -f
```

---

## BƯỚC 8 — Cấu hình Nginx reverse proxy

### 8.1 Tạo config nginx

```bash
sudo nano /etc/nginx/sites-available/aro-tracker
```

Nội dung:
```nginx
server {
    listen 80;
    server_name YOUR_ORACLE_IP;   # hoặc domain nếu có

    # Giới hạn truy cập (bảo mật — xem Bước 9)
    # allow 1.2.3.4;   # IP của bạn
    # deny all;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 300;
        proxy_connect_timeout 300;
        client_max_body_size 10M;   # cho phép upload JSON lớn
    }
}
```

### 8.2 Enable site và restart nginx

```bash
sudo ln -s /etc/nginx/sites-available/aro-tracker /etc/nginx/sites-enabled/
sudo nginx -t                        # kiểm tra config hợp lệ
sudo systemctl restart nginx
sudo systemctl enable nginx
```

Giờ vào `http://YOUR_ORACLE_IP` (port 80, không cần gõ :8000) là thấy app.

---

## BƯỚC 9 — Bảo mật cơ bản (QUAN TRỌNG)

App này chứa data nhạy cảm (BXH ARO, chiến lược team). Không nên để public hoàn toàn.

### Option A — Whitelist IP (đơn giản nhất)

Sửa nginx config, bỏ comment các dòng `allow`/`deny`:

```nginx
# Chỉ cho phép IP của bạn và AG truy cập:
allow 1.2.3.4;     # IP của Adam
allow 5.6.7.8;     # IP của AG (nếu cần)
deny all;
```

Sau đó: `sudo systemctl reload nginx`

**Nhược điểm:** IP động thì phải cập nhật thường xuyên.

### Option B — Basic Auth (username/password)

```bash
sudo apt install apache2-utils -y
sudo htpasswd -c /etc/nginx/.htpasswd adam    # nhập password khi được hỏi
```

Thêm vào nginx config trong block `location /`:
```nginx
auth_basic "ARO Tracker";
auth_basic_user_file /etc/nginx/.htpasswd;
```

Reload nginx. Giờ mỗi lần vào app phải nhập user/pass. Đơn giản và hiệu quả.

### Option C — HTTPS với Let's Encrypt (nếu có domain)

```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d yourdomain.com
```

Certbot tự cấu hình HTTPS và tự renew certificate.

**Khuyến nghị: Option B (Basic Auth)** — không cần domain, không phụ thuộc IP tĩnh, đủ bảo mật cho app cá nhân.

---

## BƯỚC 10 — Update code sau này

Khi có code mới từ local, update lên VPS:

```powershell
# Trên Windows — rsync lại code (không đụng data/):
rsync -avz --exclude='__pycache__' --exclude='*.pyc' --exclude='data/' --exclude='*.xlsx' "C:\Users\Administrator\OneDrive\Documents\ARO S2 top 100 tracking/" ubuntu@YOUR_ORACLE_IP:/opt/aro-tracker/
```

Rồi restart service trên VPS:
```bash
sudo systemctl restart aro-tracker
```

---

## VERIFY CHECKLIST

```
[ ] http://YOUR_ORACLE_IP hiển thị Dashboard
[ ] Import BXH mới → data lưu được (refresh trang vẫn còn)
[ ] sudo systemctl status aro-tracker → Active: running
[ ] VPS reboot → app tự start lại (test: sudo reboot, chờ 1 phút, vào lại URL)
[ ] Bảo mật: người khác không vào được nếu không có password/IP đúng
```

---

## TÓM TẮT LỆNH THEO THỨ TỰ

```bash
# === TRÊN VPS ===
sudo apt update && sudo apt install python3 python3-pip python3-venv nginx -y
sudo mkdir -p /opt/aro-tracker && sudo chown ubuntu:ubuntu /opt/aro-tracker
mkdir -p /opt/aro-tracker/data

# === TRÊN WINDOWS (upload code + DB) ===
scp -r "C:\...\ARO S2 top 100 tracking\data\aro_tracker.db" ubuntu@IP:/opt/aro-tracker/data/
rsync -avz --exclude='data/' --exclude='*.xlsx' --exclude='__pycache__' "C:\...\ARO S2 top 100 tracking/" ubuntu@IP:/opt/aro-tracker/

# === TRÊN VPS (tiếp) ===
cd /opt/aro-tracker
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python3 main.py   # test thủ công → Ctrl+C

sudo nano /etc/systemd/system/aro-tracker.service   # paste nội dung ở Bước 7
sudo systemctl daemon-reload && sudo systemctl enable aro-tracker && sudo systemctl start aro-tracker

sudo nano /etc/nginx/sites-available/aro-tracker   # paste nội dung ở Bước 8
sudo ln -s /etc/nginx/sites-available/aro-tracker /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl restart nginx

# Bảo mật Basic Auth:
sudo apt install apache2-utils -y
sudo htpasswd -c /etc/nginx/.htpasswd adam
# Thêm auth_basic vào nginx config → sudo systemctl reload nginx
```

---

*Nếu gặp lỗi ở bước nào, paste log lỗi cho PM để debug.*  
`sudo journalctl -u aro-tracker -n 50` — xem 50 dòng log gần nhất của app.
