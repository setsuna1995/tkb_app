# Task 4 Report: UI Streamlit Settings & Visual Rule Cards

## 1. What was implemented
- Updated `data/repositories/config.py` to persist and load:
  - `max_teacher_periods_per_day`
  - `max_heavy_per_session`
  - `hdtn_period2_afternoon`
  - `avoid_heavy_afternoon_period3`
  - `avoid_teacher_4_consecutive_morning`
  - `min_weekly_periods_for_lone_penalty`
- Added validation helper functions in `core/validation.py`:
  - `find_teacher_day_cap_violations`
  - `find_heavy_afternoon_period3_violations`
- Updated UI in `pages/10_Cau_hinh_Xep_lich.py` with a dedicated section **"Tiêu chuẩn BGD & Tiêu chí HĐSP Nhà Trường"** and associated input fields.
- Updated `pages/06_Xep_TKB.py` to check and report violations for teacher day caps and afternoon period 3 heavy subject placements.

## 2. Files changed
- `data/repositories/config.py`: Added metadata serialization/deserialization for 6 new config fields.
- `core/validation.py`: Added `find_teacher_day_cap_violations` and `find_heavy_afternoon_period3_violations`.
- `pages/10_Cau_hinh_Xep_lich.py`: Added UI input controls for all 6 new fields.
- `pages/06_Xep_TKB.py`: Added post-run validation checks and error reporting.
- `tests/test_repository.py`: Added round-trip config test.

## 3. TDD Evidence

### RED Phase Command
`python -m pytest tests/test_repository.py -k test_set_then_get_scheduling_config_round_trips_mandatory_criteria_fields`
```
================================== FAILURES ===================================
__ test_set_then_get_scheduling_config_round_trips_mandatory_criteria_fields __
E       assert 5 == 4
====================== 1 failed, 19 deselected in 0.41s =======================
```

### GREEN Phase Command
`python -m pytest tests/test_repository.py`
```
============================= test session starts =============================
collected 20 items

tests\test_repository.py ....................                            [100%]
============================= 20 passed in 3.68s ==============================
```

## 4. Self-Review Findings
- All 20 tests in `test_repository.py` pass.
- Streamlit pages now have full visibility into and control over the 15 criteria and MOET standards.
