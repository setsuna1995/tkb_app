# SDD Progress Ledger: Teacher Schedule Quality Rules

- **Feature**: Teacher Schedule Quality Constraints (Avoid Gaps, Avoid Lone Periods/1S+1C, Balance Afternoon, Mandatory Mornings T2/T5/T6, GDTC Non-Consecutive Days)
- **Date**: 2026-08-31
- **Working Directory**: `c:\Users\Kien\tkb_app`
- **SDD Artifacts**: `.superpowers/sdd/2026-08-31-teacher-schedule-quality-rules/`

---

## Pre-flight Conflict Scan Table

| Tasks | File | What Task A produces | What Task B consumes | Finding |
|---|---|---|---|---|
| 1, 2 | `core/models.py` | Adds `avoid_teacher_gaps`, `avoid_teacher_lone_periods`, `balance_afternoon_teachers`, `mandatory_morning_weekdays` to `SchedulingConfig` | Uses fields in `core/scheduler.py` for scoring & checks | Clean — Task 1 before Task 2 |
| 1, 2 | `data/repository.py` | Serializes & deserializes new config fields | Provides `SchedulingConfig` to scheduler & UI | Clean — Task 1 before Task 2 |
| 2, 3 | `core/scheduler.py` | Heuristics & quality metrics for teacher scheduling + GDTC non-consecutive rule | Consumed when scheduling runs via UI | Clean — Task 2 before Task 3 |
| 1, 3 | `pages/10_Cau_hinh_Xep_lich.py` | Uses repo get/set scheduling config for new UI controls | Displays & saves user preferences | Clean — Task 1 before Task 3 |

---

## Task Checklist

- [x] **Task 1: Domain Model & Persistence**
  - [x] Write `task-1-brief.md`
  - [x] TDD RED: Add repository tests in `tests/test_repository.py`
  - [x] TDD GREEN: Update `core/models.py` & `data/repository.py`
  - [x] Regression & Full Suite Check
  - [x] Write `task-1-report.md`
  - [x] Update `progress.md`

- [x] **Task 2: Core Scheduler Engine Optimization**
  - [x] Write `task-2-brief.md`
  - [x] TDD RED: Add unit tests in `tests/test_scheduler_teacher_quality.py`
  - [x] TDD GREEN: Update `core/scheduler.py` (scoring, off-session filters, quality ranking, GDTC non-consecutive rule)
  - [x] Regression & Full Suite Check
  - [x] Write `task-2-report.md`
  - [x] Update `progress.md`

- [x] **Task 3: UI & Guidance Updates**
  - [x] Write `task-3-brief.md`
  - [x] TDD RED: Unit tests for page configuration loading/saving
  - [x] TDD GREEN: Update `pages/10_Cau_hinh_Xep_lich.py` & `pages/11_Huong_Dan.py`
  - [x] Regression & Full Suite Check
  - [x] Write `task-3-report.md`
  - [x] Update `progress.md`

- [x] **Final Verification & Walkthrough**
