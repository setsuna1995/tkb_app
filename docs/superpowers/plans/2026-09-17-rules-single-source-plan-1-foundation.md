# Hợp nhất nguồn sự thật bộ luật — Plan 1: Nền tảng đo lường (GĐ 1–4)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dựng một nguồn sự thật duy nhất cho bộ luật HĐSP ở tầng hậu kiểm (`ScheduleView`, `EffectiveParams`, detectors, `classify`), nối nó vào solver, giao diện và bảng sức khỏe, rồi dựng test tương đương giữa mô hình CP-SAT và hậu kiểm, trong đó các bất đồng đã biết được ghi lại bằng `xfail`.

**Architecture:** Package mới `core/rules/` gồm registry luật, `ScheduleView` (một cách nhìn lịch đã chuẩn hóa), `EffectiveParams` (mọi ngưỡng tính một lần, mang cả `declared` lẫn `effective`), detectors `detect_*(view, params) -> list[Violation]` đếm theo config, và `classify` gắn mức BREACH/FORCED/SHORTFALL. Toàn bộ `find_*` trong `core/validation.py` bị xóa, không để lại lớp bọc. `build_model` resolve params một lần; `build_result` mang theo `effective_params` và `rule_counts`. `tests/test_rule_equivalence.py` là trụ cột kiểm chứng.

**Tech Stack:** Python 3.13, Google OR-Tools CP-SAT, Streamlit, pytest + pytest-xdist.

**Spec:** `docs/superpowers/specs/2026-09-17-rules-single-source-and-validation-design.md`

## Phạm vi — plan này là 1 trong 3

Spec có 9 giai đoạn, và GĐ 5 viết lại cơ chế nới lỏng của solver. Code của GĐ 5 phụ thuộc vào hình dạng thực của `EffectiveParams`/`classify` sau khi GĐ 1–4 hoàn tất, nên viết sẵn toàn bộ code của nó ngay bây giờ là đoán mò. Vì vậy chia thành:

| Plan | Giai đoạn spec | Nội dung | Viết khi |
|---|---|---|---|
| **1 (tài liệu này)** | GĐ 1, 2, 3, 4 | View, params, detectors, classify, rule_counts, test tương đương | Bây giờ |
| 2 | GĐ 5, 6 | A7 nới lỏng hai trục (`cap_var`/`exempt_u`, `Relaxation`), A1–A6 | Sau khi Plan 1 merge |
| 3 | GĐ 7, 8, 9 | Nhóm B (buổi nghỉ), Nhóm C (V1–V4, V9), Nhóm D (dọn `quality.py`, gộp helper) | Sau khi Plan 2 merge |

## Quyết định khi lập kế hoạch (lệch so với chữ của spec, giữ nguyên ý)

| # | Quyết định | Lý do |
|---|---|---|
| D1 | Thứ tự trong GĐ 1–3: tạo `Violation` + `EffectiveParams` **trước** khi chuyển detector | Spec GĐ 1 chuyển detector "chưa đổi chữ ký params", GĐ 2 thêm params, GĐ 3 thêm `Violation` → ~70 điểm gọi phải sửa 3 lần. Làm một lần với chữ ký cuối. |
| D2 | Mã luật mới dạng mô tả: `T.CONFLICT`, `T.BUSY`, `T.DAY_CAP`, `C.GDTC_PERIOD`, `C.NON_CONSEC_DAYS`, `C.MORNING_ONLY`, `C.HEAVY_CONSEC`, `C.HEAVY_P3`, `C.SUBJECT_CELLS`, `C.SINGLE_PAIR`, `ACAD.MAX`, `ACAD.MIN`. Sáu mã cũ (`II.3`…`II.14`) giữ nguyên | Code hiện có ghi số HĐSP không nhất quán (II.13 vừa là "nặng/buổi" vừa là "nặng liên tiếp"). Mã mô tả không đoán sai số. |
| D3 | `Violation` thêm `subject_id` và `count`; `ScheduleView` thêm `teacher_classes`, `ban_busy`, `allowed_cells`, `roles`, `academic_ids`, bản đồ tên; bỏ `need/classes/subjects/teachers` | Detector cần đúng các trường này; không cần các trường bị bỏ. |
| D4 | `EffectiveParams` chỉ gồm trường có người đọc trong Plan 1. `max_heavy_per_session`, `academic_floor_cells`, `max_teacher_gaps_per_session` thêm ở plan dùng chúng | YAGNI. |
| D5 | `Relaxation`, `ScheduleResult.relaxations`, `RuleSpec.breach_priority` **hoãn sang Plan 2**. `classify(violations, params)` chưa nhận `relaxations` | `relaxed_rules` cũ không có phạm vi, nên bản shim dựng từ nó không thể hạ vi phạm nào xuống FORCED mà vẫn giữ bất biến "FORCED ⊆ phạm vi đã nới" (§4.6). Shim chỉ là code chết. |
| D6 | `classify` đổi luật tier `SOFT` → `SHORTFALL` | Spec định nghĩa SHORTFALL nhưng không nói ai gắn; detector luôn trả BREACH. |
| D7 | `blocks_save=True` chỉ cho II.3/II.4/II.8 trong Plan 1 (đúng hành vi hiện tại). `C.HEAVY_CONSEC`/`ACAD.MAX` chuyển sang chặn lưu ở Plan 2 | Trước GĐ 5 chưa có `reason` nào, V1 sẽ thành BREACH chặn lưu oan với trường bật `heavy_subjects_morning_only`. |
| D8 | Test tương đương tách thành 3 hàm (A/B/C) thay vì 3 assert trong 1 hàm | Để `xfail` được từng cặp (phép kiểm, fixture, luật) — GĐ 4 dự kiến có đỏ. |
| D9 | Hậu kiểm tôn trọng cờ bật/tắt của luật qua `RuleSpec.config_flag` ở một chỗ (`detect_rule`) | Sửa luôn V9 cho bảng sức khỏe, vì bảng sức khỏe giờ đi qua cùng đường. |
| D10 | Trang Xếp TKB chạy **mọi** detector (trước đây luồng lô chỉ kiểm trùng lịch + II.3/II.4/II.8/II.14; `ACAD.MAX` chưa hiện ở trang). Vi phạm `HARD_MODEL` hiện lỗi đỏ nhưng không chặn lưu — đúng như cách trang hiện đối xử với trần môn Nặng | Một đường duy nhất. Hệ quả chấp nhận được: `ACAD.MAX` có thể báo đỏ giả ở lớp có trần thích ứng cho tới Plan 2, giống V1. |
| D11 | `compute_tkb_health_score(inp, assignment)` giữ chữ ký, tự `resolve_effective_params(inp)` thay vì đọc `result.effective_params` | Detector chỉ đọc `.declared`, và `declared` luôn bằng config, nên hai cách cho cùng kết quả; giữ chữ ký tránh sửa thêm caller. |

## Global Constraints

- Vi phạm **luôn** đếm theo config: detector chỉ đọc `Threshold.declared`. `.effective` chỉ được đọc trong `core/scheduler/cpsat/constraints.py`, `objectives.py`, `core/rules/violations.py:classify` và `params.as_effective()` gọi từ test.
- Mọi vi phạm mức `FORCED` phải có `evidence` không rỗng. Không chứng minh được thì là `BREACH`.
- Detector không nhận `relaxations` hay bất kỳ thông tin nới lỏng nào.
- Không tạo lớp bọc tương thích ngược — xóa hàm cũ, sửa thẳng điểm gọi (spec §5.4.5).
- Không sửa giá trị kỳ vọng của test để làm nó xanh. Đổi chữ ký gọi là thay đổi cơ học; nếu một kết quả kỳ vọng đổi, phải giải thích được vì sao trước khi cập nhật (spec §6.3).
- Tên biến/hàm/comment code: tiếng Anh. Chuỗi hiển thị cho người dùng (`title_vi`, `detail`, `evidence`): tiếng Việt.
- Không magic number — dùng hằng có tên.
- Commit message tiếng Anh, dạng `type: imperative`; **không** thêm `Co-Authored-By` hay "Generated with Claude Code".
- GitNexus (CLAUDE.md dự án): trước khi sửa một hàm/lớp **đã có**, chạy MCP `impact({target: "<symbol>", direction: "upstream"})` và báo rủi ro; nếu HIGH/CRITICAL thì dừng hỏi người dùng. Trước mỗi commit chạy MCP `detect_changes({scope: "all"})`. Repo chưa có `.gitnexus/run.cjs`; nếu MCP không khả dụng, ghi rõ điều đó trong báo cáo task và dùng `grep -rn "<symbol>"` thay thế.
- Chạy test bằng `python -m pytest`. Vòng lặp nhanh: `-m "not slow"`. Cuối mỗi task chạy thêm các file test được liệt kê trong task.

---

### Task 0: Chuẩn bị nhánh làm việc (human gate)

**Files:** không sửa file nào.

- [ ] **Step 1: Kiểm tra cây làm việc**

Run: `git status --short`
Expected: có thể thấy `M pages/06_Xep_TKB.py`, `M ui_common.py`, `M ui_theme.py` — đây là việc dở dang của người dùng, **không thuộc plan này**.

- [ ] **Step 2: Hỏi người dùng (dừng tại đây)**

Hỏi: "Có 3 file đang sửa dở (`pages/06_Xep_TKB.py`, `ui_common.py`, `ui_theme.py`). Task 9 của plan sửa `pages/06_Xep_TKB.py`. Bạn muốn commit chúng trước, stash, hay để tôi làm trong worktree riêng?" Không tự commit/stash.

- [ ] **Step 3: Tạo nhánh**

Run: `git switch -c feat/rules-single-source`

- [ ] **Step 4: Ghi mốc thời gian suite hiện tại**

Run: `python -m pytest -q -m "not slow"` rồi `python -m pytest -q -m slow`
Expected: cả hai PASS. Ghi lại thời gian chạy vào báo cáo task — Task 11 thêm ~5 phút test chậm, cần mốc để so.

---

### Task 1: Chuyển registry luật vào package `core/rules`

**Files:**
- Move: `core/rules_registry.py` → `core/rules/__init__.py`
- Modify: `core/scheduler/cpsat/solver.py:11`
- Modify: `pages/06_Xep_TKB.py:15`
- Modify: `tests/test_rules_registry.py:1`
- Modify: `tests/test_cpsat_model.py:996`

**Interfaces:**
- Produces: `from core.rules import RULES, HARD_POST_GENERATION_IDS, RuleSpec, RuleTier` — mọi task sau import từ đây.

- [ ] **Step 1: Đổi import trong test trước**

`tests/test_rules_registry.py` dòng 1:
```python
from core.rules import RULES, HARD_POST_GENERATION_IDS, RuleTier
```

- [ ] **Step 2: Chạy test để thấy nó đỏ**

Run: `python -m pytest tests/test_rules_registry.py -q -n 0`
Expected: FAIL với `ModuleNotFoundError: No module named 'core.rules'`

- [ ] **Step 3: Di chuyển file**

```bash
mkdir core/rules
git mv core/rules_registry.py core/rules/__init__.py
```

- [ ] **Step 4: Sửa ba điểm import còn lại**

`core/scheduler/cpsat/solver.py` dòng 11:
```python
from core.rules import HARD_POST_GENERATION_IDS
```
`pages/06_Xep_TKB.py` dòng 15:
```python
from core.rules import RULES
```
`tests/test_cpsat_model.py` dòng 996 (giữ thụt lề 4 dấu cách):
```python
    from core.rules import HARD_POST_GENERATION_IDS
```

- [ ] **Step 5: Xác nhận không còn tham chiếu cũ**

Run: `grep -rn "rules_registry" --include=*.py .`
Expected: không có kết quả.

- [ ] **Step 6: Chạy test**

Run: `python -m pytest tests/test_rules_registry.py tests/test_cpsat_model.py -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add core/rules/__init__.py core/scheduler/cpsat/solver.py pages/06_Xep_TKB.py tests/test_rules_registry.py tests/test_cpsat_model.py
git commit -m "refactor: move rule registry into core.rules package"
```

Lưu ý: `pages/06_Xep_TKB.py` có thay đổi dở dang của người dùng (Task 0). Nếu người dùng chưa commit chúng, dùng `git add -p pages/06_Xep_TKB.py` và chỉ chọn hunk dòng 15.

---

### Task 2: `Violation` và `ScheduleView`

**Files:**
- Create: `core/rules/violations.py`
- Create: `core/rules/view.py`
- Create: `tests/rule_helpers.py`
- Test: `tests/test_rule_view.py`

**Interfaces:**
- Consumes: `core.scheduler.placement._build_effective_assigned_teacher(inp) -> dict`, `core.roles.resolve_roles(subjects, extra_kep_ids, hdtn_thematic_week, single_pair_subject_ids) -> RoleIndex`, `core.roles.is_academic_subject(name) -> bool`.
- Produces:
  - `core.rules.violations`: hằng `BREACH`, `FORCED`, `SHORTFALL`; `@dataclass(frozen=True) Violation(rule_id, level="BREACH", teacher_id=None, class_id=None, subject_id=None, weekday=None, session=None, period=None, count=None, detail="", evidence="")`; `group_by_rule(violations) -> dict[str, list[Violation]]` (giữ thứ tự xuất hiện).
  - `core.rules.view`: `ScheduleView` với `.placed() -> Iterator[(Slot, subject_id, teacher_id | None)]`, `.class_name(id)`, `.subject_name(id)`, `.teacher_name(id)`; `build_schedule_view(inp, assignment) -> ScheduleView`.
  - `tests/rule_helpers.py`: `HDTN_SUBJECT_ID = 9999`; `make_input(slots, *, assigned_teacher=None, subjects=None, used_subject_ids=(), config=None, ban_busy=None, need=None, allowed_cells=None, teachers=None) -> SchedulingInput`.

- [ ] **Step 1: Viết helper dựng input cho test**

`tests/rule_helpers.py`:
```python
"""Builders for rule unit tests: a minimal SchedulingInput around hand-placed slots."""
from core.models import ROLE_HDTN, ClassRoom, SchedulingConfig, SchedulingInput, Subject, Teacher

HDTN_SUBJECT_ID = 9999  # resolve_roles() refuses a subject list without HĐTN


def make_input(slots, *, assigned_teacher=None, subjects=None, used_subject_ids=(), config=None,
               ban_busy=None, need=None, allowed_cells=None, teachers=None) -> SchedulingInput:
    assigned_teacher = dict(assigned_teacher or {})
    need = dict(need or {})
    subjects = list(subjects or [])
    known_ids = {s.subject_id for s in subjects}
    wanted_ids = set(used_subject_ids) | {sid for sid, _cid in assigned_teacher} | {sid for sid, _cid in need}
    subjects += [Subject(sid, f"Môn {sid}") for sid in sorted(wanted_ids - known_ids)]
    if not any(s.role_code == ROLE_HDTN for s in subjects):
        subjects.append(Subject(HDTN_SUBJECT_ID, "HĐTN", ROLE_HDTN))
    real_teacher_ids = sorted({tid for tid in assigned_teacher.values() if tid > 0})
    return SchedulingInput(
        classes=[ClassRoom(cid, f"Lớp {cid}") for cid in sorted({s.class_id for s in slots})],
        subjects=subjects,
        teachers=teachers if teachers is not None else [Teacher(tid, f"GV {tid}") for tid in real_teacher_ids],
        need=need,
        assigned_teacher=assigned_teacher,
        ban_busy=set(ban_busy or ()),
        slots=list(slots),
        timeslots=sorted({s.ts for s in slots}, key=lambda ts: ts.order_key),
        config=config or SchedulingConfig(),
        subject_class_allowed_cells=dict(allowed_cells or {}),
    )
```

- [ ] **Step 2: Viết test cho view**

`tests/test_rule_view.py`:
```python
from core.models import Slot, TimeSlot
from core.rules.view import build_schedule_view
from tests.rule_helpers import make_input


def _two_morning_slots():
    return [Slot(1, 101, TimeSlot(1, 2, "S", 1)), Slot(2, 101, TimeSlot(2, 2, "S", 2))]


def test_empty_sentinel_and_missing_cells_become_none():
    inp = make_input(_two_morning_slots(), assigned_teacher={(7, 101): 10})
    view = build_schedule_view(inp, {1: -1})
    assert view.assignment == {1: None, 2: None}
    assert view.slot_teacher == {1: None, 2: None}
    assert list(view.placed()) == []


def test_unassigned_subject_never_yields_a_teacher():
    """PhanCong bỏ trống -> id GV tổng hợp âm. View quy về None một lần,
    thay vì mỗi detector tự lọc bằng < 0, <= 0 hay > 0."""
    inp = make_input(_two_morning_slots(), need={(7, 101): 2})
    view = build_schedule_view(inp, {1: 7, 2: 7})
    assert [(slot.slot_id, subject_id, teacher_id) for slot, subject_id, teacher_id in view.placed()] == [
        (1, 7, None), (2, 7, None),
    ]


def test_teacher_and_teacher_classes_come_from_effective_map():
    inp = make_input(_two_morning_slots(), assigned_teacher={(7, 101): 10})
    view = build_schedule_view(inp, {1: 7})
    assert view.slot_teacher == {1: 10, 2: None}
    assert view.teacher_classes == {10: frozenset({101})}
    assert view.teacher_name(10) == "GV 10"
    assert view.class_name(404) == "Lớp #404"
```

- [ ] **Step 3: Chạy test để thấy nó đỏ**

Run: `python -m pytest tests/test_rule_view.py -q -n 0`
Expected: FAIL với `ModuleNotFoundError: No module named 'core.rules.view'`

- [ ] **Step 4: Viết `core/rules/violations.py`**

```python
"""What a rule violation is, independent of how it was found."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal, Optional

BREACH = "BREACH"        # hard rule broken with no proof it was unavoidable -- blocks save when the rule says so
FORCED = "FORCED"        # hard rule broken, and the model proved it could not do better -- carries evidence
SHORTFALL = "SHORTFALL"  # soft criterion not met -- never blocks save

Level = Literal["BREACH", "FORCED", "SHORTFALL"]


@dataclass(frozen=True)
class Violation:
    rule_id: str
    level: Level = BREACH
    teacher_id: Optional[int] = None
    class_id: Optional[int] = None
    subject_id: Optional[int] = None
    weekday: Optional[int] = None
    session: Optional[str] = None
    period: Optional[int] = None
    count: Optional[int] = None   # size of the violation when it has one (run length, periods taught...)
    detail: str = ""              # Vietnamese, shown to the user as-is
    evidence: str = ""            # required when level == FORCED: why it could not be fewer


def group_by_rule(violations: Iterable[Violation]) -> dict:
    groups: dict = {}
    for violation in violations:
        groups.setdefault(violation.rule_id, []).append(violation)
    return groups
```

- [ ] **Step 5: Viết `core/rules/view.py`**

```python
"""One normalised reading of a finished schedule, shared by every detector.

Before 2026-09-17 each find_* function filtered teacher ids its own way
(< 0, <= 0, > 0), only quality.py dropped the -1 empty-cell sentinel, and
each picked the raw or the effective teacher map on its own.
build_schedule_view is now the only place those conventions are applied.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterator, Optional

from core.models import RoleIndex, SchedulingInput, Slot
from core.roles import is_academic_subject, resolve_roles
from core.scheduler.placement import _build_effective_assigned_teacher

EMPTY_CELL_SENTINEL = -1


@dataclass(frozen=True)
class ScheduleView:
    slots: list
    assignment: dict       # slot_id -> subject_id, or None for an empty cell
    slot_teacher: dict     # slot_id -> real teacher_id, or None (empty cell / unassigned subject)
    teacher_classes: dict  # teacher_id -> frozenset of class_ids the teacher is assigned to
    ban_busy: frozenset    # {(teacher_id, ts_id)}
    allowed_cells: dict    # (subject_id, class_id) -> frozenset((weekday, session)) | None
    roles: RoleIndex
    academic_ids: frozenset
    class_names: dict
    subject_names: dict
    teacher_names: dict

    def placed(self) -> Iterator[tuple[Slot, int, Optional[int]]]:
        """(slot, subject_id, teacher_id) for every non-empty cell."""
        for slot in self.slots:
            subject_id = self.assignment[slot.slot_id]
            if subject_id is not None:
                yield slot, subject_id, self.slot_teacher[slot.slot_id]

    def class_name(self, class_id: int) -> str:
        return self.class_names.get(class_id, f"Lớp #{class_id}")

    def subject_name(self, subject_id: int) -> str:
        return self.subject_names.get(subject_id, f"Môn #{subject_id}")

    def teacher_name(self, teacher_id: int) -> str:
        return self.teacher_names.get(teacher_id, f"GV #{teacher_id}")


def build_schedule_view(inp: SchedulingInput, assignment: dict) -> ScheduleView:
    effective_teacher = _build_effective_assigned_teacher(inp)
    cells, slot_teacher = {}, {}
    for slot in inp.slots:
        subject_id = assignment.get(slot.slot_id)
        if subject_id == EMPTY_CELL_SENTINEL:
            subject_id = None
        teacher_id = effective_teacher.get((subject_id, slot.class_id))
        cells[slot.slot_id] = subject_id
        slot_teacher[slot.slot_id] = teacher_id if teacher_id is not None and teacher_id > 0 else None

    teacher_classes = defaultdict(set)
    for (_subject_id, class_id), teacher_id in effective_teacher.items():
        if teacher_id is not None and teacher_id > 0:
            teacher_classes[teacher_id].add(class_id)

    config = inp.config
    return ScheduleView(
        slots=list(inp.slots),
        assignment=cells,
        slot_teacher=slot_teacher,
        teacher_classes={tid: frozenset(cids) for tid, cids in teacher_classes.items()},
        ban_busy=frozenset(inp.ban_busy or ()),
        allowed_cells=dict(inp.subject_class_allowed_cells or {}),
        roles=resolve_roles(inp.subjects, inp.extra_kep_ids, inp.hdtn_thematic_week,
                            config.single_pair_subject_ids),
        academic_ids=frozenset(s.subject_id for s in inp.subjects if is_academic_subject(s.name)),
        class_names={c.class_id: c.name for c in inp.classes},
        subject_names={s.subject_id: s.name for s in inp.subjects},
        teacher_names={t.teacher_id: t.name for t in inp.teachers},
    )
```

- [ ] **Step 6: Chạy test**

Run: `python -m pytest tests/test_rule_view.py -q -n 0`
Expected: PASS (3 tests)

- [ ] **Step 7: Commit**

```bash
git add core/rules/violations.py core/rules/view.py tests/rule_helpers.py tests/test_rule_view.py
git commit -m "feat: add Violation and normalised ScheduleView for rule detectors"
```

---

### Task 3: `Threshold` và `EffectiveParams`

**Files:**
- Create: `core/rules/params.py`
- Modify: `tests/rule_helpers.py` (thêm `view_and_params`, `pick`)
- Test: `tests/test_rule_params.py`

**Interfaces:**
- Consumes: `make_input` (Task 2), `build_schedule_view` (Task 2).
- Produces:
  - `Threshold(declared: int, effective: int, reason: str = "")` — ném `ValueError` khi `effective != declared` mà `reason` rỗng; `Threshold.unrelaxed(value) -> Threshold`.
  - `EffectiveParams` (frozen) với các trường: `min_weekly_periods_for_lone_penalty: int`, `min_weekly_periods_for_mandatory_morning: int`, `max_load_for_4consec_penalty: int`, `lone_exempt_ids: frozenset`, `bgh_ids: frozenset`, `pinned_day_offs: dict[int,int]`, `teacher_load: dict[int,int]`, `max_heavy_consecutive: dict[(class_id, session), Threshold]`, `max_academic_per_morning: dict[class_id, Threshold]`, `max_teacher_periods_per_day: int`, `max_periods_per_session: int`, `min_academic_per_morning: int`, `mandatory_morning_weekdays: tuple`, `strict_morning_weekdays: tuple`, `gdtc_morning_allowed_periods: tuple`, `gdtc_afternoon_allowed_periods: tuple`, `morning_only_subject_ids: frozenset`, `non_consecutive_subject_ids: frozenset`, `flags: dict[str,bool]`; method `as_effective() -> EffectiveParams`.
  - `resolve_effective_params(inp) -> EffectiveParams`; hằng `MAX_LOAD_FOR_4CONSEC_PENALTY = 20`; `RULE_FLAG_NAMES: tuple[str, ...]`.
  - `tests/rule_helpers.py`: `view_and_params(slots, assignment, **make_input_kwargs) -> (ScheduleView, EffectiveParams)`; `pick(violations, *field_names) -> list[tuple]`.

- [ ] **Step 1: Viết test**

`tests/test_rule_params.py`:
```python
from dataclasses import replace

import pytest

from core.models import ROLE_GDTC, ROLE_NANG, SchedulingConfig, Slot, Subject, Teacher, TimeSlot
from core.rules.params import MAX_LOAD_FOR_4CONSEC_PENALTY, Threshold, resolve_effective_params
from tests.rule_helpers import make_input


def _slots():
    return [
        Slot(1, 101, TimeSlot(1, 2, "S", 1)),
        Slot(2, 101, TimeSlot(2, 2, "C", 1)),
        Slot(3, 102, TimeSlot(3, 2, "S", 1)),
    ]


def test_threshold_refuses_silent_relaxation():
    with pytest.raises(ValueError):
        Threshold(declared=3, effective=4)
    assert Threshold(declared=3, effective=4, reason="lớp 9A cần 4 tiết/buổi").effective == 4


def test_no_threshold_is_relaxed_before_solving():
    params = resolve_effective_params(make_input(_slots()))
    assert set(params.max_heavy_consecutive) == {(101, "S"), (101, "C"), (102, "S")}
    assert set(params.max_academic_per_morning) == {101, 102}
    thresholds = [*params.max_heavy_consecutive.values(), *params.max_academic_per_morning.values()]
    assert all(t.effective == t.declared and t.reason == "" for t in thresholds)


def test_values_come_from_config_not_scattered_defaults():
    config = SchedulingConfig(min_weekly_periods_for_lone_penalty=11, max_heavy_consecutive=2,
                              lone_session_exempt_teacher_ids=frozenset({10}))
    params = resolve_effective_params(make_input(_slots(), config=config))
    assert params.min_weekly_periods_for_lone_penalty == 11
    assert params.max_heavy_consecutive[(101, "S")].declared == 2
    assert params.lone_exempt_ids == frozenset({10})
    assert params.max_load_for_4consec_penalty == MAX_LOAD_FOR_4CONSEC_PENALTY


def test_teacher_facts_are_resolved_once():
    teachers = [Teacher(10, "Hiệu trưởng A", role="Hiệu trưởng", pinned_full_day_off=4), Teacher(20, "GV B")]
    inp = make_input(
        _slots(), teachers=teachers,
        assigned_teacher={(1, 101): 10, (2, 101): 20},
        need={(1, 101): 3, (2, 101): 0, (3, 102): 2},
    )
    params = resolve_effective_params(inp)
    assert params.bgh_ids == frozenset({10})
    assert params.pinned_day_offs == {10: 4}
    # need = 0 không tính tải; môn 3 chưa phân công -> id tổng hợp âm, không phải GV thật
    assert params.teacher_load == {10: 3}


def test_role_driven_subject_sets_follow_their_flags():
    subjects = [Subject(1, "Lý", ROLE_NANG), Subject(2, "Thể dục", ROLE_GDTC)]
    on = SchedulingConfig(heavy_subjects_morning_only=True, morning_only_subject_ids=frozenset({5}),
                          avoid_gdtc_consecutive_days=True)
    off = SchedulingConfig(heavy_subjects_morning_only=False, avoid_gdtc_consecutive_days=False)
    params_on = resolve_effective_params(make_input(_slots(), subjects=subjects, config=on))
    params_off = resolve_effective_params(make_input(_slots(), subjects=subjects, config=off))
    assert params_on.morning_only_subject_ids == frozenset({1, 5})
    assert params_on.non_consecutive_subject_ids == frozenset({2})
    assert params_off.morning_only_subject_ids == frozenset()
    assert params_off.non_consecutive_subject_ids == frozenset()


def test_as_effective_counts_against_what_the_model_enforced():
    params = resolve_effective_params(make_input(_slots()))
    widened = replace(params, max_heavy_consecutive={
        (101, "S"): Threshold(declared=3, effective=4, reason="lý do"),
    })
    assert widened.as_effective().max_heavy_consecutive[(101, "S")] == Threshold.unrelaxed(4)
    assert widened.max_heavy_consecutive[(101, "S")].declared == 3
```

- [ ] **Step 2: Chạy test để thấy nó đỏ**

Run: `python -m pytest tests/test_rule_params.py -q -n 0`
Expected: FAIL với `ModuleNotFoundError: No module named 'core.rules.params'`

- [ ] **Step 3: Viết `core/rules/params.py`**

```python
"""Every rule threshold the model enforces and the detectors count against,
resolved once per SchedulingInput.

Before 2026-09-17 each layer read config with scattered getattr calls and its
own defaults (the lone-session threshold defaulted to 15, 0 and 8 in three
places). Counting a violation always uses Threshold.declared -- the value the
school configured. Threshold.effective is what the model actually enforced and
is only used to decide whether a violation was forced (core/rules/violations.py).
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace

from core.models import RoleIndex, SchedulingConfig, SchedulingInput, is_bgh
from core.roles import resolve_roles
from core.scheduler.placement import _build_effective_assigned_teacher

MAX_LOAD_FOR_4CONSEC_PENALTY = 20
# II.14 exempts teachers above 20 periods/week. Hardcoded in objectives.py before 2026-09-17.

RULE_FLAG_NAMES = (
    "avoid_teacher_lone_periods",
    "avoid_teacher_gaps",
    "avoid_teacher_4_consecutive_morning",
    "avoid_heavy_afternoon_period3",
    "avoid_gdtc_consecutive_days",
    "balance_morning_academic_load",
    "balance_afternoon_teachers",
    "heavy_subjects_morning_only",
)


@dataclass(frozen=True)
class Threshold:
    declared: int      # from config -- the standard violations are COUNTED against
    effective: int     # what the model actually enforced -- only used to CLASSIFY
    reason: str = ""   # required whenever effective != declared

    def __post_init__(self):
        if self.effective != self.declared and not self.reason:
            raise ValueError("chênh lệch ngưỡng phải có lý do")

    @classmethod
    def unrelaxed(cls, value: int) -> "Threshold":
        return cls(declared=value, effective=value)


@dataclass(frozen=True)
class EffectiveParams:
    min_weekly_periods_for_lone_penalty: int
    min_weekly_periods_for_mandatory_morning: int
    max_load_for_4consec_penalty: int
    lone_exempt_ids: frozenset
    bgh_ids: frozenset
    pinned_day_offs: dict              # teacher_id -> weekday approved as a full day off
    teacher_load: dict                 # teacher_id -> periods/week, real teachers only
    max_heavy_consecutive: dict        # (class_id, session) -> Threshold
    max_academic_per_morning: dict     # class_id -> Threshold
    max_teacher_periods_per_day: int
    max_periods_per_session: int
    min_academic_per_morning: int
    mandatory_morning_weekdays: tuple
    strict_morning_weekdays: tuple
    gdtc_morning_allowed_periods: tuple
    gdtc_afternoon_allowed_periods: tuple
    morning_only_subject_ids: frozenset     # includes heavy subjects when heavy_subjects_morning_only
    non_consecutive_subject_ids: frozenset  # includes GDTC when avoid_gdtc_consecutive_days
    flags: dict                             # name in RULE_FLAG_NAMES -> bool

    def as_effective(self) -> "EffectiveParams":
        """Copy whose declared thresholds are what the model enforced.
        Test-only: production code always counts against config."""
        return replace(
            self,
            max_heavy_consecutive=_at_effective(self.max_heavy_consecutive),
            max_academic_per_morning=_at_effective(self.max_academic_per_morning),
        )


def _at_effective(thresholds: dict) -> dict:
    return {key: Threshold.unrelaxed(threshold.effective) for key, threshold in thresholds.items()}


def resolve_effective_params(inp: SchedulingInput) -> EffectiveParams:
    config = inp.config
    roles = resolve_roles(inp.subjects, inp.extra_kep_ids, inp.hdtn_thematic_week,
                          config.single_pair_subject_ids)
    flags = {name: bool(getattr(config, name)) for name in RULE_FLAG_NAMES}
    return EffectiveParams(
        min_weekly_periods_for_lone_penalty=config.min_weekly_periods_for_lone_penalty,
        min_weekly_periods_for_mandatory_morning=config.min_weekly_periods_for_mandatory_morning,
        max_load_for_4consec_penalty=MAX_LOAD_FOR_4CONSEC_PENALTY,
        lone_exempt_ids=frozenset(config.lone_session_exempt_teacher_ids or ()),
        bgh_ids=frozenset(t.teacher_id for t in inp.teachers if is_bgh(t)),
        pinned_day_offs={t.teacher_id: t.pinned_full_day_off for t in inp.teachers
                         if t.pinned_full_day_off is not None},
        teacher_load=_teacher_load(inp),
        max_heavy_consecutive={key: Threshold.unrelaxed(config.max_heavy_consecutive)
                               for key in {(s.class_id, s.ts.session) for s in inp.slots}},
        max_academic_per_morning={class_id: Threshold.unrelaxed(config.max_academic_per_morning)
                                  for class_id in {s.class_id for s in inp.slots}},
        max_teacher_periods_per_day=config.max_teacher_periods_per_day,
        max_periods_per_session=config.max_periods_per_session,
        min_academic_per_morning=config.min_academic_per_morning,
        mandatory_morning_weekdays=tuple(config.mandatory_morning_weekdays or ()),
        strict_morning_weekdays=tuple(config.strict_morning_weekdays or ()),
        gdtc_morning_allowed_periods=tuple(config.gdtc_morning_allowed_periods or ()),
        gdtc_afternoon_allowed_periods=tuple(config.gdtc_afternoon_allowed_periods or ()),
        morning_only_subject_ids=_morning_only_ids(config, roles, flags),
        non_consecutive_subject_ids=_non_consecutive_ids(config, roles, flags),
        flags=flags,
    )


def _teacher_load(inp: SchedulingInput) -> dict:
    effective_teacher = _build_effective_assigned_teacher(inp)
    load = defaultdict(int)
    for key, periods in inp.need.items():
        teacher_id = effective_teacher.get(key)
        if periods > 0 and teacher_id is not None and teacher_id > 0:
            load[teacher_id] += periods
    return dict(load)


def _morning_only_ids(config: SchedulingConfig, roles: RoleIndex, flags: dict) -> frozenset:
    ids = set(config.morning_only_subject_ids or ())
    if flags["heavy_subjects_morning_only"]:
        ids |= roles.heavy_ids
    return frozenset(ids)


def _non_consecutive_ids(config: SchedulingConfig, roles: RoleIndex, flags: dict) -> frozenset:
    ids = set(config.non_consecutive_subject_ids or ())
    if flags["avoid_gdtc_consecutive_days"] and roles.gdtc_id is not None:
        ids.add(roles.gdtc_id)
    return frozenset(ids)
```

- [ ] **Step 4: Thêm helper vào `tests/rule_helpers.py`**

Thêm hai dòng import vào đầu file, ngay dưới dòng `from core.models import ...`:
```python
from core.rules.params import resolve_effective_params
from core.rules.view import build_schedule_view
```
Thêm vào cuối file:
```python
def view_and_params(slots, assignment, **input_kwargs):
    used = {sid for sid in assignment.values() if sid not in (None, -1)}
    inp = make_input(slots, used_subject_ids=used, **input_kwargs)
    return build_schedule_view(inp, assignment), resolve_effective_params(inp)


def pick(violations, *field_names):
    return [tuple(getattr(v, name) for name in field_names) for v in violations]
```

- [ ] **Step 5: Chạy test**

Run: `python -m pytest tests/test_rule_params.py tests/test_rule_view.py -q -n 0`
Expected: PASS (9 tests)

- [ ] **Step 6: Commit**

```bash
git add core/rules/params.py tests/rule_helpers.py tests/test_rule_params.py
git commit -m "feat: resolve every rule threshold once into EffectiveParams"
```

---

### Task 4: Detector phía giáo viên + đăng ký mã luật `T.*`

**Files:**
- Create: `core/rules/detectors.py`
- Modify: `core/rules/__init__.py` (docstring, `RuleTier.HARD_MODEL`, 3 luật mới)
- Modify: `tests/test_rules_registry.py:4-5`
- Test: `tests/test_rule_detectors.py`

**Interfaces:**
- Consumes: `ScheduleView`, `Violation`, `EffectiveParams`, `view_and_params`, `pick`.
- Produces (mọi detector có chữ ký `(view: ScheduleView, params: EffectiveParams) -> list[Violation]`, mọi Violation mang `level="BREACH"`):
  - `detect_teacher_conflicts` → `T.CONFLICT` (teacher_id, weekday, session, period, count=số lớp)
  - `detect_teacher_busy` → `T.BUSY` (teacher_id, class_id, subject_id, weekday, session, period)
  - `detect_teacher_day_cap` → `T.DAY_CAP` (teacher_id, weekday, count)
  - `detect_teacher_gaps` → `II.7` (teacher_id, weekday, session; detail chứa `"tiết dạy: 1, 4"`)
  - `detect_teacher_4_consecutive_mornings` → `II.14` (teacher_id, weekday, session="S", count)
  - `detect_teacher_lone_sessions` → `II.4` (teacher_id, weekday, session **không** None)
  - `detect_teacher_lone_days` → `II.4` (teacher_id, weekday, session **là** None)
  - `detect_teacher_split_days` → `II.8` (teacher_id, weekday)
  - `detect_teacher_missing_mandatory_mornings` → `II.3` (teacher_id, weekday, session="S")
  - `is_teacher_busy_morning(view, teacher_id, weekday) -> bool`
  - `RuleTier.HARD_MODEL`

- [ ] **Step 1: Viết test (chuyển nguyên các ca của `tests/test_validation_hdsp_rules.py` và phần GV của `test_validation_helpers`)**

`tests/test_rule_detectors.py`:
```python
from dataclasses import replace

from core.models import SchedulingConfig, Slot, Teacher, TimeSlot
from core.rules.detectors import (
    detect_teacher_4_consecutive_mornings, detect_teacher_busy, detect_teacher_conflicts,
    detect_teacher_day_cap, detect_teacher_gaps, detect_teacher_lone_days, detect_teacher_lone_sessions,
    detect_teacher_missing_mandatory_mornings, detect_teacher_split_days,
)
from tests.rule_helpers import pick, view_and_params

NO_LONE_THRESHOLD = SchedulingConfig(min_weekly_periods_for_lone_penalty=0)
TWELVE_PERIODS_MISSING_THURSDAY = [(2, p) for p in range(1, 5)] + [(4, p) for p in range(1, 5)] + [(6, p) for p in range(1, 5)]


def _slot(slot_id, weekday, session, period, class_id=101):
    return Slot(slot_id, class_id, TimeSlot(slot_id, weekday, session, period))


def _morning_slots(weekday_period_pairs):
    return [_slot(i + 1, wd, "S", p) for i, (wd, p) in enumerate(weekday_period_pairs)]


def _split_day_slots():
    return [_slot(1, 2, "S", 1), _slot(2, 2, "C", 2)]


def _teacher_1(slots, config=None, **input_kwargs):
    """Teacher 1 teaches subject 1 in class 101 in every given slot."""
    return view_and_params(slots, {s.slot_id: 1 for s in slots},
                           assigned_teacher={(1, 101): 1}, config=config, **input_kwargs)


# --- II.3 ---

def test_missing_mandatory_morning():
    view, params = _teacher_1(_morning_slots(TWELVE_PERIODS_MISSING_THURSDAY))
    assert (1, 5) in pick(detect_teacher_missing_mandatory_mornings(view, params), "teacher_id", "weekday")


def test_missing_mandatory_morning_honours_pinned_full_day_off():
    view, params = _teacher_1(_morning_slots(TWELVE_PERIODS_MISSING_THURSDAY),
                              teachers=[Teacher(1, "GV 1", pinned_full_day_off=5)])
    assert (1, 5) not in pick(detect_teacher_missing_mandatory_mornings(view, params), "teacher_id", "weekday")


def test_missing_mandatory_morning_excuses_teacher_busy_that_morning():
    taught = _morning_slots(TWELVE_PERIODS_MISSING_THURSDAY)
    thursday = [_slot(101, 5, "S", 1), _slot(102, 5, "S", 2)]
    view, params = view_and_params(taught + thursday, {s.slot_id: 1 for s in taught},
                                   assigned_teacher={(1, 101): 1}, ban_busy={(1, 101), (1, 102)})
    assert (1, 5) not in pick(detect_teacher_missing_mandatory_mornings(view, params), "teacher_id", "weekday")


# --- II.4 / II.8 ---

def test_lone_session_respects_load_threshold():
    slots = _morning_slots([(2, 1)])
    assert detect_teacher_lone_sessions(*_teacher_1(slots, SchedulingConfig(min_weekly_periods_for_lone_penalty=15))) == []
    assert pick(detect_teacher_lone_sessions(*_teacher_1(slots, NO_LONE_THRESHOLD)),
                "teacher_id", "weekday", "session") == [(1, 2, "S")]


def test_lone_day():
    violations = detect_teacher_lone_days(*_teacher_1(_morning_slots([(2, 1)]), NO_LONE_THRESHOLD))
    assert pick(violations, "teacher_id", "weekday", "session") == [(1, 2, None)]


def test_split_day_respects_load_threshold():
    slots = _split_day_slots()
    assert detect_teacher_split_days(*_teacher_1(slots, SchedulingConfig(min_weekly_periods_for_lone_penalty=15))) == []
    assert pick(detect_teacher_split_days(*_teacher_1(slots, NO_LONE_THRESHOLD)), "teacher_id", "weekday") == [(1, 2)]


def test_split_day_is_exactly_one_plus_one_not_asymmetric():
    asymmetric = [_slot(1, 2, "S", 1), _slot(2, 2, "C", 1), _slot(3, 2, "C", 2), _slot(4, 2, "C", 3)]
    assert detect_teacher_split_days(*_teacher_1(asymmetric, NO_LONE_THRESHOLD)) == []


def test_exempt_teacher_is_skipped_by_every_lone_rule():
    exempt = SchedulingConfig(min_weekly_periods_for_lone_penalty=0, lone_session_exempt_teacher_ids=frozenset({1}))
    lone = _morning_slots([(2, 1)])
    assert detect_teacher_lone_sessions(*_teacher_1(lone, exempt)) == []
    assert detect_teacher_lone_days(*_teacher_1(lone, exempt)) == []
    assert detect_teacher_split_days(*_teacher_1(_split_day_slots(), exempt)) == []


# --- II.14 / II.7 ---

def test_four_period_morning_only_counts_for_lighter_teachers():
    view, params = _teacher_1(_morning_slots([(2, p) for p in range(1, 5)]))
    assert pick(detect_teacher_4_consecutive_mornings(view, params), "teacher_id", "weekday") == [(1, 2)]
    assert detect_teacher_4_consecutive_mornings(view, replace(params, max_load_for_4consec_penalty=2)) == []


def test_teacher_gap_within_session():
    slots = [_slot(1, 2, "S", 1), _slot(2, 2, "S", 4)]
    view, params = view_and_params(slots, {1: 100, 2: 100}, assigned_teacher={(100, 101): 10})
    gaps = detect_teacher_gaps(view, params)
    assert pick(gaps, "teacher_id", "weekday", "session") == [(10, 2, "S")]
    assert "tiết dạy: 1, 4" in gaps[0].detail


# --- T.* ---

def test_teacher_in_two_classes_at_once():
    shared = TimeSlot(1, 2, "S", 1)
    slots = [Slot(1, 101, shared), Slot(2, 102, shared)]
    view, params = view_and_params(slots, {1: 7, 2: 7}, assigned_teacher={(7, 101): 10, (7, 102): 10})
    assert pick(detect_teacher_conflicts(view, params), "teacher_id", "weekday", "session", "period", "count") == [
        (10, 2, "S", 1, 2),
    ]


def test_teacher_placed_in_busy_slot():
    slots = [_slot(1, 2, "S", 1), _slot(2, 2, "S", 2)]
    view, params = view_and_params(slots, {1: 100, 2: 100}, assigned_teacher={(100, 101): 10}, ban_busy={(10, 1)})
    assert pick(detect_teacher_busy(view, params), "teacher_id", "class_id", "weekday", "session", "period") == [
        (10, 101, 2, "S", 1),
    ]


def test_teacher_over_daily_cap():
    slots = [_slot(i, 2, "S", i) for i in range(1, 4)]
    view, params = _teacher_1(slots, SchedulingConfig(max_teacher_periods_per_day=2))
    assert pick(detect_teacher_day_cap(view, params), "teacher_id", "weekday", "count") == [(1, 2, 3)]
```

- [ ] **Step 2: Chạy test để thấy nó đỏ**

Run: `python -m pytest tests/test_rule_detectors.py -q -n 0`
Expected: FAIL với `ModuleNotFoundError: No module named 'core.rules.detectors'`

- [ ] **Step 3: Viết `core/rules/detectors.py` (phần giáo viên)**

```python
"""Post-generation detectors: one function per rule, each counting violations
of a finished schedule against the school's DECLARED thresholds.

Detectors know nothing about relaxation -- every Violation they return is a
BREACH. Whether a breach was forced is decided afterwards by
core.rules.violations.classify, so evidence can never make a violation vanish.

Each detector names the CP-SAT construct it mirrors. Change both sides
together and run tests/test_rule_equivalence.py.
"""
from __future__ import annotations

from collections import Counter, defaultdict

from core.models import WEEKDAY_NAMES
from core.rules.params import EffectiveParams
from core.rules.view import ScheduleView
from core.rules.violations import Violation

SESSION_NAMES = {"S": "Sáng", "C": "Chiều"}
MIN_FREE_MORNING_PERIODS = 2      # fewer free periods than this = cannot avoid a lone session (II.4)
LONG_MORNING_RUN = 4              # II.14
MIN_PERIODS_FOR_GAP = 2


def _day(weekday: int) -> str:
    return WEEKDAY_NAMES.get(weekday, f"Thứ {weekday}")


def _session(session: str) -> str:
    return SESSION_NAMES.get(session, str(session))


def _teacher_totals(view: ScheduleView, skip_ids: frozenset = frozenset()) -> Counter:
    return Counter(t for _slot, _subject, t in view.placed() if t is not None and t not in skip_ids)


def _teacher_session_counts(view: ScheduleView, skip_ids: frozenset = frozenset()) -> Counter:
    return Counter((t, slot.ts.weekday, slot.ts.session) for slot, _subject, t in view.placed()
                   if t is not None and t not in skip_ids)


# T.CONFLICT -- mirrors constraints.py:_add_teacher_constraints rule 1 (AddAtMostOne per teacher/timeslot)
def detect_teacher_conflicts(view: ScheduleView, params: EffectiveParams) -> list:
    classes_at = defaultdict(list)
    for slot, _subject_id, teacher_id in view.placed():
        if teacher_id is not None:
            classes_at[teacher_id, slot.ts.weekday, slot.ts.session, slot.ts.period].append(slot.class_id)
    return [
        Violation("T.CONFLICT", teacher_id=tid, weekday=wd, session=sess, period=period, count=len(class_ids),
                  detail=f"{view.teacher_name(tid)}: trùng lịch {_day(wd)} {_session(sess)} tiết {period} "
                         f"giữa các lớp {', '.join(view.class_name(c) for c in class_ids)}")
        for (tid, wd, sess, period), class_ids in classes_at.items() if len(class_ids) > 1
    ]


# T.BUSY -- mirrors constraints.py:_add_teacher_constraints rule 2 (ban_busy -> x == 0)
def detect_teacher_busy(view: ScheduleView, params: EffectiveParams) -> list:
    return [
        Violation("T.BUSY", teacher_id=tid, class_id=slot.class_id, subject_id=subject_id,
                  weekday=slot.ts.weekday, session=slot.ts.session, period=slot.ts.period,
                  detail=f"{view.teacher_name(tid)}: xếp dạy {view.class_name(slot.class_id)} vào giờ đã báo bận "
                         f"({_day(slot.ts.weekday)} {_session(slot.ts.session)} tiết {slot.ts.period})")
        for slot, subject_id, tid in view.placed()
        if tid is not None and (tid, slot.ts.ts_id) in view.ban_busy
    ]


# T.DAY_CAP (Tiêu chí II.2) -- mirrors constraints.py:_add_teacher_constraints rule 4
def detect_teacher_day_cap(view: ScheduleView, params: EffectiveParams) -> list:
    cap = params.max_teacher_periods_per_day
    per_day = Counter((t, slot.ts.weekday) for slot, _subject, t in view.placed() if t is not None)
    return [
        Violation("T.DAY_CAP", teacher_id=tid, weekday=wd, count=n,
                  detail=f"{view.teacher_name(tid)}: dạy {n} tiết vào {_day(wd)} (vượt trần {cap} tiết/ngày)")
        for (tid, wd), n in per_day.items() if n > cap
    ]


# II.7 -- mirrors objectives.py section 3 (penalty_terms["II.7"])
def detect_teacher_gaps(view: ScheduleView, params: EffectiveParams) -> list:
    periods = defaultdict(list)
    for slot, _subject_id, teacher_id in view.placed():
        if teacher_id is not None:
            periods[teacher_id, slot.ts.weekday, slot.ts.session].append(slot.ts.period)
    return [
        Violation("II.7", teacher_id=tid, weekday=wd, session=sess,
                  detail=f"{view.teacher_name(tid)}: bị trống tiết {_day(wd)} {_session(sess)} "
                         f"(tiết dạy: {', '.join(str(p) for p in sorted(ps))})")
        for (tid, wd, sess), ps in periods.items()
        if len(ps) >= MIN_PERIODS_FOR_GAP and max(ps) - min(ps) + 1 > len(ps)
    ]


# II.14 -- mirrors objectives.py section 4 (penalty_terms["II.14"])
def detect_teacher_4_consecutive_mornings(view: ScheduleView, params: EffectiveParams) -> list:
    totals = _teacher_totals(view)
    mornings = Counter((t, slot.ts.weekday) for slot, _subject, t in view.placed()
                       if t is not None and slot.ts.session == "S")
    return [
        Violation("II.14", teacher_id=tid, weekday=wd, session="S", count=n,
                  detail=f"{view.teacher_name(tid)}: dạy {n} tiết liên tục sáng {_day(wd)}")
        for (tid, wd), n in mornings.items()
        if n >= LONG_MORNING_RUN and totals[tid] <= params.max_load_for_4consec_penalty
    ]


# II.4 (buổi lẻ) -- mirrors objectives.py section 1, lone[t, wd, sess] in penalty_terms["II.4"]
def detect_teacher_lone_sessions(view: ScheduleView, params: EffectiveParams) -> list:
    totals = _teacher_totals(view, params.lone_exempt_ids)
    return [
        Violation("II.4", teacher_id=tid, weekday=wd, session=sess, count=n,
                  detail=f"{view.teacher_name(tid)}: {_day(wd)} {_session(sess)} chỉ có 1 tiết (buổi lẻ)")
        for (tid, wd, sess), n in _teacher_session_counts(view, params.lone_exempt_ids).items()
        if n == 1 and totals[tid] >= params.min_weekly_periods_for_lone_penalty
    ]


# II.4 (ngày lẻ) -- mirrors objectives.py section 1, lone_day terms in penalty_terms["II.4"]
def detect_teacher_lone_days(view: ScheduleView, params: EffectiveParams) -> list:
    totals = _teacher_totals(view, params.lone_exempt_ids)
    per_day = Counter((t, slot.ts.weekday) for slot, _subject, t in view.placed()
                      if t is not None and t not in params.lone_exempt_ids)
    return [
        Violation("II.4", teacher_id=tid, weekday=wd, count=n,
                  detail=f"{view.teacher_name(tid)}: {_day(wd)} cả ngày chỉ có đúng 1 tiết")
        for (tid, wd), n in per_day.items()
        if n == 1 and totals[tid] >= params.min_weekly_periods_for_lone_penalty
    ]


# II.8 -- mirrors objectives.py section 1, split terms in penalty_terms["II.8"].
# Narrow meaning S == 1 and C == 1 (user decision Q1, 2026-09-17).
def detect_teacher_split_days(view: ScheduleView, params: EffectiveParams) -> list:
    totals = _teacher_totals(view, params.lone_exempt_ids)
    per_session = _teacher_session_counts(view, params.lone_exempt_ids)
    days = dict.fromkeys((tid, wd) for (tid, wd, _sess) in per_session)
    return [
        Violation("II.8", teacher_id=tid, weekday=wd,
                  detail=f"{view.teacher_name(tid)}: {_day(wd)} sáng 1 tiết + chiều 1 tiết")
        for (tid, wd) in days
        if per_session[tid, wd, "S"] == 1 and per_session[tid, wd, "C"] == 1
        and totals[tid] >= params.min_weekly_periods_for_lone_penalty
    ]


def is_teacher_busy_morning(view: ScheduleView, teacher_id: int, weekday: int) -> bool:
    """A teacher counts as busy on a morning when fewer than 2 free periods remain there
    (II.4 forbids a 1-period session). Same meaning as constraints.py:_is_teacher_busy_morning;
    the two copies merge in Plan 3 (spec §5.4.4)."""
    if not view.ban_busy:
        return False
    morning = [s for s in view.slots if s.ts.weekday == weekday and s.ts.session == "S"]
    if not morning:
        return False
    own_classes = view.teacher_classes.get(teacher_id, frozenset())
    candidates = [s for s in morning if s.class_id in own_classes] or morning
    free_periods = {s.ts.period for s in candidates if (teacher_id, s.ts.ts_id) not in view.ban_busy}
    return len(free_periods) < MIN_FREE_MORNING_PERIODS


# II.3 -- mirrors objectives.py section 2 (penalty_terms["II.3"])
def detect_teacher_missing_mandatory_mornings(view: ScheduleView, params: EffectiveParams) -> list:
    watched = set(params.mandatory_morning_weekdays) | set(params.strict_morning_weekdays)
    present = {(t, slot.ts.weekday) for slot, _subject, t in view.placed()
               if t is not None and slot.ts.session == "S" and slot.ts.weekday in watched}
    violations = []
    for tid, total in _teacher_totals(view).items():
        for wd in _required_mornings(tid, total, params):
            if (tid, wd) in present or params.pinned_day_offs.get(tid) == wd or is_teacher_busy_morning(view, tid, wd):
                continue
            violations.append(Violation(
                "II.3", teacher_id=tid, weekday=wd, session="S",
                detail=f"{view.teacher_name(tid)}: không có tiết dạy sáng {_day(wd)} (sáng bắt buộc có mặt)",
            ))
    return violations


def _required_mornings(teacher_id: int, total: int, params: EffectiveParams) -> tuple:
    strict = () if teacher_id in params.bgh_ids else params.strict_morning_weekdays
    if total < params.min_weekly_periods_for_mandatory_morning:
        return tuple(strict)
    mandatory = tuple(wd for wd in params.mandatory_morning_weekdays if wd not in params.strict_morning_weekdays)
    return (*strict, *mandatory)
```

- [ ] **Step 4: Chạy test detector**

Run: `python -m pytest tests/test_rule_detectors.py -q -n 0`
Expected: PASS (13 tests)

- [ ] **Step 5: Mở rộng registry**

Trong `core/rules/__init__.py`:

Thay toàn bộ docstring module (dòng 1–13) bằng:
```python
"""Registry of every HĐSP rule a detector checks (core/rules/detectors.py) and
how a violation of it is treated.

RuleTier says who enforces the rule; RuleSpec.config_flag names the
SchedulingConfig switch that turns it off. Detectors, the solver's hard gate
and the UI all read this one table.
"""
```

Thay enum `RuleTier` bằng:
```python
class RuleTier(Enum):
    HARD_POST_GENERATION = "hard_post_generation"  # HĐSP hard gate: forced to zero, relaxed only by diagnosis
    HARD_MODEL = "hard_model"  # CP-SAT always enforces it; a violation found afterwards means the model and the check disagree
    SOFT = "soft"  # scored only; never blocks an attempt or the save button
```

Thêm vào dict `RULES`, ngay sau mục `"II.14"`:
```python
    "T.CONFLICT": RuleSpec(
        id="T.CONFLICT",
        title_vi="GV không dạy 2 lớp trong cùng một tiết",
        tier=RuleTier.HARD_MODEL,
    ),
    "T.BUSY": RuleSpec(
        id="T.BUSY",
        title_vi="Không xếp GV vào giờ đã báo bận",
        tier=RuleTier.HARD_MODEL,
    ),
    "T.DAY_CAP": RuleSpec(
        id="T.DAY_CAP",
        title_vi="GV không dạy quá số tiết/ngày theo cấu hình (Tiêu chí II.2)",
        tier=RuleTier.HARD_MODEL,
    ),
```

- [ ] **Step 6: Sửa test registry — danh sách luật giờ lớn hơn 6 một cách có chủ đích**

`tests/test_rules_registry.py`, thay hàm đầu tiên:
```python
def test_registry_keeps_the_six_hdsp_rules():
    assert {"II.3", "II.4", "II.7", "II.8", "II.9", "II.14"} <= set(RULES.keys())
```

- [ ] **Step 7: Chạy test**

Run: `python -m pytest tests/test_rule_detectors.py tests/test_rules_registry.py -q -n 0`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add core/rules/detectors.py core/rules/__init__.py tests/test_rule_detectors.py tests/test_rules_registry.py
git commit -m "feat: add teacher-side rule detectors over ScheduleView"
```

---

### Task 5: Detector phía lớp, `detect_rule`, `run_detectors`

**Files:**
- Modify: `core/rules/detectors.py` (thêm vào cuối)
- Modify: `core/rules/__init__.py` (9 luật mới)
- Modify: `tests/rule_helpers.py` (thêm `violations_of`)
- Test: `tests/test_rule_detectors.py` (thêm vào cuối)

**Interfaces:**
- Consumes: mọi thứ từ Task 4.
- Produces:
  - `detect_gdtc_periods` → `C.GDTC_PERIOD`; `detect_non_consecutive_days` → `C.NON_CONSEC_DAYS` (weekday = ngày đầu của cặp liền nhau); `detect_morning_only` → `C.MORNING_ONLY`; `detect_heavy_consecutive` → `C.HEAVY_CONSEC` (period = tiết bắt đầu, count = độ dài chuỗi, session); `detect_heavy_afternoon_period3` → `C.HEAVY_P3`; `detect_subject_cells` → `C.SUBJECT_CELLS`; `detect_single_pair` → `C.SINGLE_PAIR` (count = số ngày có ≥2 tiết); `detect_academic_overload` → `ACAD.MAX` (class_id, weekday, session="S", count; detail chứa `"quá tải"`); `detect_academic_underload` → `ACAD.MIN` (class_id, weekday, session="S", count).
  - `DETECTORS: dict[str, tuple[Callable, ...]]`
  - `detect_rule(rule_id, view, params) -> list[Violation]` — trả `[]` khi cờ `RULES[rule_id].config_flag` đang tắt.
  - `run_detectors(view, params) -> list[Violation]` — mọi luật trong `DETECTORS`.
  - `tests/rule_helpers.py`: `violations_of(rule_id, inp, assignment) -> list[Violation]`.

- [ ] **Step 1: Viết test (chuyển các ca của `test_validation_new_helpers`, phần GDTC/liền ngày của `test_validation_helpers`, hai test đơn vị trong `test_morning_academic_balance.py`)**

Thêm vào đầu `tests/test_rule_detectors.py` (gộp vào khối import sẵn có):
```python
from core.models import ROLE_GDTC, ROLE_NANG, Subject
from core.rules import RULES
from core.rules.detectors import (
    DETECTORS, detect_academic_overload, detect_academic_underload, detect_gdtc_periods,
    detect_heavy_afternoon_period3, detect_heavy_consecutive, detect_morning_only,
    detect_non_consecutive_days, detect_rule, detect_single_pair, detect_subject_cells,
)
from core.rules.params import RULE_FLAG_NAMES
```
Thêm vào cuối file:
```python
# --- C.* ---

def test_gdtc_outside_allowed_periods():
    slots = [_slot(1, 2, "S", 2), _slot(2, 2, "S", 4), _slot(3, 2, "S", 5), _slot(4, 3, "C", 1), _slot(5, 3, "C", 2)]
    view, params = view_and_params(slots, {s.slot_id: 100 for s in slots}, subjects=[Subject(100, "GDTC", ROLE_GDTC)])
    assert set(pick(detect_gdtc_periods(view, params), "class_id", "weekday", "session", "period")) == {
        (101, 2, "S", 5), (101, 3, "C", 1),
    }


def test_non_consecutive_subject_on_adjacent_days():
    slots = [_slot(1, 2, "S", 1), _slot(2, 2, "S", 4), _slot(3, 3, "S", 1), _slot(4, 4, "S", 1)]
    view, params = view_and_params(slots, {s.slot_id: 100 for s in slots},
                                   config=SchedulingConfig(non_consecutive_subject_ids=frozenset({100})))
    assert pick(detect_non_consecutive_days(view, params), "class_id", "subject_id", "weekday") == [
        (101, 100, 2), (101, 100, 3),
    ]


def test_morning_only_subject_in_afternoon():
    slots = [_slot(1, 2, "S", 1), _slot(2, 2, "C", 1)]
    view, params = view_and_params(slots, {1: 10, 2: 10},
                                   config=SchedulingConfig(morning_only_subject_ids=frozenset({10})))
    assert pick(detect_morning_only(view, params), "class_id", "subject_id", "weekday", "session", "period") == [
        (101, 10, 2, "C", 1),
    ]


def test_heavy_run_longer_than_declared_cap():
    slots = [_slot(i, 2, "S", i) for i in range(1, 5)]
    subjects = [Subject(10, "Lý", ROLE_NANG), Subject(11, "Hóa", ROLE_NANG)]
    view, params = view_and_params(slots, {1: 10, 2: 10, 3: 11, 4: 11}, subjects=subjects)
    assert pick(detect_heavy_consecutive(view, params), "class_id", "weekday", "session", "period", "count") == [
        (101, 2, "S", 1, 4),
    ]


def test_heavy_subject_at_afternoon_period_3():
    slots = [_slot(1, 2, "C", 2), _slot(2, 2, "C", 3)]
    view, params = view_and_params(slots, {1: 10, 2: 10}, subjects=[Subject(10, "Lý", ROLE_NANG)])
    assert pick(detect_heavy_afternoon_period3(view, params), "class_id", "subject_id", "period") == [(101, 10, 3)]


def test_subject_outside_allowed_cells():
    slots = [_slot(1, 2, "S", 1), _slot(2, 3, "S", 1)]
    view, params = view_and_params(slots, {1: 10, 2: 10}, allowed_cells={(10, 101): frozenset({(2, "S")})})
    assert pick(detect_subject_cells(view, params), "class_id", "subject_id", "weekday", "session", "period") == [
        (101, 10, 3, "S", 1),
    ]


def test_single_pair_subject_with_two_pairs():
    config = SchedulingConfig(single_pair_subject_ids=frozenset({10}))
    two_pairs = [_slot(1, 2, "S", 1), _slot(2, 2, "S", 2), _slot(3, 3, "S", 1), _slot(4, 3, "S", 2)]
    one_pair = [_slot(1, 2, "S", 1), _slot(2, 2, "S", 2), _slot(3, 3, "S", 1), _slot(4, 4, "S", 1)]
    two = detect_single_pair(*view_and_params(two_pairs, {s.slot_id: 10 for s in two_pairs}, config=config))
    one = detect_single_pair(*view_and_params(one_pair, {s.slot_id: 10 for s in one_pair}, config=config))
    assert pick(two, "class_id", "subject_id", "count") == [(101, 10, 2)]
    assert one == []


# --- ACAD.* ---

ACADEMIC_AND_LIGHT_SUBJECTS = [
    Subject(1, "Toán học"), Subject(2, "Ngữ văn"), Subject(3, "Ngoại ngữ"), Subject(4, "Khoa học tự nhiên"),
    Subject(5, "Tin học"), Subject(6, "Âm nhạc"), Subject(7, "Mỹ thuật"),
]


def _four_period_mornings(weekdays):
    return [_slot((wd - 2) * 4 + p, wd, "S", p) for wd in weekdays for p in range(1, 5)]


def test_morning_with_more_academic_periods_than_declared_cap():
    assignment = {1: 1, 2: 2, 3: 3, 4: 4, 5: 1, 6: 2, 7: 3, 8: 5}
    view, params = view_and_params(_four_period_mornings((2, 3)), assignment, subjects=ACADEMIC_AND_LIGHT_SUBJECTS)
    overloads = detect_academic_overload(view, params)
    assert pick(overloads, "class_id", "weekday", "count") == [(101, 2, 4)]
    assert "quá tải" in overloads[0].detail


def test_morning_with_fewer_academic_periods_than_declared_floor():
    slots = _four_period_mornings((2, 3)) + [_slot(9, 2, "C", 1), _slot(10, 2, "C", 2), _slot(11, 2, "C", 3)]
    assignment = {1: 1, 2: 5, 3: 6, 4: 7, 5: 1, 6: 2, 7: 5, 8: 6, 9: 5, 10: 6, 11: 7}
    view, params = view_and_params(slots, assignment, subjects=ACADEMIC_AND_LIGHT_SUBJECTS)
    assert pick(detect_academic_underload(view, params), "class_id", "weekday", "count") == [(101, 2, 1)]


# --- dispatch ---

def test_detect_rule_skips_rules_the_school_turned_off():
    slots = [_slot(1, 2, "S", 1), _slot(2, 2, "S", 4)]
    on = view_and_params(slots, {1: 7, 2: 7}, assigned_teacher={(7, 101): 10})
    off = view_and_params(slots, {1: 7, 2: 7}, assigned_teacher={(7, 101): 10},
                          config=SchedulingConfig(avoid_teacher_gaps=False))
    assert len(detect_rule("II.7", *on)) == 1
    assert detect_rule("II.7", *off) == []


def test_every_detected_rule_is_registered_with_a_resolvable_flag():
    assert set(DETECTORS) <= set(RULES)
    assert {rule.config_flag for rule in RULES.values()} - {None} <= set(RULE_FLAG_NAMES)
```

- [ ] **Step 2: Chạy test để thấy nó đỏ**

Run: `python -m pytest tests/test_rule_detectors.py -q -n 0`
Expected: FAIL với `ImportError: cannot import name 'DETECTORS'`

- [ ] **Step 3: Thêm detector phía lớp vào cuối `core/rules/detectors.py`**

Thêm `from core.rules import RULES` vào khối import đầu file, và hai hằng sau `MIN_PERIODS_FOR_GAP`:
```python
PAIR_SIZE = 2
AFTERNOON_HEAVY_FORBIDDEN_PERIOD = 3   # II.15
MIN_MORNING_PERIODS_FOR_ACADEMIC_FLOOR = 3
```
Thêm vào cuối file:
```python
# C.GDTC_PERIOD -- mirrors constraints.py:_add_subject_constraints rule 3
def detect_gdtc_periods(view: ScheduleView, params: EffectiveParams) -> list:
    allowed = {"S": params.gdtc_morning_allowed_periods, "C": params.gdtc_afternoon_allowed_periods}
    return [
        Violation("C.GDTC_PERIOD", class_id=slot.class_id, subject_id=subject_id, weekday=slot.ts.weekday,
                  session=slot.ts.session, period=slot.ts.period,
                  detail=f"{view.class_name(slot.class_id)}: tiết GDTC ở tiết {slot.ts.period} "
                         f"{_session(slot.ts.session)} ({_day(slot.ts.weekday)}) ngoài khung giờ cho phép")
        for slot, subject_id, _teacher in view.placed()
        if subject_id == view.roles.gdtc_id and allowed.get(slot.ts.session)
        and slot.ts.period not in allowed[slot.ts.session]
    ]


# C.NON_CONSEC_DAYS -- mirrors constraints.py:_add_subject_constraints rule 4
def detect_non_consecutive_days(view: ScheduleView, params: EffectiveParams) -> list:
    days = defaultdict(set)
    for slot, subject_id, _teacher in view.placed():
        if subject_id in params.non_consecutive_subject_ids:
            days[slot.class_id, subject_id].add(slot.ts.weekday)
    return [
        Violation("C.NON_CONSEC_DAYS", class_id=cid, subject_id=sid, weekday=wd,
                  detail=f"{view.class_name(cid)}: môn {view.subject_name(sid)} học 2 ngày liền "
                         f"({_day(wd)} - {_day(wd + 1)})")
        for (cid, sid), weekdays in days.items() for wd in sorted(weekdays) if wd + 1 in weekdays
    ]


# C.MORNING_ONLY -- mirrors constraints.py:_add_subject_constraints rules 1-2
def detect_morning_only(view: ScheduleView, params: EffectiveParams) -> list:
    return [
        Violation("C.MORNING_ONLY", class_id=slot.class_id, subject_id=subject_id, weekday=slot.ts.weekday,
                  session=slot.ts.session, period=slot.ts.period,
                  detail=f"{view.class_name(slot.class_id)}: môn {view.subject_name(subject_id)} chỉ học sáng "
                         f"nhưng xếp chiều {_day(slot.ts.weekday)} tiết {slot.ts.period}")
        for slot, subject_id, _teacher in view.placed()
        if subject_id in params.morning_only_subject_ids and slot.ts.session == "C"
    ]


def _runs(sorted_periods: list) -> list:
    """(start, length) of each maximal run of consecutive periods."""
    runs = []
    for period in sorted_periods:
        if runs and period == runs[-1][0] + runs[-1][1]:
            runs[-1] = (runs[-1][0], runs[-1][1] + 1)
        else:
            runs.append((period, 1))
    return runs


# C.HEAVY_CONSEC -- mirrors constraints.py:_add_subject_constraints rule 6 (sliding window)
def detect_heavy_consecutive(view: ScheduleView, params: EffectiveParams) -> list:
    heavy_periods = defaultdict(set)
    for slot, subject_id, _teacher in view.placed():
        if subject_id in view.roles.heavy_ids:
            heavy_periods[slot.class_id, slot.ts.weekday, slot.ts.session].add(slot.ts.period)
    violations = []
    for (cid, wd, sess), periods in heavy_periods.items():
        cap = params.max_heavy_consecutive[cid, sess].declared
        violations += [
            Violation("C.HEAVY_CONSEC", class_id=cid, weekday=wd, session=sess, period=start, count=length,
                      detail=f"{view.class_name(cid)}: {length} tiết môn Nặng liên tiếp {_day(wd)} {_session(sess)} "
                             f"từ tiết {start} (trần cấu hình {cap})")
            for start, length in _runs(sorted(periods)) if length > cap
        ]
    return violations


# C.HEAVY_P3 (Tiêu chí II.15) -- mirrors constraints.py:_add_subject_constraints rule 7
def detect_heavy_afternoon_period3(view: ScheduleView, params: EffectiveParams) -> list:
    return [
        Violation("C.HEAVY_P3", class_id=slot.class_id, subject_id=subject_id, weekday=slot.ts.weekday,
                  session="C", period=slot.ts.period,
                  detail=f"{view.class_name(slot.class_id)}: môn {view.subject_name(subject_id)} xếp tiết 3 chiều "
                         f"{_day(slot.ts.weekday)} — học sinh dễ mệt cuối ngày")
        for slot, subject_id, _teacher in view.placed()
        if subject_id in view.roles.heavy_ids and slot.ts.session == "C"
        and slot.ts.period == AFTERNOON_HEAVY_FORBIDDEN_PERIOD
    ]


# C.SUBJECT_CELLS -- mirrors constraints.py:_add_subject_constraints rule 8. Reads the same
# inp.subject_class_allowed_cells the solver used, not a second DB query (spec V7).
def detect_subject_cells(view: ScheduleView, params: EffectiveParams) -> list:
    violations = []
    for slot, subject_id, _teacher in view.placed():
        allowed = view.allowed_cells.get((subject_id, slot.class_id))
        if allowed is not None and (slot.ts.weekday, slot.ts.session) not in allowed:
            violations.append(Violation(
                "C.SUBJECT_CELLS", class_id=slot.class_id, subject_id=subject_id, weekday=slot.ts.weekday,
                session=slot.ts.session, period=slot.ts.period,
                detail=f"{view.class_name(slot.class_id)}: môn {view.subject_name(subject_id)} xếp "
                       f"{_day(slot.ts.weekday)} {_session(slot.ts.session)} ngoài các buổi được phép",
            ))
    return violations


# C.SINGLE_PAIR -- mirrors constraints.py:_add_block_constraints (single-pair branch).
# Adjacency and the zero-pair case are NOT checked yet -- that is spec V2, Plan 3.
def detect_single_pair(view: ScheduleView, params: EffectiveParams) -> list:
    per_day = defaultdict(Counter)
    for slot, subject_id, _teacher in view.placed():
        if subject_id in view.roles.single_pair_ids:
            per_day[slot.class_id, subject_id][slot.ts.weekday] += 1
    violations = []
    for (cid, sid), counts in per_day.items():
        pair_days = sorted(wd for wd, n in counts.items() if n >= PAIR_SIZE)
        excess_days = sorted(wd for wd, n in counts.items() if n > PAIR_SIZE)
        if len(pair_days) > 1 or excess_days:
            violations.append(Violation(
                "C.SINGLE_PAIR", class_id=cid, subject_id=sid, count=len(pair_days),
                detail=f"{view.class_name(cid)}: môn {view.subject_name(sid)} có {len(pair_days)} ngày xếp cặp "
                       f"({', '.join(_day(wd) for wd in pair_days)})"
                       + (f", quá 2 tiết vào {', '.join(_day(wd) for wd in excess_days)}" if excess_days else ""),
            ))
    return violations


def _morning_academic_counts(view: ScheduleView) -> Counter:
    return Counter((slot.class_id, slot.ts.weekday) for slot, subject_id, _teacher in view.placed()
                   if slot.ts.session == "S" and subject_id in view.academic_ids)


# ACAD.MAX -- mirrors constraints.py:_add_class_constraints rule 8 (upper bound)
def detect_academic_overload(view: ScheduleView, params: EffectiveParams) -> list:
    violations = []
    for (cid, wd), n in sorted(_morning_academic_counts(view).items()):
        cap = params.max_academic_per_morning[cid].declared
        if n > cap:
            violations.append(Violation(
                "ACAD.MAX", class_id=cid, weekday=wd, session="S", count=n,
                detail=f"{view.class_name(cid)}: sáng {_day(wd)} có {n} tiết học thuật (trần {cap}) — học sinh bị quá tải",
            ))
    return violations


# ACAD.MIN -- mirrors objectives.py section 6d (soft floor)
def detect_academic_underload(view: ScheduleView, params: EffectiveParams) -> list:
    counts = _morning_academic_counts(view)
    morning_sizes = Counter((s.class_id, s.ts.weekday) for s in view.slots if s.ts.session == "S")
    minimum = params.min_academic_per_morning
    return [
        Violation("ACAD.MIN", class_id=cid, weekday=wd, session="S", count=counts[cid, wd],
                  detail=f"{view.class_name(cid)}: sáng {_day(wd)} chỉ có {counts[cid, wd]} tiết học thuật "
                         f"(khuyến nghị ≥ {minimum}) — phân bố tải chưa đều")
        for (cid, wd), size in sorted(morning_sizes.items())
        if size >= MIN_MORNING_PERIODS_FOR_ACADEMIC_FLOOR and counts[cid, wd] < minimum
    ]


DETECTORS: dict = {
    "II.3": (detect_teacher_missing_mandatory_mornings,),
    "II.4": (detect_teacher_lone_sessions, detect_teacher_lone_days),
    "II.7": (detect_teacher_gaps,),
    "II.8": (detect_teacher_split_days,),
    "II.14": (detect_teacher_4_consecutive_mornings,),
    "T.CONFLICT": (detect_teacher_conflicts,),
    "T.BUSY": (detect_teacher_busy,),
    "T.DAY_CAP": (detect_teacher_day_cap,),
    "C.GDTC_PERIOD": (detect_gdtc_periods,),
    "C.NON_CONSEC_DAYS": (detect_non_consecutive_days,),
    "C.MORNING_ONLY": (detect_morning_only,),
    "C.HEAVY_CONSEC": (detect_heavy_consecutive,),
    "C.HEAVY_P3": (detect_heavy_afternoon_period3,),
    "C.SUBJECT_CELLS": (detect_subject_cells,),
    "C.SINGLE_PAIR": (detect_single_pair,),
    "ACAD.MAX": (detect_academic_overload,),
    "ACAD.MIN": (detect_academic_underload,),
}


def detect_rule(rule_id: str, view: ScheduleView, params: EffectiveParams) -> list:
    """Violations of one rule, or none when the school turned the rule off."""
    flag = RULES[rule_id].config_flag
    if flag is not None and not params.flags[flag]:
        return []
    return [violation for detector in DETECTORS[rule_id] for violation in detector(view, params)]


def run_detectors(view: ScheduleView, params: EffectiveParams) -> list:
    return [violation for rule_id in DETECTORS for violation in detect_rule(rule_id, view, params)]
```

- [ ] **Step 4: Đăng ký 9 luật phía lớp**

Thêm vào dict `RULES` trong `core/rules/__init__.py`, sau mục `"T.DAY_CAP"`:
```python
    "C.GDTC_PERIOD": RuleSpec(
        id="C.GDTC_PERIOD",
        title_vi="GDTC chỉ xếp trong khung tiết cho phép",
        tier=RuleTier.HARD_MODEL,
    ),
    "C.NON_CONSEC_DAYS": RuleSpec(
        id="C.NON_CONSEC_DAYS",
        title_vi="Môn cấm học liền ngày (gồm GDTC) không xếp 2 ngày liên tiếp",
        tier=RuleTier.HARD_MODEL,
    ),
    "C.MORNING_ONLY": RuleSpec(
        id="C.MORNING_ONLY",
        title_vi="Môn chỉ học buổi sáng không xếp vào buổi chiều",
        tier=RuleTier.HARD_MODEL,
    ),
    "C.HEAVY_CONSEC": RuleSpec(
        id="C.HEAVY_CONSEC",
        title_vi="Môn Nặng không quá số tiết liên tiếp theo cấu hình",
        tier=RuleTier.HARD_MODEL,
    ),
    "C.HEAVY_P3": RuleSpec(
        id="C.HEAVY_P3",
        title_vi="Môn Nặng không xếp tiết 3 buổi chiều (Tiêu chí II.15)",
        tier=RuleTier.HARD_MODEL,
        config_flag="avoid_heavy_afternoon_period3",
    ),
    "C.SUBJECT_CELLS": RuleSpec(
        id="C.SUBJECT_CELLS",
        title_vi="Môn chỉ xếp vào các buổi được phép theo luật môn/lớp",
        tier=RuleTier.HARD_MODEL,
    ),
    "C.SINGLE_PAIR": RuleSpec(
        id="C.SINGLE_PAIR",
        title_vi="Môn 1 cặp có đúng một cặp 2 tiết, không quá 2 tiết/ngày",
        tier=RuleTier.HARD_MODEL,
    ),
    "ACAD.MAX": RuleSpec(
        id="ACAD.MAX",
        title_vi="Buổi sáng không quá số tiết học thuật theo cấu hình",
        tier=RuleTier.HARD_MODEL,
        config_flag="balance_morning_academic_load",
    ),
    "ACAD.MIN": RuleSpec(
        id="ACAD.MIN",
        title_vi="Buổi sáng nên có tối thiểu số tiết học thuật theo cấu hình",
        tier=RuleTier.SOFT,
        config_flag="balance_morning_academic_load",
    ),
```

- [ ] **Step 5: Thêm `violations_of` vào `tests/rule_helpers.py`**

Thêm import `from core.rules.detectors import detect_rule` vào đầu file; thêm vào cuối:
```python
def violations_of(rule_id, inp, assignment):
    return detect_rule(rule_id, build_schedule_view(inp, assignment), resolve_effective_params(inp))
```

- [ ] **Step 6: Chạy test**

Run: `python -m pytest tests/test_rule_detectors.py tests/test_rules_registry.py tests/test_rule_params.py tests/test_rule_view.py -q -n 0`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add core/rules/detectors.py core/rules/__init__.py tests/rule_helpers.py tests/test_rule_detectors.py
git commit -m "feat: add class-side rule detectors and flag-aware dispatch"
```

---

### Task 6: `compute_tkb_health_score` đi qua detectors

**Files:**
- Modify: `core/validation.py:1-19` (import) và `core/validation.py:473-806` (toàn bộ `compute_tkb_health_score`)
- Test: `tests/test_tkb_quality_scoring.py` (thêm 1 test)

**Interfaces:**
- Consumes: `build_schedule_view`, `resolve_effective_params`, `run_detectors`, `group_by_rule`, `core.scheduler.quality._count_teacher_excess_gaps(slots, assigned, slot_teacher)`.
- Produces: `compute_tkb_health_score(inp, assignment) -> dict` — **cùng khóa** `overall_score`, `pedagogical_score`, `teacher_score`, `compliance_score`, `rating`, `badge_color`, `metrics{...}`, `recommendations` như trước. Thay đổi hành vi có chủ đích: luật bị tắt bằng cờ không còn bị trừ điểm (V9); II.3 giờ tôn trọng `pinned_full_day_off` ở mọi nơi.

- [ ] **Step 1: Chạy impact trước khi sửa**

MCP: `impact({target: "compute_tkb_health_score", direction: "upstream"})`. Caller đã biết: `pages/06_Xep_TKB.py:337`, `tests/test_tkb_quality_scoring.py`, `tests/test_morning_academic_balance.py:234`. Báo mức rủi ro.

- [ ] **Step 2: Viết test cho hành vi mới**

Thêm vào cuối `tests/test_tkb_quality_scoring.py`:
```python
def test_health_score_does_not_penalise_rules_the_school_turned_off():
    from core.models import SchedulingConfig, Slot, TimeSlot
    from tests.rule_helpers import make_input

    slots = [Slot(1, 101, TimeSlot(1, 2, "S", 1)), Slot(2, 101, TimeSlot(2, 2, "S", 4))]
    inp = make_input(slots, assigned_teacher={(7, 101): 10}, config=SchedulingConfig(avoid_teacher_gaps=False))
    health = compute_tkb_health_score(inp, {1: 7, 2: 7})
    assert health["metrics"]["teacher_gaps_total"] == 0
```

- [ ] **Step 3: Chạy test để thấy nó đỏ**

Run: `python -m pytest tests/test_tkb_quality_scoring.py -q -n 0`
Expected: FAIL ở test mới — `assert 1 == 0` (bảng sức khỏe hiện đếm tiết trống bất kể cờ).

- [ ] **Step 4: Thay khối import của `core/validation.py` (dòng 5–19)**

```python
from __future__ import annotations

from collections import defaultdict
from typing import Optional

from core.models import ROLE_HDTN, WEEKDAY_NAMES, SchedulingInput
from core.rules.detectors import run_detectors
from core.rules.params import resolve_effective_params
from core.rules.view import build_schedule_view
from core.rules.violations import group_by_rule
from core.scheduler.quality import (
    _count_subject_consecutive_days,
    _count_teacher_back_to_back_shifts,
    _count_teacher_excess_gaps,
)
```

- [ ] **Step 5: Thay toàn bộ hàm `compute_tkb_health_score` (từ `def compute_tkb_health_score` tới hết file)**

```python
def _recommendations(violations: list, kind: str, category: str) -> list:
    return [{"type": kind, "category": category, "message": v.detail} for v in violations]


def compute_tkb_health_score(inp: SchedulingInput, assignment: dict) -> dict:
    """Đánh giá toàn diện sức khỏe TKB theo thang điểm 100 với 3 trụ cột:
    1. Sư phạm học sinh (Pedagogical Quality - 40%)
    2. Tiện nghi & Công bằng Giáo viên (Teacher Ergonomics & Fairness - 35%)
    3. Tuân thủ HĐSP & Kế hoạch (HĐSP Compliance - 25%)

    Mọi luật HĐSP đến từ core.rules.detectors -- hàm này chỉ chấm điểm, không tự
    cài đặt lại luật. Điểm theo thang sư phạm, khác thang tối ưu của bộ giải.
    """
    view = build_schedule_view(inp, assignment)
    found = group_by_rule(run_detectors(view, resolve_effective_params(inp)))
    class_map = {c.class_id: c.name for c in inp.classes}
    subj_map = {s.subject_id: s.name for s in inp.subjects}
    teacher_map = {t.teacher_id: t.name for t in inp.teachers}

    recommendations = []

    # ─────────────────────────────────────────────────────────────
    # Trụ cột 1: SƯ PHẠM HỌC SINH (100đ)
    # ─────────────────────────────────────────────────────────────
    ped_penalty = 0.0

    # 1.1 Giãn cách môn 2-3 tiết/tuần
    cls_subj_days = defaultdict(set)
    for s, subj, _teacher in view.placed():
        cls_subj_days[(s.class_id, subj)].add(s.ts.weekday)

    consec_subject_violations = []
    for (cls_id, subj_id), days in cls_subj_days.items():
        n = inp.need.get((subj_id, cls_id), 0)
        # Bỏ qua HĐTN
        subj_obj = next((sb for sb in inp.subjects if sb.subject_id == subj_id), None)
        if subj_obj and subj_obj.role_code == ROLE_HDTN:
            continue
        if n in (2, 3):
            sorted_days = sorted(days)
            for i in range(len(sorted_days) - 1):
                if sorted_days[i + 1] == sorted_days[i] + 1:
                    w1, w2 = sorted_days[i], sorted_days[i + 1]
                    consec_subject_violations.append((cls_id, subj_id, w1, w2))
                    c_name = class_map.get(cls_id, f"Lớp #{cls_id}")
                    s_name = subj_map.get(subj_id, f"Môn #{subj_id}")
                    w1_str = WEEKDAY_NAMES.get(w1, f"T{w1}")
                    w2_str = WEEKDAY_NAMES.get(w2, f"T{w2}")
                    if len(consec_subject_violations) <= 3:
                        recommendations.append({
                            "type": "info",
                            "category": "Sư phạm",
                            "message": f"{c_name}: Môn {s_name} học 2 ngày liên tiếp ({w1_str} - {w2_str}) — khuyến nghị giãn cách thêm nếu điều kiện khung cho phép.",
                        })
    # Tiêu chí phụ: chỉ trừ nhẹ tối đa 5 điểm toàn trường để không lấn át tiêu chuẩn chính của trường
    ped_penalty += min(5.0, len(consec_subject_violations) * 0.5)

    # 1.2 Trần môn nặng liên tiếp
    heavy_run_violations = found.get("C.HEAVY_CONSEC", [])
    recommendations += _recommendations(heavy_run_violations, "warning", "Sư phạm")
    ped_penalty += len(heavy_run_violations) * 15.0

    # 1.3 Môn nặng tiết 3 chiều
    heavy_p3_violations = found.get("C.HEAVY_P3", [])
    recommendations += _recommendations(heavy_p3_violations, "warning", "Sư phạm")
    ped_penalty += len(heavy_p3_violations) * 10.0

    # 1.4 GDTC ngoài khung giờ
    gdtc_violations = found.get("C.GDTC_PERIOD", [])
    recommendations += _recommendations(gdtc_violations, "warning", "Sư phạm")
    ped_penalty += len(gdtc_violations) * 10.0

    # 1.5 Cân bằng tải môn học thuật buổi sáng
    acad_overload_violations = found.get("ACAD.MAX", [])
    acad_underload_violations = found.get("ACAD.MIN", [])
    recommendations += _recommendations(acad_overload_violations, "warning", "Sư phạm")
    recommendations += _recommendations(acad_underload_violations, "info", "Sư phạm")
    ped_penalty += min(20.0, len(acad_overload_violations) * 10.0 + len(acad_underload_violations) * 2.0)

    pedagogical_score = max(0.0, min(100.0, 100.0 - ped_penalty))

    # ─────────────────────────────────────────────────────────────
    # Trụ cột 2: TIỆN NGHI & CÔNG BẰNG GIÁO VIÊN (100đ)
    # ─────────────────────────────────────────────────────────────
    teacher_penalty = 0.0

    # 2.1 Tiết trống giữa buổi & Lũy tiến gaps (không có buổi trống thì không có gap lũy tiến)
    gaps_list = found.get("II.7", [])
    extra_gap1, extra_gap2 = (
        _count_teacher_excess_gaps(inp.slots, view.assignment, view.slot_teacher) if gaps_list else (0, 0)
    )
    teacher_penalty += min(30.0, len(gaps_list) * 1.5) + min(10.0, extra_gap1 * 1.0) + min(10.0, extra_gap2 * 2.0)
    recommendations += _recommendations(gaps_list[:5], "warning", "Giáo viên")

    # 2.2 Chống nhảy ca gắt (chiều muộn -> sáng sớm) - Tiêu chí phụ
    t_late = set()
    t_early = set()
    for s, _subj, tid in view.placed():
        if tid is None:
            continue
        if s.ts.session == "C" and s.ts.period in (4, 5):
            t_late.add((tid, s.ts.weekday, s.ts.period))
        elif s.ts.session == "S" and s.ts.period == 1:
            t_early.add((tid, s.ts.weekday))

    b2b_violations = []
    for (tid, wd, p_late) in t_late:
        if (tid, wd + 1) in t_early:
            b2b_violations.append((tid, wd, p_late))
            tname = teacher_map.get(tid, f"GV #{tid}")
            wd_str = WEEKDAY_NAMES.get(wd, f"Thứ {wd}")
            wd_next_str = WEEKDAY_NAMES.get(wd + 1, f"Thứ {wd+1}")
            if len(b2b_violations) <= 3:
                recommendations.append({
                    "type": "info",
                    "category": "Giáo viên",
                    "message": f"{tname}: Dạy chiều muộn {wd_str} (tiết {p_late}) và sáng sớm hôm sau {wd_next_str} (tiết 1) — thời gian nghỉ ngơi hơi sát.",
                })
    teacher_penalty += min(3.0, len(b2b_violations) * 1.0)

    # 2.3 Trần dạy tiết/ngày
    day_cap_violations = found.get("T.DAY_CAP", [])
    recommendations += _recommendations(day_cap_violations, "error", "Giáo viên")
    teacher_penalty += len(day_cap_violations) * 15.0

    # 2.4 Dạy 4 tiết sáng liên tiếp
    consec_morning_violations = found.get("II.14", [])
    recommendations += _recommendations(consec_morning_violations, "info", "Giáo viên")
    teacher_penalty += len(consec_morning_violations) * 5.0

    teacher_score = max(0.0, min(100.0, 100.0 - teacher_penalty))

    # ─────────────────────────────────────────────────────────────
    # Trụ cột 3: TUÂN THỦ HĐSP & KẾ HOẠCH (100đ)
    # ─────────────────────────────────────────────────────────────
    compliance_penalty = 0.0

    # 3.1 Trùng lịch
    conflicts = found.get("T.CONFLICT", [])
    compliance_penalty += len(conflicts) * 100.0
    recommendations += _recommendations(conflicts, "error", "Tuân thủ")

    # 3.2 Vi phạm giờ bận
    busy_violations = found.get("T.BUSY", [])
    compliance_penalty += len(busy_violations) * 50.0
    recommendations += _recommendations(busy_violations, "error", "Tuân thủ")

    # 3.3 Buổi lẻ 1 tiết & Ngày lẻ (II.4)
    lone_sessions = [v for v in found.get("II.4", []) if v.session is not None]
    lone_days = [v for v in found.get("II.4", []) if v.session is None]
    compliance_penalty += (len(lone_sessions) + len(lone_days)) * 15.0

    # 3.4 Ngày chia lẻ (II.8)
    split_days = found.get("II.8", [])
    compliance_penalty += len(split_days) * 15.0

    # 3.5 Thiếu sáng bắt buộc (II.3)
    missing_morning = found.get("II.3", [])
    compliance_penalty += min(20.0, len(missing_morning) * 4.0)

    compliance_score = max(0.0, min(100.0, 100.0 - compliance_penalty))

    # ─────────────────────────────────────────────────────────────
    # Tổng kết điểm & xếp loại
    # ─────────────────────────────────────────────────────────────
    overall_score = round(0.40 * pedagogical_score + 0.35 * teacher_score + 0.25 * compliance_score, 1)

    if overall_score >= 90.0:
        rating = "Xuất sắc"
        badge_color = "#28a745"
    elif overall_score >= 80.0:
        rating = "Tốt"
        badge_color = "#17a2b8"
    elif overall_score >= 70.0:
        rating = "Khá"
        badge_color = "#ffc107"
    else:
        rating = "Cần cải thiện"
        badge_color = "#dc3545"

    if not recommendations:
        recommendations.append({
            "type": "success",
            "category": "Tổng quan",
            "message": "Thời khóa biểu đạt tiêu chuẩn xuất sắc: các môn học phân bổ khoa học, giáo viên không bị phân mảnh lịch dạy.",
        })

    return {
        "overall_score": overall_score,
        "pedagogical_score": round(pedagogical_score, 1),
        "teacher_score": round(teacher_score, 1),
        "compliance_score": round(compliance_score, 1),
        "rating": rating,
        "badge_color": badge_color,
        "metrics": {
            "consecutive_subject_days": len(consec_subject_violations),
            "heavy_excess_runs": len(heavy_run_violations),
            "heavy_afternoon_p3": len(heavy_p3_violations),
            "gdtc_violations": len(gdtc_violations),
            "morning_academic_overload": len(acad_overload_violations),
            "morning_academic_underload": len(acad_underload_violations),
            "teacher_gaps_total": len(gaps_list),
            "teacher_excess_gaps": extra_gap1 + extra_gap2,
            "teacher_back_to_back": len(b2b_violations),
            "teacher_4_consec_mornings": len(consec_morning_violations),
            "teacher_day_cap_violations": len(day_cap_violations),
            "conflicts": len(conflicts),
            "busy_violations": len(busy_violations),
            "lone_sessions": len(lone_sessions),
            "lone_days": len(lone_days),
            "split_days": len(split_days),
            "missing_mornings": len(missing_morning),
        },
        "recommendations": recommendations,
    }
```

- [ ] **Step 6: Chạy test**

Run: `python -m pytest tests/test_tkb_quality_scoring.py tests/test_morning_academic_balance.py -q`
Expected: PASS. Nếu một test cũ đổi kết quả, **dừng**: tìm luật nào gây ra (thường là cờ tắt hoặc `pinned_full_day_off`), giải thích trong báo cáo task trước khi sửa gì.

- [ ] **Step 7: Commit**

```bash
git add core/validation.py tests/test_tkb_quality_scoring.py
git commit -m "refactor: score TKB health from shared rule detectors"
```

---

### Task 7: Mô hình CP-SAT đọc ngưỡng cố định từ `built.params`

**Files:**
- Modify: `core/scheduler/cpsat/types.py` (thêm trường `params`)
- Modify: `core/scheduler/cpsat_model.py:12-63,152-155`
- Modify: `core/scheduler/cpsat/constraints.py:22-26,120-127,140`
- Modify: `core/scheduler/cpsat/objectives.py:5,61-73,97,111-118,214,275-277,286,392,397`
- Modify: `core/scheduler/cpsat/solver.py:4,10,220-232,247,50-60`
- Modify: `core/models.py:210-223` (`ScheduleResult.effective_params`)
- Test: `tests/test_rule_params.py` (thêm 1 test)

**Interfaces:**
- Consumes: `resolve_effective_params(inp)`.
- Produces: `CpSatModel.params: EffectiveParams` (gắn trong `build_model`); `ScheduleResult.effective_params` (chính object `built.params`). Ngưỡng **thích ứng** (`_get_eff_max_heavy`, khối học thuật `constraints.py:434-455`) **không** đụng tới — thuộc Plan 2.

- [ ] **Step 1: Chạy impact**

MCP `impact` upstream cho: `build_model`, `build_result`, `_add_teacher_constraints`, `_add_objective`, `_presolve_capacity_screening`. Báo rủi ro; dừng hỏi nếu HIGH/CRITICAL.

- [ ] **Step 2: Viết test**

Thêm vào cuối `tests/test_rule_params.py`:
```python
def test_solver_result_carries_the_params_the_model_was_built_with():
    cpsat = pytest.importorskip("core.scheduler.cpsat_model")
    slots = [Slot(1, 101, TimeSlot(1, 3, "S", 1)), Slot(2, 101, TimeSlot(2, 4, "S", 1))]
    inp = make_input(
        slots, assigned_teacher={(1, 101): 10}, need={(1, 101): 2},
        config=SchedulingConfig(teacher_off_sessions_per_week=0, mandatory_morning_weekdays=(),
                                min_weekly_periods_for_lone_penalty=5),
    )
    built = cpsat.build_model(inp)
    result = cpsat.solve_to_result(built, time_limit_s=10.0)
    assert result.effective_params is built.params
    assert built.params == resolve_effective_params(inp)
```

- [ ] **Step 3: Chạy test để thấy nó đỏ**

Run: `python -m pytest tests/test_rule_params.py -q -n 0`
Expected: FAIL với `AttributeError: 'CpSatModel' object has no attribute 'params'`

- [ ] **Step 4: Thêm trường**

`core/scheduler/cpsat/types.py`, cuối dataclass `CpSatModel`:
```python
    params: object = None                              # EffectiveParams, attached by build_model()
```
`core/models.py`, cuối dataclass `ScheduleResult`:
```python
    effective_params: object = None  # core.rules.params.EffectiveParams the model was built with; None for non-CP-SAT results
```

- [ ] **Step 5: `build_model` resolve params một lần**

`core/scheduler/cpsat_model.py` — thêm import sau dòng `from core.roles import resolve_roles`:
```python
from core.rules.params import resolve_effective_params
```
Sau dòng `config = inp.config` (dòng 60) thêm:
```python
    params = resolve_effective_params(inp)
```
Thay dòng tạo `built` (152–154):
```python
    built = CpSatModel(model=m, x=x, inp=inp,
                       slots_by_class=dict(slots_by_class),
                       slots_by_ts=dict(slots_by_ts),
                       params=params)
```

- [ ] **Step 6: `build_result` mang params ra ngoài**

`core/scheduler/cpsat/solver.py`, trong `return ScheduleResult(...)` của `build_result`, thêm tham số sau `diagnostics=diagnostics or {},`:
```python
        effective_params=built.params,
```

- [ ] **Step 7: `constraints.py` — trần tiết/buổi và tiết/ngày**

Trong `_add_teacher_constraints`, thay:
```python
    m = built.model
    inp = built.inp
    config = inp.config
    slot_by_id = {s.slot_id: s for s in inp.slots}
```
bằng:
```python
    m = built.model
    inp = built.inp
    params = built.params
    slot_by_id = {s.slot_id: s for s in inp.slots}
```
và thay:
```python
    # 3. Trần tiết/buổi.
    for vs in vars_by_teacher_session.values():
        m.Add(sum(vs) <= config.max_periods_per_session)

    # 4. Trần tiết/ngày.
    max_teacher_day = getattr(config, "max_teacher_periods_per_day", 5)
    for vs in vars_by_teacher_day.values():
        m.Add(sum(vs) <= max_teacher_day)
```
bằng:
```python
    # 3. Trần tiết/buổi.
    for vs in vars_by_teacher_session.values():
        m.Add(sum(vs) <= params.max_periods_per_session)

    # 4. Trần tiết/ngày. Hậu kiểm đối chứng: core/rules/detectors.py:detect_teacher_day_cap
    for vs in vars_by_teacher_day.values():
        m.Add(sum(vs) <= params.max_teacher_periods_per_day)
```

Trong `_add_off_day_constraints`, thay:
```python
    mandatory_mornings = set(getattr(config, "mandatory_morning_weekdays", (2, 5, 6)))
```
bằng:
```python
    mandatory_mornings = set(built.params.mandatory_morning_weekdays)
```
(Chỉ đổi nguồn đọc; logic buổi nghỉ không đổi — thiết kế lại thuộc Plan 3, Nhóm B.)

- [ ] **Step 8: `objectives.py` — tải, ngưỡng, cờ**

Dòng 5: `from core.models import SchedulingInput, is_bgh` → `from core.models import SchedulingInput`

Thay khối đầu `_add_objective`:
```python
    m = built.model
    inp = built.inp
    config = inp.config
    x = built.x
    teacher_of = built.teacher_of
    effective_assigned = _build_effective_assigned_teacher(inp)

    load = defaultdict(int)
    for (subj_id, cls_id), n in inp.need.items():
        if n > 0:
            tid = effective_assigned.get((subj_id, cls_id))
            if tid is not None and tid > 0:
                load[tid] += n
```
bằng:
```python
    m = built.model
    inp = built.inp
    config = inp.config
    params = built.params
    x = built.x
    teacher_of = built.teacher_of
    effective_assigned = _build_effective_assigned_teacher(inp)
    load = params.teacher_load
```
Dòng 97: `c = m.NewIntVar(0, config.max_periods_per_session, f"cnt_t{t}_wd{wd}_{sess}")` → `c = m.NewIntVar(0, params.max_periods_per_session, f"cnt_t{t}_wd{wd}_{sess}")`

Thay khối 111–117:
```python
    avoid_lone = getattr(config, "avoid_teacher_lone_periods", True)
    min_lone_load = getattr(config, "min_weekly_periods_for_lone_penalty", 8)
    lone_exempt = getattr(config, "lone_session_exempt_teacher_ids", frozenset()) or frozenset()
    mand_morns = getattr(config, "mandatory_morning_weekdays", (2, 5, 6))
    strict_morns = getattr(config, "strict_morning_weekdays", ()) or ()
    min_mand_load = getattr(config, "min_weekly_periods_for_mandatory_morning", 10)
    bgh_ids = frozenset(t.teacher_id for t in inp.teachers if is_bgh(t))
```
bằng:
```python
    avoid_lone = params.flags["avoid_teacher_lone_periods"]
    min_lone_load = params.min_weekly_periods_for_lone_penalty
    lone_exempt = params.lone_exempt_ids
    mand_morns = params.mandatory_morning_weekdays
    strict_morns = params.strict_morning_weekdays
    min_mand_load = params.min_weekly_periods_for_mandatory_morning
    bgh_ids = params.bgh_ids
```
Các dòng đơn:
- `    if getattr(config, "avoid_teacher_gaps", True):` → `    if params.flags["avoid_teacher_gaps"]:`
- `    if getattr(config, "avoid_teacher_4_consecutive_morning", True):` → `    if params.flags["avoid_teacher_4_consecutive_morning"]:`
- `            if load[t] <= 20:` → `            if load[t] <= params.max_load_for_4consec_penalty:`
- `    if getattr(config, "balance_afternoon_teachers", True):` → `    if params.flags["balance_afternoon_teachers"]:`
- `    if getattr(config, "balance_morning_academic_load", True):` (dòng 392, trong `_add_objective`) → `    if params.flags["balance_morning_academic_load"]:`
- `        min_academic = getattr(config, "min_academic_per_morning", 2)` → `        min_academic = params.min_academic_per_morning`

- [ ] **Step 9: `solver.py` — sàng lọc tiền giải**

Dòng 4 `from collections import defaultdict` → xóa. Dòng 10 `from core.models import ScheduleResult, is_bgh, ROLE_HDTN` → `from core.models import ScheduleResult, ROLE_HDTN`.

Trong `_presolve_capacity_screening`, thay:
```python
    config = built.inp.config
    mand_morns = getattr(config, "mandatory_morning_weekdays", (2, 5, 6))
    strict_morns = getattr(config, "strict_morning_weekdays", ())
    min_mand_load = getattr(config, "min_weekly_periods_for_mandatory_morning", 10)
    bgh_ids = {t.teacher_id for t in built.inp.teachers if is_bgh(t)}

    load = defaultdict(int)
    for (s_id, c_id), n in built.inp.need.items():
        t_id = built.inp.assigned_teacher.get((s_id, c_id))
        if t_id is not None and t_id > 0:
            load[t_id] += n
```
bằng:
```python
    config = built.inp.config
    params = built.params
    mand_morns = params.mandatory_morning_weekdays
    strict_morns = params.strict_morning_weekdays
    min_mand_load = params.min_weekly_periods_for_mandatory_morning
    bgh_ids = params.bgh_ids
    load = params.teacher_load  # same effective teacher map the objective uses (spec A5)
```
và:
```python
            is_mand = (wd in mand_morns and wd not in strict_morns and load[t.teacher_id] >= min_mand_load)
```
→
```python
            is_mand = (wd in mand_morns and wd not in strict_morns and load.get(t.teacher_id, 0) >= min_mand_load)
```

- [ ] **Step 10: Kiểm tra không còn getattr cho ngưỡng đã chuyển**

Run: `grep -rn "getattr(config, \"\(min_weekly_periods_for_lone_penalty\|lone_session_exempt_teacher_ids\|mandatory_morning_weekdays\|strict_morning_weekdays\|min_weekly_periods_for_mandatory_morning\|max_teacher_periods_per_day\|min_academic_per_morning\|avoid_teacher_lone_periods\|avoid_teacher_gaps\|avoid_teacher_4_consecutive_morning\|balance_afternoon_teachers\)\"" core/scheduler/cpsat/`
Expected: không có kết quả. (`balance_morning_academic_load` và `heavy_subjects_morning_only` vẫn còn trong khối thích ứng của `constraints.py` — đúng, Plan 2 xử lý.)

- [ ] **Step 11: Chạy test**

Run: `python -m pytest tests/test_rule_params.py -q -n 0` rồi `python -m pytest -q -m "not slow"` rồi `python -m pytest -q -m slow tests/test_cpsat_engine_integration.py tests/test_cpsat_pinpoint_diagnosis.py tests/test_cpsat_tiered_diagnosis.py tests/test_pinned_off_override.py tests/test_teacher_busy_morning_conflict.py`
Expected: PASS toàn bộ. Đây là refactor giữ nguyên hành vi; test nào đổi kết quả nghĩa là một ngưỡng bị đọc sai — so lại với dòng gốc, không sửa test.

- [ ] **Step 12: Commit**

```bash
git add core/scheduler/cpsat/types.py core/scheduler/cpsat_model.py core/scheduler/cpsat/constraints.py core/scheduler/cpsat/objectives.py core/scheduler/cpsat/solver.py core/models.py tests/test_rule_params.py
git commit -m "refactor: read fixed rule thresholds from EffectiveParams in CP-SAT model"
```

---

### Task 8: `classify` và `RuleSpec.blocks_save`

**Files:**
- Modify: `core/rules/violations.py` (thêm `classify`)
- Modify: `core/rules/__init__.py` (`RuleSpec.blocks_save`)
- Test: `tests/test_rule_classify.py`

**Interfaces:**
- Consumes: `Violation`, `EffectiveParams`, `Threshold`, `RULES`, `RuleTier`.
- Produces: `classify(violations: list[Violation], params: EffectiveParams) -> list[Violation]`; `RuleSpec.blocks_save: bool = False` (True cho II.3, II.4, II.8). Plan 2 sẽ thêm tham số thứ ba `relaxations`.

- [ ] **Step 1: Viết test**

`tests/test_rule_classify.py`:
```python
from dataclasses import replace

from core.models import Slot, TimeSlot
from core.rules import HARD_POST_GENERATION_IDS, RULES
from core.rules.params import Threshold, resolve_effective_params
from core.rules.violations import BREACH, FORCED, SHORTFALL, Violation, classify
from tests.rule_helpers import make_input

WIDEN_REASON = "lớp 101 cần 14 tiết nặng trên 4 buổi sáng, tối thiểu 4 tiết/buổi"


def _params_with_heavy_cap(effective: int):
    slots = [Slot(1, 101, TimeSlot(1, 2, "S", 1)), Slot(2, 101, TimeSlot(2, 2, "C", 1))]
    params = resolve_effective_params(make_input(slots))
    widened = {
        (101, "S"): Threshold(declared=3, effective=effective, reason=WIDEN_REASON if effective != 3 else ""),
        (101, "C"): Threshold.unrelaxed(3),
    }
    return replace(params, max_heavy_consecutive=widened)


def _heavy_run(session="S", length=4):
    return Violation("C.HEAVY_CONSEC", class_id=101, weekday=3, session=session, period=1, count=length)


def test_soft_rule_is_a_shortfall_never_a_breach():
    [classified] = classify([Violation("II.7", teacher_id=1)], _params_with_heavy_cap(3))
    assert classified.level == SHORTFALL


def test_hard_violation_without_widened_threshold_stays_breach():
    [classified] = classify([_heavy_run()], _params_with_heavy_cap(3))
    assert classified.level == BREACH and classified.evidence == ""


def test_widened_threshold_at_the_same_scope_makes_it_forced_with_evidence():
    [classified] = classify([_heavy_run()], _params_with_heavy_cap(4))
    assert classified.level == FORCED
    assert classified.evidence == WIDEN_REASON


def test_widening_elsewhere_does_not_excuse_this_scope():
    [classified] = classify([_heavy_run(session="C")], _params_with_heavy_cap(4))
    assert classified.level == BREACH


def test_violation_beyond_the_widened_threshold_stays_breach():
    [classified] = classify([_heavy_run(length=5)], _params_with_heavy_cap(4))
    assert classified.level == BREACH


def test_classify_never_drops_a_violation():
    violations = [_heavy_run(), _heavy_run(session="C"), Violation("II.7", teacher_id=1)]
    assert len(classify(violations, _params_with_heavy_cap(4))) == len(violations)


def test_only_hdsp_hard_gate_rules_block_save_for_now():
    assert {rule_id for rule_id, rule in RULES.items() if rule.blocks_save} == set(HARD_POST_GENERATION_IDS)
```

- [ ] **Step 2: Chạy test để thấy nó đỏ**

Run: `python -m pytest tests/test_rule_classify.py -q -n 0`
Expected: FAIL với `ImportError: cannot import name 'classify'`

- [ ] **Step 3: Thêm `blocks_save` vào registry**

`core/rules/__init__.py`, trong `RuleSpec` sau `config_flag`:
```python
    blocks_save: bool = False  # a BREACH of this rule disables the save button until the user overrides
```
Thêm `blocks_save=True,` vào ba mục `"II.3"`, `"II.4"`, `"II.8"` (ngay sau dòng `config_flag=...` của mỗi mục).

- [ ] **Step 4: Thêm `classify` vào `core/rules/violations.py`**

Đổi khối import đầu file thành:
```python
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Iterable, Literal, Optional

from core.rules import RULES, RuleTier

if TYPE_CHECKING:
    from core.rules.params import EffectiveParams
```
Thêm vào cuối file:
```python
# Where a violation's own scope has an adaptive threshold. Only these rules can be
# FORCED from a threshold; Plan 2 adds result.relaxations as the second evidence source.
_SCOPED_THRESHOLD = {
    "C.HEAVY_CONSEC": lambda params, v: params.max_heavy_consecutive.get((v.class_id, v.session)),
    "ACAD.MAX": lambda params, v: params.max_academic_per_morning.get(v.class_id),
}


def classify(violations: list, params: "EffectiveParams") -> list:
    """Attach a level to the BREACHes detectors return.

    SOFT rules become SHORTFALL. A hard violation becomes FORCED only when the
    threshold at its OWN scope was widened by the model, with a reason, and the
    violation fits within the widened value. Nothing is ever dropped.
    """
    return [_classify_one(violation, params) for violation in violations]


def _classify_one(violation: Violation, params: "EffectiveParams") -> Violation:
    if RULES[violation.rule_id].tier is RuleTier.SOFT:
        return replace(violation, level=SHORTFALL)
    evidence = _threshold_evidence(violation, params)
    return replace(violation, level=FORCED, evidence=evidence) if evidence else violation


def _threshold_evidence(violation: Violation, params: "EffectiveParams") -> str:
    lookup = _SCOPED_THRESHOLD.get(violation.rule_id)
    threshold = lookup(params, violation) if lookup else None
    if threshold is None or threshold.effective == threshold.declared or violation.count is None:
        return ""
    return threshold.reason if violation.count <= threshold.effective else ""
```

- [ ] **Step 5: Chạy test**

Run: `python -m pytest tests/test_rule_classify.py tests/test_rule_detectors.py tests/test_rules_registry.py -q -n 0`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add core/rules/violations.py core/rules/__init__.py tests/test_rule_classify.py
git commit -m "feat: classify violations into BREACH, FORCED and SHORTFALL"
```

---

### Task 9: Giao diện xếp TKB dùng detectors; xóa toàn bộ `find_*`

**Files:**
- Modify: `pages/06_Xep_TKB.py` (import, `_format_rule_item`, khối kiểm tra tuần đơn ~541–696, khối kiểm tra theo lô ~993–1060, hai nút lưu 723 và 1078, dòng 947)
- Modify: `core/validation.py` (xóa `find_*` và `_is_teacher_busy_on_morning`, sửa docstring)
- Delete: `tests/test_validation_hdsp_rules.py` (đã chuyển ở Task 4)
- Modify: `tests/test_scheduler_teacher_quality.py` (xóa `test_validation_helpers`, `test_validation_new_helpers` — đã chuyển ở Task 4/5)
- Modify: `tests/test_morning_academic_balance.py`, `tests/test_cpsat_model.py`, `tests/test_cpsat_engine_integration.py`, `tests/test_mandatory_rules_compliance.py`, `tests/test_real_data_schedule.py`, `tests/test_regression_hard_gate_2026_09_02.py`, `tests/test_scheduler.py`

**Interfaces:**
- Consumes: `build_schedule_view`, `resolve_effective_params`, `run_detectors`, `classify`, `group_by_rule`, `BREACH/FORCED/SHORTFALL`, `RULES[...].blocks_save`, `violations_of`.
- Produces: `core.validation` chỉ còn `compute_actual_counts`, `compute_quota_diff`, `compute_tkb_health_score`.

- [ ] **Step 1: Chạy impact**

MCP `impact` upstream cho từng `find_*` trong `core/validation.py`. Danh sách caller phải khớp với các file ở mục **Files** trên; caller nào ngoài danh sách → thêm vào task này trước khi xóa.

- [ ] **Step 2: Xóa detector cũ trong `core/validation.py`**

Xóa mọi hàm từ `def find_teacher_conflicts` tới hết `def find_teacher_4_consecutive_morning_violations` (gồm cả `_is_teacher_busy_on_morning`). Thay docstring module (dòng 1–4) bằng:
```python
"""Quota checks (KiemTra sheet port) and the TKB health score.

Rule violations are detected in core/rules/detectors.py; this module only
compares quotas and turns detector output into a 100-point score.
"""
```

- [ ] **Step 3: Chạy test để thấy phạm vi vỡ**

Run: `python -m pytest -q -m "not slow" -p no:xdist 2>&1 | tail -20`
Expected: FAIL với `ImportError: cannot import name 'find_...' from 'core.validation'` ở các file test liệt kê trong **Files**. Đây là danh sách việc của các bước sau.

- [ ] **Step 4: Xóa các test đã chuyển**

```bash
git rm tests/test_validation_hdsp_rules.py
```
Trong `tests/test_scheduler_teacher_quality.py`: xóa trọn hai hàm `test_validation_helpers` (bắt đầu dòng 157) và `test_validation_new_helpers` (bắt đầu dòng 286).

Trong `tests/test_morning_academic_balance.py`: xóa trọn hai hàm `test_find_morning_academic_overload_violations` và `test_find_morning_academic_underload_violations`, và hàm `_make_slot` nếu không còn ai dùng (`grep -n "_make_slot" tests/test_morning_academic_balance.py`).

- [ ] **Step 5: Chuyển điểm gọi trong `tests/test_morning_academic_balance.py`**

Thay khối import:
```python
from core.validation import (
    find_morning_academic_overload_violations,
    find_morning_academic_underload_violations,
)
```
bằng:
```python
from tests.rule_helpers import violations_of
```
Thay:
```python
    academic_ids = {1, 2, 3, 4}
    overloads = find_morning_academic_overload_violations(inp.slots, assignment, academic_ids, max_academic=3)
```
bằng:
```python
    academic_ids = {1, 2, 3, 4}
    overloads = violations_of("ACAD.MAX", inp, assignment)
```
Thay:
```python
    underloads = find_morning_academic_underload_violations(inp.slots, assignment, academic_ids, min_academic=2)
```
bằng:
```python
    underloads = violations_of("ACAD.MIN", inp, assignment)
```
(`academic_ids` vẫn được dùng ở phép đếm ngay bên dưới — giữ nguyên.)

- [ ] **Step 6: Chuyển 10 điểm gọi trong `tests/test_cpsat_model.py`**

Thêm `from tests.rule_helpers import violations_of` vào khối import đầu file. Rồi thay từng cặp dòng (mỗi cặp là `from core.validation import X` + dòng assert ngay sau):

| Dòng | Thay bằng |
|---|---|
| 98–99 | `    assert violations_of("T.CONFLICT", inp, assignment) == []` |
| 122–124 | `    assert violations_of("T.BUSY", inp, assignment) == []` |
| 179–181 | `    assert violations_of("T.DAY_CAP", inp_ok, assignment) == []` |
| 214–215 | `    assert violations_of("C.MORNING_ONLY", inp, assignment) == []` |
| 285–288 | `    assert violations_of("C.GDTC_PERIOD", inp, assignment) == []` |
| 312–313 | `    assert violations_of("C.NON_CONSEC_DAYS", inp, assignment) == []` |
| 373–374 | `    assert violations_of("C.HEAVY_CONSEC", inp_ok, assignment) == []` |
| 448–449 | `    assert violations_of("C.HEAVY_P3", inp, assignment) == []` |
| 688–690 | `    assert violations_of("C.SUBJECT_CELLS", inp, assignment) == []` |
| 841–842 | `    assert violations_of("C.SINGLE_PAIR", inp, assignment) == []` |

Ngưỡng tương đương đã kiểm: mỗi test đặt ngưỡng qua `SchedulingConfig` trùng với tham số tường minh cũ (`max_teacher_periods_per_day=3`, `max_heavy_consecutive=2`, `morning_only_subject_ids={1}`, `non_consecutive_subject_ids={1}`, `single_pair_subject_ids={1}`, `subject_class_allowed_cells={(1,101): {(3,"S")}}`, `gdtc_morning_allowed_periods=(1,)`). Trong `test_max_heavy_per_session`, dòng `    heavy_ids = {1, 2, 3}` trở thành không dùng — xóa nó.

- [ ] **Step 7: Chuyển `tests/test_cpsat_engine_integration.py`**

Thay khối import `from core.validation import (...)` (dòng 9–19) bằng:
```python
from core.validation import compute_quota_diff
from tests.rule_helpers import violations_of
```
Thay toàn bộ khối từ dòng `    # 2. Teacher conflicts` tới hết assert của `    # 9. Subject class rules` bằng:
```python
    # 2-9. Mọi ràng buộc cứng mô hình ép phải không có vi phạm hậu kiểm
    for rule_id in ("T.CONFLICT", "T.BUSY", "T.DAY_CAP", "C.GDTC_PERIOD", "C.MORNING_ONLY",
                    "C.HEAVY_CONSEC", "C.NON_CONSEC_DAYS", "C.SUBJECT_CELLS"):
        found = violations_of(rule_id, inp, result.assignment)
        assert found == [], f"{rule_id} violations: {found}"
```

- [ ] **Step 8: Chuyển `tests/test_mandatory_rules_compliance.py` (hàm `test_full_schedule_15_criteria_compliance`)**

Thay:
```python
    from core.models import ROLE_GDTC, ROLE_HDTN, ROLE_NANG, ROLE_NANG_KEP, SchedulingConfig
    from core.validation import (
        compute_quota_diff, find_consecutive_subject_days, find_heavy_afternoon_period3_violations,
        find_invalid_gdtc_periods, find_max_heavy_violations, find_teacher_conflicts,
        find_teacher_day_cap_violations, find_teacher_gaps,
        find_teacher_lone_day_violations, find_teacher_lone_session_violations,
        find_teacher_missing_mandatory_morning_violations, find_teacher_split_day_violations,
    )
```
bằng:
```python
    from core.models import ROLE_HDTN, SchedulingConfig
    from core.validation import compute_quota_diff
    from tests.rule_helpers import violations_of
```
Thay từng dòng:
- `    conflicts = find_teacher_conflicts(inp.slots, result.assignment, inp.assigned_teacher)` → `    conflicts = violations_of("T.CONFLICT", inp, result.assignment)`
- `    day_cap_violations = find_teacher_day_cap_violations(inp.slots, result.assignment, inp.assigned_teacher, max_per_day=5)` → `    day_cap_violations = violations_of("T.DAY_CAP", inp, result.assignment)`
- Xóa `    gdtc_id = next(s.subject_id for s in inp.subjects if s.role_code == ROLE_GDTC)`
- `    gdtc_violations = find_invalid_gdtc_periods(inp.slots, result.assignment, gdtc_id)` → `    gdtc_violations = violations_of("C.GDTC_PERIOD", inp, result.assignment)`
- `    gdtc_consec = find_consecutive_subject_days(inp.slots, result.assignment, {gdtc_id})` → `    gdtc_consec = violations_of("C.NON_CONSEC_DAYS", inp, result.assignment)`
- Xóa `    heavy_ids = {s.subject_id for s in inp.subjects if s.role_code in (ROLE_NANG, ROLE_NANG_KEP)}`
- `    heavy_runs = find_max_heavy_violations(inp.slots, result.assignment, heavy_ids, max_consecutive=3)` → `    heavy_runs = violations_of("C.HEAVY_CONSEC", inp, result.assignment)`
- `    heavy_p3 = find_heavy_afternoon_period3_violations(inp.slots, result.assignment, heavy_ids)` → `    heavy_p3 = violations_of("C.HEAVY_P3", inp, result.assignment)`
- `    missing_morning = find_teacher_missing_mandatory_morning_violations(inp.slots, result.assignment, inp.assigned_teacher)` → `    missing_morning = violations_of("II.3", inp, result.assignment)`

Thay bốn dòng:
```python
    min_lone_load = config.min_weekly_periods_for_lone_penalty
    lone_sessions = find_teacher_lone_session_violations(inp.slots, result.assignment, inp.assigned_teacher, min_lone_load)
    lone_days = find_teacher_lone_day_violations(inp.slots, result.assignment, inp.assigned_teacher, min_lone_load)
    assert not (lone_sessions or lone_days) or "II.4" in relaxed_ids, f"Unreported II.4 violations: {lone_sessions + lone_days}"
```
bằng:
```python
    lone = violations_of("II.4", inp, result.assignment)
    assert not lone or "II.4" in relaxed_ids, f"Unreported II.4 violations: {lone}"
```
và `    split_days = find_teacher_split_day_violations(inp.slots, result.assignment, inp.assigned_teacher, min_lone_load)` → `    split_days = violations_of("II.8", inp, result.assignment)`

- [ ] **Step 9: Chuyển ba file còn lại**

`tests/test_real_data_schedule.py`: dòng 7 → `from core.validation import compute_quota_diff` và thêm `from tests.rule_helpers import violations_of`; thay cả 3 lần `conflicts = find_teacher_conflicts(inp.slots, result.assignment, inp.assigned_teacher)` → `conflicts = violations_of("T.CONFLICT", inp, result.assignment)`.

`tests/test_scheduler.py` (~dòng 666–671): `    from core.validation import compute_quota_diff, find_teacher_conflicts` → hai dòng `    from core.validation import compute_quota_diff` và `    from tests.rule_helpers import violations_of`; `    conflicts = find_teacher_conflicts(inp.slots, result.assignment, assigned_teacher)` → `    conflicts = violations_of("T.CONFLICT", inp, result.assignment)`.

`tests/test_regression_hard_gate_2026_09_02.py`: dòng 13 → `from tests.rule_helpers import violations_of`. Thay:
```python
    min_lone_load = config.min_weekly_periods_for_lone_penalty
    lone_sessions = find_teacher_lone_session_violations(inp.slots, result.assignment, inp.assigned_teacher, min_lone_load)
    lone_days = find_teacher_lone_day_violations(inp.slots, result.assignment, inp.assigned_teacher, min_lone_load)

    if lone_sessions or lone_days:
        relaxed_ids = {item.get("rule_id") for item in result.relaxed_rules}
        assert "II.4" in relaxed_ids, (
            f"Regression: found unreported lone-session/day violations "
            f"{lone_sessions + lone_days} with empty/non-matching relaxed_rules {result.relaxed_rules}"
        )
```
bằng:
```python
    lone = violations_of("II.4", inp, result.assignment)

    if lone:
        relaxed_ids = {item.get("rule_id") for item in result.relaxed_rules}
        assert "II.4" in relaxed_ids, (
            f"Regression: found unreported lone-session/day violations "
            f"{lone} with empty/non-matching relaxed_rules {result.relaxed_rules}"
        )
```

- [ ] **Step 10: Chạy test phi-UI**

Run: `grep -rn "find_[a-z_0-9]*violations\|find_teacher_\|find_invalid_gdtc\|find_consecutive_subject" --include=*.py core tests pages`
Expected: chỉ còn kết quả trong `pages/06_Xep_TKB.py` (sửa ở bước sau).

Run: `python -m pytest -q -m "not slow"` rồi `python -m pytest -q -m slow`
Expected: PASS.

- [ ] **Step 11: Sửa `pages/06_Xep_TKB.py` — import và helper**

Thay dòng 5–15:
```python
from core.models import ROLE_GDTC, ROLE_HDTN, ROLE_KEP, ROLE_NANG, ROLE_NANG_KEP, WEEKDAY_NAMES, WEEKDAYS, is_bgh
from core.validation import (
    ...
)
from core.rules import RULES
```
bằng:
```python
from core.models import ROLE_HDTN, ROLE_KEP, WEEKDAY_NAMES, WEEKDAYS
from core.rules import RULES
from core.rules.detectors import run_detectors
from core.rules.params import resolve_effective_params
from core.rules.view import build_schedule_view
from core.rules.violations import BREACH, FORCED, SHORTFALL, classify, group_by_rule
from core.validation import compute_quota_diff, compute_tkb_health_score
```
Thay toàn bộ hàm `_format_rule_item` (dòng 22–38) bằng:
```python
def _schedule_violations(inp, result) -> list:
    # getattr: a ScheduleResult kept in st.session_state across a code reload predates this field
    params = getattr(result, "effective_params", None) or resolve_effective_params(inp)
    return classify(run_detectors(build_schedule_view(inp, result.assignment), params), params)


def _write_details(violations: list) -> None:
    for violation in violations:
        st.write(f"- {violation.detail}")


def _render_rule_violations(violations: list, save_override_key: str, week_label: str = "") -> bool:
    """Show violations grouped by level. Returns True when saving is allowed."""
    blocking = group_by_rule(v for v in violations if v.level == BREACH and RULES[v.rule_id].blocks_save)
    other_breaches = group_by_rule(v for v in violations if v.level == BREACH and not RULES[v.rule_id].blocks_save)
    forced = group_by_rule(v for v in violations if v.level == FORCED)
    shortfalls = group_by_rule(v for v in violations if v.level == SHORTFALL)

    for rule_id, items in other_breaches.items():
        st.error(f"❌ {RULES[rule_id].title_vi}: {len(items)} trường hợp{week_label}.")
        with st.expander("Chi tiết", expanded=False):
            _write_details(items)

    if blocking:
        st.error(f"❌ Còn {len(blocking)} tiêu chí HĐSP bắt buộc chưa được thỏa mãn (chặn lưu){week_label}:")
        for rule_id, items in blocking.items():
            with st.expander(f"{rule_id}: {RULES[rule_id].title_vi} ({len(items)} trường hợp)", expanded=False):
                _write_details(items)

    for rule_id, items in forced.items():
        with st.expander(f"⚠️ {RULES[rule_id].title_vi}: {len(items)} trường hợp buộc phải chấp nhận "
                         f"(không chặn lưu){week_label}", expanded=False):
            for violation in items:
                st.write(f"- {violation.detail} — Lý do: {violation.evidence}")

    if shortfalls:
        total = sum(len(items) for items in shortfalls.values())
        with st.expander(f"⚠️ {total} trường hợp thuộc {len(shortfalls)} tiêu chí HĐSP mềm "
                         f"(không chặn lưu){week_label}", expanded=False):
            for rule_id, items in shortfalls.items():
                st.write(f"**{RULES[rule_id].title_vi}** ({len(items)} trường hợp)")
                _write_details(items)

    if not blocking:
        return True
    return st.checkbox("Vẫn lưu dù còn vi phạm tiêu chí HĐSP bắt buộc ở trên (không khuyến khích)",
                       key=save_override_key)
```

- [ ] **Step 12: Sửa luồng tuần đơn**

Thay toàn bộ khối bắt đầu từ dòng
```python
            conflicts = find_teacher_conflicts(inp.slots, result.assignment, inp.assigned_teacher)
```
cho tới **ngay trước** dòng
```python
            st.subheader("Kiểm tra định mức (thực tế − định mức, kỳ vọng 0)")
```
bằng:
```python
            proceed_with_hard_violations = _render_rule_violations(
                _schedule_violations(inp, result), "proceed_with_hard_violations",
            )

```
Thay dòng
```python
                    disabled=bool(hard_rule_violations) and not proceed_with_hard_violations,
```
bằng:
```python
                    disabled=not proceed_with_hard_violations,
```

- [ ] **Step 13: Sửa luồng xếp theo lô**

Thay toàn bộ khối bắt đầu từ dòng
```python
                    b_conflicts = find_teacher_conflicts(b_inp.slots, b_result.assignment, b_inp.assigned_teacher)
```
cho tới hết khối
```python
                    b_proceed_with_hard_violations = True
                    if b_hard_rule_violations:
                        b_proceed_with_hard_violations = st.checkbox(
                            "Vẫn lưu dù còn vi phạm tiêu chí HĐSP bắt buộc ở trên (không khuyến khích)",
                            key=f"batch_proceed_with_hard_violations_{wn}",
                        )
```
bằng:
```python
                    b_proceed_with_hard_violations = _render_rule_violations(
                        _schedule_violations(b_inp, b_result), f"batch_proceed_with_hard_violations_{wn}",
                        f" cho Tuần {wn}",
                    )
```
Thay dòng
```python
                        disabled=bool(b_hard_rule_violations) and not b_proceed_with_hard_violations,
```
bằng:
```python
                        disabled=not b_proceed_with_hard_violations,
```
Xóa dòng `                    b_teacher_map = {t.teacher_id: t.name for t in b_inp.teachers}` nếu `grep -n "b_teacher_map" pages/06_Xep_TKB.py` chỉ còn đúng dòng đó.

- [ ] **Step 14: Kiểm tra tĩnh trang**

Run: `python -m py_compile pages/06_Xep_TKB.py`
Expected: không lỗi.

Run: `grep -n "find_\|hard_rule_violations\|soft_rule_warnings\|_format_rule_item\|is_bgh\|ROLE_GDTC\|ROLE_NANG" pages/06_Xep_TKB.py`
Expected: không có kết quả.

- [ ] **Step 15: Kiểm tra trang thật (human gate)**

Khởi động app (`streamlit run app.py` hoặc skill `run`), vào trang "Xếp TKB", chạy xếp một tuần trên dữ liệu mẫu. Nhờ người dùng xác nhận: (a) khối vi phạm hiển thị, (b) nút lưu bị khóa khi có vi phạm II.3/II.4/II.8 và mở khi tích ô "Vẫn lưu", (c) xếp theo lô cũng hiển thị. Không commit trước khi người dùng xác nhận.

- [ ] **Step 16: Commit**

```bash
git add pages/06_Xep_TKB.py core/validation.py tests/
git commit -m "refactor: drive TKB page and tests from shared rule detectors, remove find_* validators"
```
(Nếu `pages/06_Xep_TKB.py` còn thay đổi dở dang không thuộc plan — xem Task 0 — dùng `git add -p`.)

---

### Task 10: `ScheduleResult.rule_counts`

**Files:**
- Modify: `core/models.py` (`ScheduleResult.rule_counts`)
- Modify: `core/scheduler/cpsat/solver.py` (`build_result`)
- Modify: `core/scheduler/cpsat/objectives.py:417,500,501` (đổi khóa `_morning_academic_underload` → `ACAD.MIN`)
- Test: `tests/test_rule_counts.py`

**Interfaces:**
- Consumes: `built.penalty_terms`, `violations_of`.
- Produces: `ScheduleResult.rule_counts: dict[str, int]` — mọi khóa `penalty_terms` có term, giá trị là tổng giá trị solver. **Chỉ để đối chứng trong test**, không hiển thị cho người dùng (spec §4.7).

- [ ] **Step 1: Viết test**

`tests/test_rule_counts.py`:
```python
import pytest

from core.models import SchedulingConfig, Slot, Subject, TimeSlot
from tests.rule_helpers import make_input, violations_of

cpsat = pytest.importorskip("core.scheduler.cpsat_model")

QUIET_CONFIG = dict(teacher_off_sessions_per_week=0, mandatory_morning_weekdays=())


def test_rule_counts_match_what_the_detector_finds_for_a_forced_lone_session():
    slots = [Slot(1, 101, TimeSlot(1, 3, "S", 1))]
    inp = make_input(slots, assigned_teacher={(1, 101): 10}, need={(1, 101): 1},
                     config=SchedulingConfig(min_weekly_periods_for_lone_penalty=1, **QUIET_CONFIG))
    result = cpsat.solve_to_result(cpsat.build_model(inp), time_limit_s=10.0)
    assert result.rule_counts["II.4"] == 2  # 1 buổi lẻ + 1 ngày lẻ
    assert result.rule_counts["II.4"] == len(violations_of("II.4", inp, result.assignment))


def test_academic_underload_bucket_uses_the_registry_rule_id():
    slots = [Slot(i, 101, TimeSlot(i, 2, "S", i)) for i in (1, 2, 3)]
    inp = make_input(slots, subjects=[Subject(1, "Toán học"), Subject(2, "Âm nhạc")],
                     assigned_teacher={(1, 101): 10, (2, 101): 20}, need={(1, 101): 1, (2, 101): 1},
                     config=SchedulingConfig(**QUIET_CONFIG))
    built = cpsat.build_model(inp)
    assert "ACAD.MIN" in built.penalty_terms
    assert "_morning_academic_underload" not in built.penalty_terms
```

- [ ] **Step 2: Chạy test để thấy nó đỏ**

Run: `python -m pytest tests/test_rule_counts.py -q -n 0`
Expected: FAIL — `AttributeError: 'ScheduleResult' object has no attribute 'rule_counts'` và `assert 'ACAD.MIN' in {...}`.

- [ ] **Step 3: Đổi khóa phạt học thuật**

Run: `grep -rn "_morning_academic_underload" --include=*.py .`
Expected: chỉ 3 dòng trong `core/scheduler/cpsat/objectives.py` (417, 500, 501). Thay cả ba chuỗi `"_morning_academic_underload"` bằng `"ACAD.MIN"`.

- [ ] **Step 4: Thêm `rule_counts`**

`core/models.py`, cuối `ScheduleResult`:
```python
    rule_counts: dict = field(default_factory=dict)  # rule_id -> violations the MODEL counted; cross-check only, never shown
```
`core/scheduler/cpsat/solver.py`, trong `build_result` ngay trước `successes_found = ...`:
```python
    rule_counts = {
        rule_id: int(sum(solver.Value(term) for term in terms))
        for rule_id, terms in built.penalty_terms.items() if terms
    }
```
và thêm `rule_counts=rule_counts,` vào `return ScheduleResult(...)`.

- [ ] **Step 5: Chạy test**

Run: `python -m pytest tests/test_rule_counts.py tests/test_morning_academic_balance.py tests/test_cpsat_model.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add core/models.py core/scheduler/cpsat/solver.py core/scheduler/cpsat/objectives.py tests/test_rule_counts.py
git commit -m "feat: report per-rule model violation counts on ScheduleResult"
```

---

### Task 11: Test tương đương mô hình ↔ hậu kiểm

**Files:**
- Create: `tests/test_rule_equivalence.py`
- Modify: `pytest.ini`

**Interfaces:**
- Consumes: `sched.run`, `DETECTORS`, `detect_rule`, `build_schedule_view`, `resolve_effective_params`, `classify`, `result.effective_params.as_effective()`, `result.rule_counts`.
- Produces: `KNOWN_DRIFT: dict[(check, fixture, rule_id), reason]` — danh sách bất đồng đã biết mà Plan 2/3 phải xóa dần.

- [ ] **Step 1: Gom test chậm theo nhóm xdist**

`pytest.ini`, dòng `addopts`:
```ini
addopts = -n auto --dist loadgroup
```
(`loadgroup` giống `load` với test không gắn nhóm; test gắn `xdist_group` chạy chung một worker nên mỗi fixture chỉ giải một lần.)

- [ ] **Step 2: Viết test**

`tests/test_rule_equivalence.py`:
```python
"""Tầng mô hình (CP-SAT) và tầng hậu kiểm (detectors) phải đồng ý về từng luật.

Ba phép kiểm tách bạch (spec 2026-09-17 §6.1):
  model_promise      -- đếm lại trên ngưỡng mô hình đã ép phải khớp số mô hình tự đếm.
  forced_evidence    -- mọi vi phạm FORCED phải kèm bằng chứng.
  unexplained_breach -- BREACH chỉ được phép ở fixture cố ý dựng ra nó.

Bất đồng đã biết nằm trong KNOWN_DRIFT kèm nguyên nhân và plan sẽ sửa.
Không thêm mục nào khi chưa giải thích được vì sao nó đỏ.
"""
from __future__ import annotations

import copy
import functools
import os
from dataclasses import replace

import pytest

from core import scheduler as sched
from core.models import ROLE_HDTN, WEEKDAYS, ClassRoom, SchedulingConfig, SchedulingInput, Slot, Subject, Teacher, TimeSlot
from core.rules.detectors import DETECTORS, detect_rule
from core.rules.params import resolve_effective_params
from core.rules.view import build_schedule_view
from core.rules.violations import BREACH, FORCED, classify
from data import db, repository as repo
from io_excel.importer import import_xlsm

pytest.importorskip("ortools")
pytestmark = [pytest.mark.slow, pytest.mark.xdist_group("rule_equivalence")]

SAMPLE_SCHOOL = os.path.join(os.path.dirname(__file__), "..", "io_excel", "sample_school.xlsm")
FIXTURE_TIME_LIMIT_S = 30
OVERSUBSCRIBED_EXTRA_PERIODS = 2
LONE_TEACHER_ID = 10
LONE_CLASS_ID = 101
LONE_HDTN_SUBJECT_ID = 99


@functools.lru_cache(maxsize=None)
def _imported_sample_school() -> SchedulingInput:
    conn = db.get_connection(":memory:")
    db.init_db(conn)
    import_xlsm(conn, SAMPLE_SCHOOL)
    inp = repo.build_scheduling_input(conn, parity="L", seed=2026)
    conn.close()
    return inp


def _sample_school(**config_changes) -> SchedulingInput:
    inp = copy.deepcopy(_imported_sample_school())
    inp.config = replace(inp.config, cpsat_time_limit_seconds=FIXTURE_TIME_LIMIT_S, **config_changes)
    return inp


def _lone_exempt() -> SchedulingInput:
    inp = _sample_school()
    params = resolve_effective_params(inp)
    _load, lightest_gated_teacher = min(
        (load, tid) for tid, load in params.teacher_load.items()
        if load >= params.min_weekly_periods_for_lone_penalty
    )
    inp.config = replace(inp.config, lone_session_exempt_teacher_ids=frozenset({lightest_gated_teacher}))
    return inp


def _single_pair() -> SchedulingInput:
    inp = _sample_school()
    literature = next(s.subject_id for s in inp.subjects if s.name.strip().lower().startswith("ngữ văn"))
    inp.config = replace(inp.config, single_pair_subject_ids=frozenset({literature}))
    return inp


def _oversubscribed() -> SchedulingInput:
    inp = _sample_school()
    class_id = inp.classes[0].class_id
    capacity = sum(1 for s in inp.slots if s.class_id == class_id)
    class_need = {key: n for key, n in inp.need.items() if key[1] == class_id and n > 0}
    inp.need[min(class_need)] += max(0, capacity - sum(class_need.values())) + OVERSUBSCRIBED_EXTRA_PERIODS
    return inp


def _infeasible_ii4() -> SchedulingInput:
    """Một GV, mỗi ngày đúng 1 ô sáng, mỗi môn 1 tiết: mọi buổi của GV buộc là buổi lẻ,
    nên II.4 không thể thỏa. Không có buổi chiều nên không dính II.8; tải 6 < ngưỡng
    sáng bắt buộc 10 nên không dính II.3."""
    timeslots = [TimeSlot(i + 1, wd, "S", 1) for i, wd in enumerate(WEEKDAYS)]
    subjects = [Subject(i + 1, f"Môn {i + 1}") for i in range(len(timeslots))]
    need = {(s.subject_id, LONE_CLASS_ID): 1 for s in subjects}
    return SchedulingInput(
        classes=[ClassRoom(LONE_CLASS_ID, "6A1")],
        subjects=subjects + [Subject(LONE_HDTN_SUBJECT_ID, "HĐTN", ROLE_HDTN)],
        teachers=[Teacher(LONE_TEACHER_ID, "GV A")],
        need=need,
        assigned_teacher={key: LONE_TEACHER_ID for key in need},
        ban_busy=set(),
        slots=[Slot(i + 1, LONE_CLASS_ID, ts) for i, ts in enumerate(timeslots)],
        timeslots=timeslots,
        config=SchedulingConfig(min_weekly_periods_for_lone_penalty=0, teacher_off_sessions_per_week=0,
                                cpsat_time_limit_seconds=FIXTURE_TIME_LIMIT_S),
    )


FIXTURES = {
    "baseline": _sample_school,
    "heavy_morning_only": lambda: _sample_school(heavy_subjects_morning_only=True),
    "oversubscribed": _oversubscribed,
    "lone_exempt": _lone_exempt,
    "off_enabled": lambda: _sample_school(teacher_off_sessions_per_week=2),
    "off_disabled": lambda: _sample_school(teacher_off_sessions_per_week=0),
    "single_pair": _single_pair,
    "infeasible_ii4": _infeasible_ii4,
}
EXPECTED_BREACH_FIXTURES = frozenset({"infeasible_ii4"})
RULE_IDS = tuple(sorted(DETECTORS))

# (check, fixture, rule_id) -> "nguyên nhân -- plan sửa". Điền theo quy trình ở Task 11 Step 4.
KNOWN_DRIFT: dict = {}


@functools.lru_cache(maxsize=None)
def _solved(fixture: str):
    inp = FIXTURES[fixture]()
    result = sched.run(inp)
    assert result.success, f"{fixture}: {result.failure_reason}"
    return result, build_schedule_view(inp, result.assignment)


def _cases(check: str) -> list:
    return [
        pytest.param(
            fixture, rule_id, id=f"{fixture}-{rule_id}",
            marks=[pytest.mark.xfail(strict=True, reason=KNOWN_DRIFT[check, fixture, rule_id])]
            if (check, fixture, rule_id) in KNOWN_DRIFT else [],
        )
        for fixture in FIXTURES for rule_id in RULE_IDS
    ]


@pytest.mark.parametrize("fixture, rule_id", _cases("model_promise"))
def test_model_keeps_its_own_promise(fixture, rule_id):
    result, view = _solved(fixture)
    recounted = len(detect_rule(rule_id, view, result.effective_params.as_effective()))
    modelled = result.rule_counts.get(rule_id, 0)
    assert recounted == modelled, (
        f"{rule_id}: mô hình tự đếm {modelled} trên ngưỡng nó ép, hậu kiểm đếm {recounted} — hai tầng trôi lệch"
    )


@pytest.mark.parametrize("fixture, rule_id", _cases("forced_evidence"))
def test_forced_violation_has_evidence(fixture, rule_id):
    result, view = _solved(fixture)
    params = result.effective_params
    unexplained = [v for v in classify(detect_rule(rule_id, view, params), params)
                   if v.level == FORCED and not v.evidence]
    assert not unexplained, f"{rule_id}: FORCED mà không có bằng chứng — phải là BREACH: {unexplained}"


@pytest.mark.parametrize("fixture, rule_id", _cases("unexplained_breach"))
def test_no_unexplained_breach(fixture, rule_id):
    result, view = _solved(fixture)
    params = result.effective_params
    breaches = [v for v in classify(detect_rule(rule_id, view, params), params) if v.level == BREACH]
    assert not breaches or fixture in EXPECTED_BREACH_FIXTURES, (
        f"{rule_id}: {len(breaches)} vi phạm không giải thích được — bug mô hình hoặc thiếu bằng chứng nới lỏng: "
        f"{[v.detail for v in breaches[:5]]}"
    )
```

- [ ] **Step 3: Chạy lần đầu, thu danh sách đỏ**

Run: `python -m pytest tests/test_rule_equivalence.py -q -rf --no-header`
Expected: có thể FAIL — **đây là kết quả dự kiến của GĐ 4**, không phải lỗi của task. Thời gian ~3–6 phút. Nếu một fixture báo `result.success` False: tăng `FIXTURE_TIME_LIMIT_S` lên 45 và chạy lại; nếu vẫn False thì dừng và báo người dùng.

- [ ] **Step 4: Phân loại từng dòng đỏ**

Với **mỗi** test FAIL, đối chiếu với bảng nguyên nhân đã biết dưới đây. Khớp → thêm một mục vào `KNOWN_DRIFT` với chuỗi lý do đúng như cột "Lý do ghi vào KNOWN_DRIFT". Không khớp dòng nào → **không** thêm; đọc message assert, tìm nguyên nhân gốc, ghi vào báo cáo task như một phát hiện mới và hỏi người dùng trước khi xfail.

| Mẫu (check, fixture, rule) | Nguyên nhân | Lý do ghi vào KNOWN_DRIFT |
|---|---|---|
| (`model_promise`, bất kỳ, `II.7`) | Mô hình đếm từng **tiết** trống (`objectives.py` mục 3), detector đếm từng **buổi** có trống | `"II.7: mô hình đếm tiết trống, detector đếm buổi có trống — phát hiện 2026-09-17, chờ quyết định ở Plan 3"` |
| (`model_promise`, `heavy_morning_only`, `C.HEAVY_CONSEC`) | Trần nặng thích ứng `_get_eff_max_heavy` chưa vào `Threshold.effective` | `"V1: trần nặng thích ứng chưa ghi vào Threshold — Plan 2 (A7 cap_var)"` |
| (`unexplained_breach`, `heavy_morning_only`, `C.HEAVY_CONSEC`) | Như trên, chưa có `reason` để hạ FORCED | cùng chuỗi V1 ở trên |
| (`model_promise` hoặc `unexplained_breach`, bất kỳ, `ACAD.MAX`) | Trần học thuật thích ứng `constraints.py:440` chưa vào `Threshold.effective` | `"V4: trần học thuật thích ứng chưa ghi vào Threshold — Plan 2"` |
| (`unexplained_breach`, bất kỳ, `II.3`/`II.4`/`II.8`) **và** `result.relaxed_rules` của fixture đó chứa đúng rule_id | Nới lỏng kiểu công tắc chưa có phạm vi nên không hạ FORCED được | `"Nới lỏng chưa có phạm vi (relaxed_rules cũ) — Plan 2 (A7 Relaxation)"` |
| (`model_promise`, `lone_exempt`, `II.8`) | GV miễn trừ vẫn bị đếm vào `penalty_terms["II.8"]` | `"A3: GV miễn trừ vẫn bị hard-gate II.8 — Plan 2"` |

Để kiểm cột cuối của dòng "nới lỏng": `python -c "import tests.test_rule_equivalence as t; r,_=t._solved('<fixture>'); print(r.relaxed_rules)"`.

- [ ] **Step 5: Chạy lại hai lần để bắt kết quả không tất định**

Run hai lần: `python -m pytest tests/test_rule_equivalence.py -q -rxXf`
Expected: 0 FAILED, 0 XPASS ở cả hai lần. Một mục chỉ đỏ ở một trong hai lần (CP-SAT đa luồng + dừng sớm theo đồng hồ) → đổi riêng mục đó sang `xfail(strict=False)`, bằng cách thêm hậu tố `" [không tất định]"` vào lý do và sửa `_cases` thành:
```python
            marks=[pytest.mark.xfail(strict=not KNOWN_DRIFT[check, fixture, rule_id].endswith("[không tất định]"),
                                     reason=KNOWN_DRIFT[check, fixture, rule_id])]
```
(Chỉ sửa `_cases` nếu thực sự có mục không tất định.)

- [ ] **Step 6: Báo cáo cho người dùng (human gate)**

In bảng `KNOWN_DRIFT` cuối cùng, cùng mọi phát hiện mới ở Step 4, cho người dùng. Đây là đầu vào trực tiếp của Plan 2. Chờ xác nhận trước khi commit.

- [ ] **Step 7: Commit**

```bash
git add tests/test_rule_equivalence.py pytest.ini
git commit -m "test: add model-vs-detector rule equivalence harness with known drift"
```

---

### Task 12: Kiểm tra hoàn tất Plan 1

**Files:** không sửa file nào (trừ khi một kiểm tra dưới đây fail).

- [ ] **Step 1: Toàn bộ suite**

Run: `python -m pytest -q -m "not slow"` rồi `python -m pytest -q -m slow -rxX`
Expected: 0 FAILED. XFAIL chỉ đến từ `tests/test_rule_equivalence.py`. So thời gian với mốc Task 0.

- [ ] **Step 2: Tiêu chí dạng grep**

```bash
grep -rn "find_[a-z_0-9]*(" --include=*.py core pages tests
grep -rn "rules_registry" --include=*.py .
grep -rn "\.effective\b" --include=*.py core pages | grep -v "core/rules/params.py\|core/rules/violations.py"
```
Expected: cả ba không có kết quả. (Plan 1 chưa cho `constraints.py`/`objectives.py` đọc `.effective` — việc đó thuộc Plan 2.)

- [ ] **Step 3: Phân tích thay đổi đồ thị**

MCP: `detect_changes({scope: "compare", base_ref: "main"})`. Nếu `partial: true` hoặc `truncated: true` thì chạy lại. Báo các process bị ảnh hưởng.

- [ ] **Step 4: Đối chiếu spec**

Đánh dấu trong báo cáo cuối các mục đã xong của spec: GĐ 1 (view + chuyển detector + cập nhật điểm gọi), GĐ 2 (params, `built.params`, `result.effective_params`), GĐ 3 (`Violation.level`, `classify`, `blocks_save` — `breach_priority` và `relaxations` hoãn theo D5), GĐ 4 (`rule_counts`, test tương đương ba phép kiểm). Liệt kê mọi mục `KNOWN_DRIFT` làm đầu vào của Plan 2.

- [ ] **Step 5: Hỏi hướng tích hợp**

Dùng skill `superpowers:finishing-a-development-branch`.
