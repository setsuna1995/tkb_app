# Kế hoạch thực hiện: Khắc phục xung đột Rules & Đồng bộ trọng số điểm TKB

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Khắc phục triệt để 3 điểm xung đột quy tắc (bế tắc toán học trần học thuật khi cấm chiều, kẹt logic GV bận sáng bán phần với II.3/II.4, ghim nghỉ trọn ngày bị nuốt âm thầm) và đồng bộ hệ thống nhận diện môn học thuật cùng trọng số phạt ngày chia lẻ.

**Architecture:** Bổ sung hàm nhận diện môn học thuật `is_academic_subject` tại `core/roles.py` dùng chung cho toàn bộ scheduler và validator; cập nhật logic tính `effective_max` tại `cpsat/constraints.py` để tự động nâng trần học thuật sáng khi cấm môn nặng chiều; tinh chỉnh `_is_teacher_busy_morning` coi GV bận nếu số ô rảnh $< 2$; cho phép `pinned_full_day_off` của BGH ưu tiên vượt qua `FORBIDDEN_OFF_CELLS`; và nâng hằng số `TEACHER_SPLIT_DAY_PENALTY` lên 700 đồng nhất giữa Greedy, CP-SAT và Quality.

**Tech Stack:** Python 3.13, Google OR-Tools CP-SAT, Pytest, SQLite.

**Spec:** Báo cáo đánh giá và phê duyệt giải pháp ngày 2026-09-07 trong phiên thảo luận `brainstorming`.

## Global Constraints

- Không làm phá vỡ bất kỳ quy tắc sư phạm hay ràng buộc cứng nào hiện có.
- Mọi hàm sửa đổi đều phải đồng bộ song song ở cả 3 tầng: CP-SAT Solver (`core/scheduler/cpsat/`), Greedy Engine (`core/scheduler/`), và Validation Dashboard (`core/validation.py`).
- Giữ 100% độ tương thích với cơ sở dữ liệu `truong-thcs.db` và các file cấu hình hiện hữu.
- Toàn bộ test suite phải vượt qua (PASS) sau khi hoàn thành mỗi task (TDD).

---

### Task 1: Nhận diện toàn diện môn học thuật cốt lõi

**Files:**
- Create: `tests/test_academic_subject_resolution.py`
- Modify: `core/roles.py:1-45`
- Modify: `core/scheduler/cpsat/constraints.py:330-334`
- Modify: `core/scheduler/cpsat/objectives.py:379-383`
- Modify: `core/validation.py:574-578`

**Interfaces:**
- Produces: `is_academic_subject(subject_name: str) -> bool` trong `core/roles.py`.
- Consumes: Được gọi bởi `constraints.py`, `objectives.py`, `validation.py` để lấy tập hợp `academic_ids`.

- [ ] **Step 1: Viết failing test kiểm tra nhận diện môn học thuật**

Tạo file `tests/test_academic_subject_resolution.py`:
```python
from core.roles import is_academic_subject


def test_is_academic_subject():
    # Nhóm Toán
    assert is_academic_subject("Toán") is True
    assert is_academic_subject("Toán học") is True
    assert is_academic_subject("Toán 6") is True

    # Nhóm Ngữ văn
    assert is_academic_subject("Ngữ văn") is True
    assert is_academic_subject("Văn") is True
    assert is_academic_subject("Ngữ Văn 7") is True

    # Nhóm Ngoại ngữ / Tiếng Anh
    assert is_academic_subject("Ngoại ngữ") is True
    assert is_academic_subject("Tiếng Anh") is True
    assert is_academic_subject("Tiếng Anh 8 (Global Success)") is True
    assert is_academic_subject("Anh") is True

    # Nhóm Khoa học tự nhiên
    assert is_academic_subject("Khoa học tự nhiên") is True
    assert is_academic_subject("Khoa học tự nhiên (Vật lý)") is True
    assert is_academic_subject("Khoa học tự nhiên (Hóa học)") is True
    assert is_academic_subject("Khoa học tự nhiên (Sinh học)") is True
    assert is_academic_subject("KHTN") is True

    # Nhóm môn không phải học thuật cốt lõi
    assert is_academic_subject("Giáo dục thể chất") is False
    assert is_academic_subject("Tin học") is False
    assert is_academic_subject("Âm nhạc") is False
    assert is_academic_subject("Mỹ thuật") is False
    assert is_academic_subject("Giáo dục công dân") is False
    assert is_academic_subject("Công nghệ") is False
    assert is_academic_subject("Hoạt động trải nghiệm, hướng nghiệp") is False
    assert is_academic_subject("Lịch sử và Địa lý") is False
```

- [ ] **Step 2: Chạy test để xác nhận test fail**

Chạy: `pytest tests/test_academic_subject_resolution.py`
Kỳ vọng: FAIL vì `is_academic_subject` chưa được định nghĩa trong `core/roles.py`.

- [ ] **Step 3: Triển khai hàm `is_academic_subject` trong `core/roles.py` và cập nhật các nơi sử dụng**

Thêm vào `core/roles.py`:
```python
ACADEMIC_SUBJECT_PREFIXES = (
    "toán",
    "ngữ văn",
    "văn",
    "ngoại ngữ",
    "tiếng anh",
    "anh",
    "khoa học tự nhiên",
    "khtn",
)


def is_academic_subject(subject_name: str) -> bool:
    """Xác định môn học có thuộc nhóm học thuật cốt lõi (Toán, Văn, Ngoại ngữ/Tiếng Anh, KHTN) hay không."""
    if not subject_name:
        return False
    name_clean = subject_name.strip().lower()
    return any(name_clean.startswith(prefix) for prefix in ACADEMIC_SUBJECT_PREFIXES)
```

Thay thế logic lọc `academic_ids` bằng `is_academic_subject(s.name)` tại:
1. `core/scheduler/cpsat/constraints.py` (dòng 330):
```python
        academic_ids = {
            s.subject_id for s in inp.subjects
            if is_academic_subject(s.name)
        }
```
2. `core/scheduler/cpsat/objectives.py` (dòng 380):
```python
        academic_ids = {
            s.subject_id for s in inp.subjects
            if is_academic_subject(s.name)
        }
```
3. `core/validation.py` (dòng 575):
```python
    academic_ids = {
        s.subject_id for s in inp.subjects
        if is_academic_subject(s.name)
    }
```

- [ ] **Step 4: Chạy test xác nhận pass**

Chạy: `pytest tests/test_academic_subject_resolution.py`
Kỳ vọng: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/roles.py core/scheduler/cpsat/constraints.py core/scheduler/cpsat/objectives.py core/validation.py tests/test_academic_subject_resolution.py
git commit -m "fix: unify academic subject recognition with is_academic_subject helper"
```

---

### Task 2: Tự động nới trần thông minh khi môn Nặng cấm chiều

**Files:**
- Modify: `core/scheduler/cpsat/constraints.py:345-353`
- Modify: `tests/test_morning_academic_balance.py`

**Interfaces:**
- Consumes: `config.heavy_subjects_morning_only`, `config.max_academic_per_morning`.
- Produces: `effective_max` an toàn, chống bế tắc toán học cho buổi sáng khi môn nặng bị cấm ở buổi chiều.

- [ ] **Step 1: Viết failing test cho trường hợp cấm môn nặng chiều kết hợp trần sáng $\le 3$**

Thêm test case vào `tests/test_morning_academic_balance.py`:
```python
def test_cpsat_morning_academic_ceiling_when_heavy_morning_only():
    """Kiểm tra: Khi lớp có buổi chiều nhưng bật heavy_subjects_morning_only=True,
    và tổng số tiết học thuật (16 tiết / 5 sáng) vượt quá 5x3=15, trần sáng phải tự động
    nâng lên ceil(16/5) = 4 thay vì gây Infeasible model."""
    import core.scheduler.cpsat_model as cpsat
    from core.models import Subject, ClassRoom, TimeSlot, Slot, SchedulingConfig, SchedulingInput

    # 1 lớp học 5 sáng (mỗi sáng 4 tiết) + 1 chiều (3 tiết) = 23 slots
    slots = []
    slot_id = 1
    # 5 sáng (T2..T6)
    for wd in range(2, 7):
        for p in range(1, 5):
            ts = TimeSlot(ts_id=slot_id, weekday=wd, session="S", period=p)
            slots.append(Slot(slot_id=slot_id, class_id=1, ts=ts))
            slot_id += 1
    # 1 chiều (T3)
    for p in range(1, 4):
        ts = TimeSlot(ts_id=slot_id, weekday=3, session="C", period=p)
        slots.append(Slot(slot_id=slot_id, class_id=1, ts=ts))
        slot_id += 1

    # 16 tiết học thuật (Toán 4, Văn 4, Anh 4, KHTN 4) + 3 tiết nhẹ (Tin 3)
    subjects = [
        Subject(subject_id=1, name="Toán", role_code=1),  # Heavy
        Subject(subject_id=2, name="Ngữ văn", role_code=1),  # Heavy
        Subject(subject_id=3, name="Tiếng Anh", role_code=1),  # Heavy
        Subject(subject_id=4, name="Khoa học tự nhiên", role_code=1),  # Heavy
        Subject(subject_id=5, name="Tin học", role_code=0),  # Light
    ]
    need = {(1, 1): 4, (2, 1): 4, (3, 1): 4, (4, 1): 4, (5, 1): 3}
    assigned_teacher = {
        (1, 1): 101, (2, 1): 102, (3, 1): 103, (4, 1): 104, (5, 1): 105
    }

    config = SchedulingConfig(
        heavy_subjects_morning_only=True,  # Cấm môn nặng ở chiều!
        balance_morning_academic_load=True,
        max_academic_per_morning=3,
        avoid_teacher_lone_periods=False,
    )
    inp = SchedulingInput(
        classes=[ClassRoom(class_id=1, name="9A1", sort_order=0)],
        subjects=subjects,
        teachers=[],
        slots=slots,
        need=need,
        assigned_teacher=assigned_teacher,
        config=config,
    )

    built = cpsat.build_model(inp)
    solver = cpsat._create_solver(built)
    solver.parameters.max_time_in_seconds = 5.0
    status = solver.Solve(built.model)
    assert status in (cpsat.cp_model.OPTIMAL, cpsat.cp_model.FEASIBLE), "CP-SAT phải giải được nhờ dynamic ceiling!"
```

- [ ] **Step 2: Chạy test để xác nhận test fail**

Chạy: `pytest tests/test_morning_academic_balance.py::test_cpsat_morning_academic_ceiling_when_heavy_morning_only`
Kỳ vọng: FAIL vì CP-SAT báo INFEASIBLE (trần 3 tiết/sáng $\times$ 5 sáng = 15 tiết $< 16$ tiết cần xếp, trong khi chiều bị cấm môn nặng).

- [ ] **Step 3: Triển khai dynamic ceiling tại `core/scheduler/cpsat/constraints.py`**

Trong `core/scheduler/cpsat/constraints.py` dòng 348-352:
```python
                is_heavy_morning_only = getattr(config, "heavy_subjects_morning_only", False)
                must_all_in_morning = (class_id not in class_has_afternoon) or is_heavy_morning_only
                if must_all_in_morning and c_mornings > 0:
                    effective_max = max(config.max_academic_per_morning, (c_academic_need + c_mornings - 1) // c_mornings)
                else:
                    effective_max = config.max_academic_per_morning
```

- [ ] **Step 4: Chạy test xác nhận pass**

Chạy: `pytest tests/test_morning_academic_balance.py::test_cpsat_morning_academic_ceiling_when_heavy_morning_only`
Kỳ vọng: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/scheduler/cpsat/constraints.py tests/test_morning_academic_balance.py
git commit -m "fix: compute dynamic academic morning ceiling when heavy_subjects_morning_only is active"
```

---

### Task 3: Chuẩn hoá điều kiện GV bận sáng bán phần với II.3 và II.4

**Files:**
- Create: `tests/test_teacher_busy_morning_conflict.py`
- Modify: `core/scheduler/cpsat/constraints.py:477-494`
- Modify: `core/scheduler/quality.py:136-150`
- Modify: `core/validation.py:434-453`

**Interfaces:**
- Consumes: `inp.ban_busy`, `candidate_slots`.
- Produces: `_is_teacher_busy_morning` trả về `True` (miễn trừ II.3) nếu số ô rảnh khả dụng của GV trong buổi sáng $< 2$.

- [ ] **Step 1: Viết failing test cho trường hợp GV chỉ rảnh 1 tiết sáng do GV_Bận**

Tạo file `tests/test_teacher_busy_morning_conflict.py`:
```python
from core.models import ClassRoom, SchedulingConfig, SchedulingInput, Slot, Subject, Teacher, TimeSlot
import core.scheduler.cpsat_model as cpsat


def test_teacher_busy_morning_with_less_than_2_free_slots():
    """Kiểm tra: Khi GV bị bận 3/4 tiết sáng Thứ 2 (chỉ còn rảnh 1 tiết),
    GV phải được tự động coi là bận buổi sáng đó để không bị kẹt xung đột giữa
    II.3 (ép có mặt) và II.4 (cấm buổi 1 tiết)."""
    # 1 lớp học sáng Thứ 2 (4 tiết)
    slots = []
    for p in range(1, 5):
        ts = TimeSlot(ts_id=p, weekday=2, session="S", period=p)
        slots.append(Slot(slot_id=p, class_id=1, ts=ts))

    subjects = [
        Subject(subject_id=1, name="Toán", role_code=1),
        Subject(subject_id=2, name="Ngữ văn", role_code=1),
    ]
    need = {(1, 1): 2, (2, 1): 2}
    assigned_teacher = {(1, 1): 10, (2, 1): 20}
    teachers = [
        Teacher(teacher_id=10, name="GV Toán"),
        Teacher(teacher_id=20, name="GV Văn"),
    ]
    # GV 10 bận tiết 1, 2, 3 -> chỉ rảnh tiết 4 (1 tiết duy nhất!)
    ban_busy = {(10, 1), (10, 2), (10, 3)}

    config = SchedulingConfig(
        strict_morning_weekdays=(2,),  # Sáng Thứ 2 bắt buộc toàn thể GV
        avoid_teacher_lone_periods=True,
    )
    inp = SchedulingInput(
        classes=[ClassRoom(class_id=1, name="6A1", sort_order=0)],
        subjects=subjects,
        teachers=teachers,
        slots=slots,
        need=need,
        assigned_teacher=assigned_teacher,
        ban_busy=ban_busy,
        config=config,
    )

    # Pass 1 phải giải thành công không bị infeasible hoặc phạt II.3
    res = cpsat.solve(inp, time_limit_s=5.0)
    assert res.success is True
    # GV 10 không bị ép xếp vào tiết 4 (để tránh buổi lẻ II.4) và không bị phạt II.3
    relaxed_ids = [r["rule_id"] for r in res.relaxed_rules]
    assert "II.3" not in relaxed_ids
```

- [ ] **Step 2: Chạy test để xác nhận test fail**

Chạy: `pytest tests/test_teacher_busy_morning_conflict.py`
Kỳ vọng: FAIL vì `_is_teacher_busy_morning` thấy còn 1 slot rảnh nên trả về `False`, dẫn đến II.3 ép có mặt mà II.4 cấm lẻ 1 tiết.

- [ ] **Step 3: Cập nhật hàm `_is_teacher_busy_morning` ở 3 module**

1. Tại `core/scheduler/cpsat/constraints.py` (hàm `_is_teacher_busy_morning`):
```python
def _is_teacher_busy_morning(inp: SchedulingInput, teacher_id: int, weekday: int) -> bool:
    """Kiểm tra xem GV có bị bận buổi sáng thứ `weekday` hay không.
    Nếu số ô rảnh khả dụng của GV trong buổi sáng đó < 2 tiết, coi như bận
    (vì theo II.4 không thể xếp buổi 1 tiết cho GV)."""
    if not inp.ban_busy:
        return False
    morn_slots = [s for s in inp.slots if s.ts.weekday == weekday and s.ts.session == "S"]
    if not morn_slots:
        return False
    eff = _build_effective_assigned_teacher(inp)
    candidate_slots = [
        s for s in morn_slots
        if any(eff.get((subj.subject_id, s.class_id)) == teacher_id for subj in inp.subjects)
    ]
    if not candidate_slots:
        free_slots = [s for s in morn_slots if (teacher_id, s.ts.ts_id) not in inp.ban_busy]
        return len(free_slots) < 2
    free_candidate_slots = [s for s in candidate_slots if (teacher_id, s.ts.ts_id) not in inp.ban_busy]
    return len(free_candidate_slots) < 2
```

2. Tại `core/scheduler/quality.py` (hàm `_is_teacher_busy_on_morning_quality`):
```python
def _is_teacher_busy_on_morning_quality(teacher_id: int, wd: int, slots: list[Slot], slot_teacher: dict, ban_busy: set) -> bool:
    if not ban_busy:
        return False
    morn_slots = [s for s in slots if s.ts.weekday == wd and s.ts.session == "S"]
    if not morn_slots:
        return False
    classes_for_teacher = {s.class_id for s in slots if slot_teacher.get(s.slot_id) == teacher_id}
    candidate_slots = [s for s in morn_slots if s.class_id in classes_for_teacher]
    if not candidate_slots:
        free_slots = [s for s in morn_slots if (teacher_id, s.ts.ts_id) not in ban_busy]
        return len(free_slots) < 2
    free_candidate_slots = [s for s in candidate_slots if (teacher_id, s.ts.ts_id) not in ban_busy]
    return len(free_candidate_slots) < 2
```

3. Tại `core/validation.py` (hàm `_is_teacher_busy_morning_validation`):
Đồng bộ điều kiện tương tự: nếu số ô rảnh $< 2$ thì trả về `True`.

- [ ] **Step 4: Chạy test xác nhận pass**

Chạy: `pytest tests/test_teacher_busy_morning_conflict.py`
Kỳ vọng: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/scheduler/cpsat/constraints.py core/scheduler/quality.py core/validation.py tests/test_teacher_busy_morning_conflict.py
git commit -m "fix: exempt teacher from mandatory morning when free periods in morning < 2"
```

---

### Task 4: Quyền ưu tiên cho Ghim nghỉ trọn ngày (`pinned_full_day_off`) (Hướng A)

**Files:**
- Create: `tests/test_pinned_off_override.py`
- Modify: `core/scheduler/cpsat/constraints.py:70-116`
- Modify: `core/scheduler/teacher_off.py:30-48`

**Interfaces:**
- Consumes: `teacher.pinned_full_day_off`.
- Produces: Lệnh ghim nghỉ trọn ngày của BGH được áp dụng vô điều kiện cho mọi thứ trong tuần (kể cả Thứ 2 nếu BGH đã duyệt), ghi đè toàn bộ `FORBIDDEN_OFF_CELLS` và `mandatory_morning_weekdays`.

- [ ] **Step 1: Viết failing test cho trường hợp ghim nghỉ trọn ngày vào Thứ 2 và Thứ 6**

Tạo file `tests/test_pinned_off_override.py`:
```python
from core.models import ClassRoom, SchedulingConfig, SchedulingInput, Slot, Subject, Teacher, TimeSlot
import core.scheduler.cpsat_model as cpsat


def test_pinned_full_day_off_on_friday_is_honored():
    """Kiểm tra: Khi BGH ghim nghỉ trọn ngày Thứ 6 cho GV (pinned_full_day_off=6),
    lệnh ghim này phải được tôn trọng và GV không có bất kỳ tiết nào vào Thứ 6,
    không bị FORBIDDEN_OFF_CELLS nuốt mất."""
    slots = []
    slot_id = 1
    for wd in range(2, 7):
        for s in ("S", "C"):
            for p in range(1, 4):
                ts = TimeSlot(ts_id=slot_id, weekday=wd, session=s, period=p)
                slots.append(Slot(slot_id=slot_id, class_id=1, ts=ts))
                slot_id += 1

    subjects = [Subject(subject_id=1, name="Môn 1", role_code=0)]
    need = {(1, 1): 10}
    assigned_teacher = {(1, 1): 99}
    teachers = [
        Teacher(teacher_id=99, name="GV Nghỉ T6", pinned_full_day_off=6)
    ]

    config = SchedulingConfig(
        strict_morning_weekdays=(),
        mandatory_morning_weekdays=(2, 5),
    )
    inp = SchedulingInput(
        classes=[ClassRoom(class_id=1, name="6A", sort_order=0)],
        subjects=subjects,
        teachers=teachers,
        slots=slots,
        need=need,
        assigned_teacher=assigned_teacher,
        config=config,
    )

    res = cpsat.solve(inp, time_limit_s=5.0)
    assert res.success is True
    # Kiểm tra GV 99 không có tiết nào vào Thứ 6
    eff_slots_t6 = [
        s.slot_id for s in slots if s.ts.weekday == 6 and res.assignment.get(s.slot_id) == 1
    ]
    assert len(eff_slots_t6) == 0, "GV đã được ghim nghỉ trọn ngày Thứ 6 thì không được có tiết Thứ 6"


def test_pinned_full_day_off_on_monday_is_honored():
    """Kiểm tra: BGH đã duyệt ghim nghỉ Thứ 2 cho GV (pinned_full_day_off=2),
    GV không có bất kỳ tiết nào vào Thứ 2 (kể cả sáng Thứ 2)."""
    slots = []
    slot_id = 1
    for wd in range(2, 7):
        for s in ("S", "C"):
            for p in range(1, 4):
                ts = TimeSlot(ts_id=slot_id, weekday=wd, session=s, period=p)
                slots.append(Slot(slot_id=slot_id, class_id=1, ts=ts))
                slot_id += 1

    subjects = [Subject(subject_id=1, name="Môn 1", role_code=0)]
    need = {(1, 1): 10}
    assigned_teacher = {(1, 1): 98}
    teachers = [
        Teacher(teacher_id=98, name="GV Nghỉ T2", pinned_full_day_off=2)
    ]

    config = SchedulingConfig(
        strict_morning_weekdays=(2,),
        mandatory_morning_weekdays=(2, 5, 6),
    )
    inp = SchedulingInput(
        classes=[ClassRoom(class_id=1, name="6A", sort_order=0)],
        subjects=subjects,
        teachers=teachers,
        slots=slots,
        need=need,
        assigned_teacher=assigned_teacher,
        config=config,
    )

    res = cpsat.solve(inp, time_limit_s=5.0)
    assert res.success is True
    eff_slots_t2 = [
        s.slot_id for s in slots if s.ts.weekday == 2 and res.assignment.get(s.slot_id) == 1
    ]
    assert len(eff_slots_t2) == 0, "GV đã được BGH duyệt ghim nghỉ Thứ 2 thì không được có tiết Thứ 2"
```

- [ ] **Step 2: Chạy test để xác nhận test fail**

Chạy: `pytest tests/test_pinned_off_override.py`
Kỳ vọng: FAIL vì `(6, "S")` và `(2, "S")` nằm trong `forbidden`, lệnh pin bị bỏ qua và GV vẫn bị xếp tiết.

- [ ] **Step 3: Triển khai quyền ưu tiên cho `pinned_full_day_off`**

1. Tại `core/scheduler/cpsat/constraints.py` (trong `_add_off_day_constraints`):
```python
        if teacher and teacher.pinned_full_day_off is not None:
            wd = teacher.pinned_full_day_off
            # Hướng A: BGH ghim nghỉ trọn ngày có quyền override mọi forbidden của trường kể cả Thứ 2
            pinned |= {(wd, "S"), (wd, "C")}
            pinned_weekdays.add(wd)
        if teacher and teacher.pinned_afternoon_off is not None:
            wd = teacher.pinned_afternoon_off
            if (wd, "C") not in forbidden and wd not in pinned_weekdays:
                pinned.add((wd, "C"))
                pinned_weekdays.add(wd)
```

2. Tại `core/scheduler/teacher_off.py` (trong `_assign_off_slots`):
Đồng bộ tương tự: `pinned_full_day_off` được phép ghim trọn vẹn cho `wd`.

- [ ] **Step 4: Chạy test xác nhận pass**

Chạy: `pytest tests/test_pinned_off_override.py`
Kỳ vọng: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/scheduler/cpsat/constraints.py core/scheduler/teacher_off.py tests/test_pinned_off_override.py
git commit -m "feat: allow admin pinned_full_day_off to override school forbidden off cells (except monday chao co)"
```

---

### Task 5: Đồng bộ trọng số phạt ngày chia lẻ II.8 lên 700

**Files:**
- Modify: `core/scheduler/constants.py:37-43`
- Test: `tests/test_quality.py`

**Interfaces:**
- Produces: `TEACHER_SPLIT_DAY_PENALTY = 700` đồng bộ ở cả Greedy và CP-SAT.

- [ ] **Step 1: Cập nhật hằng số trong `core/scheduler/constants.py`**

Sửa `TEACHER_SPLIT_DAY_PENALTY` từ 520 thành 700:
```python
TEACHER_SPLIT_DAY_PENALTY = 700   # điểm phạt khi tạo ngày 1 sáng + 1 chiều. Đồng bộ 700 giữa Greedy, CP-SAT Objective và Quality
```

- [ ] **Step 2: Chạy regression test cho scheduler và quality**

Chạy: `pytest tests/test_quality.py tests/test_scheduler.py`
Kỳ vọng: PASS.

- [ ] **Step 3: Commit**

```bash
git add core/scheduler/constants.py
git commit -m "refactor: sync TEACHER_SPLIT_DAY_PENALTY to 700 across greedy and cpsat"
```

---

### Task 6: Kiểm thử hồi quy toàn diện & Nghiệm thu toàn trường

**Files:**
- Run: Toàn bộ test suite trong `tests/`
- Script: Kiểm thử chạy trên cơ sở dữ liệu `schools/truong-thcs.db`

- [ ] **Step 1: Chạy toàn bộ test suite**

Chạy: `pytest tests/`
Kỳ vọng: Tất cả tests đều PASS (xanh 100%).

- [ ] **Step 2: Nghiệm thu xếp TKB thực tế trên `schools/truong-thcs.db`**

Chạy:
```bash
python -c "
from data.db import get_connection
from data.repository import build_scheduling_input
import core.scheduler.cpsat_model as cpsat
from core.validation import compute_tkb_health_score

conn = get_connection('schools/truong-thcs.db')
inp = build_scheduling_input(conn)
res = cpsat.solve(inp, time_limit_s=15.0)
print('Solve success:', res.success)
assert res.success is True
health = compute_tkb_health_score(inp, res.assignment)
print('Health Score:', health['overall_score'], 'Rating:', health['rating'])
print('Metrics:', health['metrics'])
"
```
Kỳ vọng: Xếp thành công, Health score $\ge 85$ ("Tốt" hoặc "Xuất sắc").
