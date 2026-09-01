# Task 5 Brief: UI Updates for `06_Xep_TKB.py` & `08_Lich_su_Tuan.py`

## 1. Objective & Scope
- **Objective**: Update `pages/06_Xep_TKB.py` to allow users to select a specific week in the school year (Tuần 1 -> Tuần 35) or Parity mode, automatically applying that week's exact curriculum quota (`need`). Update the quota diff table to validate against `get_periods_for_week(conn, week_no=chosen_week)`. Enhance batch scheduling ("Xếp nhiều tuần cùng lúc") to support scheduling across any selected range of weeks (e.g. 1..18, 19..35) with their week-specific quotas. Also update `08_Lich_su_Tuan.py` if needed.
- **Scope**:
  - `pages/06_Xep_TKB.py`:
    - Week selection: radio to choose "Tuần cụ thể trong năm (1-35)" vs "Tuần Chẵn / Lẻ".
    - Pass `week_no=chosen_week` to `repo.build_scheduling_input(...)`.
    - Pass `repo.get_periods_for_week(conn, week_no=chosen_week)` to `compute_quota_diff`.
    - Save run with `week_no=chosen_week`.
    - In batch mode, allow selecting weeks $1..35$, scheduling each with its corresponding `week_no` and verifying quota diff for each week.
- **Out of Scope**: Core solver algorithm changes (already verified in Task 3).

## 2. Interface Specifications
- Streamlit interactive UI in `pages/06_Xep_TKB.py`.

## 3. TDD Strategy
- Check compilation and run tests on scheduling workflows.

## 4. Safety & Invariants
- Preserves all soft constraints, teacher unavailability checks, GDTC rules, heavy subject limits, and official timetable saving.
