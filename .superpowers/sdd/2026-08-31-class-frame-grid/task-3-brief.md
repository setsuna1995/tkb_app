# Task 3: UI Update (Class Frame Grid)

## Objective & Scope
- Completely redesign `pages/05_Khung_tiet.py`.
- Remove the old formula-based frame (morning/afternoon periods, study sunday, allow saturday, short weekday, etc.).
- Introduce a grid UI (Thứ 2 -> Thứ 7, Sáng Tiết 1-5, Chiều Tiết 1-4) with checkboxes.
- The user can pick a Khối (Grade) or Lớp (Class), or use a "Bulk Apply" to apply a single grid pattern to multiple classes.
- Save explicitly to `class_allowed_cells` via `repo.set_class_allowed_cells`.

## UI/UX Flow
1. School check, auth check.
2. Filter/Select target: Khối or Lớp. If Lớp, show its existing `class_allowed_cells` (or fallback to `frame_template` to prefill the grid). Wait, fallback logic in UI: if no `class_allowed_cells` exist, we can prefill the grid using `frame_mod.active_cells` of its old `frame_template`.
3. Display Grid (Sáng 1-5, Chiều 1-4) across Th2 - Th7.
4. "Lưu khung tiết" button.

## Verification
- Manual verification only. Open the UI, change the grid for 6A5, save it. Check the database and verify the schedule generation runs without errors.
