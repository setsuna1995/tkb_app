# Task 1 Report: Domain Model & Persistence for Teacher Quality Rules

## 1. What was implemented
- Added 4 new fields to `core.models.SchedulingConfig`:
  - `avoid_teacher_gaps: bool = True` (Tránh tiết trống của GV trong buổi)
  - `avoid_teacher_lone_periods: bool = True` (Tránh 1 tiết/ngày và sáng 1 chiều 1)
  - `balance_afternoon_teachers: bool = True` (Tránh GV nghỉ full chiều khi dạy lớp có tiết chiều)
  - `mandatory_morning_weekdays: tuple = (2, 5, 6)` (Sáng bắt buộc có mặt toàn thể GV)
- Updated `data.repository.get_scheduling_config` and `set_scheduling_config` to parse and serialize these fields with backward-compatible defaults.
- Updated default `non_consecutive_subject_ids` fallback in repository to auto-include GDTC / Thể dục.

## 2. Files Changed
- `core/models.py`
- `data/repository.py`
- `tests/test_repository.py`

## 3. TDD Evidence

### RED Phase
- **Command**: `python -m pytest tests/test_repository.py`
- **Output**:
```text
FAILED tests/test_repository.py::test_set_then_get_scheduling_config_round_trips_teacher_quality_fields
TypeError: SchedulingConfig.__init__() got an unexpected keyword argument 'avoid_teacher_gaps'
1 failed, 18 passed in 3.28s
```

### GREEN Phase
- **Command**: `python -m pytest tests/test_repository.py`
- **Output**:
```text
19 passed in 3.42s
```

## 4. Self-Review & Invariants
- Defaults preserve 100% backward compatibility.
- DB round-trip tested and verified for all combinations.
