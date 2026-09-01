# Task 3 Report: Scheduling Engine & Builder Integration with `week_no`

## 1. What was implemented
- Updated `build_scheduling_input` in `data/repositories/builder.py` with `week_no: Optional[int] = None`.
- Dynamically resolved subject/class period quotas (`need`) using `get_periods_for_week(conn, week_no=week_no, parity=parity)`.
- Updated `compute_quota_diff` in `core/validation.py` to support both 2-tuple week dictionaries and 3-tuple parity dictionaries.
- Verified that Week 1 (30 periods for K8/K9) vs Week 10 (29 periods for K8/K9) load accurate requirements and evaluate zero diff on successful solutions.

## 2. Files Changed
- `data/repositories/builder.py`: Added `week_no` parameter to `build_scheduling_input`.
- `core/validation.py`: Made `compute_quota_diff` accept optional parity and week-specific period mappings.
- `tests/test_weekly_scheduling_integration.py`: Integration tests asserting week-specific input construction and quota diff calculation.

## 3. TDD Evidence
### RED Phase:
```
TypeError: compute_quota_diff() missing 1 required positional argument: 'parity'
```

### GREEN Phase:
```
============================= test session starts =============================
collected 26 items

tests\test_weekly_curriculum.py ...                                      [ 11%]
tests\test_weekly_importer.py .                                          [ 15%]
tests\test_weekly_scheduling_integration.py ..                           [ 23%]
tests\test_repository.py ....................                            [100%]

============================= 26 passed in 2.35s ==============================
```

## 4. Self-Review Findings
- Zero regressions on existing `build_scheduling_input` calls since `week_no` is optional and defaults to `None`.
