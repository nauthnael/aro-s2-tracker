# ARO Sprint 2 — Hướng Dẫn Cài Đặt & Sử Dụng

## 🔧 Cài Đặt (chỉ làm 1 lần)

### Bước 1: Cài Python packages
Mở Command Prompt hoặc PowerShell, chạy:
```
pip install openpyxl pandas
```

### Bước 2: Tạo file Master Excel
Mở Command Prompt trong thư mục tracker, chạy:
```
cd "C:\Users\Administrator\OneDrive\Documents\ARO S2 top 100 tracking"
python ARO_create_master.py
```

→ Tạo ra file **ARO_MASTER.xlsx** với 5 sheets, tự động import 18 ngày data từ v24.

---

## 📅 Quy Trình Hàng Ngày (sau 12:00 GMT+7)

### Bước 1 — Dán data vào Excel
1. Mở `ARO_MASTER.xlsx`
2. Vào sheet **📥 INPUT**
3. Nhập ngày hôm nay vào **ô C3** (ví dụ: `29/04/2026`)
4. Copy 4 cột từ bảng BXH ARO (Rank | Username | Jade | Refs)
5. Dán vào vùng **B6:E105**
6. **Lưu file** (Ctrl+S)

> ⚠️ Format dán: 4 cột tương ứng Rank | Username | Jade ("800.84K") | Refs ("46 (19 Tier 1 + 27 Tier 2)")

### Bước 2 — Nhờ Claude cập nhật và viết báo cáo
Nói với Claude:
```
"Cập nhật BXH ngày 29/04 và viết báo cáo cho tôi"
```

Claude sẽ tự động:
1. Chạy `python ARO_report.py` → cập nhật HISTORY + TRACKER + DASHBOARD
2. Đọc DASHBOARD → viết báo cáo 3 phần

---

## 📊 Cấu Trúc File ARO_MASTER.xlsx

| Sheet | Mô tả | Ai chỉnh sửa |
|-------|-------|-------------|
| 📥 INPUT | Dán data BXH hàng ngày | **Bạn** |
| 🗃️ HISTORY | Raw database (tất cả lịch sử) | Script tự động |
| 📊 TRACKER | Metrics mỗi user (W.Rate, Proj...) | Script tự động |
| 🏆 DASHBOARD | Báo cáo tổng hợp | Script tự động |
| ⚙️ CONFIG | Cài đặt (team list, ngưỡng...) | **Bạn** nếu cần |

---

## 🛠️ Các Lệnh Script

| Lệnh | Tác dụng |
|------|---------|
| `python ARO_create_master.py` | Tạo file Master (chỉ 1 lần) |
| `python ARO_update.py` | Update từ INPUT sheet |
| `python ARO_update.py --date 2026-04-29` | Update với ngày cụ thể |
| `python ARO_update.py --json data.json` | Update từ JSON file |
| `python ARO_update.py --delayed` | Đánh dấu ngày bị delay |
| `python ARO_update.py --skip-input` | Chỉ recompute metrics |
| `python ARO_report.py` | Update + xuất báo cáo Markdown |
| `python ARO_report.py --read-only` | Chỉ đọc DASHBOARD, không update |

---

## 📋 Format Data Khi Dán

ARO website thường cho phép copy bảng BXH trực tiếp. Khi dán vào Excel, cần 4 cột:

```
Cột B (Rank):   1, 2, 3, ...
Cột C (User):   nau***@gmail.com, pha***@gmail.com, ...
Cột D (Jade):   800.84K, 660.19K, 572.23K, ...  (script tự parse K/M)
Cột E (Refs):   46 (19 Tier 1 + 27 Tier 2), ...  (script tự parse T1/T2)
```

---

## ⚠️ Xử Lý Trường Hợp Đặc Biệt

### BXH bị delay
Nếu nghi ngờ BXH không cập nhật (jade tăng rất ít):
```
python ARO_update.py --delayed
```
Script sẽ downweight ngày đó trong W.Rate.

### Thêm team member mới
1. Mở sheet **⚙️ CONFIG**
2. Thêm username vào phần Team Roster (cột A/B/C)
3. Cập nhật `TEAM_T2` list trong `ARO_update.py` (dòng ~20)

### Thêm alias tên trùng
Nếu có user mới trùng tên với user cũ, thêm alias vào `ALIAS_MAP` trong `ARO_update.py`.

---

## 📁 Files Trong Thư Mục

```
ARO S2 top 100 tracking/
├── ARO_MASTER.xlsx          ← File chính (Excel)
├── ARO_create_master.py     ← Script tạo file (chạy 1 lần)
├── ARO_update.py            ← Script update hàng ngày
├── ARO_report.py            ← Script tạo báo cáo (Claude dùng)
├── SETUP_HUONG_DAN.md       ← File này
├── ARO_context.md           ← Context cho Cowork
├── ARO_daily_workflow.md    ← Workflow chi tiết
├── ARO_Sprint2_v24_28Apr.xlsx  ← File cũ (backup)
└── ARO_Team_Planner.xlsx    ← Kế hoạch team
```
