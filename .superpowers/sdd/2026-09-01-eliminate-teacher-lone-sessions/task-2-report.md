# Task 2 Report: Xây Dựng Thuật Toán Local Repair `_repair_teacher_lone_sessions`

## 1. What was implemented
- **Cài đặt thuật toán Local Repair cho giáo viên (`core/scheduler/swaps.py`)**:
  - Hàm `_repair_teacher_lone_sessions`: Tự động tìm kiếm tất cả các buổi dạy chỉ có đúng 1 tiết của giáo viên.
  - Sử dụng chiến thuật Evacuate/Consolidate: Thực hiện hoán đổi hợp lệ (qua kiểm tra nghiêm ngặt `_feasible`, không phá vỡ khối KEP và tính liên tục của lớp) để di chuyển tiết lẻ đó ghép vào một buổi khác mà giáo viên đã có tiết, trả buổi ban đầu về 0 tiết (giáo viên được nghỉ trọn buổi).
- **Tích hợp vào quy trình Engine (`core/scheduler/engine.py`)**:
  - Gọi `_repair_teacher_lone_sessions` ngay sau pha sửa khối KEP (`_repair_unpaired_blocks`) và trước pha kiểm tra chất lượng giải pháp.
- **Xuất khẩu (`core/scheduler/__init__.py`)**:
  - Bổ sung `_repair_teacher_lone_sessions` vào `__all__`.

## 2. Files changed
- `core/scheduler/swaps.py`: Thêm `_repair_teacher_lone_sessions`.
- `core/scheduler/engine.py`: Tích hợp vào quy trình solver.
- `core/scheduler/__init__.py`: Cập nhật xuất khẩu hàm.
- `tests/test_scheduler_teacher_quality.py`: Thêm test case `test_repair_teacher_lone_sessions_evacuates_or_pairs`.

## 3. TDD Evidence
- **Command**: `python -m pytest tests/test_scheduler_teacher_quality.py`
- **Output**:
```
============================= 12 passed in 0.09s ==============================
```

## 4. Self-Review Findings
- Thuật toán giải phóng thành công các buổi lẻ 1 tiết, đưa về trạng thái hợp lý (0 tiết hoặc $\ge 2$ tiết/buổi).
- Toàn bộ ràng buộc cứng và tính hợp lệ của thời khoá biểu lớp được duy trì 100%.
