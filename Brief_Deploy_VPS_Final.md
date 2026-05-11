# Brief Deploy VPS — ARO Dashboard + ARO S2 Tracker (Docker)
> Ngày: 2026-05-11 | Ubuntu 24.04 | Domain: caphe.in

---

## KIẾN TRÚC SAU KHI DEPLOY

```
Internet (port 80/443)
        │
        ▼
  Host Nginx (SSL, routing)
        ├── as2dashboard.caphe.in → 127.0.0.1:8081  (Docker — ARO Dashboard)
        └── as2tracker.caphe.in  → 127.0.0.1:8080  (Docker — ARO S2 Tracker)
```

**Thay đổi với app Dashboard cũ:** đổi 1 dòng `80:80` → `8081:80` trong docker-compose.yml.  
**App Tracker mới:** 1 container Python/FastAPI, DB SQLite mount vào volume.

---

## BƯỚC 1 — DNS: Tạo 2 A Record

Vào trang quản lý DNS của `caphe.in`, thêm:

| Type | Name         | Value          | TTL  |
|------|--------------|----------------|------|
| A    | as2dashboard | `<VPS_IP>`     | Auto |
| A    | as2tracker   | `<VPS_IP>`     | Auto |

Lấy IP VPS bằng lệnh trên VPS:
```bash
curl ifconfig.me
```

Chờ 5-10 phút rồi verify:
```bash
ping as2tracker.caphe.in   # phải trả về IP của VPS
```

---

## BƯỚC 2 — Sửa ARO Dashboard: đổi port 80 → 8081

SSH vào VPS, vào thư mục repo Dashboard:
```bash
cd ~/aro-manager/dashboard   # hoặc đường dẫn thực tế
nano docker-compose.yml
```

Tìm dòng `"80:80"` trong service frontend, đổi thành `"8081:80"`:
```yaml
# Trước:
ports:
  - "80:80"

# Sau:
ports:
  - "8081:80"
```

Restart:
```bash
docker compose down && docker compose up -d
```

Verify:
```bash
curl http://127.0.0.1:8081   # phải trả về HTML của Dashboard
```

---

## BƯỚC 3 — Deploy ARO S2 Tracker

### 3.1 Clone repo

```bash
cd ~
git clone https://github.com/nauthnael/aro-s2-tracker.git aro-tracker
cd aro-tracker
```

### 3.2 Upload DB từ Windows lên VPS

Chạy lệnh này trên **Windows PowerShell** (máy local, không phải VPS):

```powershell
scp "C:\Users\Administrator\OneDrive\Documents\ARO S2 top 100 tracking\data\aro_tracker.db" ubuntu@<VPS_IP>:~/aro-tracker/data/aro_tracker.db
```

Verify trên VPS:
```bash
ls -lh ~/aro-tracker/data/aro_tracker.db
# Phải thấy file vài MB, không phải 0 bytes
```

### 3.3 Build và chạy Docker

```bash
cd ~/aro-tracker
docker compose up -d --build
```

Verify:
```bash
docker compose ps           # phải thấy app đang Up
curl http://127.0.0.1:8080  # phải trả về HTML Dashboard tracker
```

---

## BƯỚC 4 — Cài và cấu hình Host Nginx

### 4.1 Cài nginx

```bash
sudo apt update && sudo apt install nginx -y
sudo systemctl enable nginx
sudo systemctl start nginx
```

### 4.2 Config cho as2dashboard.caphe.in

```bash
sudo nano /etc/nginx/sites-available/as2dashboard
```

Paste:
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

### 4.3 Config cho as2tracker.caphe.in

```bash
sudo nano /etc/nginx/sites-available/as2tracker
```

Paste:
```nginx
server {
    listen 80;
    server_name as2tracker.caphe.in;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 300;
        client_max_body_size 10M;
    }
}
```

### 4.4 Enable và reload

```bash
sudo ln -s /etc/nginx/sites-available/as2dashboard /etc/nginx/sites-enabled/
sudo ln -s /etc/nginx/sites-available/as2tracker /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

sudo nginx -t              # phải thấy: syntax is ok
sudo systemctl reload nginx
```

Verify:
```bash
curl http://as2dashboard.caphe.in   # HTML Dashboard
curl http://as2tracker.caphe.in     # HTML Tracker
```

---

## BƯỚC 5 — SSL Let's Encrypt (HTTPS)

```bash
sudo apt install certbot python3-certbot-nginx -y

sudo certbot --nginx -d as2dashboard.caphe.in -d as2tracker.caphe.in
```

Khi hỏi:
- Email: nhập email
- Agree: `Y`
- Redirect HTTP→HTTPS: chọn `2` (khuyến nghị)

Verify:
```bash
curl https://as2tracker.caphe.in   # phải trả về HTML (không có SSL error)
```

---

## BƯỚC 6 — Bảo mật Basic Auth cho Tracker

App Tracker chứa data chiến lược team — nên giới hạn truy cập.

```bash
sudo apt install apache2-utils -y
sudo htpasswd -c /etc/nginx/.htpasswd admin
# Nhập và confirm password
```

Sửa nginx config tracker:
```bash
sudo nano /etc/nginx/sites-available/as2tracker
```

Thêm 2 dòng `auth_basic` vào block `location /`:
```nginx
location / {
    auth_basic "ARO S2 Tracker";
    auth_basic_user_file /etc/nginx/.htpasswd;

    proxy_pass http://127.0.0.1:8080;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_read_timeout 300;
    client_max_body_size 10M;
}
```

```bash
sudo nginx -t && sudo systemctl reload nginx
```

---

## VERIFY CHECKLIST

```
[ ] curl http://127.0.0.1:8081 → HTML ARO Dashboard
[ ] curl http://127.0.0.1:8080 → HTML ARO Tracker
[ ] https://as2dashboard.caphe.in → Dashboard hiển thị đúng
[ ] https://as2tracker.caphe.in → hỏi user/pass → Tracker hiển thị đúng
[ ] Import BXH mới → data lưu được (refresh vẫn còn)
[ ] docker compose ps (trong ~/aro-tracker) → app: Up
[ ] Reboot test: sudo reboot → chờ 1 phút → cả 2 app tự lên
```

---

## UPDATE CODE SAU NÀY

Khi có code mới:
```bash
cd ~/aro-tracker
git pull origin master
docker compose up -d --build
```

DB không bị mất vì nằm trong volume `./data/`.

---

## XỬ LÝ LỖI THƯỜNG GẶP

**Tracker không vào được (502):**
```bash
cd ~/aro-tracker
docker compose ps       # kiểm tra container có Up không
docker compose logs     # xem lỗi
```

**Dashboard không vào được sau khi đổi port:**
```bash
cd ~/aro-manager/dashboard
docker compose ps
curl http://127.0.0.1:8081
```

**Certbot lỗi:**
```bash
# Đảm bảo DNS đã propagate và nginx đang chạy trên port 80
ping as2tracker.caphe.in   # phải ra IP đúng
sudo systemctl status nginx
```

**Xem log tracker real-time:**
```bash
cd ~/aro-tracker
docker compose logs -f
```
