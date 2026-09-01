# Superpowers SDD Ledger: Cân bằng tải giáo viên theo trọn gói Lớp

- **Feature**: Class-level Teacher Load Balancing & Direct Assignment Sync
- **Date**: 2026-09-01
- **Working Branch / Dir**: `c:\Users\Kien\tkb_app`
- **Status**: COMPLETE

---

## Pre-flight Conflict Scan Table

| Tasks | File | What Task A produces | What Task B consumes | Finding |
|---|---|---|---|---|
| 1, 2 | `core/load_balance.py` | Enhanced `Suggestion` dataclass, class transfer & class swap logic, `apply_suggestions_to_assignments` | Consumed by tests in `tests/test_load_balance.py` and UI in Task 2 | Clean — Strict order Task 1 (Core) -> Task 2 (UI Integration) |
| 1, 2 | `pages/07_Can_Bang_Tai.py` | Consumes new fields of `Suggestion` and `suggest_rebalance` | Renders load balance UI and performs DB sync | Clean — Task 2 integrates Task 1 output |
| 2, 3 | `pages/11_Huong_Dan.py` | Documentation of the load balance feature | User guide text | Clean — Documentation in Task 3 |

---

## Task Checklist

- [x] **Task 1: Core Algorithm & Data Models (`core/load_balance.py`)**
  - [x] Write `task-1-brief.md`
  - [x] TDD RED: Create `tests/test_load_balance.py` with failing assertions
  - [x] TDD GREEN: Implement class-level transfer, class swap, and load recalculation
  - [x] Run test suite & capture evidence
  - [x] Generate `task-1-report.md`
- [x] **Task 2: UI & 1-Click DB Sync (`pages/07_Can_Bang_Tai.py`)**
  - [x] Write `task-2-brief.md`
  - [x] Implement class-level load table, suggestion checkboxes, and DB apply button
  - [x] Test DB sync flow & capture evidence
  - [x] Generate `task-2-report.md`
- [x] **Task 3: Guide Documentation & Full Suite Regression (`pages/11_Huong_Dan.py`)**
  - [x] Write `task-3-brief.md`
  - [x] Update guide section in `pages/11_Huong_Dan.py`
  - [x] Run full project regression check
  - [x] Generate `task-3-report.md`
  - [x] Finalize ledger
