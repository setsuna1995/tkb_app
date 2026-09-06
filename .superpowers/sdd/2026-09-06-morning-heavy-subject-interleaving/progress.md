# Superpowers SDD: Cân Bằng và Xen Kẽ Môn Học Thuật Buổi Sáng (Morning Academic Load Balancing)

**Thời gian**: 2026-09-06
**Branch / Commit**: `main` (commit `1487a1f`)
**Mục tiêu**: Đảm bảo mỗi buổi sáng của học sinh đều có sự phân bổ cân đối giữa môn học thuật cốt lõi (Toán, Văn, Ngoại ngữ, KHTN) và môn nhẹ/thư giãn (GDTC, Nhạc, Họa, Tin, Công nghệ, GDCD, HĐTN), triệt tiêu hoàn toàn buổi sáng bị nhồi 4 tiết nặng hoặc buổi sáng bị "trắng" môn học thuật.

---

## 1. Pre-flight Conflict Scan Table

| Tasks | File | What Task A produces | What Task B consumes | Finding |
|---|---|---|---|---|
| 1, 2 | `core/models.py` | Thêm các trường config `balance_morning_academic_load`, `max_academic_per_morning`, `min_academic_per_morning` | Đọc cấu hình để thiết lập ràng buộc CP-SAT | Clean — Task 1 định nghĩa trước, Task 2 sử dụng |
| 1, 3 | `core/validation.py` | Thêm hàm `find_morning_academic_load_violations` | Gọi trong `compute_tkb_health_score` để tính điểm sư phạm | Clean — Disjoint functions |
| 2, 3 | `core/scheduler/cpsat/` | Thiết lập ràng buộc trần cứng $\le 3$ và phạt mềm $< 2$ | Kiểm thử hồi quy và đo lường health score | Clean — Strict order 2 -> 3 |

---

## 2. Task Checklist

- [x] **Task 1**: Định nghĩa cấu hình tải học thuật buổi sáng và các hàm thẩm định vi phạm (`core/models.py`, `core/validation.py`, `tests/test_morning_academic_balance.py`) [COMPLETED]
- [x] **Task 2**: Triển khai ràng buộc CP-SAT trần cứng $\le 3$ và hàm phạt mềm sàn $< 2$ (`core/scheduler/cpsat/constraints.py`, `core/scheduler/cpsat/objectives.py`) [COMPLETED]
- [x] **Task 3**: Tích hợp vào `compute_tkb_health_score`, cập nhật UI cảnh báo và kiểm thử nghiệm thu toàn trường trên `truong-thcs.db` [COMPLETED]

---

## 3. Nhật Ký Tiến Độ (Execution Log)

- **2026-09-06 (Task 1)**: Hoàn thành Task 1. Cấu hình `SchedulingConfig` bổ sung 3 trường `balance_morning_academic_load`, `max_academic_per_morning`, `min_academic_per_morning`. Thêm 2 hàm validation `find_morning_academic_overload_violations` và `find_morning_academic_underload_violations`. 3 unit tests TDD PASSED. (Báo cáo: `task-1-report.md`).
- **2026-09-06 (Task 2)**: Hoàn thành Task 2. Thêm hằng số `MORNING_ACADEMIC_UNDERLOAD_SOFT_PENALTY = 120`. Triển khai Hard Constraint $\le 3$ trong `_add_class_constraints`. Triển khai Soft Penalty $< 2$ trong `_add_objective`. TDD RED/GREEN thành công. Toàn bộ 305 tests PASSED in 50.26s. (Báo cáo: `task-2-report.md`).
- **2026-09-06 (Task 3)**: Hoàn thành Task 3. Tích hợp các chỉ số tải học thuật buổi sáng vào `compute_tkb_health_score` trong `core/validation.py`. Unit tests PASSED. Nghiệm thu toàn trường thành công trên `schools/truong-thcs.db`: triệt tiêu 100% quá tải học thuật (0 buổi >3 tiết), lớp 7A4 không còn bị nhồi 4 môn nặng liên tiếp, số buổi lẻ giáo viên giảm từ 6 xuống 4, điểm Sư phạm tăng +6.0đ (từ 81 lên 87). (Báo cáo: `task-3-report.md`).



