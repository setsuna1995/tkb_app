# Task 1 Report: Core Data & Repository Enhancement for Teacher 35-Week Workload Profile

## 1. What was implemented
- Upgraded `get_teacher_quota_view` in `data/repositories/curriculum.py` to calculate comprehensive 35-week workload metrics:
  - `weekly_loads`: `{1: load_1, ..., 35: load_35}`
  - `load_full_year_avg`: full-year average load across all 35 weeks
  - `load_hk1_avg`: semester 1 average load (weeks 1..18)
  - `load_hk2_avg`: semester 2 average load (weeks 19..35)
  - `max_week`, `max_load`, `min_week`, `min_load`: peak and lowest workload weeks
  - `over_current`, `over_hk1`, `over_hk2`, `over_year`: deviations against `cap`
  - `under_current`, `under_year`: warnings against `min_floor`
  - `assignments`: each teacher's assignment includes `weekly_periods` mapping for all 35 weeks.

## 2. Files Changed
- `data/repositories/curriculum.py`: Extended `get_teacher_quota_view`.
- `tests/test_teacher_weekly_quota.py`: Added unit test asserting 35-week teacher workload calculations.

## 3. TDD Evidence
### RED Phase:
```
FAILED tests/test_teacher_weekly_quota.py::test_teacher_quota_view_35_week_profile
KeyError: 'load_full_year_avg'
```

### GREEN Phase:
```
tests\test_weekly_curriculum.py ...                                      [ 42%]
tests\test_weekly_importer.py .                                          [ 57%]
tests\test_weekly_scheduling_integration.py ..                           [ 85%]
tests\test_teacher_weekly_quota.py .                                     [100%]

============================== 7 passed in 0.92s ==============================
```

## 4. Self-Review Findings
- All legacy keys (`load`, `load_chan`, `load_le`, `load_avg`, `over`, `under`) are preserved for 100% backward compatibility.
