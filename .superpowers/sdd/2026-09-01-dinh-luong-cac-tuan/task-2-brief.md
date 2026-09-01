# Task 2 Brief: Excel Weekly Importer Module

## 1. Objective & Scope
- **Objective**: Implement `io_excel/weekly_importer.py` to parse full-year weekly curriculum workbooks (such as `Định lượng số tiết theo tuần năm học 2026_2027.xlsx` or uploaded Excel files), automatically recognize sheets for all grades (HKI/HKII for Khối 6, 7, 8, 9), map subjects/sub-disciplines (KHTN: Lý/Hóa/Sinh, LS&ĐL: Sử/Địa, Nghệ thuật: Âm nhạc/Mỹ thuật, GDĐP, HĐTN...), associate them to classes of the appropriate grade, and bulk insert into `weekly_curriculum`. Also compute/update average parity periods in `periods_per_week`.
- **Scope**:
  - `import_weekly_curriculum_from_excel(conn, file_path_or_bytes) -> dict` returning summary stats (e.g. `imported_records`, `weeks_count`, `grades_found`, `classes_updated`, `subjects_mapped`).
  - Robust fuzzy / alias matching for subject & sub-discipline names.
  - Grade detection for classes (e.g., matching by first digit '6', '7', '8', '9' or grade property).
- **Out of Scope**: Streamlit UI components (handled in Task 4).

## 2. Interface Specifications
```python
def import_weekly_curriculum_from_excel(conn: sqlite3.Connection, file_source: str | bytes | BinaryIO) -> dict:
    """Parses Excel file and saves weekly curriculum for all classes and weeks into weekly_curriculum."""
```

## 3. TDD Strategy
- Test file: `tests/test_weekly_importer.py`
- Tests:
  - Test importing the real file `Định lượng số tiết theo tuần năm học 2026_2027.xlsx` into `truong-thcs.db` (or in-memory mock with full classes and subjects).
  - Verify total periods per week for Khối 6 (29), Khối 7 (29), Khối 8 (30 in weeks 1-9 & 28-35, 29 in weeks 10-27), Khối 9 (30 in weeks 1-9 & 28-35, 29 in weeks 10-27).
  - Verify that `periods_per_week` (Chẵn / Lẻ) is also populated or synchronized.
- RED expectation: `ModuleNotFoundError` / `ImportError` for `io_excel.weekly_importer`.
- GREEN expectation: all tests pass with exact 35-week periods verification.

## 4. Safety & Invariants
- Handles both file path strings and uploaded bytes/file-like objects.
- Does not crash on empty/merged cells or trailing summary rows.
