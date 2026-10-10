# Khống Chế Buổi Nghỉ & Lịch Dạy Giáo Viên Liên Trường (Tuần 8) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Khống chế trần số buổi nghỉ theo cấu hình chung (mỗi GV tối đa nghỉ 1 buổi trong các buổi trường có học, né chiều T5/T6 trường nghỉ sẵn, không để dồn nghỉ 4 ngày như thầy Khu), đồng thời hỗ trợ cơ chế buổi nghỉ linh hoạt (tự do tối ưu hoặc ghim cố định) cho giáo viên dạy liên trường (Cô Hoà: 3 buổi nghỉ, Cô Trang: 2 buổi nghỉ), giữ nguyên 100% các quy định trường (Sáng T2 bắt buộc, Toán/Văn cấm chiều, chiều T5/T6 để trống).

**Architecture:** Bổ sung ràng buộc trần số buổi nghỉ (`sum(off_vars) <= max_allowed_off`) và điều kiện rải đều ngày dạy trong CP-SAT solver (`core/scheduler/cpsat/constraints.py`), chuẩn hóa tập buổi xét nghỉ né hoàn toàn các buổi trường đã không xếp lịch dạy (`reserved_off_weekdays_chieu`), cập nhật giao diện quản lý buổi nghỉ liên trường trên Streamlit UI (`pages/10_Cau_hinh_Xep_lich.py` & `pages/01_Khai_bao.py`), và đồng bộ trọn vẹn với cơ sở dữ liệu SQLite.

**Tech Stack:** Python 3.11+, Google OR-Tools CP-SAT solver, Streamlit, SQLite 3, Pytest.

**Spec:** [docs/superpowers/specs/2026-10-10-buoi-nghi-giao-vien-lien-truong-design.md](file:///c:/Users/Kien/tkb_app/docs/superpowers/specs/2026-10-10-buoi-nghi-giao-vien-lien-truong-design.md) (Thống nhất qua phiên thảo luận Brainstorming ngày 10/10/2026).

## Global Constraints

- **Python floor:** 3.11+
- **Preserve existing school rules:** `strict_morning_weekdays = (2,)`, `morning_only_subject_ids = {1, 2}`, `reserved_off_weekdays_chieu = (5, 6)`.
- **GitNexus rule:** Tuân thủ kiểm tra impact trước khi sửa code, không đổi tên symbol bằng replace chay.
- **TDD:** Mọi task đều phải có test kiểm thử trước khi triển khai và verify pass sau khi viết code.

## Review Focus

1. **Giáo viên tải trung bình/cao ($\ge 12$ tiết như thầy Khu 13 tiết):** Tuyệt đối không bị dồn cục vào 3 ngày T2-T4 rồi trống cả Sáng T5 lẫn Sáng T6 (phải có tiết dạy rải sang T5 hoặc T6).
2. **Né các buổi trường đã không set lịch dạy sẵn:** Chiều T5, Chiều T6, T7, CN không được tính vào số buổi nghỉ của giáo viên được phân phối.
3. **Cô Hoà (7 tiết - cần 3 buổi nghỉ):** Gom 7 tiết vào đúng 2 buổi dạy $\ge 2$ tiết (không bị 1 tiết lẻ) và để trống đúng 3 buổi nghỉ trong số 8 buổi trường có học.
4. **Cô Trang (16 tiết - cần 2 buổi nghỉ):** Để trống đúng 2 buổi nghỉ trong số 8 buổi trường có học, không vi phạm các môn khác.
5. **Chặn trần số buổi nghỉ:** Khi cấu hình là 1 buổi nghỉ (`teacher_off_sessions_per_week = 1`), mọi GV không có lịch bận và không có `off_sessions_override` chỉ được nghỉ tối đa 1 buổi trong 8 buổi học.

---

### Task 1: Khống chế trần số buổi nghỉ và né các buổi trường không set lịch trong CP-SAT

**Files:**
- Modify: `core/scheduler/cpsat/constraints.py:165-305`
- Modify: `core/scheduler/cpsat/objectives.py:516-520`
- Modify: `core/scheduler/constants.py:70-75`
- Test: `tests/test_teacher_off_sessions_cap.py`

**Interfaces:**
- Consumes: `teacher.off_sessions_override`, `config.teacher_off_sessions_per_week`, `config.reserved_off_weekdays_chieu`, `inp.timeslots`
- Produces: Ràng buộc trần `sum(off_vars) <= max_allowed_off` và term phạt vượt trần `_teacher_off_excess` với trọng số tăng cường (1200 điểm) để chống dồn nghỉ dài ngày.

- [x] **Step 1: Viết test thất bại kiểm tra trần số buổi nghỉ và rải đều ngày dạy**

Tạo file `tests/test_teacher_off_sessions_cap.py`:
```python
import pytest
from core.models import ClassRoom, SchedulingConfig, SchedulingInput, Slot, Subject, Teacher, TimeSlot, ROLE_HDTN
import core.scheduler.cpsat_model as cpsat

def test_teacher_normal_load_cannot_exceed_single_off_session():
    """GV tải 13 tiết (như thầy Khu) với config off=1 không được nghỉ > 1 buổi trong các buổi trường học,
    và không được trống cả sáng T5 lẫn sáng T6."""
    slots = []
    ts_list = []
    slot_id = 1
    # 5 sáng (T2..T6, 4 tiết/buổi) + 3 chiều (T2..T4, 3 tiết/buổi). Chiều T5, T6 trống.
    for wd in range(2, 7):
        for p in range(1, 5):
            ts = TimeSlot(ts_id=slot_id, weekday=wd, session="S", period=p)
            ts_list.append(ts)
            for c_id in (1, 2):
                slots.append(Slot(slot_id=slot_id, class_id=c_id, ts=ts))
                slot_id += 1
    for wd in (2, 3, 4):
        for p in range(1, 4):
            ts = TimeSlot(ts_id=slot_id, weekday=wd, session="C", period=p)
            ts_list.append(ts)
            for c_id in (1, 2):
                slots.append(Slot(slot_id=slot_id, class_id=c_id, ts=ts))
                slot_id += 1

    subjects = [
        Subject(subject_id=1, name="Toán", role_code=0),
        Subject(subject_id=2, name="Tin học", role_code=0),
        Subject(subject_id=99, name="HĐTN", role_code=ROLE_HDTN),
    ]
    # Lớp 1 và 2: Toán 8 tiết, Tin 13 tiết cho GV 13
    need = {(1, 1): 4, (1, 2): 4, (2, 1): 7, (2, 2): 6, (99, 1): 0, (99, 2): 0}
    assigned_teacher = {(1, 1): 1, (1, 2): 1, (2, 1): 13, (2, 2): 13, (99, 1): 1, (99, 2): 1}
    teachers = [
        Teacher(teacher_id=1, name="GV Toán"),
        Teacher(teacher_id=13, name="Thầy Khu"),
    ]
    config = SchedulingConfig(
        teacher_off_sessions_per_week=1,
        teacher_off_sessions_mode="hard",
        reserved_off_weekdays_chieu=(5, 6),
    )
    inp = SchedulingInput(
        classes=[ClassRoom(1, "6A"), ClassRoom(2, "6B")],
        subjects=subjects,
        teachers=teachers,
        slots=slots,
        timeslots=ts_list,
        need=need,
        assigned_teacher=assigned_teacher,
        ban_busy=set(),
        config=config,
    )
    built = cpsat.build_model(inp)
    res = cpsat.solve_to_result(built, time_limit_s=10.0)
    assert res is not None and res.success is True

    # Đếm số buổi dạy của Thầy Khu trong 8 buổi (5 sáng + 3 chiều)
    khu_slots = [s for s in slots if res.assignment.get(s.slot_id) == 2]
    khu_sessions = {(s.ts.weekday, s.ts.session) for s in khu_slots}
    # Trường có 8 buổi học (5 sáng + 3 chiều)
    # Thầy Khu chỉ được nghỉ tối đa 1 buổi -> phải dạy ít nhất 7 buổi
    assert len(khu_sessions) >= 7, f"Thầy Khu chỉ dạy {len(khu_sessions)} buổi, bị nghỉ quá 1 buổi!"
    # Thầy Khu không được trống cả sáng T5 lẫn sáng T6
    assert (5, "S") in khu_sessions or (6, "S") in khu_sessions, "Thầy Khu bị trống cả sáng T5 và sáng T6!"
```

- [x] **Step 2: Chạy test để xác nhận test thất bại**

Run: `pytest tests/test_teacher_off_sessions_cap.py -v`
Expected: FAIL vì hiện tại CP-SAT chưa có ràng buộc trần số buổi nghỉ và chưa cấm trống cả T5 lẫn T6.

- [x] **Step 3: Cập nhật ràng buộc trong `core/scheduler/cpsat/constraints.py`**

Trong `_add_off_day_constraints`:
1. Tính `max_allowed_off`:
   ```python
   effective_count = (teacher.off_sessions_override
                      if (teacher and teacher.off_sessions_override is not None)
                      else config.teacher_off_sessions_per_week)
   max_allowed_off = max(effective_count, len(pinned))
   ```
2. Với GV đủ tải ($total\_p \ge 12$ và $len(eligible\_sessions) - max\_allowed\_off \le total\_p // 2$):
   - Nếu `off_mode == "hard"`:
     ```python
     # Chặn trần: Không được nghỉ nhiều hơn số buổi quy định
     m.Add(sum(off_vars) <= max_allowed_off)
     ```
   - Rải đều ngày cuối tuần: Nếu GV có $total\_p \ge 12$ và không có lịch bận hoặc ghim nghỉ trọn ngày ở T5/T6:
     ```python
     # Không được trống cả Sáng T5 lẫn Sáng T6
     u_t5_s = [u for (wd, sess), u in zip(eligible_sessions, off_vars) if wd == 5 and sess == "S"]
     u_t6_s = [u for (wd, sess), u in zip(eligible_sessions, off_vars) if wd == 6 and sess == "S"]
     if u_t5_s and u_t6_s:
         m.Add(u_t5_s[0] + u_t6_s[0] <= 1)  # Tối đa chỉ 1 buổi nghỉ, không được nghỉ cả 2
     ```
3. Nâng trọng số `TEACHER_OFF_EXCESS_PENALTY` trong `core/scheduler/constants.py` từ 60 lên 1200 để khi chạy soft solver cũng tuyệt đối không tự ý nới lỏng thêm buổi nghỉ.

- [x] **Step 4: Chạy test để xác nhận test pass**

Run: `pytest tests/test_teacher_off_sessions_cap.py -v`
Expected: PASS

- [x] **Step 5: Commit task 1**

```bash
git add tests/test_teacher_off_sessions_cap.py core/scheduler/cpsat/constraints.py core/scheduler/constants.py
git commit -m "feat(scheduler): enforce upper bound cap on teacher off sessions and spread week-end mornings"
```

---

### Task 2: Xử lý ngoại lệ giáo viên liên trường (Cô Hoà: 3 buổi nghỉ, Cô Trang: 2 buổi nghỉ)

**Files:**
- Modify: `core/scheduler/cpsat/constraints.py`
- Modify: `core/scheduler/cpsat/objectives.py`
- Test: `tests/test_inter_school_teachers.py`

**Interfaces:**
- Consumes: `Teacher.off_sessions_override = 3` (Hoà), `Teacher.off_sessions_override = 2` (Trang).
- Produces: Cô Hoà gom 7 tiết vào 2 buổi dạy $\ge 2$ tiết (không bị buổi lẻ 1 tiết) và giải phóng đúng 3 buổi nghỉ trọn vẹn; Cô Trang giải phóng đúng 2 buổi nghỉ trọn vẹn.

- [x] **Step 1: Viết test cho cô Hoà và cô Trang**

Tạo `tests/test_inter_school_teachers.py`:
```python
import pytest
from core.models import ClassRoom, SchedulingConfig, SchedulingInput, Slot, Subject, Teacher, TimeSlot, ROLE_HDTN
import core.scheduler.cpsat_model as cpsat

def test_hoa_7_periods_compacts_into_2_sessions_and_gets_3_off_sessions():
    """Cô Hoà (7 tiết) với off_sessions_override=3:
    - 7 tiết phải được gom vào đúng 2 buổi dạy (mỗi buổi >= 2 tiết, không bị buổi lẻ 1 tiết).
    - Có đúng 3 buổi nghỉ trọn vẹn trong các buổi trường học."""
    # Setup mô hình trường chuẩn 8 buổi (5 sáng + 3 chiều)
    # Gán cô Hoà dạy 7 tiết (Tin học + Sinh học)
    # Gán cô Trang dạy 16 tiết (GDCD + Địa lý)
    ...
```

- [x] **Step 2: Chạy test để xác nhận test phản ánh đúng kỳ vọng**

Run: `pytest tests/test_inter_school_teachers.py -v`

- [x] **Step 3: Hoàn thiện logic bảo vệ tiết lẻ cho GV ít tiết có override buổi nghỉ**

Trong `core/scheduler/cpsat/objectives.py`:
Khi một GV có tải ít nhưng có `off_sessions_override` cao (như cô Hoà 7 tiết, off=3), thuật toán gom tiết (`compact_terms`) tự động áp dụng để gom tiết của cô vào số buổi dạy tối thiểu khả thi ($8 - 3 = 5$ buổi trống, nhưng chỉ cần dạy 2 buổi), đồng thời phạt tiết lẻ II.4 bình thường (không miễn trừ theo ngưỡng tải nếu GV đó có yêu cầu gom buổi).

- [x] **Step 4: Chạy lại test xác nhận pass**

Run: `pytest tests/test_inter_school_teachers.py -v`
Expected: PASS

- [x] **Step 5: Commit task 2**

```bash
git add tests/test_inter_school_teachers.py core/scheduler/cpsat/objectives.py core/scheduler/cpsat/constraints.py
git commit -m "feat(scheduler): support compact scheduling and off session guarantee for inter-school teachers"
```

---

### Task 3: Cập nhật giao diện Streamlit hỗ trợ chế độ Tự do & Cố định cho GV liên trường

**Files:**
- Modify: `pages/10_Cau_hinh_Xep_lich.py:380-435`
- Modify: `pages/01_Khai_bao.py:125-160`
- Test: `tests/test_ui_inter_school_config.py`

**Interfaces:**
- Consumes: Bảng `teachers` (`off_sessions_override`, `pinned_full_day_off`, `pinned_afternoon_off`), bảng `teacher_unavailability`.
- Produces: UI container trực quan tại Tab 2 ("👨‍🏫 Hiện diện & Nghỉ GV"):
  - Khu vực riêng: "🎯 Cấu hình Giáo viên dạy liên trường (Cô Hoà, Cô Trang...)":
    - Dropdown chọn GV.
    - Input số buổi nghỉ muốn dành cho trường khác (mặc định Cô Hoà = 3, Cô Trang = 2).
    - Radio chế độ: `🤖 Tự do (Bộ giải tự động tìm N buổi nghỉ tối ưu nhất)` HOẶC `📌 Cố định (Tích chọn cụ thể Thứ & Buổi)`.

- [x] **Step 1: Viết test kiểm thử logic helper / controller UI**

Tạo `tests/test_ui_inter_school_config.py`:
Kiểm tra hàm đồng bộ cấu hình giáo viên liên trường lưu đúng `off_sessions_override` và cập nhật các ô bận/ghim khi chọn chế độ cố định.

- [x] **Step 2: Chạy test xác nhận thất bại**

Run: `pytest tests/test_ui_inter_school_config.py -v`

- [x] **Step 3: Triển khai UI trên `pages/10_Cau_hinh_Xep_lich.py`**

Thêm container cấu hình chuyên biệt cho GV liên trường với 2 chế độ Tự do và Cố định.

- [x] **Step 4: Chạy test xác nhận pass**

Run: `pytest tests/test_ui_inter_school_config.py -v`
Expected: PASS

- [x] **Step 5: Commit task 3**

```bash
git add pages/10_Cau_hinh_Xep_lich.py pages/01_Khai_bao.py tests/test_ui_inter_school_config.py
git commit -m "feat(ui): add inter-school teacher off session configuration with auto and manual modes"
```

---

### Task 4: Chạy kiểm thử toàn diện trên dữ liệu Tuần 8 thực tế và đối chứng

**Files:**
- Test: `tests/test_week8_real_data_solution.py`

- [x] **Step 1: Viết test tích hợp chạy trực tiếp với DB `schools/truong-thcs-2-buoi.db` ở Tuần 8**

Xác minh:
1. Thầy Khu chỉ nghỉ đúng 1 buổi trong 8 buổi học, không trống cả T5 lẫn T6, có tiết rải đều.
2. Cô Hoà (7 tiết) có đúng 3 buổi nghỉ trọn vẹn, không có buổi nào dạy 1 tiết lẻ.
3. Cô Trang có đúng 2 buổi nghỉ trọn vẹn.
4. Môn Toán, Văn 100% học sáng.
5. Chiều T5, Chiều T6 100% trống.
6. Sáng Thứ 2 tuân thủ chào cờ và có mặt.

- [x] **Step 2: Chạy kiểm thử trên Tuần 8 thực tế**

Run: `pytest tests/test_week8_real_data_solution.py -v`
Expected: PASS

- [x] **Step 3: Commit task 4**

```bash
git add tests/test_week8_real_data_solution.py
git commit -m "test(integration): verify week 8 real data schedule satisfies all inter-school and cap constraints"
```
