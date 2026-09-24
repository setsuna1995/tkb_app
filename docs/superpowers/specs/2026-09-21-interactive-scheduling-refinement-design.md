# Đặc tả Thiết kế: Bộ Điều phối TKB 2 Giai đoạn & Hệ thống Hướng dẫn Dẫn dắt
**Interactive Scheduling Refinement Studio & 3-Tier Guidance System**

- **Ngày tạo**: 2026-09-21
- **Trạng thái**: Bản thảo đề xuất (Pending Approval)
- **Mục tiêu**: Giải quyết triệt để tình huống người dùng chạy xếp TKB lần đầu nhưng kết quả chưa 100% ưng ý; đồng thời cung cấp hệ thống dẫn dắt 3 tầng giúp mọi người dùng phát hiện, hiểu rõ và làm chủ các công cụ tối ưu hóa TKB.

---

## 1. Bối cảnh & Vấn đề

1. **Thực trạng xếp TKB lần đầu**:
   - Khi chạy lần đầu, CP-SAT tìm ra một nghiệm thỏa mãn 100% ràng buộc cứng và tối ưu hóa theo hàm mục tiêu toán học.
   - Tuy nhiên, trong thực tế quản lý trường học, có thể nảy sinh những điểm chưa ưng ý theo cảm nhận chủ quan hoặc đặc thù của trường:
     - 1-2 giáo viên vẫn bị trống tiết (lủng tiết giữa buổi) hoặc chưa được nghỉ đúng buổi mong muốn.
     - Phân bố môn học của một số lớp chưa đều (ví dụ môn nặng dồn nhiều vào các ngày liên tiếp).
   - Hiện tại, người dùng chỉ có 1 nút "Chạy xếp TKB", kết quả ghi đè lên phiên làm việc, không thể so sánh được sự khác biệt giữa các phương án.

2. **Khó khăn của người dùng (UX Discoverability)**:
   - Các cơ chế toán học mạnh mẽ như: Đổi Seed ngẫu nhiên, Tăng Time Limit giải sâu, hay Ưu tiên giữ TKB cũ (`cpsat_minimize_changes`) đang bị phân tán hoặc ẩn sâu trong tab cấu hình.
   - Người dùng thông thường không biết rằng: *Chỉ cần đổi Seed là thuật toán sẽ đi theo một nhánh tìm kiếm mới để sinh ra một TKB hoàn toàn khác mà vẫn chuẩn 100% quy tắc!*
   - Thiếu công cụ khóa (Lock/Pin) các lớp/tiết đã đẹp để chỉ tinh chỉnh các phần chưa ưng.

---

## 2. Giải pháp Tổng thể: Quy trình 2 Giai đoạn (Workflow C)

Quy trình làm việc được chia làm 2 giai đoạn nối tiếp nhau một cách tự nhiên và mạch lạc:

```
[Bấm 'Chạy xếp TKB']
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│ GIAI ĐOẠN 1: Studio Sinh & Đối sánh Phương án (On-Demand)    │
│  - Sinh Phương án 1 (Baseline)                              │
│  - Nút '🎲 Thử phương án khác (Đổi Seed)'                   │
│  - Nút '⏱️ Giải sâu hơn (+30s Time Limit)'                  │
│  - Thẻ đối sánh KPI đa phương án (Health Score, Tiết lủng)  │
│  - Chọn 1 Phương án làm Nền tảng (Baseline)                 │
└─────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│ GIAI ĐOẠN 2: Khóa & Tinh chỉnh Chi tiết (Refinement)        │
│  - Khóa cấp Lớp (Ví dụ: Khóa toàn bộ Khối 12)               │
│  - Khóa cấp Giáo viên (Ví dụ: Khóa lịch GV đã rất chuẩn)    │
│  - Khóa cấp Ô (Ghim tiết cụ thể)                            │
│  - Nút '🎯 Tinh chỉnh các ô còn lại' (Incremental Re-solve) │
│    + Ô đã khóa: Ép Ràng buộc CỨNG                           │
│    + Ô chưa khóa: CP-SAT Minimize Changes + Solution Hint   │
│  - Công cụ Đổi chéo thông minh (Smart Swap có kiểm tra trùng)│
└─────────────────────────────────────────────────────────────┘
        │
        ▼
[Lưu chính thức & Xuất Excel]
```

---

## 3. Hệ thống Hướng dẫn & Dẫn dắt 3 Tầng (3-Tier Guidance System)

Nhằm đảm bảo người dùng luôn nhận biết và biết cách sử dụng tính năng, hệ thống cung cấp 3 tầng hỗ trợ:

### 3.1. Tầng 1: Trợ lý Gợi ý tại chỗ (In-Context Assistant Banner & Tooltips)
- **Vị trí**: Nằm ngay phía trên kết quả xếp TKB tại `pages/06_Xep_TKB.py`.
- **Nội dung hiển thị**:
  > 💡 **TKB chưa hoàn toàn vừa ý? Bạn có thể tối ưu theo 2 bước đơn giản:**  
  > 1. **Thử phương án khác**: Bấm **`🎲 Thử phương án khác (Đổi Seed)`** để tìm nhánh mới, hoặc **`⏱️ Giải sâu hơn`** để máy tính triệt tiêu các tiết lủng của giáo viên.  
  > 2. **Khóa & Tinh chỉnh**: Khi đã chọn được phương án ưng ý nhất ➔ bấm **`🔒 Khóa các lớp đã đẹp`** ➔ bấm **`🎯 Tinh chỉnh các ô còn lại`**.
- **Tooltips cho từng nút điều khiển**:
  - `🎲 Thử phương án khác`: *"Đổi số ngẫu nhiên (Seed) để thuật toán khám phá cách xếp mới hoàn toàn nhưng vẫn đúng 100% quy chuẩn."*
  - `⏱️ Giải sâu hơn`: *"Tăng thời gian chạy CP-SAT để máy tính suy nghĩ kỹ hơn, giúp triệt tiêu các tiết trống/lủng của giáo viên."*
  - `🔒 Khóa lớp / Ghim ô`: *"Bảo vệ các lớp hoặc tiết đã rất đẹp, không cho thuật toán đụng vào khi tinh chỉnh."*
  - `🎯 Tinh chỉnh ô còn lại`: *"Giữ nguyên tối đa khung TKB hiện tại, chỉ đảo các ô chưa khóa để khắc phục chỗ lủng."*

### 3.2. Tầng 2: Hộp "Cẩm nang Tối ưu TKB 30 Giây" (Quick Help Expander)
- Nằm cạnh Action Bar với tiêu đề: `❓ Cẩm nang: Nên làm gì khi TKB chưa đúng ý? (Bấm xem nhanh)`.
- Bảng đối chiếu tình huống thực tế:
  | Tình huống thực tế bạn gặp | Giải pháp khuyên dùng | Thao tác thực hiện |
  | :--- | :--- | :--- |
  | **Thấy TKB nhìn chung chưa ưng, muốn xem kiểu bố trí khác** | Đổi sang nhánh tìm kiếm ngẫu nhiên mới. | Bấm **`🎲 Thử phương án khác`** |
  | **TKB khá ổn nhưng còn 2-3 GV bị lủng tiết giữa buổi** | Cho solver thêm thời gian để vét cạn giải pháp ghép kín tiết. | Bấm **`⏱️ Giải sâu hơn (+30s)`** |
  | **Khối 12 đã rất đẹp, chỉ còn Khối 10 bị xấu** | Khóa trọn vẹn Khối 12, chỉ cho solver giải lại Khối 10. | Tích chọn **`🔒 Khóa Lớp Khối 12`** ➔ Bấm **`🎯 Tinh chỉnh`** |
  | **Chỉ cần đổi chéo 2 tiết cụ thể cho nhau** | Đổi thủ công an toàn (tự kiểm tra xung đột GV). | Dùng công cụ **`Smart Swap (Đổi chéo)`** |

### 3.3. Tầng 3: Tài liệu Chuẩn tại Trang Hướng dẫn (`pages/11_Huong_Dan.py`)
- Tại **Tab 4 (Xếp TKB & Xuất Excel)**, bổ sung chuyên mục lớn:
  - **"Chiến lược Tối ưu hóa & Tinh chỉnh TKB Đa Giai đoạn"**.
  - Giải thích nguyên lý: Seed ngẫu nhiên là gì, cơ chế Hard Lock kết hợp Soft Minimize Changes.
  - Hướng dẫn thực hành 4 bước chuẩn dành cho BGH nhà trường.

---

## 4. Chi tiết Kiến trúc & Luồng Dữ liệu (Technical Architecture)

### 4.1. Cấu trúc Quản lý State (`st.session_state`)
Tại `pages/06_Xep_TKB.py`:
```python
# Danh sách các phương án ứng viên đã sinh ra trong phiên làm việc
st.session_state["candidates"] = {
    # candidate_id: {
    #     "name": str,                  # "Phương án 1", "Phương án 2 (Seed 99)"
    #     "seed": int,
    #     "time_limit": int,
    #     "result": ScheduleResult,
    #     "input": SchedulingInput,
    #     "health_score": int,          # Điểm đánh giá (0 - 100)
    #     "hole_periods": int,          # Tổng số tiết lủng GV
    #     "shortfalls_count": int,      # Số vi phạm mềm
    #     "created_at": str,
    # }
}
st.session_state["active_candidate_id"] = int  # ID của phương án đang được chọn xem/làm nền tảng
st.session_state["locked_slots"] = set()       # Tập hợp {slot_id} đã được khóa
st.session_state["locked_classes"] = set()     # Tập hợp {class_id} đã được khóa
st.session_state["locked_teachers"] = set()    # Tập hợp {teacher_id} đã được khóa
```

### 4.2. Mở rộng Model Dữ liệu (`core/models.py`)
Trong `SchedulingInput`:
```python
@dataclass
class SchedulingInput:
    ...
    locked_slots: dict = field(default_factory=dict)
    # dict[int, int]: Ánh xạ slot_id -> subject_id bị khóa cứng (bắt buộc solver phải xếp môn này vào slot này)
    reference_assignment: dict = field(default_factory=dict)
    # dict[int, int]: Ánh xạ slot_id -> subject_id của phương án hiện tại dùng làm hint và tính cpsat_minimize_changes
```

### 4.3. Cơ chế Khóa Cứng trong Solver (`core/scheduler/cpsat/constraints.py`)
Thêm hàm xây dựng ràng buộc khóa:
```python
def _add_locked_slots_constraints(built: CpSatModel) -> None:
    """Áp đặt ràng buộc CỨNG tuyệt đối cho các ô đã được người dùng khóa."""
    m = built.model
    x = built.x
    locked_slots = getattr(built.inp, "locked_slots", {}) or {}
    for slot_id, subject_id in locked_slots.items():
        if (slot_id, subject_id) in x:
            m.Add(x[slot_id, subject_id] == 1)
```
- **Ưu điểm vượt trội**: CP-SAT Presolver sẽ cố định biến `x[slot_id, subject_id] = 1` ở cấp độ tiền xử lý (pre-solve), loại bỏ toàn bộ các nhánh khả dĩ khác của slot này, giúp tốc độ giải tinh chỉnh tăng gấp 3-5 lần!

### 4.4. Cơ chế Nạp Nghiệm Cũ & Tinh chỉnh Mềm (`core/scheduler/cpsat/objectives.py`)
- Khi người dùng bấm **`🎯 Tinh chỉnh các ô còn lại`**:
  1. Các ô trong `locked_slots` được ép cứng bằng `_add_locked_slots_constraints`.
  2. Bật cờ `config.cpsat_minimize_changes = True`.
  3. Biến `s.old_subject_id` của các slot được nạp từ `reference_assignment` (nghiệm của phương án trước).
  4. Solver nạp solution hint xuất phát từ nghiệm trước (`_add_solution_hint`).
  5. Hàm mục tiêu phạt 100 điểm cho mỗi ô chưa khóa bị thay đổi (`_add_change_minimisation`), thúc đẩy solver chỉ đổi các ô thật sự gây ra vi phạm hoặc tiết lủng!

### 4.5. Cơ chế Đổi chéo Thông minh (Smart Swap)
- Cung cấp giao diện trực quan cho phép người dùng chọn 2 ô $(A, B)$ của cùng 1 lớp (hoặc giữa 2 tiết):
  - Kiểm tra xem Giáo viên của môn tại ô A có bị trùng tiết tại ô B hay không (và ngược lại).
  - Kiểm tra xem có vi phạm môn Giáo dục thể chất, Chào cờ, Sinh hoạt lớp hay không.
  - Nếu hợp lệ: Cập nhật trực tiếp `result.assignment` và tính lại KPI tức thì mà không cần chạy lại solver.

---

## 5. Kế hoạch Kiểm thử & Xác thực (Verification Plan)

### 5.1. Kiểm thử Đơn vị Tự động (Automated Unit Tests)
1. `tests/test_interactive_refinement.py`:
   - `test_locked_slots_hard_constraint`: Xác minh khi truyền `locked_slots`, solver không bao giờ thay đổi các ô này.
   - `test_candidate_seed_diversity`: Xác minh khi thay đổi `seed`, solver sinh ra các nghiệm có sự khác biệt rõ rệt nhưng vẫn 100% hợp lệ.
   - `test_incremental_resolve_minimizes_changes`: Xác minh khi tinh chỉnh với `cpsat_minimize_changes`, trên 85% các ô chưa khóa được giữ nguyên vị trí ban đầu.
   - `test_smart_swap_validation`: Kiểm tra logic hoán đổi 2 tiết và bắt lỗi xung đột giáo viên.

### 5.2. Kiểm thử Hồi quy Toàn diện (Full Regression Tests)
- Chạy toàn bộ test suite cốt lõi (122+ solver tests) để đảm bảo không có bất kỳ ảnh hưởng phụ nào đến thuật toán xếp lịch hiện hành.

### 5.3. Kiểm thử Giao diện & Trải nghiệm Người dùng (Manual & UI Verification)
- Xác minh Banner gợi ý xuất hiện đúng thời điểm sau lần chạy đầu tiên.
- Xác minh Expander cẩm nang 30 giây hiển thị rõ ràng, dễ đọc.
- Xác minh người dùng có thể chuyển đổi mượt mà giữa Phương án 1, 2, 3 và bấm khóa/tinh chỉnh thành công.
- Xác minh tài liệu mới tại `pages/11_Huong_Dan.py`.
