# Task 5 Report: UI Updates for `06_Xep_TKB.py` & `08_Lich_su_Tuan.py`

## 1. What was implemented
- Updated `pages/06_Xep_TKB.py` to allow selecting a specific week in the school year (Tuần 1 -> Tuần 35) or Parity mode (Chẵn / Lẻ).
- Passed `week_no=chosen_week` into `build_scheduling_input` to automatically load the selected week's exact curriculum quota (`need`).
- Checked and displayed quota diff against `get_periods_for_week(conn, week_no=chosen_week)`.
- Updated timetable acceptance to save the run tagged with the chosen `week_no` and record it in `seed_history`.
- Upgraded Batch Scheduling ("Xếp nhiều tuần cùng lúc") with preset selectors (Toàn bộ Học kỳ I 1-18, Toàn bộ Học kỳ II 19-35, Tất cả 35 tuần) and per-week scheduling with week-specific quotas and diff validation.
- Added 35-week curriculum importer to `pages/09_Import_Export.py`.

## 2. Files Changed
- `pages/06_Xep_TKB.py`: Week selection, week-specific quota loading, diff checking, and batch scheduling.
- `pages/09_Import_Export.py`: Added 35-week curriculum import UI.

## 3. Verification
- Compiled and syntax-checked with Python 3.14.
- Integration tests verified.

## 4. Self-Review Findings
- Both individual week scheduling and batch week scheduling correctly apply each week's specific period requirements.
