# Task 1 Brief: Database Schema & Repository Layer for Weekly Curriculum

## 1. Objective & Scope
- **Objective**: Create the SQLite table `weekly_curriculum` and repository functions in `data/repositories/curriculum.py` (and re-export in `data/repository.py`) to support full-year (35 weeks) period quota management, with fallback to parity `periods_per_week` if a week is unconfigured.
- **Scope**:
  - `weekly_curriculum` table DDL in `data/db.py` (`init_db` creates table).
  - Functions:
    - `get_weekly_curriculum(conn, class_id=None, week_no=None) -> dict[tuple[int, int, int], int]`
    - `set_weekly_curriculum(conn, subject_id: int, class_id: int, week_no: int, periods: int) -> None`
    - `bulk_set_weekly_curriculum(conn, entries: list[tuple[int, int, int, int]]) -> None`
    - `get_periods_for_week(conn, week_no: int, parity: Optional[str] = None) -> dict[tuple[int, int], int]`
    - `list_configured_weeks(conn) -> list[int]`
    - `get_teacher_quota_view(conn, parity: str = "C", week_no: Optional[int] = None) -> list[dict]`
- **Out of Scope**: UI modifications, Excel parsing logic (handled in later tasks).

## 2. Interface Specifications
```python
def get_weekly_curriculum(conn: sqlite3.Connection, class_id: Optional[int] = None, week_no: Optional[int] = None) -> dict[tuple[int, int, int], int]: ...
def set_weekly_curriculum(conn: sqlite3.Connection, subject_id: int, class_id: int, week_no: int, periods: int) -> None: ...
def bulk_set_weekly_curriculum(conn: sqlite3.Connection, entries: list[tuple[int, int, int, int]]) -> None: ...
def get_periods_for_week(conn: sqlite3.Connection, week_no: int, parity: Optional[str] = None) -> dict[tuple[int, int], int]: ...
def list_configured_weeks(conn: sqlite3.Connection) -> list[int]: ...
```

## 3. TDD Strategy
- Test file: `tests/test_weekly_curriculum.py`
- Tests:
  - `test_weekly_curriculum_crud()`: test insertion, update, querying by class/week.
  - `test_get_periods_for_week_exact_and_fallback()`: test week with exact records vs week falling back to parity 'C'/'L'.
  - `test_teacher_quota_view_with_week_no()`: test teacher loads computed for week_no.
- RED expectation: `ImportError` or `AttributeError` for `get_weekly_curriculum`, `get_periods_for_week`, table not found.
- GREEN expectation: all tests in `tests/test_weekly_curriculum.py` pass.

## 4. Safety & Invariants
- Thread-safe SQLite connections.
- Clean fallback to `periods_per_week` ensuring zero regressions for legacy workflows.
