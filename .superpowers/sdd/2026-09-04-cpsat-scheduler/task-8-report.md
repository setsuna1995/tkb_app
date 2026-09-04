# Task 8 Report: Nối vào `run()`, fallback, UI, và test song song

- **Task**: 8
- **Status**: Complete
- **Date**: 2026-09-05
- **Branch/Worktree**: cpsat-scheduler (.worktrees/cpsat-scheduler)

---

## 1. What was implemented

Theo đúng phân tích từ /grill-me và task-8-brief.md:
1. **Cấu hình an toàn (`SchedulingConfig`)**:
   - Thêm `use_cpsat: bool = False` (mặc định tắt an toàn).
   - Thêm `cpsat_time_limit_seconds: int = 30` (giới hạn thời gian giải tối ưu).
   - Bổ sung `solver_name: str = "heuristic"` vào `ScheduleResult` để UI biết phương án được giải bằng bộ giải nào.
2. **Lưu trữ cấu hình trong DB (`data/repositories/config.py`)**:
   - Cập nhật `get_scheduling_config` và `set_scheduling_config` đọc/ghi 2 trường `sched_use_cpsat` và `sched_cpsat_time_limit_seconds`.
3. **Giao diện người dùng (UI Streamlit)**:
   - `pages/10_Cau_hinh_Xep_lich.py`: Thêm mục *Bộ giải tối ưu toàn cục (CP-SAT)* với checkbox *"Dùng bộ giải CP-SAT (thử nghiệm)"* và ô nhập thời gian giới hạn *"Giới hạn thời gian giải (giây)"* kèm hướng dẫn chi tiết.
   - `pages/06_Xep_TKB.py`: Hiển thị banner kết quả rõ ràng (*"Tối ưu bằng CP-SAT (toàn cục)"* khi `solver_name == "cpsat"` hoặc thông báo cảnh báo fallback nếu bộ giải tự động lùi về engine cũ).
4. **Tích hợp `engine.run()` với cơ chế Fallback an toàn**:
   - Trước vòng lặp heuristic, kiểm tra `config.use_cpsat`:
     - Khối `try/except` bọc kín bộ giải CP-SAT.
     - Nếu thiếu `ortools` (`CpSatUnavailable`) hoặc timeout / exception bất kỳ: tự động fallback êm sang engine cũ và ghi log.
     - Tuyệt đối không bao giờ làm sập Streamlit UI.
5. **Điều tiết luồng song song trên `pytest-xdist -n auto`**:
   - `cpsat_model.py`: Giới hạn `workers = min(workers, 2)` khi phát hiện môi trường `pytest-xdist` hoặc test đang chạy, thiết lập `solver.parameters.random_seed` để chống thread thrashing.

---

## 2. Files changed

- `core/models.py`:
  - Thêm `use_cpsat`, `cpsat_time_limit_seconds` vào `SchedulingConfig`.
  - Thêm `solver_name` vào `ScheduleResult`.
- `core/scheduler/cpsat_model.py`:
  - Thiết lập `solver_name="cpsat"` trong `build_result`.
  - Hỗ trợ điều tiết thread worker và random seed trong `solve` và `solve_to_result`.
- `core/scheduler/engine.py`:
  - Tích hợp gọi CP-SAT trước vòng lặp attempts với fallback an toàn.
- `data/repositories/config.py`:
  - Đọc/ghi cấu hình CP-SAT vào bảng config.
- `pages/10_Cau_hinh_Xep_lich.py`:
  - Thêm phần cấu hình UI cho CP-SAT.
- `pages/06_Xep_TKB.py`:
  - Thêm solver banner hiển thị trên giao diện xếp TKB.
- `tests/test_cpsat_engine_integration.py`:
  - Bộ 5 test kiểm thử tích hợp chuyên sâu cho Task 8.

---

## 3. Test Evidence

### Toàn bộ 5 test tích hợp Task 8 (`tests/test_cpsat_engine_integration.py`) PASS:
Lệnh chạy: `python -m pytest tests/test_cpsat_engine_integration.py -n auto -v`
```
tests/test_cpsat_engine_integration.py::test_fallback_when_ortools_unavailable PASSED
tests/test_cpsat_engine_integration.py::test_cpsat_solution_passes_all_validation_functions PASSED
tests/test_cpsat_engine_integration.py::test_use_cpsat_false_preserves_legacy_engine_behavior PASSED
tests/test_cpsat_engine_integration.py::test_fallback_when_timeout PASSED
tests/test_cpsat_engine_integration.py::test_cpsat_does_not_lose_to_legacy_engine_on_any_metric PASSED

======================== 5 passed in 103.72s (0:01:43) ========================
```

### Toàn bộ test suite dự án PASS với `pytest-xdist -n auto`:
Lệnh chạy: `python -m pytest tests/ -q -n auto`
```
........................................................................ [ 25%]
........................................................................ [ 50%]
........................................................................ [ 76%]
..................s............X........................................ [100%]
281 passed, 1 skipped, 1 xpassed in 280s
```

---

## 4. Đo nghiệm thực tế trên trường thật (`truong-thcs.db` Tuần 2)

Dữ liệu đo đạc thực tế độc lập:
- Build model time: 0.265s
- Solve time: 30.176s
- Cells changed: 138/236 (bảo tồn tối đa các ô cũ)

| Tiêu chí HĐSP | Legacy Engine | CP-SAT Solver | Nhận xét |
|---|---|---|---|
| **II.3 (Thiếu sáng bắt buộc)** | 3 | 3 | Ngang ngửa (Match) |
| **II.4 (Buổi dạy lẻ 1 tiết)** | 2 | 2 | Ngang ngửa (Match) |
| **II.8 (Ngày chia lẻ 1 sáng + 1 chiều)** | 0 | 0 | Tuyệt đối sạch vi phạm |
| **II.7 (Tiết trống giữa buổi)** | 40 | **14** | **Thắng áp đảo (giảm 65% số tiết trống!)** |
| **II.14 (4 tiết sáng liên tiếp)** | 2 | **0** | **Xóa sạch hoàn toàn vi phạm 100%!** |
| **Tổng điểm phạt chất lượng** | **24,200** | **12,950** | **CP-SAT giảm gần 50% tổng điểm phạt!** |
