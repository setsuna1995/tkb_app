# Task 2 Report: Excel Weekly Importer Module

## 1. What was implemented
- Created `io_excel/weekly_importer.py` implementing `import_weekly_curriculum_from_excel(conn, file_source)`.
- Added robust subject and sub-discipline mapping (KHTN: Lý, Hóa, Sinh; LS&ĐL: Sử, Địa; Nghệ thuật: Âm nhạc, Mỹ thuật; GDĐP; HĐTN...).
- Grade-to-sheet detection ignoring summary sheets and parsing `HKI_K6`, `HK2_K6`, `HKI_K7`, `HK2_K7`, `HKI_K8`, `HK2_K8`, `HKI_K9`, `HK2_K9`.
- Multi-class batch insertion for each grade across all 35 weeks.
- Synchronized average period count to parity `periods_per_week` ('C' and 'L').

## 2. Files Changed
- `io_excel/weekly_importer.py`: New module for importing 35-week curriculum workbooks.
- `io_excel/__init__.py`: Exported `import_weekly_curriculum_from_excel`.
- `tests/test_weekly_importer.py`: New unit tests asserting full 35-week import on `Định lượng số tiết theo tuần năm học 2026_2027.xlsx`.

## 3. TDD Evidence
### RED Phase:
```
FAILED tests/test_weekly_importer.py::test_import_weekly_curriculum_real_excel - ModuleNotFoundError: No module named 'io_excel.weekly_importer'
```

### GREEN Phase:
```
============================= test session starts =============================
collected 4 items

tests\test_weekly_curriculum.py ...                                      [ 75%]
tests\test_weekly_importer.py .                                          [100%]

============================== 4 passed in 0.69s ==============================
```

## 4. Self-Review Findings
- Successfully verified 29 periods across all 35 weeks for K6 & K7, and 30 periods (weeks 1-9, 28-35) / 29 periods (weeks 10-27) for K8 & K9.
