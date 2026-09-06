# Task 2 Report: Ràng Buộc CP-SAT Trần Cứng và Phạt Mềm Sàn Tải Học Thuật Buổi Sáng

## 1. What was implemented
- Thêm hằng số `MORNING_ACADEMIC_UNDERLOAD_SOFT_PENALTY = 120` vào [core/scheduler/constants.py](file:///c:/Users/Kien/tkb_app/core/scheduler/constants.py).
- Bổ sung ràng buộc Hard Constraint (trần cứng $\le 3$ tiết học thuật/buổi sáng) trong `_add_class_constraints` ([core/scheduler/cpsat/constraints.py](file:///c:/Users/Kien/tkb_app/core/scheduler/cpsat/constraints.py)) khi `config.balance_morning_academic_load = True`. Kèm cơ chế phòng thủ tự động nới lỏng trần nếu tổng số tiết học thuật tuần vượt quá năng lực các buổi sáng khi lớp không có buổi chiều.
- Bổ sung hàm phạt mềm Soft Penalty (sàn $< 2$ tiết học thuật cho buổi sáng $\ge 3$ tiết tổng) trong `_add_objective` ([core/scheduler/cpsat/objectives.py](file:///c:/Users/Kien/tkb_app/core/scheduler/cpsat/objectives.py)). Trọng số phạt 120 (nhỏ hơn 250 của lone day, 350 của gap, 500 của lone session) đảm bảo không bao giờ đánh đổi để làm hỏng lịch giáo viên.
- Mở rộng 2 bài test CP-SAT solver trong [tests/test_morning_academic_balance.py](file:///c:/Users/Kien/tkb_app/tests/test_morning_academic_balance.py):
  - `test_cpsat_morning_academic_hard_ceiling`: Xác nhận không có buổi sáng nào vượt quá 3 tiết học thuật.
  - `test_cpsat_morning_academic_soft_floor`: Xác nhận solver phân bổ đều 2 tiết học thuật mỗi sáng thay vì dồn lệch vào 1 sáng.

## 2. Files changed
- `core/scheduler/constants.py` (modified)
- `core/scheduler/cpsat/constraints.py` (modified)
- `core/scheduler/cpsat/objectives.py` (modified)
- `tests/test_morning_academic_balance.py` (modified)

## 3. TDD Evidence
- **RED Phase**:
  - `test_cpsat_morning_academic_hard_ceiling`: FAIL với `overloads: [(101, 2, 4), (101, 4, 4)]` do solver cũ dồn cả 4 tiết học thuật vào sáng Thứ 2 và Thứ 4.
  - `test_cpsat_morning_academic_soft_floor`: FAIL với `underloads: [(101, 2, 1)]` do solver cũ phân bổ lệch `{2: 1, 3: 3, 4: 2}`.
- **GREEN Phase**:
  - Cả 2 bài test CP-SAT pass hoàn hảo:
    - Case 1 (Ceiling): Phân bổ chuyển thành `{2: 3, 3: 2, 4: 3}` (tất cả các sáng $\le 3$, 0 vi phạm overload).
    - Case 2 (Floor): Phân bổ chuyển thành `{2: 2, 3: 2, 4: 2}` (mọi sáng đều đúng 2 tiết học thuật, 0 vi phạm underload).
  - Toàn bộ test suite 305 tests vượt qua trong 50.26s: `305 passed in 50.26s`.

## 4. Self-Review & Verification
- Phân tích GitNexus impact trước khi sửa: cả `_add_class_constraints` và `_add_objective` đều có risk `LOW`.
- Ràng buộc trần cứng không ảnh hưởng đến các lớp học bình thường vì tỉ lệ học thuật THCS là 15 tiết / 5 sáng = 3.0.
- Trọng số phạt sàn 120 bảo vệ tuyệt đối các quy chuẩn giáo viên II.3, II.4.
