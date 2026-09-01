# Task 2 Brief: Xây Dựng Thuật Toán Local Repair `_repair_teacher_lone_sessions`

## Objective & Scope
- **Mục tiêu**: Xây dựng thuật toán local repair chuyên biệt cho giáo viên (`_repair_teacher_lone_sessions`), chủ động tìm và xử lý các buổi có đúng 1 tiết của giáo viên bằng cách dồn tiết hoặc chuyển tiết để đưa về 0 tiết (nghỉ trọn buổi) hoặc $\ge 2$ tiết.
- **Phạm vi**:
  - `core/scheduler/swaps.py`: Cài đặt `_repair_teacher_lone_sessions`.
  - `core/scheduler/engine.py`: Gọi `_repair_teacher_lone_sessions` trong quy trình giải (sau `_repair_lone_periods` và `_repair_unpaired_blocks`).
  - `core/scheduler/__init__.py`: Xuất khẩu hàm mới.

## Interface Specifications
```python
def _repair_teacher_lone_sessions(
    inp: SchedulingInput,
    state: _State,
    role_index: RoleIndex,
    assigned_teacher: dict,
    slots_by_class: dict,
    day_capacity: Optional[dict] = None,
    config: Optional[SchedulingConfig] = None,
    subject_class_allowed_cells: Optional[dict] = None,
    slot_by_coord: Optional[dict] = None,
) -> None:
```

## TDD Strategy
- **File test**: `tests/test_scheduler_teacher_quality.py`
- **Tên test**: `test_repair_teacher_lone_sessions_evacuates_or_pairs`
- **RED phase**: Tạo một trạng thái TKB trong đó 1 giáo viên bị lẻ đúng 1 tiết ở buổi sáng thứ 2, chạy `_repair_teacher_lone_sessions`, xác nhận hàm giải phóng buổi đó thành 0 tiết hoặc ghép thành 2 tiết.
- **GREEN phase**: Cài đặt hoàn chỉnh thuật toán trong `swaps.py` và kết nối vào `engine.py`.

## Safety & Invariants
- Mọi phép swap di chuyển tiết đều phải qua `_feasible` kiểm tra tính hợp lệ.
- Không phá vỡ bất biến của lớp (không để lớp bị lủng hay lẻ 1 tiết).
- Không phá vỡ liên kết khối môn Kép (`role_index.block_size`).
