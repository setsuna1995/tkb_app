# SDD Progress Ledger: Định lượng số tiết đầy đủ các tuần trong năm học (2026-2027)

**Feature**: Định lượng 35 tuần năm học & Xếp TKB theo tuần tương ứng  
**Date**: 2026-09-01  
**Status**: In Progress (Planning Phase)  

---

## Pre-flight Conflict Scan Table

| Tasks | File | What Task A produces | What Task B consumes | Finding |
|---|---|---|---|---|
| 1, 2 | `data/repositories/curriculum.py` | `weekly_curriculum` repository functions | Consumes in Excel importer to store 35 weeks | Clean — Task 1 -> Task 2 order |
| 1, 3 | `data/repositories/builder.py` | `get_periods_for_week` | Consumes in `build_scheduling_input(..., week_no)` | Clean — Task 1 -> Task 3 order |
| 2, 4 | `pages/03_DinhMuc.py` | `import_weekly_curriculum_from_excel` | Consumes importer in UI button | Clean — Task 2 -> Task 4 order |
| 3, 5 | `pages/06_Xep_TKB.py` | `week_no` support in builder | Consumes `week_no` in UI scheduler | Clean — Task 3 -> Task 5 order |

---

## Task Checklist

- [x] **Task 1**: Database Schema & Repository Layer for Weekly Curriculum (`weekly_curriculum`, CRUD, fallback, teacher quota view)
- [x] **Task 2**: Excel Weekly Importer Module (`io_excel/weekly_importer.py` for parsing 35-week sheets & auto-mapping)
- [x] **Task 3**: Scheduling Engine & Builder Integration (`builder.py`, `build_scheduling_input` with `week_no`, quota diff)
- [x] **Task 4**: UI Updates: `03_DinhMuc.py` (Full-year weekly view, editing, auto-import from Excel)
- [x] **Task 5**: UI Updates: `06_Xep_TKB.py` & `08_Lich_su_Tuan.py` (Selecting specific week 1..35, week-based scheduling & batch scheduling)
- [x] **Task 6**: Full Suite Regression Check & Walkthrough
