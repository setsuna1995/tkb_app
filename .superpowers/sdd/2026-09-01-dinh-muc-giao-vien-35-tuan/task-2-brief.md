# Task 2 Brief: Scheduling Engine & Pre-check Feasibility Alignment with Weekly Teacher Quota

## 1. Objective & Scope
- **Objective**: Ensure that before and during scheduling, teacher workload feasibility checks and over-quota warnings in `pages/06_Xep_TKB.py` evaluate the teacher's load specifically for the selected week `week_no`:
  - When scheduling single week `week_no`: `over = [q for q in quota_view if q["cap"] > 0 and q["over_current"] > 0]`.
  - Display clear warning text showing the exact period count for that week: `"Tải Tuần {week_no}: {load}/{cap} (vượt +{over_current})"`.
  - In batch mode: for each week $W \in \text{batch\_week\_nos}$, check teacher over-quota for week $W$ (`over_current`).
- **Scope**: `pages/06_Xep_TKB.py` and integration tests.
- **Out of Scope**: General curriculum tab UI (handled in Task 3).

## 2. Interface Specifications
- In `pages/06_Xep_TKB.py`:
  - `quota_view = repo.get_teacher_quota_view(conn, parity=parity, week_no=chosen_week)`
  - `over = [q for q in quota_view if q["cap"] > 0 and q["over_current"] > 0]`
  - Warning formatting: `f"- {q['name']}: Tải {q['load']}/{q['cap']} (vượt +{q['over_current']})"`

## 3. TDD Strategy
- Check compilation and run scheduling integration tests.

## 4. Safety & Invariants
- Preserves all constraint checking and scheduler engine execution.
