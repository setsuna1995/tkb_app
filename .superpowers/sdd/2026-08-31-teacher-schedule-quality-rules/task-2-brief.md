# Task 2 Brief: Core Scheduler Engine Optimization

## 1. Objective & Scope
- **Objective**: Implement teacher schedule quality optimizations and GDTC non-consecutive days rule in `core/scheduler.py`:
  1. **GDTC non-consecutive rule**: Ensure GDTC is never scheduled on 2 consecutive days for the same class (both via `role_index.gdtc_id` and `non_consecutive_subject_ids`).
  2. **Teacher Gaps**: Avoid teacher idle gaps in a session (e.g. period 1 then 4 with 2-3 free) via `TEACHER_CONSECUTIVE_BONUS` and `TEACHER_GAP_PENALTY`.
  3. **Lone Periods & Split Days**: Avoid 1 period/day and 1 morning + 1 afternoon split days via `TEACHER_SESSION_PAIR_BONUS` and `TEACHER_SPLIT_DAY_PENALTY`.
  4. **Teacher Afternoon Balance**: Avoid teachers having full afternoons off when teaching afternoon-eligible classes via `TEACHER_AFTERNOON_BALANCE_BONUS`.
  5. **Mandatory Attendance Mornings**: Strictly bar off-sessions on `mandatory_morning_weekdays` (T2, T5, T6) and incentivize morning teaching on these days via `TEACHER_MANDATORY_MORNING_BONUS`.
  6. **Solution Quality Metric**: Rank multiple successful solutions not just by `cells_changed`, but also by teacher quality penalty score (0 gaps, 0 lone days, 0 split days).

## 2. Interface & Scoring Constants
```python
TEACHER_CONSECUTIVE_BONUS = 50
TEACHER_GAP_PENALTY = 80
TEACHER_SESSION_PAIR_BONUS = 60
TEACHER_SPLIT_DAY_PENALTY = 60
TEACHER_AFTERNOON_BALANCE_BONUS = 40
TEACHER_MANDATORY_MORNING_BONUS = 35
```

Helper functions in `core/scheduler.py`:
- `_count_teacher_gaps(state) -> int`
- `_count_teacher_lone_days(state) -> int`
- `_count_teacher_split_sessions(state) -> int`
- `_teacher_quality_penalty(state, config) -> int`

## 3. TDD Strategy
- **New test file**: `tests/test_scheduler_teacher_quality.py`
- **Tests to write**:
  - `test_gdtc_auto_non_consecutive_days`: Asserts GDTC is never on consecutive days for a class.
  - `test_avoid_teacher_gaps_penalty_and_consecutive_bonus`: Asserts consecutive periods are favored over gap periods.
  - `test_avoid_teacher_lone_period_day`: Asserts teacher periods are paired in the same session rather than split into 1-period days or 1S+1C.
  - `test_mandatory_morning_weekdays_strictly_enforced`: Asserts no teacher has off-slots on mandatory mornings (T2, T5, T6).
  - `test_balance_afternoon_teachers_scoring`: Asserts teachers teaching afternoon classes receive afternoon placements.
- **RED Phase**: Run `python -m pytest tests/test_scheduler_teacher_quality.py` and verify tests fail or assert against expected behaviors.
- **GREEN Phase**: Implement in `core/scheduler.py` and verify all tests in `tests/test_scheduler_teacher_quality.py` and existing `tests/` pass.

## 4. Safety & Invariants
- Do not degrade solver convergence or break existing constraints (liền mạch lớp, môn kép, môn nặng, chào cờ, SHL).
- Existing test suite (168 tests) must pass with 0 regressions.
