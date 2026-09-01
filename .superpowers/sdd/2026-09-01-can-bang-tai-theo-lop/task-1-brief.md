# Task 1 Brief: Core Algorithm & Data Models (`core/load_balance.py`)

## 1. Objective & Scope
- Nâng cấp module `core/load_balance.py` đảm bảo quy tắc:
  1. Mọi đề xuất chuyển giao phân công phải ở cấp độ **Trọn gói Lớp** `(subject_id, class_id)`. Không bao giờ chia cắt lẻ số tiết của một lớp.
  2. Số tiết tuần Chẵn và tuần Lẻ của lớp đó đều được chuyển đồng thời sang giáo viên mới.
  3. Hỗ trợ 2 hình thức cân bằng:
     - **Chuyển 1 lớp (Transfer)**: GV A chuyển trọn gói 1 lớp môn X cho GV B.
     - **Hoán đổi 2 lớp (Swap)**: GV A chuyển lớp Y1 cho GV B, GV B chuyển lớp Y2 (cùng môn X) cho GV A khi độ chênh lệch tải nhỏ (1-2 tiết).
  4. Dataclass `Suggestion` ghi nhận đầy đủ chi tiết:
     - `action_type: str = "transfer"` ("transfer" hoặc "swap")
     - `over_teacher_id: int`
     - `over_amount: float`
     - `subject_id: int`
     - `class_id: int`
     - `periods_c: int`
     - `periods_l: int`
     - `periods: float` (trung bình 2 tuần)
     - `to_teacher_id: int`
     - `to_teacher_load: float`
     - `to_teacher_cap: int`
     - `from_teacher_new_load: float`
     - `to_teacher_new_load: float`
     - `swap_subject_id: int | None = None`
     - `swap_class_id: int | None = None`
     - `swap_periods_c: int = 0`
     - `swap_periods_l: int = 0`
     - `swap_periods: float = 0.0`
     - `reason: str = "vuot_tran"`
  5. Cung cấp hàm `apply_suggestion_to_assignments(assignments, suggestion)` và `apply_all_suggestions(assignments, suggestions)` trả về `dict` phân công mới.

## 2. Interface Specification
```python
@dataclass
class Suggestion:
    over_teacher_id: int
    over_amount: float
    subject_id: int
    class_id: int
    periods: float
    to_teacher_id: int
    to_teacher_load: float
    to_teacher_cap: int
    reason: str = "vuot_tran"
    action_type: str = "transfer"  # "transfer" | "swap"
    periods_c: int = 0
    periods_l: int = 0
    from_teacher_new_load: float = 0.0
    to_teacher_new_load: float = 0.0
    swap_subject_id: int | None = None
    swap_class_id: int | None = None
    swap_periods_c: int = 0
    swap_periods_l: int = 0
    swap_periods: float = 0.0

def suggest_rebalance(
    assignments: dict,
    periods_per_week: dict,
    parity: str,
    teacher_caps: dict,
    floor_margin: int = 3,
    allow_swap: bool = True,
) -> tuple[list[Suggestion], list[UnresolvedOverload], list[UnresolvedUnderload]]: ...

def apply_suggestion_to_assignments(assignments: dict, suggestion: Suggestion) -> dict: ...
```

## 3. TDD Strategy
- Test file: `tests/test_load_balance.py`
- **RED Phase**:
  - Test 1: `test_suggest_rebalance_transfer_whole_class` (Kiểm tra chuyển trọn gói 1 lớp, số tiết C, L, TB và tải mới của 2 GV).
  - Test 2: `test_suggest_rebalance_swap_classes` (Kiểm tra hoán đổi 2 lớp khi lệch 1 tiết).
  - Test 3: `test_apply_suggestion_to_assignments` (Kiểm tra áp dụng cập nhật `assignments`).
  - Expected failure: `AttributeError` / missing fields on `Suggestion`, missing swap logic, missing `apply_suggestion_to_assignments`.
- **GREEN Phase**:
  - Cập nhật `core/load_balance.py` với đầy đủ fields, thuật toán class transfer + swap, và các hàm helper.
  - Chạy `python -m pytest tests/test_load_balance.py -v` -> Tất cả PASS.

## 4. Invariants & Safety
- Không sửa trực tiếp input `assignments` trong hàm `suggest_rebalance` (thuần tính toán).
- Không chia cắt số tiết: một `(subject_id, class_id)` luôn đi cùng nhau.
