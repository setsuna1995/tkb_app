# Task 4 Brief: UI Streamlit Settings & Visual Rule Cards

## 1. Objective & Scope
1. Update `data/repositories/config.py` to persist and load:
   - `max_teacher_periods_per_day`
   - `max_heavy_per_session`
   - `hdtn_period2_afternoon`
   - `avoid_heavy_afternoon_period3`
   - `avoid_teacher_4_consecutive_morning`
   - `min_weekly_periods_for_lone_penalty`
2. Update `pages/10_Cau_hinh_Xep_lich.py` to display user-friendly input controls and descriptions for these pedagogical rules.
3. Update `pages/06_Xep_TKB.py` with validation checks for:
   - Teacher max 5 periods/day violations (`find_teacher_day_cap_violations`).
   - Heavy subjects afternoon period 3 violations (`find_heavy_afternoon_period3_violations`).

## 2. Interface Specifications
- `repo.get_scheduling_config(conn)` round-trips all new fields.
- `repo.set_scheduling_config(conn, config)` persists all new fields into `app_meta`.

## 3. TDD Strategy
- Test in `tests/test_repository.py`:
  - Verify round-trip persistence of all new config fields.
- Expected RED: Missing persistence keys.
- Update `data/repositories/config.py`.
- Expected GREEN: Config round-trips correctly.
