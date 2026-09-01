# Task 2 Report: Scheduling Engine & Pre-check Feasibility Alignment with Weekly Teacher Quota

## 1. What was implemented
- Updated pre-check feasibility and over-quota warnings in `pages/06_Xep_TKB.py` to evaluate `over_current` for the selected `week_no`.
- Added warning messaging showing the exact load and cap for the chosen week: `f"- {q['name']}: Tải {q['load']}/{q['cap']} (vượt +{q['over_current']})"`.
- Upgraded Batch Scheduling ("Xếp nhiều tuần cùng lúc") to pre-check over-quota teachers for each individual week in `batch_week_nos`.

## 2. Files Changed
- `pages/06_Xep_TKB.py`: Week-aligned teacher quota warnings in single and batch scheduling modes.

## 3. Verification
- Compiled and syntax-checked with Python 3.14.
- Integration tests verified.

## 4. Self-Review Findings
- Preserves user override checkbox (`proceed_anyway`) while ensuring that warnings are accurate to the selected week's curriculum distribution.
