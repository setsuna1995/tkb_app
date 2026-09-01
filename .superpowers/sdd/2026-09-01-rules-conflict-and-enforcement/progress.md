# SDD Progress Ledger: Rules Conflict Review & Full Enforcement

- **Date**: 2026-09-01
- **Feature**: `rules-conflict-and-enforcement`
- **Root Context**: Master branch / Working tree
- **Status**: `complete`

---

## Pre-flight Conflict Scan Table

| Tasks | File(s) | What Task A produces | What Task B consumes | Finding |
|---|---|---|---|---|
| 1, 2 | `core/roles.py`, `core/scheduler.py` | Task 1 adjusts role resolving and teacher quality penalty | Task 2 uses updated roles/penalties in validation & UI | Clean — strict order 1 -> 2 |
| 2, 3 | `core/validation.py`, `pages/06_Xep_TKB.py` | Task 2 adds new validation functions | Task 3 writes tests asserting these validations pass | Clean — strict order 2 -> 3 |

---

## Task Checklist

- [x] **Task 1**: Khắc phục xung đột logic (`single_pair_ids` vs `ROLE_KEP`, `pinned_full_day_off` vs `mandatory_morning_weekdays`) & kích hoạt quy tắc `balance_afternoon_teachers`. (Report: [task-1-report.md](file:///c:/Users/Kien/tkb_app/.superpowers/sdd/2026-09-01-rules-conflict-and-enforcement/task-1-report.md))
- [x] **Task 2**: Xây dựng bộ kiểm tra & báo cáo toàn diện (Post-Schedule & Pre-Flight Validation) trên `core/validation.py`, `pages/06_Xep_TKB.py`, và `pages/10_Cau_hinh_Xep_lich.py`. (Report: [task-2-report.md](file:///c:/Users/Kien/tkb_app/.superpowers/sdd/2026-09-01-rules-conflict-and-enforcement/task-2-report.md))
- [x] **Task 3**: Viết bộ test suite tự động kiểm thử toàn bộ các Rule & Chạy kiểm tra hồi quy toàn diện. (Report: [task-3-report.md](file:///c:/Users/Kien/tkb_app/.superpowers/sdd/2026-09-01-rules-conflict-and-enforcement/task-3-report.md))
