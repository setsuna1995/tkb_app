# Task 1 Brief: Điều chỉnh Greedy Heuristics & Constants để Tránh Buổi 1 Tiết Cho GV

## Objective & Scope
- **Mục tiêu**: Điều chỉnh trọng số điểm thưởng/phạt trong thuật toán greedy placement để chủ động ưu tiên ghép cặp 2+ tiết/buổi cho giáo viên và ngăn chặn việc mở buổi mới chỉ có 1 tiết.
- **Phạm vi**:
  - `core/scheduler/constants.py`: Tăng `TEACHER_SESSION_PAIR_BONUS` từ 150 lên 320.
  - `core/scheduler/heuristics.py`: 
    1. Tăng thưởng khi thêm tiết thứ 2 (`current_in_session == 1` -> +320).
    2. Điều kiện hoá `TEACHER_MANDATORY_MORNING_BONUS`: Chỉ áp dụng ép sáng bắt buộc khi giáo viên có đủ số tiết trong tuần (>= 12 tiết) để tránh rải vụn các buổi 1 tiết cho GV ít tiết.
    3. Thêm phạt khi mở buổi mới `current_in_session == 0` mà GV còn quá ít tiết còn lại.

## Interface Specifications
Không thay đổi chữ ký hàm của `_pick_best_scored`.
Chỉ cập nhật logic tính `score` bên trong hàm.

## TDD Strategy
- **File test**: `tests/test_scheduler_teacher_quality.py`
- **Tên test**: `test_greedy_prefers_pairing_over_lone_session`
- **RED phase**: Viết test kiểm tra hàm chọn ứng viên `_pick_best_scored` ưu tiên ghép vào buổi đã có 1 tiết hơn là mở một buổi hoàn toàn mới.
- **GREEN phase**: Cập nhật `constants.py` và `heuristics.py` để test pass.

## Safety & Invariants
- Giữ vững toàn bộ các bất biến cứng về feasibility (không vi phạm phòng kín, tiết cấm, trần tiết).
