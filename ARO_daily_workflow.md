# ARO Sprint 2 — Daily Workflow cho Cowork
> Hướng dẫn Cowork xử lý BXH tự động mỗi ngày

---

## WORKFLOW 1: CẬP NHẬT BXH HÀNG NGÀY

### Trigger
Chạy mỗi ngày sau 12:00 trưa GMT+7 khi nhận được file BXH mới.

### Input
File BXH dạng JSON (paste trực tiếp hoặc file .txt/.json), ví dụ:
```json
[{"#":"1","username":"nau***@gmail.com","jades earned from campaign":"800.84K","referral count":"46 (19 Tier 1 + 27 Tier 2)"}...]
```

### Các bước xử lý

**Bước 1 — Parse data**
```
- Lọc bỏ các dòng separator {"#":"s","username":"s",...}
- Lấy: rank (#), username, jade (chuyển K→số nguyên), T1 refs, T2 refs
- Xử lý trùng tên:
  * Nếu 2 user cùng email prefix: so jade, đặt alias [1],[2]...
  * qua*** #38 (31,910 jade) = team member → alias "qua[T]***"
  * qua*** #88 (14,000 jade) = farm → alias "qua[F]***"
  * hun*** #20 (66,240 jade) = không phải team
  * hun*** mới (jade thấp) = team member mới
```

**Bước 2 — Load file Excel hiện tại**
```
Mở file: ARO_Sprint2_v[XX]_[DD]Apr.xlsx
Đọc sheet "📊 Master Tracker":
  - Cột username (A)
  - Cột jade ngày hôm qua (cột cuối trong dải jade)
```

**Bước 3 — Tính toán**
```python
# Với mỗi user:
delta = jade_hôm_nay - jade_hôm_qua

# W.Rate (weighted rate) — trọng số tăng dần cho ngày gần nhất
# weight_cuối = 15, giảm về 1 cho 18 ngày trước
W_Rate = sum(delta_i * weight_i) / sum(weight_i)

# Dự báo 31/05
ngay_con_lai = (date(2026,5,31) - date.today()).days
proj_31may = jade_hôm_nay + W_Rate * ngay_con_lai

# Prize dự báo
if proj_31may ranks #1: prize = "$5,000"
elif proj_31may ranks #2-5: prize = "$2,000"
elif proj_31may ranks #6-10: prize = "$1,000"
elif proj_31may ranks #11-50: prize = "$200"
elif proj_31may ranks #51-100: prize = "$50"
```

**Bước 4 — Cập nhật Excel**
```
Tạo file mới: ARO_Sprint2_v[XX+1]_[DD]Apr.xlsx
- Sheet 1 "📊 Master Tracker":
  * Thêm cột rank và jade ngày mới
  * Cập nhật cột Δ (3 ngày gần nhất)
  * Cập nhật W.Rate và Proj 31/05
  * Tô màu: nau*** = xanh đậm, team = xanh dương, ngày bị delay = cam
- Sheet 2 "📈 Rank Movement":
  * Thêm cột rank ngày mới
  * Cập nhật trend và status
```

**Bước 5 — Xuất báo cáo**

Xuất báo cáo dạng markdown gồm 3 phần:

```
## 📊 Báo Cáo [DD]/04 — [TIÊU ĐỀ NỔI BẬT NHẤT HÔM NAY]

### Báo Cáo 1: Top 10
[Bảng top 10 với: rank, user, jade, Δ hôm nay, W.Rate, refs, nhận xét]

### Báo Cáo 2: Top 10 T1 Refs Nhiều Nhất
[Bảng 10 user có nhiều T1 refs nhất, kèm verdict: ✅ Thật / ❌ Farm / ⚠️ Mix]

### Báo Cáo 3: Team nau***
[Bảng team: rank, jade, Δ, proj 31/05, prize dự kiến]
[Cảnh báo nếu có member rate giảm hoặc rớt rank]

### Ngưỡng & Cảnh báo
[Ngưỡng #50 hôm nay vs hôm qua]
[Cảnh báo nếu tăng > 2,000/ngày]
[Gương mặt mới xuất hiện]
```

---

## WORKFLOW 2: PHÂN TÍCH CHUYÊN SÂU (theo yêu cầu)

### 2A — Phân tích user cụ thể
```
Input: username
Output:
- Lịch sử rank + jade 18 ngày (biểu đồ text)
- W.Rate và xu hướng
- Phân tích refs: farm hay thật?
- Dự báo 31/05
```

### 2B — Tính toán chiến lược VPS
```
Input: số VPS, ngày còn lại
Output: So sánh các plan (1 acc top10 vs nhiều acc top50 vs nhiều acc top100)
Công thức:
  jade_1_acc = T1 × vps × jade_per_vps × 15% × days + T1×500 + milestone
  prize_per_plan = n_accs × prize_per_rank
  roi = total_prize / total_vps
```

### 2C — Kiểm tra milestone
```
Input: username, T1 refs, jade BXH
Check:
  jade_expected = T1×500 + milestone(T1) + daily_commission_tích_lũy
  if jade_actual < jade_expected: báo thiếu milestone
```

### 2D — Cập nhật team roster
```
Khi thêm thành viên mới:
- Xác nhận ref level (T1 hay T2 của nau***)
- Ghi chú trùng tên nếu có
- Theo dõi từ ngày join
- Cảnh báo nếu chưa xuất hiện trên BXH sau 2 ngày
```

---

## WORKFLOW 3: BÁO CÁO TUẦN (mỗi Chủ nhật)

```
Tổng hợp 7 ngày qua:
1. nau*** — jade tăng bao nhiêu, gap vs #2 thay đổi thế nào
2. Team — thành viên nào leo nhanh nhất, ai cần chú ý
3. Ngưỡng #50/#100 — xu hướng tăng trưởng
4. Đối thủ đáng chú ý — user nào đang bùng nổ
5. Dự báo 31/05 cập nhật — có thay đổi so với tuần trước không
6. Khuyến nghị hành động cho tuần tới
```

---

## WORKFLOW 4: CẢNH BÁO TỰ ĐỘNG

Tự động cảnh báo khi phát hiện:

| Điều kiện | Cảnh báo |
|-----------|---------|
| nau*** rate giảm > 30% so W.Rate | 🔴 Rate nau*** giảm bất thường |
| Gap vs #2 thu hẹp < 100K | 🟡 Đối thủ đang đuổi kịp |
| Team member rate = 0 liên tiếp 2 ngày | 🔴 [Tên] có thể bị gián đoạn node |
| Ngưỡng #50 tăng > 2,000/ngày | 🟡 Ngưỡng top50 đang tăng nhanh |
| User mới xuất hiện với refs > 100 | ℹ️ [User] farm mới xuất hiện |
| BXH chỉ có < 100 entries hoặc jade đứng yên | ⚠️ Có thể BXH chưa cập nhật (delay) |

---

## QUY TẮC ĐẶC BIỆT

### Xử lý delay BXH
- Nếu Δ của toàn bộ top 10 thấp bất thường (< 20% W.Rate bình thường):
  → Đánh dấu ngày đó màu CAM trong Excel
  → Downweight ×2 thay vì ×15 trong W.Rate
  → Ghi chú "⚠️ Possible delay"
  → KHÔNG dùng data ngày đó để đánh giá xu hướng

### Phân biệt trùng tên
- **qua*****: #38 (31K, 1 T1 ref) = team | #88 (14K, 20 T1 farm) = không phải team
- **hun*****: #20 (66K, 2 T1) = không phải team | jade thấp = team mới
- **tra*****: #27 và #33 đều là tra*** khác nhau → alias [1] và [2]
- **mal*****: #3 (572K) = mal[1]*** top BXH | #49 (25K) = mal[2]*** khác
- **kha*****: #47 (25K, 28 T1) và #75 (16K, 2 T1) = 2 người khác nhau
- **rom*****: #97 (12K, 7 T1) = rom[1]*** | nếu có thêm = rom[2]***

### Alias nhất quán
Luôn dùng các alias đã thiết lập:
- nau*** = "nau***" (leader)
- T1 ref trực tiếp của nau***: dan***
- Team T2: qua[T]***, inf***, caf***, kdl***, nha***, dic***, xzo***, hun[mới]***, qua[mới]***, cha***

---

## FILE NAMING CONVENTION

```
Excel tracker: ARO_Sprint2_v[VERSION]_[DD]Apr.xlsx
  Ví dụ: ARO_Sprint2_v25_29Apr.xlsx

Version tăng 1 mỗi ngày có data mới.
Version hiện tại: v24 (28/04/2026)
```

---

## CONTEXT NHANH CHO COWORK

Khi bắt đầu task mới, nhắc Cowork:
```
Tôi đang track ARO Sprint 2 Testnet cho account nau*** (hiện #1 BXH, 800K jade).
Event kết thúc 31/05/2026. File mới nhất: ARO_Sprint2_v24_28Apr.xlsx.
Đọc ARO_context.md để biết cơ chế tính jade, team roster, và lịch sử.
```

