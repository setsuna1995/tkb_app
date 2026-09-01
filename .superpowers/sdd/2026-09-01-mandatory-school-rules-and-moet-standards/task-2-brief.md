# Task 2 Brief: Hard Constraints & Feasibility Rules

## 1. Objective & Scope
Implement feasibility checks in `core/scheduler/feasibility.py`, `core/scheduler/state.py`, and `core/scheduler/placement.py`:
1. **Teacher daily period cap (Tiêu chí II.2)**: `state.teacher_day_count[(teacher_id, ts.weekday)] < config.max_teacher_periods_per_day` (default 5).
2. **Session heavy subject periods cap (Tiêu chí I.2 & II.13)**: `state.session_heavy_count[(class_id, ts.weekday, ts.session)] < config.max_heavy_per_session` (default 3).
3. **Avoid heavy subjects on afternoon period 3 (Tiêu chí II.15)**: Disallow heavy subject placement at `session == "C"` and `period == 3` when `config.avoid_heavy_afternoon_period3` is True.

## 2. Interface Specifications
- `_State.teacher_day_count`: `(teacher_id, weekday) -> int`
- `_State.session_heavy_count`: `(class_id, weekday, session) -> int`
- `_feasible()` returns `False` when any of these limits are exceeded.

## 3. TDD Strategy
- Write unit tests in `tests/test_mandatory_rules_compliance.py`:
  - `test_teacher_max_periods_per_day_constraint()`: Placing a 6th period in a day for a teacher must be rejected when cap is 5.
  - `test_class_max_heavy_per_session_constraint()`: Placing a 4th heavy period in a session for a class must be rejected when cap is 3.
  - `test_avoid_heavy_afternoon_period3_constraint()`: Placing a heavy subject at afternoon period 3 must be rejected.
- Expected RED: Tests fail because constraints are not yet checked in `_feasible`.
- Implement changes in `core/scheduler/state.py`, `core/scheduler/placement.py`, and `core/scheduler/feasibility.py`.
- Expected GREEN: All 3 unit tests pass.
