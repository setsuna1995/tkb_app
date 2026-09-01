# Task 2 Brief: Xây Dựng Bộ Kiểm Tra & Báo Cáo Toàn Diện (Validation & Reporting)

## 1. Objective & Scope
- **Mục tiêu**:
  1. Mở rộng `core/validation.py` với các hàm kiểm tra tự động bao phủ tất cả các quy tắc cấu hình:
     - `find_morning_only_violations` (môn cấm chiều).
     - `find_max_heavy_violations` (vượt trần môn nặng liên tiếp).
     - `find_subject_class_rule_violations` (vi phạm luật môn/lớp theo buổi).
     - `find_single_pair_violations` (vi phạm quy tắc đúng 1 cặp 2 tiết).
  2. Tích hợp đầy đủ các hàm kiểm tra và báo cáo chất lượng lịch dạy (tiết lủng/trống `find_teacher_gaps`) trên giao diện xem trước của `pages/06_Xep_TKB.py`.
  3. Thêm bộ cảnh báo xung đột cấu hình tiền khả thi (Pre-flight Validation) trên `pages/10_Cau_hinh_Xep_lich.py`.

## 2. Interface Specifications
- **`core/validation.py`**:
  ```python
  def find_morning_only_violations(slots: list, assignment: dict, morning_only_ids: set) -> list:
      """Returns [(class_id, subject_id, weekday, period), ...] for any morning-only subject placed in afternoon."""

  def find_max_heavy_violations(slots: list, assignment: dict, heavy_ids: set, max_consecutive: int = 3) -> list:
      """Returns [(class_id, weekday, session, start_period, length), ...] for any run of heavy subjects exceeding max_consecutive."""

  def find_subject_class_rule_violations(slots: list, assignment: dict, subject_class_rules: list) -> list:
      """Returns [(class_id, subject_id, weekday, session, period), ...] for any placement violating allowed_cells."""

  def find_single_pair_violations(slots: list, assignment: dict, single_pair_ids: set) -> list:
      """Returns [(class_id, subject_id, violation_type), ...] for single-pair subjects with >1 pair or invalid distribution."""
  ```

- **`pages/06_Xep_TKB.py`**:
  Hiển thị các thông báo xác thực sau khi xếp TKB:
  - Báo lỗi nếu phát hiện vi phạm ràng buộc cứng.
  - Báo thông tin / khuyến nghị chất lượng nếu phát hiện tiết lủng (`find_teacher_gaps`).

- **`pages/10_Cau_hinh_Xep_lich.py`**:
  Kiểm tra xung đột ngay khi chọn:
  - Cảnh báo nếu cùng 1 môn vừa chọn "Bắt buộc sáng (cấm chiều)" vừa chọn "Ưu tiên buổi chiều".
  - Cảnh báo nếu luật gán buổi của môn chỉ có buổi Chiều trong khi môn đó bị cấm chiều.

## 3. TDD Strategy
- **Test File**: `tests/test_scheduler_teacher_quality.py` hoặc `tests/test_scheduler_constraints.py`.
- **Tests to Add**:
  - `test_validation_morning_only_violations()`
  - `test_validation_max_heavy_violations()`
  - `test_validation_subject_class_rule_violations()`
  - `test_validation_single_pair_violations()`
- **RED Phase**: Viết các bài test gọi các hàm mới trong `core/validation.py` và quan sát `AttributeError` / `AssertionError`.
- **GREEN Phase**: Cài đặt các hàm trong `core/validation.py` và cập nhật UI.

## 4. Safety & Invariants
- `validation.py` là module pure logic (không phụ thuộc Streamlit/DB), trả về list các vi phạm.
- UI `pages/06_Xep_TKB.py` chỉ đọc kết quả kiểm tra để render, không làm thay đổi dữ liệu TKB.
