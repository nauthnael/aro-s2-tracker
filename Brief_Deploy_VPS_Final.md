# Brief Deploy VPS — ARO Dashboard + ARO S2 Tracker (2 apps, 1 VPS)
> Ngày: 2026-05-11 | Ubuntu 24.04 | Domain: caphe.in

---

## TỔNG QUAN KIẾN TRÚC SAU KHI DEPLOY

```
Internet (port 80/443)
        │
        ▼
  Host Nginx  ──────────────────────────────────────────
        │                                               │
        ▼                                               ▼
as2dashboard.caphe.in                      as2tracker.caphe.in
        │                                               │
        ▼                                               ▼
127.0.0.1:8081                             127.0.0.1:8000
(Docker nginx container)                   (uvicorn systemd service)
        │
        ▼
  ARO Dashboard app
```

**Thay đổi so với hiện tại:**
- Docker ARO Dashboard: đổi bind port `80` → `8081` (1 dòng config)
- Thêm: Host nginx xử lý port 80/443, route 2 subdomain
- Thêm: ARO S2 Tracker chạy qua systemd trên port 8000
- Thêm: SSL Let's Encrypt cho cả 2 subdomain

---

## BƯỚC 1 — DNS: Tạo A Record cho 2 subdomain

Vào trang quản lý DNS của `caphe.in`, thêm 2 A record:

| Type | Name         | Value (IP VPS) | TTL |
|------|--------------|----------------|-----|
| A    | as2dashboard | `<VPS_IP>`     | Auto |
| A    | as2tracker   | `<VPS_IP>`     | TTL |

> Thay `<VPS_IP>` bằng IP thật của VPS (lấy bằng lệnh `curl ifconfig.me` trên VPS).

Chờ DNS propagate (~5-10 phút). Verify bằng:
```bash
ping as2dashboard.caphe.in
ping as2tracker.caphe.in
```
Cả 2 phải trả về IP của VPS mới tiếp tục.

---

## BƯỚC 2 — Sửa ARO Dashboard: đổi port 80 → 8081

SSH vào VPS:
```bash
ssh ubuntu@<VPS_IP>
```

Vào thư mục repo ARO Dashboard và sửa docker-compose.yml:
```bash
cd ~/aro-manager/dashboard    # hoặc đường dẫn thực tế repo đang nằm
nano docker-compose.yml
```

Tìm dòng (trong service frontend hoặc nginx):
```yaml
ports:
  - "80:80"
```

Đổi thành:
```yaml
ports:
  - "8081:80"
```

Lưu file (Ctrl+O, Enter, Ctrl+X), rồi restart Docker:
```bash
docker compose down
docker compose up -d
```

Verify Docker đã chạy đúng port:
```bash
sudo ss -tlnp | grep 8081
# Phải thấy docker-proxy đang listen 8081
curl http://127.0.0.1:8081
# Phải trả về HTML của ARO Dashboard
```

---

## BƯỚC 3 — Cài Host Nginx

```bash
sudo apt update
sudo apt install nginx -y
sudo systemctl enable nginx
sudo systemctl start nginx
```

Verify:
```bash
sudo systemctl status nginx
# Phải thấy: Active: active (running)
```

---

## BƯỚC 4 — Cấu hình Nginx cho 2 subdomain

### 4.1 Tạo config cho as2dashboard.caphe.in

```bash
sudo nano /etc/nginx/sites-available/as2dashboard
```

Paste nội dung sau:
```nginx
server {
    listen 80;
    server_name as2dashboard.caphe.in;

    location / {
        proxy_pass http://127.0.0.1:8081;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 300;
        client_max_body_size 10M;
    }
}
```

### 4.2 Tạo config cho as2tracker.caphe.in

```bash
sudo nano /etc/nginx/sites-available/as2tracker
```

Paste nội dung sau:
```nginx
server {
    listen 80;
    server_name as2tracker.caphe.in;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 300;
        client_max_body_size 10M;
    }
}
```

### 4.3 Enable cả 2 site và reload nginx

```bash
sudo ln -s /etc/nginx/sites-available/as2dashboard /etc/nginx/sites-enabled/
sudo ln -s /etc/nginx/sites-available/as2tracker /etc/nginx/sites-enabled/

# Xóa config default (nếu có) để tránh conflict:
sudo rm -f /etc/nginx/sites-enabled/default

sudo nginx -t
# Phải thấy: syntax is ok / test is successful

sudo systemctl reload nginx
```

Verify tạm (chưa có SSL, chưa có tracker):
```bash
curl http://as2dashboard.caphe.in
# Phải trả về HTML của ARO Dashboard
```

---

## BƯỚC 5 — Deploy ARO S2 Tracker

### 5.1 Clone repo từ GitHub

```bash
cd /opt
sudo mkdir aro-tracker
sudo chown ubuntu:ubuntu aro-tracker
git clone https://github.com/nauthnael/aro-s2-tracker.git aro-tracker
cd aro-tracker
```

### 5.2 Tạo virtualenv và cài packages

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Verify:
```bash
python3 -c "import fastapi, uvicorn, sqlalchemy; print('OK')"
# Phải in ra: OK
```

### 5.3 Tạo thư mục data

```bash
mkdir -p /opt/aro-tracker/data
```

---

## BƯỚC 6 — Upload DB từ Windows lên VPS

Chạy lệnh này trên **Windows PowerShell** (không phải VPS):

```powershell
scp "C:\Users\Administrator\OneDrive\Documents\ARO S2 top 100 tracking\data\aro_tracker.db" ubuntu@<VPS_IP>:/opt/aro-tracker/data/aro_tracker.db
```

Verify trên VPS:
```bash
ls -lh /opt/aro-tracker/data/aro_tracker.db
# Phải thấy file ~vài MB, không phải 0 bytes
```

---

## BƯỚC 7 — Tạo Systemd Service cho Tracker

```bash
sudo nano /etc/systemd/system/aro-tracker.service
```

Paste nội dung sau:
```ini
[Unit]
Description=ARO S2 Tracker
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

Enable và start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable aro-tracker
sudo systemctl start aro-tracker
sudo systemctl status aro-tracker
# Phải thấy: Active: active (running)
```

Xem log nếu có lỗi:
```bash
sudo journalctl -u aro-tracker -n 30
```

Verify app chạy được:
```bash
curl http://127.0.0.1:8000/api/dashboard
# Phải trả về JSON có data (không phải error)
```

---

## BƯỚC 8 — SSL Let's Encrypt cho cả 2 subdomain

```bash
sudo apt install certbot python3-certbot-nginx -y

sudo certbot --nginx -d as2dashboard.caphe.in -d as2tracker.caphe.in
```

Certbot sẽ hỏi:
- Email: nhập email của bạn
- Agree terms: `Y`
- Share email: tùy (`N` cũng được)
- Redirect HTTP→HTTPS: chọn `2` (Redirect — khuyến nghị)

Sau khi xong, certbot tự sửa nginx config để thêm HTTPS. Verify:
```bash
curl https://as2tracker.caphe.in/api/dashboard
# Phải trả về JSON
```

---

## BƯỚC 9 — Bảo mật Basic Auth cho Tracker (khuyến nghị)

App Tracker chứa data nhạy cảm về chiến lược team, nên giới hạn truy cập.

```bash
sudo apt install apache2-utils -y
sudo htpasswd -c /etc/nginx/.htpasswd admin
# Nhập password khi được hỏi (nhớ password này)
```

Sửa nginx config của tracker:
```bash
sudo nano /etc/nginx/sites-available/as2tracker
```

Thêm 2 dòng vào trong block `location /`:
```nginx
location / {
    auth_basic "ARO S2 Tracker";
    auth_basic_user_file /etc/nginx/.htpasswd;

    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_read_timeout 300;
    client_max_body_size 10M;
}
```

Reload nginx:
```bash
sudo nginx -t && sudo systemctl reload nginx
```

---

## VERIFY CHECKLIST — Test từng mục

```
[ ] curl http://127.0.0.1:8081 → trả về HTML ARO Dashboard
[ ] curl http://127.0.0.1:8000/api/dashboard → trả về JSON có data
[ ] https://as2dashboard.caphe.in → ARO Dashboard hiển thị đúng
[ ] https://as2tracker.caphe.in → hỏi user/pass → sau đó hiển thị Dashboard tracker
[ ] Import BXH mới trên tracker → data lưu được
[ ] sudo systemctl status aro-tracker → Active: running
[ ] Reboot test: sudo reboot → chờ 1 phút → cả 2 app tự khởi động lại
```

---

## BƯỚC 10 — Update code tracker sau này

Khi có code mới, trên VPS:
```bash
cd /opt/aro-tracker
git pull origin master
sudo systemctl restart aro-tracker
```

---

## XỬ LÝ LỖI THƯỜNG GẶP

**Tracker không start được:**
```bash
sudo journalctl -u aro-tracker -n 50
# Xem log → thường do thiếu package hoặc DB path sai
```

**Nginx lỗi 502 Bad Gateway:**
```bash
# App chưa start hoặc port sai
sudo systemctl status aro-tracker
curl http://127.0.0.1:8000
```

**Certbot lỗi "Could not bind to IPv4":**
```bash
# Port 80 đang bị Docker chiếm, chưa có nginx host
sudo systemctl status nginx
sudo ss -tlnp | grep 80
```

**Docker Dashboard không vào được sau khi đổi port:**
```bash
cd ~/aro-manager/dashboard
docker compose ps    # kiểm tra container đang chạy
docker compose logs  # xem log lỗi
```
