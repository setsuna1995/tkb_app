# Task 2 Brief: Ràng Buộc CP-SAT Trần Cứng và Phạt Mềm Sàn Tải Học Thuật Buổi Sáng

## 1. Objective & Scope
- Thêm hằng số `MORNING_ACADEMIC_UNDERLOAD_SOFT_PENALTY = 120` vào `core/scheduler/constants.py`.
- Thêm ràng buộc Hard Constraint khống chế trần học thuật buổi sáng ($\le 3$ tiết) trong `_add_class_constraints` ([core/scheduler/cpsat/constraints.py](file:///c:/Users/Kien/tkb_app/core/scheduler/cpsat/constraints.py)) khi `config.balance_morning_academic_load` bật.
- Thêm phạt mềm Soft Penalty phạt sàn thiếu tải học thuật buổi sáng ($< 2$ tiết cho các buổi sáng có $\ge 3$ tiết tổng) trong `_add_objective` ([core/scheduler/cpsat/objectives.py](file:///c:/Users/Kien/tkb_app/core/scheduler/cpsat/objectives.py)).
- Viết integration/unit tests trong [tests/test_morning_academic_balance.py](file:///c:/Users/Kien/tkb_app/tests/test_morning_academic_balance.py) mô phỏng giải CP-SAT với ràng buộc và hàm mục tiêu mới.

## 2. Mathematical Modeling in CP-SAT
1. **Academic Subjects Definition**:
   `academic_ids = {s.subject_id for s in inp.subjects if any(s.name.startswith(h) for h in ('Toán', 'Ngữ văn', 'Ngoại ngữ', 'Khoa học tự nhiên'))}`

2. **Hard Ceiling Constraint (Trần cứng $\le 3$)**:
   Đối với mỗi lớp $c$ và mỗi thứ $w$ trong tuần có tiết buổi sáng ($S$):
   $$\sum_{s \in S_{c, w}} \sum_{subj \in \text{academic\_ids}} x[s, subj] \le \text{effective\_max}$$
   Với `effective_max = config.max_academic_per_morning` (mặc định 3).
   *Defensive Guard*: Nếu lớp không có buổi chiều và nhu cầu học thuật vượt quá `max_academic * số buổi sáng`, tự động điều chỉnh trần để không bao giờ gây infeasible.

3. **Soft Floor Penalty (Phạt mềm sàn $< 2$)**:
   Đối với mỗi lớp $c$ và thứ $w$ có buổi sáng với $\ge 3$ tiết tổng:
   $$V_{c, w} = \sum_{s \in S_{c, w}} \sum_{subj \in \text{academic\_ids}} x[s, subj]$$
   Biến Boolean chỉ thị `underload`:
   $$V_{c, w} \le (\text{min\_academic\_per\_morning} - 1) \iff \text{underload}_{c, w} = 1$$
   $$V_{c, w} \ge \text{min\_academic\_per\_morning} \iff \text{underload}_{c, w} = 0$$
   Phạt vào hàm mục tiêu: $\text{MORNING\_ACADEMIC\_UNDERLOAD\_SOFT\_PENALTY} \times \sum \text{underload}_{c, w}$ với trọng số 120.

## 3. TDD Strategy
1. **RED Phase**:
   - Viết test `test_cpsat_morning_academic_hard_ceiling` và `test_cpsat_morning_academic_soft_floor` trong `tests/test_morning_academic_balance.py`.
   - Chạy test -> Dự kiến FAIL (vì solver chưa có ràng buộc và phạt này, tạo ra phân bổ 4 tiết nặng hoặc 1 tiết nặng).
2. **GREEN Phase**:
   - Thêm hằng số vào `core/scheduler/constants.py`.
   - Cập nhật `core/scheduler/cpsat/constraints.py` và `core/scheduler/cpsat/objectives.py`.
   - Chạy lại test -> Dự kiến PASS 100%.

## 4. Safety & Invariants
- Giữ nguyên các luật giáo viên II.3, II.4, II.7, II.8, II.9, II.14.
- Trọng số phạt 120 < 250 (lone day) < 350 (gap) < 500 (lone session), đảm bảo quyền lợi lịch giáo viên luôn được ưu tiên hơn việc dồn môn nhẹ.
