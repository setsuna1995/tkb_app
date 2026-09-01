# Task 1 Report: Database Schema & Repository Layer for Weekly Curriculum

## 1. What was implemented
- Added SQLite table `weekly_curriculum` to schema in `data/db.py`.
- Added weekly curriculum CRUD & lookup functions in `data/repositories/curriculum.py`:
  - `get_weekly_curriculum(conn, class_id=None, week_no=None)`
  - `set_weekly_curriculum(conn, subject_id, class_id, week_no, periods)`
  - `bulk_set_weekly_curriculum(conn, entries)`
  - `list_configured_weeks(conn)`
  - `get_periods_for_week(conn, week_no, parity=None)` with clean parity fallback.
- Enhanced `get_teacher_quota_view(conn, parity="C", week_no=None)` to compute load for specific weeks.
- Re-exported functions in `data/repository.py`.

## 2. Files Changed
- `data/db.py`: Added table `weekly_curriculum`.
- `data/repositories/curriculum.py`: Implemented weekly curriculum functions and extended `get_teacher_quota_view`.
- `data/repository.py`: Re-exported new functions in `__all__`.
- `tests/test_weekly_curriculum.py`: New unit tests for weekly curriculum operations.

## 3. TDD Evidence
### RED Phase:
```
FAILED tests/test_weekly_curriculum.py::test_weekly_curriculum_crud - AttributeError: module 'data.repository' has no attribute 'set_weekly_curriculum'
FAILED tests/test_weekly_curriculum.py::test_get_periods_for_week_exact_and_fallback - AttributeError: module 'data.repository' has no attribute 'get_periods_for_week'
FAILED tests/test_weekly_curriculum.py::test_teacher_quota_view_with_week_no - AttributeError: module 'data.repository' has no attribute 'set_weekly_curriculum'
```

### GREEN Phase:
```
============================= test session starts =============================
collected 23 items

tests\test_weekly_curriculum.py ...                                      [ 13%]
tests\test_repository.py ....................                            [100%]

============================= 23 passed in 1.49s ==============================
```

## 4. Self-Review Findings
- `get_periods_for_week` gracefully falls back to `periods_per_week` based on parity when a week is not explicitly configured, preserving 100% compatibility with all existing workflows.
