# Task 2 Brief: Interactive UIfor Checkbox Matrix in `pages/04_GV_Ban.py`

## 1. Objective & Scope
-  Redesign `pages/04_GV_Ban.py` with 3 tabs:
  1. **T＂ch chọn theo Giáo viên (Interactive Checkbox Grid)**:
     - Select a teacher from a dropdown (displaying role, blocked periods summary).
     - Quick preset actions:
       * Nghé T1 (T3, T5)
       * Nghé T1 (T3, T4, T5)
       * Nghí T1 (T3-6)
       * Nghí S4 + C1 cả tuần
       * Nghí trọn sáng / chiều / cả ngày
       * Xóa trắng tiết bận
     - Interactive `data_editor` grid: Buoi, Tiet, plus Thu 2 .. Thu 7 as boolean checkboxes.
     - Button to save busy periods for that teacher using `repo.set_teacher_busy_cells`.
  2. **Ma trận bận toàn trường (School Overview Grid)**:
     - A matrix view listing all teachers and showing their busy slots visually.
  3. **Bảng quy tắc chi tiết (List View)**:
     - Existing `GV_Ban` table editor (Giáo viên, Thứ, Buoể, Tiết) for manual overrides.

## 2. Invariants
- Saving in the grid must immediately reflect in the scheduler input.
- No blocking of auth or school selection gates on the page.
- Preserve existing current APIs and sidebar helpers.
