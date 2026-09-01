# SDD Progress Ledger: Eliminate Teacher Lone Period Sessions

- **Date**: 2026-09-01
- **Feature**: `eliminate-teacher-lone-sessions`
- **Root Context**: Master branch / Working tree
- **Status**: `complete`

---

## Pre-flight Conflict Scan Table

| Tasks | File(s) | What Task A produces | What Task B consumes | Finding |
|---|---|---|---|---|
| 1, 2 | `core/scheduler/constants.py`, `core/scheduler/heuristics.py`, `core/scheduler/swaps.py` | Task 1 adjusts greedy heuristics and bonuses | Task 2 builds `_repair_teacher_lone_sessions` | Clean — sequential enhancement |
| 2, 3 | `core/scheduler/engine.py`, `core/scheduler/quality.py` | Task 2 adds local repair to engine pipeline | Task 3 updates quality penalties and runs full regression suite | Clean — strict order 2 -> 3 |

---

## Task Checklist

- [x] **Task 1**: Điều chỉnh Greedy Heuristics & Constants (`constants.py`, `heuristics.py`) — Tăng thưởng ghép cặp cho GV, điều kiện hoá ép sáng theo tải. (Report: task-1-report.md)
- [x] **Task 2**: Xây dựng thuật toán Local Repair `_repair_teacher_lone_sessions` trong `swaps.py` & tích hợp vào `engine.py`. (Report: task-2-report.md)
- [x] **Task 3**: Tăng trọng số phạt trong `quality.py`, bổ sung Unit/Integration Tests & Chạy kiểm tra hồi quy toàn diện. (Report: task-3-report.md)
