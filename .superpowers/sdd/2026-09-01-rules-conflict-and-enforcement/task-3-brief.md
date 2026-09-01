# Task 3 Brief: Bộ Test Suite Tự Động Kiểm Thử Toàn Bộ Các Rule & Kiểm Tra Hồi Quy Toàn Diện

## 1. Objective & Scope
- **Mục tiêu**:
  1. Bổ sung các bài unit test tự động bao phủ tất cả 32 quy tắc và các tình huống xung đột/ràng buộc đã khắc phục:
     - `single_pair_ids` ưu tiên chuẩn xác khi môn được đặt `ROLE_KEP`.
     - `balance_afternoon_teachers` tính điểm phạt chuẩn khi GV bị trống tiết chiều.
     - `find_morning_only_violations`, `find_max_heavy_violations`, `find_subject_class_rule_violations`, `find_single_pair_violations`.
     - Kiểm tra `_assign_off_slots` không phân bổ vào `mandatory_morning_weekdays`.
  2. Chạy toàn bộ test suite (toàn bộ 179+ test cases trong `tests/`) và đảm bảo 100% pass không có bất kỳ lỗi hồi quy nào.

## 2. Test Plan & Expected Outcomes
- **Commands**: `python -m pytest`
- **Expected Results**: Tất cả 179+ tests PASS (bao gồm các test về importer, exporter, frame, scheduler, backup, setup status, teacher quality, constraints).

## 3. Safety & Invariants
- Giữ vững tính bất biến của thuật toán và các fixture dữ liệu thực tế (`sample_school.xlsm`).
