# Task 3 Brief: Scheduling Engine & Builder Integration with `week_no`

## 1. Objective & Scope
- **Objective**: Update `build_scheduling_input` in `data/repositories/builder.py` (and `data/repository.py`) to accept optional `week_no: Optional[int] = None`. When provided, it loads class/subject period requirements (`need`) from `get_periods_for_week(conn, week_no=week_no, parity=parity)`. Also update/verify validation helpers (such as `compute_quota_diff`) to accept week-specific period dict or `week_no`.
- **Scope**:
  - `data/repositories/builder.py`: `build_scheduling_input(...)` signature and `need` resolution.
  - `core/validation.py`: `compute_quota_diff` verification (accepts `periods_per_week` dict or week-specific `(s, c)` mapping).
  - Integration test: running scheduler on week 1 vs week 10.
- **Out of Scope**: UI components (handled in Task 5).

## 2. Interface Specifications
```python
def build_scheduling_input(
    conn: sqlite3.Connection,
    parity: str = "C",
    seed: int = 0,
    extra_kep_ids: frozenset = frozenset(),
    hdtn_thematic_week: bool = False,
    week_no: Optional[int] = None,
) -> SchedulingInput: ...
```

## 3. TDD Strategy
- Test file: `tests/test_weekly_scheduling_integration.py`
- Tests:
  - Test building scheduling input with `week_no=1` vs `week_no=10` on real school data.
  - Verify that `inp.need` for K8 and K9 has 30 total periods in Week 1, and 29 total periods in Week 10.
  - Test `sched.run(inp)` solving successfully.
  - Test `compute_quota_diff` returning 0 for all classes.
- RED expectation: `build_scheduling_input` does not accept `week_no` or does not reflect week-specific quota in `need`.
- GREEN expectation: all tests pass.

## 4. Safety & Invariants
- When `week_no` is `None`, behavior is 100% identical to legacy `parity` behavior.
