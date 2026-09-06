# Task 1 Report: Cấu Hình Tải Học Thuật Buổi Sáng & Thẩm Định Vi Phạm

## 1. What was implemented
- Thêm 3 trường cấu hình vào `SchedulingConfig` ([core/models.py](file:///c:/Users/Kien/tkb_app/core/models.py)):
  - `balance_morning_academic_load: bool = True`
  - `max_academic_per_morning: int = 3`
  - `min_academic_per_morning: int = 2`
- Thêm 2 hàm thẩm định vi phạm tải môn học thuật buổi sáng vào [core/validation.py](file:///c:/Users/Kien/tkb_app/core/validation.py):
  - `find_morning_academic_overload_violations`: Trả về các buổi sáng có $> \text{max\_academic}$ tiết học thuật (mặc định > 3).
  - `find_morning_academic_underload_violations`: Trả về các buổi sáng có $< \text{min\_academic}$ tiết học thuật (mặc định < 2, áp dụng cho buổi sáng có $\ge 3$ tiết).
- Viết 3 unit tests TDD trong [tests/test_morning_academic_balance.py](file:///c:/Users/Kien/tkb_app/tests/test_morning_academic_balance.py).

## 2. Files changed
- `core/models.py` (modified)
- `core/validation.py` (modified)
- `tests/test_morning_academic_balance.py` (new)

## 3. TDD Evidence
- **RED phase**:
  `ImportError: cannot import name 'find_morning_academic_overload_violations' from 'core.validation'`
- **GREEN phase**:
  `3 passed in 3.43s`

## 4. Self-Review
- Không phá vỡ bất kỳ trường mặc định nào của `SchedulingConfig`.
- Toàn bộ unit test chạy thành công 100%.
