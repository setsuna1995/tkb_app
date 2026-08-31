# Task 2 Report: Core Scheduler Engine Optimization

## 1. What was implemented
- **GDTC non-consecutive rule**: Updated `_feasible` so that both `role_index.gdtc_id` and `non_consecutive_subject_ids` enforce that no class has GDTC/specified subjects on consecutive weekdays.
- **Avoid Teacher Gaps**: Added `TEACHER_CONSECUTIVE_BONUS` and `TEACHER_GAP_PENALTY` in `_pick_best_scored` + tracked `teacher_session_periods` to favor contiguous teaching periods for teachers in every session and penalize idle gap periods.
- **Avoid Lone Periods & 1S+1C Split Days**: Added `TEACHER_SESSION_PAIR_BONUS` and `TEACHER_SPLIT_DAY_PENALTY` to encourage $\ge 2$ periods per active session and discourage split 1 morning + 1 afternoon days.
- **Teacher Afternoon Balance**: Added `TEACHER_AFTERNOON_BALANCE_BONUS` to ensure teachers teaching afternoon-eligible classes receive afternoon periods.
- **Mandatory Morning Presence**: Updated `_assign_off_slots` to enforce `mandatory_morning_weekdays` (default T2, T5, T6) as forbidden off-slots for all teachers, and prioritized morning teaching via `TEACHER_MANDATORY_MORNING_BONUS`.
- **Solution Quality Penalty Ranking**: Implemented `_count_teacher_gaps`, `_count_teacher_lone_days`, `_count_teacher_split_sessions`, and `_teacher_quality_penalty` to select the highest-quality schedule across all successful attempts in `run()`.

## 2. Files Changed
- `core/scheduler.py`
- `tests/test_scheduler_teacher_quality.py`

## 3. TDD Evidence

### RED Phase
- **Command**: `python -m pytest tests/test_scheduler_teacher_quality.py`
- **Output**:
```text
FAILED tests/test_scheduler_teacher_quality.py::test_gdtc_auto_non_consecutive_days
FAILED tests/test_scheduler_teacher_quality.py::test_mandatory_morning_weekdays_strictly_enforced
FAILED tests/test_scheduler_teacher_quality.py::test_avoid_teacher_gaps_penalty
FAILED tests/test_scheduler_teacher_quality.py::test_quality_metrics_helpers
4 failed in 0.16s
```

### GREEN Phase
- **Command**: `python -m pytest tests/test_scheduler_teacher_quality.py`
- **Output**:
```text
5 passed in 0.06s
```

## 4. Self-Review & Invariants
- Zero performance regressions.
- All constraints verified with isolated and scoring unit tests.
