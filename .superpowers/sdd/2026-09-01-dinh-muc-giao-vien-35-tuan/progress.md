# SDD Progress Ledger: Định mức Giáo viên dựa trên Định lượng 35 tuần năm học

- **Feature Branch / Workspace**: `c:\Users\Kien\tkb_app`
- **Spec / Plan Reference**: `implementation_plan.md`
- **Date**: 2026-09-01

---

## Pre-flight Conflict Scan Table

| Tasks | File | What Task A produces | What Task B consumes | Finding |
|---|---|---|---|---|
| 1, 2 | `data/repositories/curriculum.py` | Enhances `get_teacher_quota_view` with 35-week metrics & weekly loads | Consumed in `pages/06_Xep_TKB.py` & `feasibility.py` | Clean — sequential dependency Task 1 -> Task 2 |
| 1, 3 | `data/repositories/curriculum.py` | Provides 35-week metrics dictionary and weekly load matrix | Consumed in `pages/03_DinhMuc.py` UI | Clean — Task 3 builds UI on top of Task 1 model |
| 2, 3 | `pages/06_Xep_TKB.py`, `pages/03_DinhMuc.py` | Separate UI files | Independent pages | Clean — zero conflict |

---

## Task Checklist

- [x] **Task 1**: Core Data & Repository Enhancement for Teacher 35-Week Workload Profile (`get_teacher_quota_view`, 35-week loads, semester averages HK1/HK2, weekly min/max, unit tests)
- [x] **Task 2**: Scheduling Engine & Pre-check Feasibility Alignment with Weekly Teacher Quota (`pages/06_Xep_TKB.py`, `feasibility.py`, integration tests)
- [x] **Task 3**: UI Modernization for `pages/03_DinhMuc.py` Teacher Tab (35-week workload view mode, semester averages, 35-week Teacher Workload Heatmap/Matrix, drill-down per teacher)
- [x] **Task 4**: Full Test Suite Regression, Real School Verification & Walkthrough
