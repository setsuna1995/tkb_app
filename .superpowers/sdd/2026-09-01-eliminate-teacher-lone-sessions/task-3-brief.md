# Task 3 Brief: Nâng Cấp Trọng Số Phạt Quality & Điều Kiện Hoá Sáng Bắt Buộc Theo Tải

## Objective & Scope
- **Mục tiêu**:
  1. Tăng trọng số phạt `_count_teacher_lone_sessions` trong `core/scheduler/quality.py` từ 180 lên **500** điểm để bộ lọc Best-of-N ưu tiên giải pháp không có buổi lẻ 1 tiết.
  2. Điều chỉnh ngưỡng `_count_teacher_missing_mandatory_mornings`: Chỉ áp dụng kiểm tra 3 sáng bắt buộc đối với giáo viên có tổng tải tuần $\ge 10$ tiết (thay vì $\ge 5$ tiết, vì GV dưới 10 tiết không thể phân bổ vào 3 sáng mà vẫn giữ $\ge 2$ tiết/buổi).
  3. Bổ sung test kiểm thử toàn diện và chạy kiểm tra hồi quy toàn bộ test suite dự án.

## Interface Specifications
Không thay đổi chữ ký hàm, chỉ cập nhật logic tính penalty trong `_teacher_quality_penalty` và `_count_teacher_missing_mandatory_mornings`.

## TDD Strategy
- **File test**: `tests/test_scheduler_teacher_quality.py`
- **RED/GREEN phase**:
  1. Viết test kiểm tra hàm `_count_teacher_missing_mandatory_mornings` bỏ qua GV tải thấp (< 10 tiết) để không ép rải tiết.
  2. Viết test kiểm tra `_teacher_quality_penalty` phạt nặng hơn đáng kể cho buổi lẻ 1 tiết.
  3. Chạy full test suite (`pytest tests/`).

## Safety & Invariants
- Đảm bảo 100% test suite vượt qua không có hồi quy.
