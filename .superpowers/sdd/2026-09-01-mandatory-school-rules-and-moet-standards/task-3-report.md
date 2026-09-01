# Task 3 Report: Scoring Heuristics & Quality Penalties

## 1. What was implemented
- Implemented `hdtn_period2_afternoon` heuristic preference in `_pick_best_scored` (`core/scheduler/heuristics.py`) to schedule the unpinned HĐTN topic period into the afternoon session for classes with afternoon sessions (Tiêu chí II.6).
- Implemented `avoid_teacher_4_consecutive_morning` heuristic penalty in `_pick_best_scored` and metric `_count_teacher_4_consecutive_mornings` in `core/scheduler/quality.py` for teachers with total load $\le 20$ (Tiêu chí II.14).
- Added workload threshold parameter `min_weekly_periods` to `_count_teacher_lone_days` and `_count_teacher_lone_sessions` in `core/scheduler/quality.py`, allowing low-workload teachers ($< 15$) to be exempt from lone session penalties (Tiêu chí II.4).
- Integrated all penalty components into `_teacher_quality_penalty`.

## 2. Files changed
- `core/scheduler/heuristics.py`: Added HĐTN afternoon preference and 4-period morning avoidance heuristics.
- `core/scheduler/quality.py`: Added `_count_teacher_4_consecutive_mornings`, updated lone period counts with `min_weekly_periods`, updated `_teacher_quality_penalty`.
- `core/models.py`: Config defaults aligned.
- `tests/test_mandatory_rules_compliance.py`: Added 3 unit tests.

## 3. TDD Evidence

### RED Phase Command
`python -m pytest tests/test_mandatory_rules_compliance.py`
```
================================== FAILURES ===================================
____________ test_teacher_lone_period_penalty_exempts_low_workload ____________
E       TypeError: _count_teacher_lone_sessions() got an unexpected keyword argument 'min_weekly_periods'
_________________ test_teacher_4_consecutive_mornings_penalty _________________
E       ImportError: cannot import name '_count_teacher_4_consecutive_mornings' from 'core.scheduler.quality'
========================= 2 failed, 5 passed in 0.16s =========================
```

### GREEN Phase Command
`python -m pytest tests/test_scheduler_teacher_quality.py tests/test_mandatory_rules_compliance.py`
```
============================= test session starts =============================
collected 21 items

tests\test_scheduler_teacher_quality.py ..............                   [ 66%]
tests\test_mandatory_rules_compliance.py .......                         [100%]

============================= 21 passed in 0.10s ==============================
```

## 4. Self-Review Findings
- All 21 teacher quality and compliance tests pass seamlessly.
- Scoring heuristics and quality penalty functions are synchronized.
