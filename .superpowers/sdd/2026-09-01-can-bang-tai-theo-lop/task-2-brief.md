# Task 2 Brief: UI & 1-Click DB Sync (`pages/07_Can_Bang_Tai.py`)

## 1. Objective & Scope
- Nâng cấp toàn diện giao diện trang `pages/07_Can_Bang_Tai.py`:
  1. Thể hiện rõ ràng nguyên tắc: **Phân công theo trọn gói Lớp** (toàn bộ tiết của lớp trong tuần Chẵn và tuần Lẻ).
  2. Hiển thị **Bảng Tổng Hợp Tải Giáo Viên**: Tên GV, Vai trò, Trần, Sàn, Tải tuần C/L/TB, Trạng thái (Vượt trần / Dưới sàn / Cân bằng), Danh sách các lớp đang dạy.
  3. Hiển thị **Bảng Đề Xuất Phân Công**:
     - Checkbox chọn từng đề xuất.
     - Loại đề xuất (Chuyển 1 lớp / Hoán đổi 2 lớp).
     - Chi tiết lớp & môn kèm số tiết (C/L/TB).
     - Biến động tải của GV chuyển đi và GV nhận (Tải cũ -> Tải mới / Trần).
  4. Bổ sung tính năng **Áp dụng trực tiếp vào DB Phân công**:
     - Nút "⚡ Áp dụng các đề xuất đã chọn vào Phân công" và "⚡ Áp dụng tất cả đề xuất".
     - Ghi trực tiếp vào bảng `assignments` qua `repo.set_assignment`.
     - Tự động làm mới giao diện và hiển thị thông báo thành công.

## 2. Integration & TDD Strategy
- Thêm test case `test_apply_suggestions_to_database` trong `tests/test_load_balance.py` để kiểm tra lưu trữ thực tế vào cơ sở dữ liệu SQLite trong bộ nhớ.
- Kiểm tra tính toàn vẹn của dữ liệu sau khi apply (không có lớp nào bị bỏ sót hay mất phân công).

## 3. UI/UX Invariants
- Sử dụng giao diện Streamlit hiện đại, màu sắc trực quan (badges trạng thái, highlight bảng đề xuất).
- Bảo toàn sidebar chuyển trường và sao lưu dữ liệu.
