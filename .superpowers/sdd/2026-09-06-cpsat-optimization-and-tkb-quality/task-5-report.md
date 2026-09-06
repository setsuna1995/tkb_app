# Task 5 Report: Bảng Đánh Giá Sức Khỏe TKB (Health Score & Dashboard)

- **Task**: Xây dựng thuật toán tính "Điểm Sức Khỏe TKB" (Thang 100) theo 3 trụ cột và tích hợp giao diện trực quan trên trang Xếp TKB (`pages/06_Xep_TKB.py`).
- **Status**: COMPLETE
- **Date**: 2026-09-06

---

## 1. Summary of Changes

1. **Thuật toán chấm điểm `compute_tkb_health_score(...)` (`core/validation.py`)**:
   - Tính toán điểm số trên thang 100 cho 3 trụ cột độc lập:
     - **Trụ cột 1: Sư Phạm Học Sinh (40%)**:
       - Giãn cách môn 2-3 tiết/tuần (tránh học 2 ngày liên tiếp).
       - Không dồn quá 3 tiết môn nặng liên tiếp.
       - Tránh xếp môn nặng vào tiết 3 buổi chiều.
       - Xếp môn GDTC trong khung giờ thể chất quy định.
     - **Trụ cột 2: Tiện Nghi & Công Bằng Giáo Viên (35%)**:
       - Đếm tiết trống (gaps) và phạt lũy tiến (gap thứ 2, gap thứ 3+) để san đều tiết trống giữa các GV.
       - Chống nhảy ca gắt (chiều muộn tiết 4/5 $\to$ sáng sớm hôm sau tiết 1).
       - Đảm bảo trần tiết dạy tối đa 5 tiết/ngày.
       - Hạn chế dạy 4 tiết sáng liên tục.
     - **Trụ cột 3: Tuân Thủ HĐSP & Kế Hoạch (25%)**:
       - Không có buổi lẻ 1 tiết (II.4) và ngày lẻ (II.4).
       - Không có ngày chia lẻ 1 sáng + 1 chiều (II.8).
       - Có mặt đầy đủ các sáng bắt buộc (II.3).
       - Không vi phạm khai báo bận (GV_Bận).
       - Không trùng lịch dạy giữa các lớp.
   - **Xếp loại chuẩn xác**: "Xuất sắc" ($\ge 90$), "Tốt" ($80-89$), "Khá" ($70-79$), "Cần cải thiện" ($< 70$).
   - **Tự động sinh Khuyến Nghị Sư Phạm Cụ Thể**: Chỉ rõ từng lớp, môn học, giáo viên và thứ/tiết cần lưu ý tinh chỉnh.

2. **Giao diện Dashboard trên `pages/06_Xep_TKB.py`**:
   - Hiển thị ngay phía trên bảng TKB khi xếp xong lịch:
     - 4 thẻ metric: Điểm Tổng Thể, Chỉ Số Sư Phạm Học Sinh, Chỉ Số Tiện Nghi & Công Bằng GV, Chỉ Số Tuân Thủ HĐSP.
     - Expander danh sách khuyến nghị sư phạm có màu sắc phân cấp (`info`, `warning`, `error`, `success`).

---

## 2. Test Verification

- `tests/test_tkb_quality_scoring.py`: 3/3 passed (100%), bao gồm:
  - `test_perfect_tkb_health_score`: Kiểm tra TKB hoàn hảo đạt 100/100 điểm.
  - `test_penalized_tkb_health_score`: Kiểm tra TKB có vi phạm bị trừ điểm chính xác và sinh khuyến nghị.
  - `test_sample_school_health_score_integration`: Giải thực tế `sample_school.xlsm` với CP-SAT và tính điểm hợp lệ.
