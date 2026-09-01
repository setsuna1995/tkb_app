# Task 1 Report: Core Algorithm & Data Models (`core/load_balance.py`)

## 1. What was implemented
- Nâng cấp module `core/load_balance.py`:
  - Mở rộng dataclass `Suggestion` với các trường: `action_type` ("transfer" | "swap"), `periods_c`, `periods_l`, `from_teacher_new_load`, `to_teacher_new_load`, `swap_subject_id`, `swap_class_id`, `swap_periods_c`, `swap_periods_l`, `swap_periods`.
  - Thuật toán `suggest_rebalance` tuân thủ nghiêm ngặt nguyên tắc **Trọn gói Lớp (Class-level atomic transfer)**, chuyển trọn vẹn số tiết của lớp cả tuần Chẵn và tuần Lẻ.
  - Tích hợp cơ chế **Hoán đổi 2 lớp cùng môn (2-way Class Swap)** khi độ lệch tải nhỏ (1-2 tiết) hoặc chuyển 1 chiều làm mất cân bằng.
  - Viết hàm `apply_suggestion_to_assignments` và `apply_all_suggestions` để cập nhật bảng phân công sạch sẽ.

## 2. Files Changed / Created
- `core/load_balance.py`: Updated logic and data structures.
- `tests/test_load_balance.py`: Created test suite for load balancing.

## 3. TDD Evidence

### Command Run
`python -m pytest tests/test_load_balance.py -v`

### RED Phase Terminal Output
```
=================================== ERRORS ====================================
_________________ ERROR collecting tests/test_load_balance.py _________________
ImportError while importing test module 'C:\Users\Kien\tkb_app\tests\test_load_balance.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
..\AppData\Local\Python\pythoncore-3.14-64\Lib\importlib\__init__.py:88: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests\test_load_balance.py:2: in <module>
    from core.load_balance import (
E   ImportError: cannot import name 'apply_suggestion_to_assignments' from 'core.load_balance' (C:\Users\Kien\tkb_app\core\load_balance.py)
=========================== short test summary info ===========================
ERROR tests/test_load_balance.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
============================== 1 error in 0.24s ===============================
```

### GREEN Phase Terminal Output
```
============================= test session starts =============================
platform win32 -- Python 3.14.7, pytest-9.1.1, pluggy-1.6.0 -- C:\Users\Kien\AppData\Local\Python\pythoncore-3.14-64\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\Kien\tkb_app
plugins: anyio-4.14.2
collecting ... collected 5 items

tests/test_load_balance.py::test_compute_teacher_loads PASSED            [ 20%]
tests/test_load_balance.py::test_suggest_rebalance_transfer_whole_class PASSED [ 40%]
tests/test_load_balance.py::test_suggest_rebalance_swap_classes PASSED   [ 60%]
tests/test_load_balance.py::test_apply_suggestion_to_assignments PASSED  [ 80%]
tests/test_load_balance.py::test_suggest_rebalance_asymmetric_weeks PASSED [100%]

============================== 5 passed in 0.05s ==============================
```

## 4. Self-Review & Invariants Check
- [x] Không bao giờ chia cắt lẻ số tiết trong cùng một lớp: Verified.
- [x] Số tiết tuần C và L chuyển đồng thời cùng nhau: Verified.
- [x] Không có side-effects biến đổi input assignments/periods gốc: Verified.
- [x] Regression tests trên các module khác: 38 passed in 1.41s.
