# Task 1 Brief: Khắc phục Xung Đột Logic & Kích Hoạt Quy Tắc Cân Đối Buổi Chiều

## 1. Objective & Scope
- **Mục tiêu**:
  1. Đảm bảo cấu hình `single_pair_subject_ids` (môn đúng 1 cặp 2 tiết liền nhau, các tiết còn lại lẻ như Ngữ văn) có độ ưu tiên chính xác trong `core/roles.py`, không bị `ROLE_KEP` ghi đè vô hiệu hóa.
  2. Kích hoạt quy tắc `balance_afternoon_teachers` (cân đối tiết buổi chiều cho GV) trong `core/scheduler.py`: xây dựng hàm tính phạt `_count_teacher_missing_afternoon_duty` cho các GV dạy lớp có tiết chiều nhưng không được xếp buổi chiều nào, và tích hợp vào `_teacher_quality_penalty`.
  3. Xử lý đồng bộ kiểm tra `pinned_full_day_off` không bị âm thầm hủy bỏ khi trùng với `mandatory_morning_weekdays` (hoặc kiểm tra rõ ràng ngay ở validation UI).

## 2. Interface Specifications
- **`core/roles.py: resolve_roles`**:
  ```python
  def resolve_roles(subjects: list, extra_kep_ids: frozenset = frozenset(),
                    hdtn_thematic_week: bool = False,
                    single_pair_subject_ids: frozenset = frozenset()) -> RoleIndex:
  ```
  Nếu `subject_id in single_pair_subject_ids`:
  - Loại khỏi `idx.kep_ids` (nếu có từ trước do `role_code == ROLE_KEP` hoặc `ROLE_NANG_KEP`).
  - Thêm vào `idx.single_pair_ids`.
  - Thiết lập `idx.block_size[subject_id] = 2`.

- **`core/scheduler.py: _count_teacher_missing_afternoon_duty` & `_teacher_quality_penalty`**:
  ```python
  def _count_teacher_missing_afternoon_duty(
      slots: list[Slot],
      assigned: dict,
      slot_teacher: dict,
      teachers: list[Teacher],
      classes: list[ClassRoom],
      need: dict,
      assigned_teacher_map: dict
  ) -> int:
  ```
  Tính số lượng giáo viên dạy lớp có học buổi chiều nhưng lại không có bất kỳ tiết chiều nào trong tuần khi `config.balance_afternoon_teachers == True`.
  Tích hợp phạt trong `_teacher_quality_penalty`.

- **`pages/01_Khai_bao.py`**:
  Kiểm tra validation: Nếu GV ghim `pinned_full_day_off` trùng vào ngày trong `config.mandatory_morning_weekdays` (hoặc `forbidden_off_cells`), hiển thị thông báo lỗi rõ ràng trước khi lưu.

## 3. TDD Strategy
- **Test File**: `tests/test_scheduler_teacher_quality.py`
- **Tests to Add**:
  1. `test_single_pair_overrides_role_kep()`: Khởi tạo môn có `role_code=ROLE_KEP`, nhưng truyền `single_pair_subject_ids={1}` -> `role_index.single_pair_ids` phải chứa môn 1, và môn 1 không nằm trong `role_index.kep_ids`.
  2. `test_balance_afternoon_teachers_penalty()`: Tạo lịch trong đó GV dạy lớp 2 buổi nhưng không có tiết chiều nào -> kiểm tra phạt chất lượng hoạt động khi `balance_afternoon_teachers=True`.
  3. `test_pinned_full_day_off_mandatory_morning_validation()`: Kiểm tra validation không cho phép ghim nghỉ trọn ngày vào thứ có sáng bắt buộc đi làm.
- **Expected RED Phase**: Các bài test trên ban đầu sẽ fail do code hiện tại chưa xử lý các trường hợp này.
- **GREEN Phase**: Cập nhật `core/roles.py`, `core/scheduler.py`, `pages/01_Khai_bao.py`.

## 4. Safety & Invariants
- Không làm vỡ 176 bài test hiện có.
- Không thay đổi hành vi mặc định khi `balance_afternoon_teachers=False` hoặc khi không có `single_pair_subject_ids`.
