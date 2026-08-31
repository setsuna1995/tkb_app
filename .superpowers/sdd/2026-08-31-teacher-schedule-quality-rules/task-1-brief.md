# Task 1 Brief: Domain Model & Persistence for Teacher Quality Rules

## 1. Objective & Scope
- **Objective**: Extend `core.models.SchedulingConfig` with fields for teacher quality rules, and ensure `data.repository.get_scheduling_config` and `set_scheduling_config` persist and retrieve these fields faithfully.
- **Scope**:
  - `core/models.py`: `SchedulingConfig` dataclass.
  - `data/repository.py`: `get_scheduling_config()`, `set_scheduling_config()`.
  - `tests/test_repository.py`: Round-trip tests for new fields.

## 2. Interface Specifications
```python
@dataclass
class SchedulingConfig:
    # Existing fields...
    avoid_teacher_gaps: bool = True
    avoid_teacher_lone_periods: bool = True
    balance_afternoon_teachers: bool = True
    mandatory_morning_weekdays: tuple = (2, 5, 6)
```

In `data/repository.py`:
- `sched_avoid_teacher_gaps` (bool as "1"/"0")
- `sched_avoid_teacher_lone_periods` (bool as "1"/"0")
- `sched_balance_afternoon_teachers` (bool as "1"/"0")
- `sched_mandatory_morning_weekdays` (tuple of ints parsed via `_parse_weekday_tuple` / `_format_weekday_tuple`)

## 3. TDD Strategy
- **Test file**: `tests/test_repository.py`
- **New test function**: `test_set_then_get_scheduling_config_round_trips_teacher_quality_fields(conn)`
- **Expected RED failure**: `TypeError: SchedulingConfig.__init__() got unexpected keyword argument 'avoid_teacher_gaps'` or assertion failure where saved custom values are not returned.
- **Minimal Implementation (GREEN)**:
  - Add fields with default values to `core/models.py`.
  - Add parse/serialize logic in `data/repository.py`.

## 4. Safety & Invariants
- Default values must maintain 100% backward compatibility for all existing tests and callers without breaking signatures.
