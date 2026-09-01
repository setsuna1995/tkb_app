# Task 3 Brief: Guide Documentation & Full Suite Regression (`pages/11_Huong_Dan.py`)

## 1. Objective & Scope
- Cập nhật tài liệu hướng dẫn sử dụng tại `pages/11_Huong_Dan.py` (Mục "⚖️ Cân bằng tải giáo viên"):
  - Giải thích rõ nguyên lý phân công theo trọn gói Lớp.
  - Hướng dẫn tính năng chuyển 1 lớp nguyên vẹn và hoán đổi chéo 2 lớp cùng môn.
  - Hướng dẫn cách sử dụng nút bấm áp dụng trực tiếp vào Phân công chuyên môn.
- Chạy toàn bộ các test suite regression kiểm tra không có lỗi tiềm ẩn.

## 2. Implementation Steps
1. Thay đổi nội dung mục "⚖️ Cân bằng tải giáo viên" trong `pages/11_Huong_Dan.py`.
2. Chạy regression test suite `python -m pytest tests/test_load_balance.py tests/test_models.py tests/test_repository.py tests/test_setup_status.py -v`.
3. Tạo `task-3-report.md` và đóng ledger `progress.md`.
