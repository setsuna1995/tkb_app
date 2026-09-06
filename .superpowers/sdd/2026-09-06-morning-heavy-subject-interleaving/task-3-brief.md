# Task 3 Brief: Tích Hợp Health Score & Nghiệm Thu Toàn Trường

## 1. Objective & Scope
- Tích hợp kiểm tra vi phạm quá tải / thiếu tải môn học thuật buổi sáng vào hàm `compute_tkb_health_score` trong [core/validation.py](file:///c:/Users/Kien/tkb_app/core/validation.py):
  - Bổ sung khuyến nghị warning/info cho học sinh và nhà trường khi có buổi sáng bị dồn quá 3 tiết học thuật hoặc < 2 tiết học thuật.
  - Phản ánh vi phạm vào `pedagogical_score` và trả về số lượng vi phạm trong `metrics["morning_academic_overload"]` và `metrics["morning_academic_underload"]`.
- Viết unit test kiểm tra tích hợp trong [tests/test_morning_academic_balance.py](file:///c:/Users/Kien/tkb_app/tests/test_morning_academic_balance.py).
- Chạy nghiệm thu thực tế toàn trường với cơ sở dữ liệu [schools/truong-thcs.db](file:///c:/Users/Kien/tkb_app/schools/truong-thcs.db):
  - Xác nhận phân bổ môn học thuật buổi sáng của các lớp (đặc biệt là 7A4, 8A5,...).
  - Xác nhận 0 buổi lẻ giáo viên (II.4), 0 ngày chia lẻ (II.8), 100% tuân thủ các quy tắc cốt lõi của trường.

## 2. Interface Specifications
```python
# core/validation.py - compute_tkb_health_score
# In "Trụ cột 1: TÍNH SƯ PHẠM & HỌC SINH":
academic_ids = {s.subject_id for s in inp.subjects if any(s.name.startswith(h) for h in ('Toán', 'Ngữ văn', 'Ngoại ngữ', 'Khoa học tự nhiên'))}
# Evaluates overload (> max_academic) and underload (< min_academic)
# Appends warnings/info to recommendations
# Metrics dictionary includes:
#   "morning_academic_overload": len(acad_overload_violations),
#   "morning_academic_underload": len(acad_underload_violations),
```

## 3. Verification Plan
1. **Automated Unit Tests**:
   - `tests/test_morning_academic_balance.py`: `test_health_score_includes_morning_academic_metrics`
2. **Whole-School End-to-End Simulation**:
   - Chạy kịch bản giải TKB đầy đủ trên `schools/truong-thcs.db`.
   - Kiểm tra `health["overall_score"]`, `health["compliance_score"]`.
   - So sánh lịch sáng của lớp 7A4 trước và sau khi có ràng buộc.
3. **Full Regression Check**:
   - `py -3.14 -m pytest -m "not slow"`.

## 4. Safety & Invariants
- Điểm trừ tính sư phạm được khống chế mức trần hợp lý (`min(20.0, ...)`), không làm sụt giảm bất hợp lý điểm TKB tổng thể.
- Mọi trường dữ liệu trả về từ `compute_tkb_health_score` giữ nguyên cấu trúc dict hiện có.
