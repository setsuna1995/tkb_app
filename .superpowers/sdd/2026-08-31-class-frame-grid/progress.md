# Progress Ledger: Class Frame Checkbox Grid

## Plan Reference & Context
Feature: Allow specifying exact allowed cells for a class's timetable frame using a checkbox grid, similar to the Teacher Unavailability feature, but for positive "allowed" cells.
Replacing mathematical formulas (`morning_periods`, `afternoon_periods`) with explicit cells.

## Pre-flight Conflict Scan Table
| Tasks | File | What Task A produces | What Task B consumes | Finding |
|---|---|---|---|---|
| 1, 2 | `data/db.py`, `data/repository.py` | Schema and CRUD for `class_allowed_cells` | Integration in `build_scheduling_input` | Clean — sequential |
| 2, 3 | `core/frame.py` | Updated logic for `active_cells` (obsolete) | UI relies on repo, not `core.frame` | Clean — disjoint regions |
| 1, 3 | `pages/05_Khung_tiet.py` | UI redesign for Khung Tiết | DB/CRUD functions from Task 1 | Clean — sequential |

## Task Checklist
- [x] **Task 1**: DB Schema and Repository (create `class_allowed_cells` table, CRUD functions).
- [x] **Task 2**: Core Logic Integration (update `build_scheduling_input` to merge `class_allowed_cells` and fallback to `frame_template`).
- [x] **Task 3**: UI Update (rewrite `pages/05_Khung_tiet.py` to use a checkbox grid).
- [x] **Task 4**: Dynamic Non-Consecutive Days Constraint (update `models.py`, `repository.py`, `scheduler.py`, `pages/10_Cau_hinh_Xep_lich.py`).
