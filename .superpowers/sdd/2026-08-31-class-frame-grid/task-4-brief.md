# Task 4: Dynamic Non-Consecutive Days Constraint

## Objective & Scope
- Introduce a new scheduling constraint: Certain subjects (like GDTC - Physical Education) should not be scheduled on consecutive days for the same class (e.g., if placed on Monday, cannot be placed on Tuesday).
- The constraint must be dynamically configurable in the UI ("Cấu hình xếp lịch"), so the user can select which subjects the rule applies to.
- If a subject has a block size of 1, the algorithm naturally prevents it from being scheduled twice on the *same* day, so this new rule strictly checks *adjacent* days.

## Implementation Details
1. **`core/models.py`**: Add `non_consecutive_subject_ids: frozenset = frozenset()` to `SchedulingConfig`.
2. **`data/repository.py`**: Update `get_scheduling_config` and `set_scheduling_config` to read/write `sched_non_consecutive_subject_ids` (as a comma-separated string) from/to `app_meta`.
3. **`core/scheduler.py`**: In `_feasible(state, slot, subject_id, teacher_id)`, add:
   ```python
   if subject_id in config.non_consecutive_subject_ids:
       # Check previous day
       if ts.weekday - 1 >= 2 and state.placed.get((class_id, subject_id, ts.weekday - 1)):
           return False
       # Check next day
       if ts.weekday + 1 <= 7 and state.placed.get((class_id, subject_id, ts.weekday + 1)):
           return False
   ```
4. **`pages/10_Cau_hinh_Xep_lich.py`**: Add a multiselect UI for "Môn không xếp liền ngày" and link it to the config.

## TDD Strategy
- Create a test `test_non_consecutive_constraint` in `tests/test_scheduler.py` (or similar file).
- RED phase: The scheduler schedules a subject on consecutive days when forced.
- GREEN phase: The `_feasible` check correctly prevents consecutive day scheduling, causing backtracking or failure if no other slot is available.
