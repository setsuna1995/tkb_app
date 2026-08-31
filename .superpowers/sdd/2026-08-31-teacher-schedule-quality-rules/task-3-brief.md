# Task 3 Brief: UI Configuration & Guidance Updates

## 1. Objective & Scope
- **Objective**: Expose all teacher schedule quality rules and non-consecutive days settings in the Streamlit UI on `pages/10_Cau_hinh_Xep_lich.py`, update `pages/11_Huong_Dan.py`, and update `ui_common.py`.
- **Scope**:
  - `pages/10_Cau_hinh_Xep_lich.py`: UI form controls and saving logic.
  - `pages/11_Huong_Dan.py`: Help documentation for teacher schedule quality rules.
  - `ui_common.py`: Sidebar information.

## 2. UI Controls Specification
In `pages/10_Cau_hinh_Xep_lich.py`:
1. Subheader: "Chất lượng lịch giáo viên"
   - Checkbox: "Tránh tiết trống của giáo viên trong buổi" (`avoid_teacher_gaps`)
   - Checkbox: "Tránh giáo viên đi dạy 1 tiết/ngày hoặc sáng 1 tiết + chiều 1 tiết" (`avoid_teacher_lone_periods`)
   - Checkbox: "Cân đối tiết buổi chiều cho GV (tránh để GV nghỉ full chiều khi dạy lớp 2 buổi)" (`balance_afternoon_teachers`)
   - Multiselect: "Buổi sáng bắt buộc toàn thể GV đi làm / có mặt" (`mandatory_morning_weekdays`)
2. In "Môn không xếp liền ngày":
   - Multiselect `non_consecutive_subject_ids` (with help note that GDTC is included by default).

## 3. TDD Strategy
- Create automated test asserting that repo and config serialization handle all UI parameters.
- Verify UI rendering without errors.
- RED Phase: Verify configuration state updates when inputs change.
- GREEN Phase: Integrate into `pages/10_Cau_hinh_Xep_lich.py` and test.

## 4. Safety & Invariants
- Preserves all existing UI sections and layout aesthetics.
