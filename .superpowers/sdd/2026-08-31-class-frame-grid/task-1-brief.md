# Task 1: DB Schema and Repository (create `class_allowed_cells` table)

## Objective & Scope
- Add `class_allowed_cells` table to the database schema in `data/db.py`.
- Create CRUD operations in `data/repository.py` for this new table.
- We will NOT yet integrate this into the scheduling engine (that's Task 2).

## Interface Specifications
```sql
CREATE TABLE IF NOT EXISTS class_allowed_cells (
    class_id     INTEGER NOT NULL REFERENCES classes(class_id) ON DELETE CASCADE,
    weekday      INTEGER NOT NULL,
    session      TEXT NOT NULL,
    period       INTEGER NOT NULL,
    PRIMARY KEY (class_id, weekday, session, period)
);
```

```python
# data/repository.py
def get_class_allowed_cells(conn: sqlite3.Connection, class_id: int) -> list[tuple[int, str, int]]:
    pass # returns list of (weekday, session, period)

def get_all_class_allowed_cells(conn: sqlite3.Connection) -> dict[int, list[tuple[int, str, int]]]:
    pass # returns class_id -> list of (weekday, session, period)

def set_class_allowed_cells(conn: sqlite3.Connection, class_id: int, cells: list[tuple[int, str, int]]) -> None:
    pass # Replaces all allowed cells for the class
```

## TDD Strategy
- New test file: `tests/test_class_frame_grid.py`
- Write a test `test_class_allowed_cells_crud` that:
  - Creates a class
  - Sets some allowed cells using `set_class_allowed_cells`
  - Retrieves them using `get_class_allowed_cells` and asserts they match
  - Uses `get_all_class_allowed_cells` to assert bulk retrieval works
- Run the test, expect `ImportError` or `OperationalError` (missing table).
- Implement the schema in `db.py` and functions in `repository.py`.
- Run the test, expect GREEN.

## Safety & Invariants
- Use in-memory SQLite for tests (`sqlite3.connect(":memory:")`) to avoid touching disk.
- Ensure `ON DELETE CASCADE` is set on `class_id` foreign key.
