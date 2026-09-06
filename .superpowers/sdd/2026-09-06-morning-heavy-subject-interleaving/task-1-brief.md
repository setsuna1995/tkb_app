# Task 1 Brief: Cấu Hình Tải Học Thuật Buổi Sáng & Thẩm Định Vi Phạm

## 1. Objective & Scope
- Bổ sung cấu hình `balance_morning_academic_load`, `max_academic_per_morning`, `min_academic_per_morning` vào `SchedulingConfig` trong [core/models.py](file:///c:/Users/Kien/tkb_app/core/models.py).
- Bổ sung các hàm kiểm tra vi phạm quá tải / thiếu tải môn học thuật buổi sáng trong [core/validation.py](file:///c:/Users/Kien/tkb_app/core/validation.py).
- Viết unit tests kiểm tra tính đúng đắn theo quy trình TDD Red-Green trong `tests/test_morning_academic_balance.py`.

## 2. Interface Specifications
```python
# core/models.py
@dataclass
class SchedulingConfig:
    # ...
    balance_morning_academic_load: bool = True
    max_academic_per_morning: int = 3
    min_academic_per_morning: int = 2

# core/validation.py
def find_morning_academic_overload_violations(
    slots: list, assignment: dict, academic_ids: set, max_academic: int = 3
) -> list[tuple[int, int, int]]:
    """Returns [(class_id, weekday, count), ...] where count > max_academic."""

def find_morning_academic_underload_violations(
    slots: list, assignment: dict, academic_ids: set, min_academic: int = 2
) -> list[tuple[int, int, int]]:
    """Returns [(class_id, weekday, count), ...] where count < min_academic (for mornings having at least 3 periods total)."""
```

## 3. TDD Strategy
1. **RED Phase**:
   - Viết test trong `tests/test_morning_academic_balance.py` kiểm tra logic đếm và phát hiện vi phạm quá tải (>3) và thiếu tải (<2).
   - Chạy `py -3.14 -m pytest tests/test_morning_academic_balance.py` -> Dự kiến FAIL (ImportError / AttributeError).
2. **GREEN Phase**:
   - Cập nhật `core/models.py` và `core/validation.py`.
   - Chạy lại test -> Dự kiến PASS 100%.

## 4. Safety & Invariants
- Giữ nguyên toàn bộ giá trị mặc định của các cấu hình khác trong `SchedulingConfig`.
- Không làm thay đổi signature của bất kỳ hàm validation hiện có nào.
