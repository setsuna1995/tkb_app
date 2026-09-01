# Task 1 Report: Domain Models & Config Extensions

## 1. What was implemented
- Extended `SchedulingConfig` in `core/models.py` with configuration fields for the 15 school criteria (HĐSP) and MOET rules:
  - `max_teacher_periods_per_day: int = 5` (Tiêu chí II.2)
  - `max_heavy_per_session: int = 3` (Tiêu chí I.2 & II.13)
  - `hdtn_period2_afternoon: bool = True` (Tiêu chí II.6)
  - `avoid_heavy_afternoon_period3: bool = True` (Tiêu chí II.15)
  - `avoid_teacher_4_consecutive_morning: bool = True` (Tiêu chí II.14)
  - `min_weekly_periods_for_lone_penalty: int = 15` (Tiêu chí II.4)

## 2. Files changed
- `core/models.py`: Added 6 new fields to `SchedulingConfig`
- `tests/test_mandatory_rules_compliance.py`: Added Task 1 test

## 3. TDD Evidence

### RED Phase Command
`python -m pytest tests/test_mandatory_rules_compliance.py`
```
================================== FAILURES ===================================
________ test_scheduling_config_has_all_hdsp_and_moet_criteria_fields _________
    def test_scheduling_config_has_all_hdsp_and_moet_criteria_fields():
>       assert hasattr(config, "max_teacher_periods_per_day")
E       AssertionError: assert False
============================== 1 failed in 0.11s ==============================
```

### GREEN Phase Command
`python -m pytest tests/test_mandatory_rules_compliance.py`
```
============================= test session starts =============================
collected 1 item

tests\test_mandatory_rules_compliance.py .                               [100%]
============================== 1 passed in 0.05s ==============================
```

## 4. Self-Review Findings
- All existing tests pass (`tests/test_models.py`).
- Defaults preserve backwards-compatibility and reflect standard pedagogical requirements.
