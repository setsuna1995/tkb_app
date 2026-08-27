# SDD Progress Ledger: Teacher Busy Checkbox Matrix & Khu Unavailability Rules

- **Feature slug**: teacher-busy-matrix-and-khu-rules
- **Date**: 2026-08-27
- **Branch/Target**: main
- **Status**: COMPLETE

---

## 1. Context & User Requirements

1. **Rule Change**: Thầy Lương Văn Khu không cho đi Tiết 1 Thứ 3 và Thứ 5 (Tuesday 3, Thursday 5).
2. **Feature Addition**: Thêm phần tích chọn trực quan (checkbox grid) không xếp vào tiết nào cho mọi giáo viên.

---

## 2. Pre-flight Conflict Scan Table

| Tasks | File | What Task A produces | What Task B consumes | Finding |
|---|---|---|---|---|
| 1, 2 | data/repository.py | Defines get_teacher_busy_cells, compress_busy_cells, set_teacher_busy_cells | Consumed in pages/04_GV_Ban.py for grid rendering & saving | Clean - strict order Task 1 -> Task 2 |
| 1, 3 | io_excel/importer.py & scripts/build_fixture.py | Fixture with Khu T3/T5 S1 rules & idempotent import | Tested in tests/test_real_data_schedule.py & tests/test_importer.py | Clean - disjoint regions |
| 2, 3 | pages/04_GV_Ban.py | Checkbox UI & preset actions | Tested via unit tests for data transformations & UI validation | Clean - disjoint regions |

---

## 3. Task Checklist

- [x] Task 1: Backend Data & Repository Enhancements for Teacher Busy Grid (TDD)
- [x] Task 2: Interactive UI for Checkbox Matrix in pages/04_GV_Ban.py
- [x] Task 3: Full Test Suite & Timetable Verification (73/73 tests PASS)
