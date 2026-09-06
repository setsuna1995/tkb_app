# Task 4 Report: Bổ Sung Ràng Buộc Sư Phạm & Công Bằng Giáo Viên

- **Task**: Bổ sung Soft Constraints sư phạm (giãn cách môn 2-3 tiết/tuần) & công bằng giáo viên (chống nhảy ca gắt chiều muộn -> sáng sớm, phạt lũy tiến tiết trống)
- **Status**: COMPLETE
- **Date**: 2026-09-06

---

## 1. Summary of Changes

1. **Anti Back-to-Back Shifts (Chống nhảy ca gắt)**:
   - File: `core/scheduler/cpsat/objectives.py`, `core/scheduler/quality.py`, `core/scheduler/constants.py`
   - Constant: `TEACHER_BACK_TO_BACK_SHIFT_PENALTY = 250`
   - Mô hình CP-SAT: Theo dõi cặp buổi (Chiều muộn tiết 4/5 ngày $w$ và Sáng hôm sau tiết 1 ngày $w+1$) cho từng giáo viên, phạt 250 điểm mỗi vi phạm.

2. **Subject Dispersion Preference (Giãn cách môn 2-3 tiết/tuần)**:
   - File: `core/scheduler/cpsat/objectives.py`, `core/scheduler/quality.py`, `core/scheduler/constants.py`
   - Constant: `SUBJECT_CONSECUTIVE_DAY_SOFT_PENALTY = 200`
   - Mô hình CP-SAT: Đối với môn học có tải 2–3 tiết/tuần trong 1 lớp (trừ HĐTN), ưu tiên giãn cách tối thiểu 1 ngày trống giữa các buổi học, phạt 200 điểm mềm nếu xếp 2 ngày liên tiếp kề nhau.

3. **Progressive Gap Penalty (Phạt lũy tiến tiết trống giáo viên)**:
   - File: `core/scheduler/cpsat/objectives.py`, `core/scheduler/quality.py`, `core/scheduler/constants.py`
   - Constants:
     - `TEACHER_GAP_SECOND_PENALTY = 700`
     - `TEACHER_GAP_EXCESS_PENALTY = 1500`
   - Mô hình CP-SAT: Solver tự động phân bổ đều tiết trống giữa các giáo viên trong tuần thay vì dồn nhiều tiết trống vào một người:
     - Gap 1: 350
     - Gap 2: 700 (+350)
     - Gap 3+: 1500 (+800)

4. **Quality Tracking Metrics**:
   - Thêm các hàm phân tích chất lượng trong `core/scheduler/quality.py`:
     - `_count_teacher_excess_gaps(slots, assigned, slot_teacher) -> tuple[int, int]`
     - `_count_teacher_back_to_back_shifts(slots, assigned, slot_teacher) -> int`
     - `_count_subject_consecutive_days(slots, assigned, need) -> int`
   - Tích hợp vào `_teacher_quality_penalty(...)`, đồng bộ hóa 100% với hàm mục tiêu CP-SAT.

---

## 2. Test Verification

- `tests/test_pedagogical_and_fairness_quality.py`: 3/3 passed (100%).
- Full regression suite: 55/55 tests passed in 72.70s.
