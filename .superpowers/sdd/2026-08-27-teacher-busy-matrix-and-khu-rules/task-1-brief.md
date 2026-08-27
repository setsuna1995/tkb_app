# Task 1 Brief: Backend Data & Repository Enhancements for Teacher Busy Grid

## 1. Objective & Scope
- Implement backend data helpers in data/repository.py to extract, convert, compress, and persist teacher busy cells.
- Update io_excel/importer.py to make GV_Ban importing idempotent by clearing old entries first.
- Update 	ests/fixtures/TKB_9lop_moi.xlsm and io_excel/export_template.xlsm with Thầy Khu banned from Morning Period 1 on Tuesday (3) and Thursday (5).

## 2. Interface Specifications
- get_teacher_busy_cells(conn: sqlite3.Connection, teacher_id: int) -> set[tuple[int, str, int]]
- compress_busy_cells(cells: set[tuple[int, str, int]]) -> list[tuple[str, str, str]]
- set_teacher_busy_cells(conn: sqlite3.Connection, teacher_id: int, busy_cells: set[tuple[int, str, int]]) -> None
- clear_unavailability(conn: sqlite3.Connection, teacher_id: int | None = None) -> None

## 3. TDD Strategy
- Test file: 	ests/test_busy_grid.py
- RED Phase: Assert new functions and compression logic on a fresh SQLite database.
- GREEN Phase: Validate that functions pass all assertions and round-trip conversions without data loss.

## 4. Invariants
- No schema migrations required (uses existing 	eacher_unavailability table).
- Zero regression on existing scheduler or importer functionality.
