# Task 2 Report: Xây Dựng Bộ Kiểm Tra & Báo Cáo Toàn Diện (Validation & Reporting)

## 1. What was implemented
- **Mở rộng `core/validation.py`**:
  - `find_morning_only_violations`: Kiểm tra môn cấm chiều có bị xếp xuống chiều không.
  - `find_max_heavy_violations`: Kiểm tra lớp có bị dồn quá số tiết môn Nặng liên tiếp không.
  - `find_subject_class_rule_violations`: Kiểm tra môn/lớp có bị xếp ngoài các ô (thứ, buổi) cho phép không.
  - `find_single_pair_violations`: Kiểm tra môn 1 cặp liền tiết có bị phân bổ sai quy tắc không.
- **Tích hợp kiểm tra & báo cáo trên `pages/06_Xep_TKB.py`**:
  - Tự động chạy tất cả 8 hàm kiểm tra vi phạm ràng buộc sau khi xếp TKB.
  - Hiển thị khu vực cảnh báo chất lượng lịch dạy của giáo viên (các buổi có tiết trống / lủng `find_teacher_gaps`).
- **Thêm Pre-flight Validation trên `pages/10_Cau_hinh_Xep_lich.py`**:
  - Cảnh báo xung đột nếu cùng 1 môn vừa chọn "Bắt buộc sáng (cấm chiều)" vừa chọn "Ưu tiên buổi chiều".
  - Chặn tạo luật gán buổi chỉ cho phép buổi Chiều nếu môn đó đang bị cấm xếp buổi chiều.

## 2. Files changed
- `core/validation.py`: Thêm 4 hàm kiểm tra vi phạm quy tắc.
- `pages/06_Xep_TKB.py`: Tích hợp toàn diện các validator và expander cảnh báo chất lượng lịch GV.
- `pages/10_Cau_hinh_Xep_lich.py`: Thêm cảnh báo xung đột cấu hình tiền khả thi.
- `tests/test_scheduler_teacher_quality.py`: Bổ sung test `test_validation_new_helpers`.

## 3. TDD Evidence
- **Command**: `python -m pytest tests/test_scheduler_teacher_quality.py`
- **RED Output**:
```
FAILED tests/test_scheduler_teacher_quality.py::test_validation_new_helpers
AttributeError: module 'core.validation' has no attribute 'find_morning_only_violations'
```
- **GREEN Output**:
```
tests\test_scheduler_teacher_quality.py ..........                       [100%]
============================= 10 passed in 0.06s ==============================
```

## 4. Self-Review Findings
- Toàn bộ các quy tắc cấu hình hiện đều có hàm kiểm tra tự động độc lập và hiển thị trực quan cho người dùng ngay sau khi xếp TKB.
