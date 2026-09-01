# Task 2 Report: Hard Constraints & Feasibility Rules

## 1. What was implemented
- Added `teacher_day_count` to `_State` and updated `_put_at` / `_remove_at` to track daily teacher workload.
- Added `session_heavy_count` to `_State` and updated `_put_at` / `_remove_at` to track heavy periods per session for a class.
- Enforced hard feasibility checks in `_feasible`:
  - `teacher_day_count < max_teacher_periods_per_day` (Tiêu chí II.2: Mỗi GV không quá tải vượt 5 tiết/ngày).
  - `session_heavy_count < max_heavy_per_session` (Tiêu chuẩn I.2 & Tiêu chí II.13: Tối đa 3 tiết môn nặng trong 1 buổi cho 1 lớp).
  - `avoid_heavy_afternoon_period3`: Disallow placing heavy subjects at afternoon period 3 (`ts.session == "C" and ts.period == 3`) (Tiêu chí II.15).

## 2. Files changed
- `core/scheduler/state.py`: Added `teacher_day_count` and `session_heavy_count`
- `core/scheduler/placement.py`: Updated `_put_at` and `_remove_at`
- `core/scheduler/feasibility.py`: Added 3 hard pruning checks in `_feasible`
- `tests/test_mandatory_rules_compliance.py`: Added 3 new unit tests

## 3. TDD Evidence

### RED Phase Command
`python -m pytest tests/test_mandatory_rules_compliance.py`
```
================================== FAILURES ===================================
_________________ test_teacher_max_periods_per_day_constraint _________________
E       AttributeError: '_State' object has no attribute 'teacher_day_count'
_________________ test_class_max_heavy_per_session_constraint _________________
E       AttributeError: '_State' object has no attribute 'session_heavy_count'
________________ test_avoid_heavy_afternoon_period3_constraint ________________
E       AssertionError: assert True is False
========================= 3 failed, 1 passed in 0.15s =========================
```

### GREEN Phase Command
`python -m pytest tests/test_mandatory_rules_compliance.py`
```
============================= test session starts =============================
collected 4 items

tests\test_mandatory_rules_compliance.py ....                            [100%]
============================== 4 passed in 0.07s ==============================
```

## 4. Self-Review Findings
- Zero regressions across `tests/test_scheduler_constraints.py` and `tests/test_scheduler_teacher_quality.py` (15/15 passed).
- Incremental updates in `_put_at` and `_remove_at` ensure $O(1)$ fast lookup in `_feasible`.
