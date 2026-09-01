# Task 3 Brief: Scoring Heuristics & Quality Penalties

## 1. Objective & Scope
Implement scoring heuristics and quality penalty refinements:
1. **Tiêu chí II.6 (HĐTN 3 tiết)**: Prefer placing the unpinned HĐTN period (thematic topic) into afternoon session ("C") for classes with afternoon sessions when `config.hdtn_period2_afternoon` is True.
2. **Tiêu chí II.14 (Hạn chế GV dạy 4 tiết sáng liên tục nếu tải <= 20 tiết/tuần)**: In `_pick_best_scored` and `_teacher_quality_penalty`, apply penalty when placing a 4th morning period for a teacher whose load is $\le 20$.
3. **Tiêu chí II.4 (Hạn chế GV dạy 1 tiết/buổi hoặc 1 tiết/ngày, trừ GV < 15 tiết/tuần)**: Exempt teachers with load $< 15$ from lone session and lone day quality penalties in `_count_teacher_lone_sessions` and `_count_teacher_lone_days`.

## 2. Interface Specifications
- `_count_teacher_lone_days(slots, assigned, slot_teacher, min_weekly_periods=15) -> int`
- `_count_teacher_lone_sessions(slots, assigned, slot_teacher, min_weekly_periods=15) -> int`
- `_count_teacher_4_consecutive_mornings(slots, assigned, slot_teacher, max_load_for_penalty=20) -> int`
- `_teacher_quality_penalty(...)` integrates all 15 pedagogical penalties.

## 3. TDD Strategy
- Write unit tests in `tests/test_mandatory_rules_compliance.py`:
  - `test_teacher_lone_period_penalty_exempts_low_workload()`
  - `test_teacher_4_consecutive_mornings_penalty()`
  - `test_hdtn_period2_afternoon_heuristic_scoring()`
- Expected RED: Missing functions/arguments or unpenalized scores.
- Implement in `core/scheduler/quality.py` and `core/scheduler/heuristics.py`.
- Expected GREEN: All tests pass.
