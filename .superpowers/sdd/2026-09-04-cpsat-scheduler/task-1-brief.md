# Task 1: Khung mô hình CP-SAT + ràng buộc định mức

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the CP-SAT model skeleton — the `x[slot, subject]` boolean grid,
"every cell holds exactly one subject", and "each (subject, class) pair gets
exactly its required number of periods" — and prove the result passes the app's
own quota validator.

**Why (Vietnamese):** Đây là nền của mọi task sau. Hai ràng buộc trong task này
là thứ định nghĩa "một TKB hợp lệ" ở mức cơ bản nhất: mỗi ô có đúng một môn, và
mỗi cặp (môn, lớp) được đúng số tiết mà định mức yêu cầu. Nếu sai ở đây thì mọi
ràng buộc tinh vi phía sau đều vô nghĩa.

Lưu ý quan trọng về dữ liệu trường này: `need` = 236 và số ô = 236, tức **dư địa
bằng 0** — mọi ô đều bắt buộc phải có tiết. Nhưng KHÔNG được viết mô hình dựa
trên giả định đó: trường khác có thể dư ô, và chính engine cũ có cơ chế để ô
trống (gán `-1`). Vì vậy ràng buộc phải là "mỗi ô có **tối đa** 1 môn" cộng với
"đúng định mức", chứ không phải "mỗi ô có **đúng** 1 môn".

**Files:**
- Create: `core/scheduler/cpsat_model.py`
- Create: `tests/test_cpsat_model.py`
- Modify: `requirements.txt` (thêm `ortools`)

**Interfaces:**
- Produces:
  - `build_model(inp: SchedulingInput) -> CpSatModel` — dataclass chứa
    `model: cp_model.CpModel`, `x: dict[tuple[int, int], BoolVar]` khoá là
    `(slot_id, subject_id)`, và `inp` để các task sau dùng lại.
  - `solve(built: CpSatModel, time_limit_s: float = 10.0) -> dict[int, int] | None`
    — trả `{slot_id: subject_id}` cho các ô có môn (ô để trống KHÔNG xuất hiện
    trong dict), hoặc `None` nếu không giải được.
  - `CpSatUnavailable` — exception khi `ortools` không import được.

---

- [ ] **Step 1: Thêm phụ thuộc**

Sửa `requirements.txt`, thêm dòng cuối:

```
ortools>=9.10
```

Cài: `python -m pip install ortools`

- [ ] **Step 2: Viết test thất bại**

Tạo `tests/test_cpsat_model.py`:

```python
import pytest

from core.models import (
    ROLE_HDTN, ROLE_THUONG, ClassRoom, SchedulingConfig, SchedulingInput,
    Slot, Subject, Teacher, TimeSlot,
)
from core.validation import compute_quota_diff

cpsat = pytest.importorskip("core.scheduler.cpsat_model")


def _tiny_input():
    """1 lớp, 6 ô sáng Thứ 2 (tiết 1-3) và Thứ 3 (tiết 1-3), 2 môn cần 3 tiết mỗi môn.
    Vừa khít 6 ô = 6 tiết, nên mọi ô đều phải có môn."""
    ts = [TimeSlot(i + 1, wd, "S", p) for i, (wd, p) in enumerate(
        [(2, 1), (2, 2), (2, 3), (3, 1), (3, 2), (3, 3)])]
    slots = [Slot(i + 1, 101, t) for i, t in enumerate(ts)]
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]
    return SchedulingInput(
        classes=[ClassRoom(101, "6A1")],
        subjects=subjects,
        teachers=[Teacher(10, "GV A"), Teacher(20, "GV B")],
        need={(1, 101): 3, (2, 101): 3},
        assigned_teacher={(1, 101): 10, (2, 101): 20},
        ban_busy=set(), slots=slots, timeslots=ts,
        config=SchedulingConfig(),
    )


def test_solution_meets_every_subject_class_quota():
    inp = _tiny_input()
    built = cpsat.build_model(inp)
    assignment = cpsat.solve(built, time_limit_s=10.0)
    assert assignment is not None, "phải giải được bài toán vừa khít này"

    diff = compute_quota_diff(inp.slots, assignment, inp.need)
    bad = {k: v for k, v in diff.items() if v != 0}
    assert bad == {}, f"sai định mức: {bad}"


def test_each_cell_holds_at_most_one_subject():
    inp = _tiny_input()
    built = cpsat.build_model(inp)
    assignment = cpsat.solve(built, time_limit_s=10.0)
    # assignment là dict slot_id -> subject_id nên "tối đa 1" là bất biến của
    # kiểu dữ liệu; điều cần khẳng định là không ô nào bị bỏ sót ở bài vừa khít.
    assert len(assignment) == len(inp.slots)


def test_leaves_cells_empty_when_there_is_slack():
    """Dư địa > 0: chỉ cần 2 tiết cho 6 ô -> 4 ô phải để trống, không được
    nhồi cho đủ. Engine cũ để trống bằng sentinel -1; ở đây ô trống đơn giản
    là không có mặt trong dict kết quả."""
    inp = _tiny_input()
    inp.need = {(1, 101): 2}
    built = cpsat.build_model(inp)
    assignment = cpsat.solve(built, time_limit_s=10.0)
    assert assignment is not None
    assert len(assignment) == 2
    assert all(sid == 1 for sid in assignment.values())
```

- [ ] **Step 3: Chạy test để xác nhận nó thất bại**

Run: `python -m pytest tests/test_cpsat_model.py -v`
Expected: FAIL — `core.scheduler.cpsat_model` chưa tồn tại (importorskip sẽ skip;
nếu thấy SKIPPED thì đó cũng là trạng thái "chưa làm", tiếp tục Step 4).

- [ ] **Step 4: Viết `core/scheduler/cpsat_model.py`**

```python
"""Mô hình CP-SAT cho bài toán xếp TKB.

Vì sao có file này: kiến trúc tham lam + sửa cục bộ trong engine.py không giải
được các ràng buộc toàn cục (ghép cặp GV với các buổi sáng bắt buộc; ràng buộc
kích thước nhóm của luật buổi lẻ) -- mỗi lần sửa cho GV này lại phá của GV khác.
Xem .superpowers/sdd/2026-09-04-cpsat-scheduler/design.md §1.

File này CHỈ dựng và giải mô hình. Việc chọn dùng nó hay dùng engine cũ nằm ở
engine.py (Task 8).
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from core.models import SchedulingInput

try:
    from ortools.sat.python import cp_model
    _HAS_ORTOOLS = True
except ImportError:  # pragma: no cover - phụ thuộc mềm
    cp_model = None
    _HAS_ORTOOLS = False


class CpSatUnavailable(RuntimeError):
    """ortools chưa được cài. Caller phải bắt và quay về engine cũ."""


@dataclass
class CpSatModel:
    model: object                      # cp_model.CpModel
    x: dict                            # (slot_id, subject_id) -> BoolVar
    inp: SchedulingInput
    slots_by_class: dict = field(default_factory=dict)
    slots_by_ts: dict = field(default_factory=dict)
    # Các task sau điền thêm vào đây; khai báo sẵn để không phải sửa dataclass
    # nhiều lần và để người đọc thấy trước hình dạng cuối cùng:
    teacher_of: dict = field(default_factory=dict)     # Task 2: (slot_id, subject_id) -> teacher_id
    role_index: object = None                          # Task 3: kết quả resolve_roles()
    penalty_terms: dict = field(default_factory=dict)  # Task 6: mã tiêu chí -> list biến phạt


def build_model(inp: SchedulingInput) -> CpSatModel:
    if not _HAS_ORTOOLS:
        raise CpSatUnavailable("ortools chưa được cài")

    m = cp_model.CpModel()

    slots_by_class = defaultdict(list)
    slots_by_ts = defaultdict(list)
    for s in inp.slots:
        slots_by_class[s.class_id].append(s)
        slots_by_ts[s.ts.ts_id].append(s)

    # Chỉ tạo biến cho cặp (ô, môn) mà lớp của ô đó THỰC SỰ cần môn đó. Bỏ hẳn
    # các cặp vô nghĩa giúp mô hình nhỏ đi nhiều lần.
    x = {}
    for s in inp.slots:
        for subj in inp.subjects:
            if inp.need.get((subj.subject_id, s.class_id), 0) > 0:
                x[s.slot_id, subj.subject_id] = m.NewBoolVar(
                    f"x_s{s.slot_id}_m{subj.subject_id}")

    # Mỗi ô có TỐI ĐA 1 môn -- không phải "đúng 1". Trường có dư địa thì ô thừa
    # được để trống, giống cơ chế gán -1 của engine cũ.
    for s in inp.slots:
        vs = [x[s.slot_id, subj.subject_id] for subj in inp.subjects
              if (s.slot_id, subj.subject_id) in x]
        if vs:
            m.AddAtMostOne(vs)

    # Đúng định mức mỗi (môn, lớp).
    for (subject_id, class_id), n in inp.need.items():
        if n <= 0:
            continue
        vs = [x[s.slot_id, subject_id] for s in slots_by_class[class_id]
              if (s.slot_id, subject_id) in x]
        m.Add(sum(vs) == n)

    return CpSatModel(model=m, x=x, inp=inp,
                      slots_by_class=dict(slots_by_class),
                      slots_by_ts=dict(slots_by_ts))


def solve(built: CpSatModel, time_limit_s: float = 10.0,
          workers: int = 8) -> Optional[dict]:
    """Trả {slot_id: subject_id} cho các ô CÓ môn, hoặc None nếu không giải được.
    Ô để trống không xuất hiện trong dict."""
    if not _HAS_ORTOOLS:
        raise CpSatUnavailable("ortools chưa được cài")

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(time_limit_s)
    solver.parameters.num_search_workers = int(workers)
    status = solver.Solve(built.model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    assignment = {}
    for (slot_id, subject_id), var in built.x.items():
        if solver.Value(var):
            assignment[slot_id] = subject_id
    return assignment
```

- [ ] **Step 5: Chạy test để xác nhận pass**

Run: `python -m pytest tests/test_cpsat_model.py -v`
Expected: 3 PASSED

- [ ] **Step 6: Xác nhận không phá gì của engine cũ**

Run: `python -m pytest tests/ -q`
Expected: 244 passed, 1 xpassed (đúng như trước task này). File mới chưa được
engine.py gọi tới nên con số phải không đổi.

- [ ] **Step 7: Commit**

```bash
git add requirements.txt core/scheduler/cpsat_model.py tests/test_cpsat_model.py
git commit -m "feat(cpsat): model skeleton with cell and quota constraints"
```
