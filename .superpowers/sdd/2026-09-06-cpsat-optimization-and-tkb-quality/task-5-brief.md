# Task 5 Brief: Bảng Đánh Giá Sức Khỏe TKB (Health Score & Dashboard)

- **Task**: Xây dựng thuật toán tính "Điểm Sức Khỏe TKB" (Thang 100) theo 3 trụ cột và giao diện trực quan trên trang Xếp TKB (`pages/06_Xep_TKB.py`).
- **Feature Slug**: `2026-09-06-cpsat-optimization-and-tkb-quality`
- **Dependencies**: Task 4 (các hàm đo lường chất lượng & penalty terms đã hoàn thiện).

---

## 1. Requirements

1. **Hàm tính điểm `compute_tkb_health_score(...)` trong `core/validation.py`**:
   - **Chỉ Số Sư Phạm (Pedagogical Score - 0 đến 100)**:
     - Giãn cách môn 2-3 tiết/tuần: trừ 5 điểm/lần vi phạm liên tiếp.
     - Dồn môn nặng liên tiếp (> 3 tiết): trừ 15 điểm/lần.
     - Môn nặng tiết 3 chiều: trừ 10 điểm/lần.
     - GDTC ngoài khung giờ cho phép: trừ 10 điểm/lần.
   - **Chỉ Số Tiện Nghi & Công Bằng Giáo Viên (Teacher Ergonomics & Fairness - 0 đến 100)**:
     - Tiết trống (gaps): trừ 4 điểm/gap thông thường; trừ thêm 8 điểm/gap nếu GV bị $\ge 2$ gaps; trừ thêm 15 điểm/gap nếu GV bị $\ge 3$ gaps.
     - Nhảy ca gắt (chiều muộn tiết 4/5 -> sáng sớm hôm sau tiết 1): trừ 5 điểm/lần.
     - Vượt trần $\le 5$ tiết/ngày: trừ 20 điểm/lần.
     - Dạy 4 tiết sáng liên tục: trừ 5 điểm/lần.
   - **Chỉ Số Tuân Thủ HĐSP & Kế Hoạch (HĐSP Compliance - 0 đến 100)**:
     - Buổi lẻ 1 tiết (II.4): trừ 25 điểm/lần.
     - Ngày chia lẻ 1 sáng + 1 chiều (II.8): trừ 20 điểm/lần.
     - Thiếu sáng bắt buộc (II.3): trừ 25 điểm/lần.
     - Vi phạm giờ bận GV: trừ 50 điểm/lần.
     - Trùng lịch GV: trừ 100 điểm/lần.
   - **Điểm Sức Khỏe Tổng Thể (Overall Health Score)** = $\text{round}(0.4 \times \text{Pedagogical} + 0.35 \times \text{Teacher} + 0.25 \times \text{Compliance}, 1)$.
   - **Khuyến Nghị Sư Phạm Tự Động (Recommendations)**:
     - Danh sách các khuyến nghị cụ thể (lớp nào, môn nào, thầy cô nào) có thể tinh chỉnh thủ công để TKB đạt chất lượng hoàn hảo.

2. **Giao diện người dùng trên `pages/06_Xep_TKB.py`**:
   - Hiển thị ngay trên phần hiển thị kết quả xếp lịch:
     - Container nổi bật với 4 chỉ số metric: Điểm Tổng Thể, Điểm Sư Phạm Lớp Học, Điểm Tiện Nghi & Công Bằng GV, Điểm Tuân Thủ HĐSP.
     - Badge xếp loại: "Xuất sắc" ($\ge 90$), "Tốt" ($80-89$), "Khá" ($70-79$), "Cần cải thiện" ($< 70$).
     - Expander phân tích chi tiết & danh sách khuyến nghị sư phạm cho người xếp lịch.

---

## 2. Test Plan
- File test: `tests/test_tkb_quality_scoring.py`
- Kiểm tra tính toán điểm số từ một TKB mẫu (chuẩn xác từng tiêu chí).
- Kiểm tra danh sách khuyến nghị sư phạm sinh ra chuẩn xác.
