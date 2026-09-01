# Task 2 Report: UI & 1-Click DB Sync (`pages/07_Can_Bang_Tai.py`)

## 1. What was implemented
- Nâng cấp giao diện trang `pages/07_Can_Bang_Tai.py`:
  - Thể hiện rõ nguyên tắc cốt lõi: **Phân công theo trọn gói Lớp (môn × lớp)**, chuyển đồng thời toàn bộ số tiết tuần Chẵn và tuần Lẻ, bảo toàn tính đồng bộ của TKB.
  - Bổ sung **Bảng Tổng Hợp Tải Giáo Viên**: Tên GV, Vai trò, Giảm trừ, Trần (Cap), Sàn (Floor), Tải tuần C/L/TB, Trạng thái (Vượt trần / Dưới sàn / Cân bằng), và danh sách toàn bộ các lớp đang phụ trách.
  - Bổ sung **Bảng Đề Xuất Điều Chỉnh Phân Công**:
    - Hiển thị theo từng Lớp & Môn (số tiết C, L, TB).
    - Phân biệt rõ hình thức: ➡️ Chuyển 1 lớp vs 🔁 Đổi chéo 2 lớp (Class Swap).
    - Hiển thị biến động tải cụ thể của cả GV chuyển đi và GV nhận (Tải cũ → mới / Trần).
    - Cột checkbox "Áp dụng" cho phép người dùng chọn linh hoạt từng đề xuất.
  - Bổ sung **2 Nút Áp Dụng 1-Click**:
    - "⚡ Áp dụng các đề xuất đã chọn"
    - "⚡ Áp dụng TẤT CẢ đề xuất"
    - Cập nhật trực tiếp vào cơ sở dữ liệu SQLite qua `repo.set_assignment` và tự động làm mới giao diện (`st.rerun()`).

## 2. Files Changed
- `pages/07_Can_Bang_Tai.py`: Complete UI upgrade.
- `tests/test_load_balance.py`: Added DB integration test `test_apply_suggestions_to_database`.

## 3. Test Evidence

### Command Run
`python -m pytest tests/test_load_balance.py -v`

### Output
```
============================= test session starts =============================
platform win32 -- Python 3.14.7, pytest-9.1.1, pluggy-1.6.0 -- C:\Users\Kien\AppData\Local\Python\pythoncore-3.14-64\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\Kien\tkb_app
plugins: anyio-4.14.2
collecting ... collected 7 items

tests/test_load_balance.py::test_compute_teacher_loads PASSED            [ 14%]
tests/test_load_balance.py::test_suggest_rebalance_transfer_whole_class PASSED [ 28%]
tests/test_load_balance.py::test_suggest_rebalance_swap_classes PASSED   [ 42%]
tests/test_load_balance.py::test_apply_suggestion_to_assignments PASSED  [ 57%]
tests/test_load_balance.py::test_apply_all_suggestions PASSED            [ 71%]
tests/test_load_balance.py::test_suggest_rebalance_asymmetric_weeks PASSED [ 85%]
tests/test_load_balance.py::test_apply_suggestions_to_database PASSED    [100%]

============================== 7 passed in 0.15s ==============================
```

## 4. Self-Review
- [x] Giao diện hỗ trợ cả chuyển 1 chiều và đổi chéo 2 chiều.
- [x] Nút áp dụng lưu chuẩn xác vào DB, không mất mát dữ liệu.
- [x] Sidebar backup và school switcher được bảo toàn.
