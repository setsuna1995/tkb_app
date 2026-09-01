# Task 3 Report: Guide Documentation & Regression Testing (`pages/11_Huong_Dan.py`)

## 1. What was implemented
- Cập nhật tài liệu hướng dẫn sử dụng trong `pages/11_Huong_Dan.py` tại mục "⚖️ Cân bằng tải giáo viên":
  - Làm rõ nguyên lý **Cân bằng tải theo trọn gói Lớp (môn × lớp)**, bảo toàn toàn bộ số tiết trong cả tuần Chẵn và tuần Lẻ, không cắt lẻ từng tiết.
  - Giới thiệu 2 hình thức: **Chuyển 1 lớp nguyên vẹn** và **Đổi chéo 2 lớp cùng môn (Class Swap)** khi độ lệch tải nhỏ.
  - Hướng dẫn thao tác chọn đề xuất và bấm **"Áp dụng vào Phân công"** (1-click sync) để lưu trực tiếp vào cơ sở dữ liệu.
- Chạy kiểm thử tự động toàn diện kiểm tra tính đúng đắn và độ tin cậy.

## 2. Files Changed
- `pages/11_Huong_Dan.py`: Updated documentation guide.

## 3. Verification & Evidence
- Tất cả unit tests và integration tests liên quan đến cân bằng tải, cơ sở dữ liệu và các phân hệ khác đều hoạt động hoàn hảo.
