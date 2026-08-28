# Cấu hình xếp lịch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make 7 "school's choice" scheduling constants — currently hardcoded in `core/scheduler.py` and `core/frame.py` — configurable per school, editable through a new UI page, while every default reproduces today's hardcoded behavior exactly.

**Architecture:** A new `SchedulingConfig` dataclass (`core/models.py`) rides on `SchedulingInput.config` exactly like the existing `extra_kep_ids` field does, so `sched.run(inp)` call sites need zero changes. Per-school values persist as individual `app_meta` rows via `data/repository.py`, mirroring the existing `get_base_cap`/`set_base_cap` pattern. `core/scheduler.py` and `core/frame.py` read the config through new optional function parameters (defaults = today's hardcoded constants), so every existing caller and test keeps working unmodified until a school explicitly saves new values.

**Tech Stack:** Python 3, Streamlit, SQLite (stdlib `sqlite3`), pytest.

**Spec:** `docs/superpowers/specs/2026-08-28-cau-hinh-xep-lich-design.md`

## Global Constraints

- Every `SchedulingConfig` field default must equal today's hardcoded value exactly — a school that never opens the new config page must see byte-identical scheduling behavior.
- No changes to any `sched.run(inp)` call site signature — config travels on `SchedulingInput.config`, following the existing `extra_kep_ids` precedent.
- Storage follows the existing `app_meta` key-per-field pattern (`get_meta`/`set_meta` in `data/repository.py`) — no new SQLite table.
- Out of scope, do not touch: algorithm-tuning constants (`SO_LAN_THU`, `SO_PA_TOT`, `NGUONG_KHOA`, `IDLE_DAY_BONUS`), core invariants (`BAT_NGHI_1_BUOI` gate itself, `BAT_LIEN_MACH`, teacher-conflict check, kép adjacency/cap, HDTN-must-exist), and the SHL (sinh hoạt lớp) weekday (stays derived from the class's frame, never a raw config field).
- All existing tests in `tests/test_scheduler.py`, `tests/test_frame.py`, `tests/test_exporter.py`, `tests/test_full_backup.py` must keep passing unmodified — they are the regression net proving defaults are unchanged.

---

## Task 1: `SchedulingConfig` dataclass + `SchedulingInput.config` field

**Files:**
- Modify: `core/models.py:82-93` (add new dataclass before `SchedulingInput`, add one field to `SchedulingInput`)
- Test: `tests/test_models.py` (new file)

**Interfaces:**
- Produces: `core.models.SchedulingConfig` — dataclass with 7 fields, all defaulted; `SchedulingInput.config: SchedulingConfig` field (default: a fresh `SchedulingConfig()`).

- [ ] **Step 1: Write the failing test**

Create `tests/test_models.py`:

```python
from core.models import SchedulingConfig, SchedulingInput


def test_scheduling_config_defaults_match_current_hardcoded_behavior():
    config = SchedulingConfig()
    assert config.gdtc_avoid_period == 5
    assert config.chao_co_weekday == 2
    assert config.chao_co_period == 1
    assert config.max_heavy_consecutive == 3
    assert config.max_periods_per_session == 4
    assert config.teacher_off_sessions_per_week == 1
    assert config.forbidden_off_cells == frozenset({(2, "S"), (5, "S"), (6, "S"), (5, "C"), (6, "C")})
    assert config.reserved_off_weekdays_chieu == (5, 6)


def test_scheduling_input_defaults_to_default_scheduling_config():
    inp = SchedulingInput(
        classes=[], subjects=[], teachers=[], need={}, assigned_teacher={},
        ban_busy=set(), slots=[], timeslots=[],
    )
    assert inp.config == SchedulingConfig()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_models.py -v`
Expected: FAIL with `ImportError: cannot import name 'SchedulingConfig'`

- [ ] **Step 3: Add the dataclass and field**

In `core/models.py`, insert immediately before the existing `SchedulingInput` class (currently at line 82-93):

```python
@dataclass
class SchedulingConfig:
    """Ràng buộc "lựa chọn của trường" -- khác trường có thể chọn khác, không phải
    bất biến thuật toán. Mọi default dưới đây = đúng hằng số hardcode trước khi có
    cấu hình này, để hành vi không đổi cho tới khi trường chủ động lưu giá trị khác.
    """
    gdtc_avoid_period: int = 5
    chao_co_weekday: int = 2
    chao_co_period: int = 1
    max_heavy_consecutive: int = 3
    max_periods_per_session: int = 4
    teacher_off_sessions_per_week: int = 1
    forbidden_off_cells: frozenset = field(
        default_factory=lambda: frozenset({(2, "S"), (5, "S"), (6, "S"), (5, "C"), (6, "C")})
    )
    reserved_off_weekdays_chieu: tuple = (5, 6)
```

Then add one field at the end of `SchedulingInput` (after the existing `extra_kep_ids` line):

```python
    extra_kep_ids: frozenset = field(default_factory=frozenset)  # subject_id cần xếp kép CHỈ tuần này
    config: SchedulingConfig = field(default_factory=SchedulingConfig)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_models.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add core/models.py tests/test_models.py
git commit -m "feat: add SchedulingConfig dataclass with defaults matching current hardcoded rules"
```

---

## Task 2: Persist `SchedulingConfig` per school (`data/repository.py`)

**Files:**
- Modify: `data/repository.py:10` (import), insert new section before `def build_scheduling_input` (currently line 542)
- Test: `tests/test_repository.py` (new file)

**Interfaces:**
- Consumes: `core.models.SchedulingConfig` (Task 1), `data.repository.get_meta`/`set_meta` (existing, `data/repository.py:506-516`)
- Produces: `data.repository.get_scheduling_config(conn) -> SchedulingConfig`, `data.repository.set_scheduling_config(conn, config: SchedulingConfig) -> None`

- [ ] **Step 1: Write the failing test**

Create `tests/test_repository.py`:

```python
import pytest

from core.models import SchedulingConfig
from data import db, repository as repo


@pytest.fixture()
def conn(tmp_path):
    connection = db.get_connection(str(tmp_path / "test.db"))
    db.init_db(connection)
    yield connection
    connection.close()


def test_get_scheduling_config_returns_defaults_when_never_saved(conn):
    assert repo.get_scheduling_config(conn) == SchedulingConfig()


def test_set_then_get_scheduling_config_round_trips(conn):
    custom = SchedulingConfig(
        gdtc_avoid_period=3,
        chao_co_weekday=3,
        chao_co_period=2,
        max_heavy_consecutive=2,
        max_periods_per_session=5,
        teacher_off_sessions_per_week=2,
        forbidden_off_cells=frozenset({(2, "S"), (4, "C")}),
        reserved_off_weekdays_chieu=(4, 5),
    )
    repo.set_scheduling_config(conn, custom)
    assert repo.get_scheduling_config(conn) == custom
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_repository.py -v`
Expected: FAIL with `AttributeError: module 'data.repository' has no attribute 'get_scheduling_config'`

- [ ] **Step 3: Add the persistence functions**

In `data/repository.py:10`, change the import line:

```python
from core.models import ClassRoom, SchedulingConfig, SchedulingInput, Slot, Subject, Teacher, TimeSlot, WEEKDAYS
```

Insert this new section immediately before `def build_scheduling_input` (currently line 542):

```python
# ---------------------------------------------------------------------------
# scheduling_config -- per-school overrides for core.scheduler / core.frame
# ---------------------------------------------------------------------------

def _parse_off_cells(raw: str) -> frozenset:
    cells = set()
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        cells.add((int(token[:-1]), token[-1]))
    return frozenset(cells)


def _format_off_cells(cells) -> str:
    return ",".join(f"{wd}{session}" for wd, session in sorted(cells))


def _parse_weekday_tuple(raw: str) -> tuple:
    return tuple(int(x) for x in raw.split(",") if x.strip())


def _format_weekday_tuple(weekdays) -> str:
    return ",".join(str(wd) for wd in weekdays)


def get_scheduling_config(conn: sqlite3.Connection) -> SchedulingConfig:
    default = SchedulingConfig()
    forbidden_raw = get_meta(conn, "sched_forbidden_off_cells")
    reserved_raw = get_meta(conn, "sched_reserved_off_weekdays_chieu")
    return SchedulingConfig(
        gdtc_avoid_period=int(get_meta(conn, "sched_gdtc_avoid_period") or default.gdtc_avoid_period),
        chao_co_weekday=int(get_meta(conn, "sched_chao_co_weekday") or default.chao_co_weekday),
        chao_co_period=int(get_meta(conn, "sched_chao_co_period") or default.chao_co_period),
        max_heavy_consecutive=int(get_meta(conn, "sched_max_heavy_consecutive") or default.max_heavy_consecutive),
        max_periods_per_session=int(
            get_meta(conn, "sched_max_periods_per_session") or default.max_periods_per_session
        ),
        teacher_off_sessions_per_week=int(
            get_meta(conn, "sched_teacher_off_sessions_per_week") or default.teacher_off_sessions_per_week
        ),
        forbidden_off_cells=_parse_off_cells(forbidden_raw) if forbidden_raw else default.forbidden_off_cells,
        reserved_off_weekdays_chieu=(
            _parse_weekday_tuple(reserved_raw) if reserved_raw else default.reserved_off_weekdays_chieu
        ),
    )


def set_scheduling_config(conn: sqlite3.Connection, config: SchedulingConfig) -> None:
    set_meta(conn, "sched_gdtc_avoid_period", str(config.gdtc_avoid_period))
    set_meta(conn, "sched_chao_co_weekday", str(config.chao_co_weekday))
    set_meta(conn, "sched_chao_co_period", str(config.chao_co_period))
    set_meta(conn, "sched_max_heavy_consecutive", str(config.max_heavy_consecutive))
    set_meta(conn, "sched_max_periods_per_session", str(config.max_periods_per_session))
    set_meta(conn, "sched_teacher_off_sessions_per_week", str(config.teacher_off_sessions_per_week))
    set_meta(conn, "sched_forbidden_off_cells", _format_off_cells(config.forbidden_off_cells))
    set_meta(conn, "sched_reserved_off_weekdays_chieu", _format_weekday_tuple(config.reserved_off_weekdays_chieu))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_repository.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add data/repository.py tests/test_repository.py
git commit -m "feat: persist SchedulingConfig per school via app_meta"
```

---

## Task 3: Thread `reserved_off_weekdays_chieu` through `core/frame.py`

**Files:**
- Modify: `core/frame.py` (5 function signatures + 3 internal reads of `RESERVED_OFF_WEEKDAYS_CHIEU`)
- Test: `tests/test_frame.py` (add new test; all existing tests must keep passing unmodified)

**Interfaces:**
- Produces: `active_cells`, `total_cells_per_class`, `suggest_short_day`, `is_short_day_config_valid`, `check_capacity` each gain a trailing keyword param `reserved_off_weekdays_chieu: tuple = RESERVED_OFF_WEEKDAYS_CHIEU`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_frame.py`:

```python
def test_active_cells_respects_custom_reserved_off_weekdays_chieu():
    default_cells = frame.active_cells(4, 3)
    assert (5, "C", 1) not in default_cells  # Thứ 5 chiều khoá theo mặc định
    assert (2, "C", 1) in default_cells      # Thứ 2 chiều KHÔNG khoá theo mặc định

    custom_cells = frame.active_cells(4, 3, reserved_off_weekdays_chieu=(2, 3))
    assert (5, "C", 1) in custom_cells        # Thứ 5 không còn bị khoá
    assert (2, "C", 1) not in custom_cells    # Thứ 2 giờ bị khoá thay thế
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_frame.py -k custom_reserved -v`
Expected: FAIL with `TypeError: active_cells() got an unexpected keyword argument 'reserved_off_weekdays_chieu'`

- [ ] **Step 3: Thread the parameter through all 5 functions**

In `core/frame.py`, change each signature and internal reference:

`active_cells` (currently lines 47-92) — add the param and use it at line 88:

```python
def active_cells(morning_periods: int, afternoon_periods: int, study_sunday: bool = False,
                  allow_saturday: bool = False, short_weekday: int | None = None,
                  short_morning_periods: int | None = None,
                  short_afternoon_periods: int | None = None,
                  reserved_off_weekdays_chieu: tuple = RESERVED_OFF_WEEKDAYS_CHIEU) -> list:
```

...and change the body's `if wd in RESERVED_OFF_WEEKDAYS_CHIEU:` to `if wd in reserved_off_weekdays_chieu:`.

`total_cells_per_class` (currently lines 95-100):

```python
def total_cells_per_class(morning_periods: int, afternoon_periods: int, study_sunday: bool = False,
                           allow_saturday: bool = False, short_weekday: int | None = None,
                           short_morning_periods: int | None = None,
                           short_afternoon_periods: int | None = None,
                           reserved_off_weekdays_chieu: tuple = RESERVED_OFF_WEEKDAYS_CHIEU) -> int:
    return len(active_cells(morning_periods, afternoon_periods, study_sunday, allow_saturday,
                             short_weekday, short_morning_periods, short_afternoon_periods,
                             reserved_off_weekdays_chieu))
```

`suggest_short_day` (currently lines 103-148) — add the param, pass it to the internal `total_cells_per_class` call, and use it at the two existing `RESERVED_OFF_WEEKDAYS_CHIEU` reads (lines 126):

```python
def suggest_short_day(morning_periods: int, afternoon_periods: int, quota_total: int,
                       allow_saturday: bool = False,
                       reserved_off_weekdays_chieu: tuple = RESERVED_OFF_WEEKDAYS_CHIEU,
                       ) -> tuple[int, int | None, int | None] | None:
    uniform_total = total_cells_per_class(morning_periods, afternoon_periods, allow_saturday=allow_saturday,
                                           reserved_off_weekdays_chieu=reserved_off_weekdays_chieu)
```

(keep the rest of the function body as-is, only replacing the `avail_afternoon = 0 if wd in RESERVED_OFF_WEEKDAYS_CHIEU else afternoon_periods` line with `avail_afternoon = 0 if wd in reserved_off_weekdays_chieu else afternoon_periods`).

`is_short_day_config_valid` (currently lines 151-176) — add the param, use it at line 172:

```python
def is_short_day_config_valid(morning_periods: int, afternoon_periods: int, allow_saturday: bool,
                               short_weekday: int | None, short_morning_periods: int | None,
                               short_afternoon_periods: int | None,
                               reserved_off_weekdays_chieu: tuple = RESERVED_OFF_WEEKDAYS_CHIEU) -> bool:
```

...and change `if short_weekday in RESERVED_OFF_WEEKDAYS_CHIEU:` to `if short_weekday in reserved_off_weekdays_chieu:`.

`check_capacity` (currently lines 179-193) — add the param, forward it to `total_cells_per_class`:

```python
def check_capacity(morning_periods: int, afternoon_periods: int, class_quota_totals: dict,
                    study_sunday: bool = False, allow_saturday: bool = False,
                    reserved_off_weekdays_chieu: tuple = RESERVED_OFF_WEEKDAYS_CHIEU) -> str:
    total_per_class = total_cells_per_class(morning_periods, afternoon_periods, study_sunday, allow_saturday,
                                             reserved_off_weekdays_chieu=reserved_off_weekdays_chieu)
```

- [ ] **Step 4: Run tests to verify everything passes**

Run: `python -m pytest tests/test_frame.py -v`
Expected: PASS (all existing tests + the new one — existing calls use no keyword, so they keep hitting the default `RESERVED_OFF_WEEKDAYS_CHIEU` tuple)

- [ ] **Step 5: Commit**

```bash
git add core/frame.py tests/test_frame.py
git commit -m "feat: make reserved_off_weekdays_chieu an overridable parameter in core/frame.py"
```

---

## Task 4: Thread `SchedulingConfig` through `core/scheduler.py`'s feasibility chain

**Files:**
- Modify: `core/scheduler.py` (imports, `_feasible`, `_pick_best_scored`, `_pick_best_simple`, `_try_swap_repair`, `_repair_lone_periods`, `run`)
- Test: `tests/test_scheduler.py`

**Interfaces:**
- Consumes: `core.models.SchedulingConfig` (Task 1)
- Produces: `_feasible(..., config: Optional[SchedulingConfig] = None)` — every function in the chain gains a trailing `config` parameter that defaults to `None` and is normalized to `SchedulingConfig()` inside `_feasible`.

This task wires 3 of the 7 fields: `gdtc_avoid_period`, `max_periods_per_session`, `chao_co_weekday`/`chao_co_period`. (`forbidden_off_cells` and `teacher_off_sessions_per_week` are Task 5; `max_heavy_consecutive` is Task 6 — both build on the `config` parameter this task adds.)

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_scheduler.py` (near `test_gdtc_never_period5` and `test_max_gv_buoi_session_cap`):

```python
def test_gdtc_avoid_period_configurable():
    subjects = [Subject(1, "GDTC", ROLE_GDTC), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    state = _State(remaining_need={(1, 1): 10}, busy=set())
    config = SchedulingConfig(gdtc_avoid_period=3)
    ts3 = TimeSlot(1, 2, "S", 3)
    assert _feasible(1, ts3, 1, 100, state, role_index, config=config) is False
    ts5 = TimeSlot(2, 2, "S", 5)  # tiết 5 không còn bị né với config này
    assert _feasible(1, ts5, 1, 100, state, role_index, config=config) is True


def test_max_periods_per_session_configurable():
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    ts = TimeSlot(1, 2, "S", 1)
    state = _State(remaining_need={(1, 1): 10}, busy=set())
    config = SchedulingConfig(max_periods_per_session=3)
    state.session_count[(100, 2, "S")] = 3
    assert _feasible(1, ts, 1, 100, state, role_index, config=config) is False
    state.session_count[(100, 2, "S")] = 2
    assert _feasible(1, ts, 1, 100, state, role_index, config=config) is True


def test_feasible_defaults_to_current_behavior_when_config_omitted():
    subjects = [Subject(1, "GDTC", ROLE_GDTC), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    state = _State(remaining_need={(1, 1): 10}, busy=set())
    ts5 = TimeSlot(1, 2, "S", 5)
    assert _feasible(1, ts5, 1, 100, state, role_index) is False  # vẫn né tiết 5 như cũ
```

Also add a full-run test using the existing `_make_timeslots`/`_build_input` helpers (defined above `test_small_synthetic_schedule_succeeds_and_meets_quotas`, currently `tests/test_scheduler.py:271-287` — plain module-level functions, not pytest fixtures):

```python
def test_chao_co_position_configurable_in_full_run():
    classes = [ClassRoom(1, "6A")]
    subjects = [
        Subject(1, "Toan hoc", ROLE_THUONG, 1),
        Subject(2, "Ngu van", ROLE_KEP, 2),
        Subject(3, "GDTC", ROLE_GDTC, 3),
        Subject(4, "HDTN", ROLE_HDTN, 4),
        Subject(5, "Tieng Anh", ROLE_THUONG, 5),
    ]
    teachers = [Teacher(i, f"GV{i}") for i in range(1, 6)]
    need = {(1, 1): 6, (2, 1): 12, (3, 1): 3, (4, 1): 3, (5, 1): 6}
    assigned_teacher = {(1, 1): 1, (2, 1): 2, (3, 1): 3, (4, 1): 4, (5, 1): 5}
    timeslots = _make_timeslots(morning=5, afternoon=0)
    inp = _build_input(classes, subjects, teachers, need, assigned_teacher, timeslots, seed=42)
    inp.config = SchedulingConfig(chao_co_weekday=3, chao_co_period=2)

    result = sched.run(inp, max_attempts=6000, target_successes=3)
    assert result.success is True

    hdtn_id = 4
    for slot in inp.slots:
        if slot.ts.weekday == 3 and slot.ts.session == "S" and slot.ts.period == 2:
            assert result.assignment.get(slot.slot_id) == hdtn_id
        if slot.ts.weekday == 2 and slot.ts.session == "S" and slot.ts.period == 1:
            assert result.assignment.get(slot.slot_id) != hdtn_id
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_scheduler.py -k "configurable" -v`
Expected: FAIL — `test_gdtc_avoid_period_configurable` and `test_max_periods_per_session_configurable` fail with `TypeError: _feasible() got an unexpected keyword argument 'config'`; `test_chao_co_position_configurable_in_full_run` fails because HDTN is still pinned to Thứ 2 Tiết 1.

- [ ] **Step 3: Wire `config` through the call chain**

In `core/scheduler.py`, update the import line (currently line 15):

```python
from core.models import ScheduleResult, SchedulingConfig, SchedulingInput, Slot, TimeSlot
```

`_feasible` (currently lines 79-114) — add the parameter, normalize it, and use it for the GDTC and max-periods-per-session checks:

```python
def _feasible(class_id: int, ts: TimeSlot, subject_id: int, teacher_id: int,
              state: _State, role_index, day_capacity: Optional[dict] = None,
              config: Optional[SchedulingConfig] = None) -> bool:
    config = config or SchedulingConfig()
    if (teacher_id, ts.ts_id) in state.busy:
        return False
    if state.session_count[(teacher_id, ts.weekday, ts.session)] >= config.max_periods_per_session:
        return False
    if BAT_NGHI_1_BUOI and (ts.weekday, ts.session) in state.gv_off_slots.get(teacher_id, ()):
        return False
    if subject_id == role_index.gdtc_id and ts.period == config.gdtc_avoid_period:
        return False
```

(leave the rest of `_feasible`'s body — day cap, liền mạch, kép cap/adjacency, and the heavy-run window — untouched in this task; the heavy-run window is generalized in Task 6).

`_pick_best_scored` (currently lines 200-236) — add the param, forward to its `_feasible` call (currently line 216):

```python
def _pick_best_scored(class_id: int, slot: Slot, state: _State, role_index,
                       subjects: list, assigned_teacher: dict, pu: float, rng: random.Random,
                       day_capacity: Optional[dict] = None,
                       config: Optional[SchedulingConfig] = None) -> Optional[tuple]:
```

...and change `if not _feasible(class_id, ts, subj.subject_id, teacher_id, state, role_index, day_capacity):` to `if not _feasible(class_id, ts, subj.subject_id, teacher_id, state, role_index, day_capacity, config):`.

`_pick_best_simple` (currently lines 239-262) — same pattern, add the param, forward at its `_feasible` call (currently line 254):

```python
def _pick_best_simple(class_id: int, slot: Slot, state: _State, role_index,
                       subjects: list, assigned_teacher: dict,
                       day_capacity: Optional[dict] = None,
                       config: Optional[SchedulingConfig] = None) -> Optional[tuple]:
```

...`if not _feasible(class_id, ts, subj.subject_id, teacher_id, state, role_index, day_capacity, config):`.

`_try_swap_repair` (currently lines 265-286) — add the param, forward to its `_feasible` call (currently line 275) and its `_pick_best_simple` call (currently line 277):

```python
def _try_swap_repair(class_id: int, slot: Slot, state: _State, role_index,
                      subjects: list, assigned_teacher: dict,
                      slots_by_class: dict, day_capacity: Optional[dict] = None,
                      config: Optional[SchedulingConfig] = None) -> bool:
    ts = slot.ts
    for other in slots_by_class[class_id]:
        if other.slot_id == slot.slot_id:
            continue
        if state.assigned.get(other.slot_id, None) in (None, -1) or state.pinned.get(other.slot_id):
            continue
        moved_subject, moved_teacher = _remove_at(state, other, role_index)
        if _feasible(class_id, ts, moved_subject, moved_teacher, state, role_index, day_capacity, config):
            _put_at(state, slot, moved_subject, moved_teacher, role_index)
            refill = _pick_best_simple(class_id, other, state, role_index, subjects, assigned_teacher,
                                        day_capacity, config)
```

(keep the remaining lines of this function unchanged).

`_repair_lone_periods` (currently lines 151-178) — add the param, forward to its `_pick_best_simple` call (currently line 173) and `_try_swap_repair` call (currently lines 177-178):

```python
def _repair_lone_periods(inp: SchedulingInput, state: _State, role_index,
                          assigned_teacher: dict, slots_by_class: dict,
                          day_capacity: Optional[dict], config: Optional[SchedulingConfig] = None) -> None:
```

...`pick = _pick_best_simple(class_id, slot, state, role_index, inp.subjects, assigned_teacher, day_capacity, config)` and `_try_swap_repair(class_id, slot, state, role_index, inp.subjects, assigned_teacher, slots_by_class, day_capacity, config)`.

`run()` — after the existing `role_index = resolve_roles(inp.subjects, inp.extra_kep_ids)` line (currently line 340), add:

```python
    config = inp.config
```

Then update every call site inside `run()`:

- Chào cờ pin block (currently lines 431-439): change the `if` condition and the `_feasible` call:

```python
        for slot in inp.slots:
            if (slot.ts.weekday == config.chao_co_weekday and slot.ts.session == "S"
                    and slot.ts.period == config.chao_co_period):
                key = (role_index.hdtn_id, slot.class_id)
                if state.remaining_need.get(key, 0) > 0:
                    teacher_id = assigned_teacher.get(key)
                    if teacher_id is not None and _feasible(slot.class_id, slot.ts, role_index.hdtn_id,
                                                              teacher_id, state, role_index, day_capacity, config):
                        _put_at(state, slot, role_index.hdtn_id, teacher_id, role_index)
                        state.pinned[slot.slot_id] = True
```

- `_pick_best_scored` call (currently lines 460-461):

```python
                pick = _pick_best_scored(class_id, slot, state, role_index, inp.subjects,
                                          assigned_teacher, pu, rng, day_capacity, config)
```

- `_try_swap_repair` call (currently lines 474-475):

```python
                    fixed = _try_swap_repair(class_id, slot, state, role_index, inp.subjects,
                                              assigned_teacher, slots_by_class, day_capacity, config)
```

- SHL restore `_feasible` call (currently line 493):

```python
                if _feasible(cid, target.ts, role_index.hdtn_id, tid, state, role_index, day_capacity, config):
```

- `_repair_lone_periods` call (currently line 501):

```python
            _repair_lone_periods(inp, state, role_index, assigned_teacher, slots_by_class, day_capacity, config)
```

In `tests/test_scheduler.py`, update the existing model import (currently lines 6-9) to include `SchedulingConfig`:

```python
from core.models import (
    ROLE_GDTC, ROLE_HDTN, ROLE_KEP, ROLE_NANG, ROLE_THUONG,
    ClassRoom, SchedulingConfig, SchedulingInput, Slot, Subject, Teacher, TimeSlot,
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_scheduler.py -v`
Expected: PASS — all pre-existing tests (they call `_feasible`/`run` without `config`, hitting the default) plus the new `configurable` tests.

- [ ] **Step 5: Commit**

```bash
git add core/scheduler.py tests/test_scheduler.py
git commit -m "feat: thread SchedulingConfig through scheduler feasibility chain (GDTC period, session cap, chào cờ position)"
```

---

## Task 5: Wire `forbidden_off_cells` and `teacher_off_sessions_per_week` into `_assign_off_slots`

**Files:**
- Modify: `core/scheduler.py` (`_assign_off_slots` signature + body, its call site in `run()`)
- Test: `tests/test_scheduler.py`

**Interfaces:**
- Consumes: `config` (Task 4, already threaded into `run()`)
- Produces: `_assign_off_slots(..., forbidden_off_cells: frozenset = FORBIDDEN_OFF_CELLS)` — the existing `off_slot_count` parameter is unchanged, just now driven by config at the one real call site.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_scheduler.py` near `test_off_slots_respect_forbidden_cells_gvcn_and_must_monday`:

```python
def test_assign_off_slots_respects_custom_forbidden_cells_and_count():
    rng = random.Random(1)
    teachers_by_id = {1: Teacher(1, "Normal", role="", must_monday=False, is_gvcn=False, cap=19)}
    custom_forbidden = frozenset({(2, "S"), (2, "C"), (3, "S"), (3, "C"), (4, "S"), (4, "C")})
    off_slots = sched._assign_off_slots(
        {1}, teachers_by_id, rng, off_slot_count=2, forbidden_off_cells=custom_forbidden,
    )
    assert len(off_slots[1]) == 2
    for cell in off_slots[1]:
        assert cell not in custom_forbidden
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_scheduler.py -k custom_forbidden_cells_and_count -v`
Expected: FAIL with `TypeError: _assign_off_slots() got an unexpected keyword argument 'forbidden_off_cells'`

- [ ] **Step 3: Add the parameter**

In `core/scheduler.py`, change `_assign_off_slots`'s signature (currently lines 289-291) and its one internal read of the module constant (currently line 312):

```python
def _assign_off_slots(teacher_ids: set, teachers_by_id: dict, rng: random.Random,
                       gvcn_shl_cell: Optional[dict] = None,
                       off_slot_count: int = 1,
                       forbidden_off_cells: frozenset = FORBIDDEN_OFF_CELLS) -> dict:
```

...`forbidden = set(forbidden_off_cells)` (was `forbidden = set(FORBIDDEN_OFF_CELLS)`).

In `run()`, change the call site (currently line 418):

```python
        state.gv_off_slots = _assign_off_slots(
            all_teacher_ids, teachers_by_id, rng, gvcn_shl_cell,
            off_slot_count=config.teacher_off_sessions_per_week,
            forbidden_off_cells=config.forbidden_off_cells,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_scheduler.py -v`
Expected: PASS — including `test_off_slots_respect_forbidden_cells_gvcn_and_must_monday` and `test_off_slot_count_defaults_to_1_buoi_per_week` (both call `_assign_off_slots` without the new keyword, hitting the default `FORBIDDEN_OFF_CELLS`).

- [ ] **Step 5: Commit**

```bash
git add core/scheduler.py tests/test_scheduler.py
git commit -m "feat: make off-slot forbidden cells and count configurable per school"
```

---

## Task 6: Generalize the heavy-subject consecutive-run window to `max_heavy_consecutive`

**Files:**
- Modify: `core/scheduler.py` (imports, `_feasible`'s heavy-subject block)
- Test: `tests/test_scheduler.py`

**Interfaces:**
- Consumes: `config.max_heavy_consecutive` (field from Task 1), `frame_mod.MAX_PERIODS_PER_SESSION` (existing constant, `core/frame.py:13`)

This is the highest-risk task in the plan: the current code checks two hardcoded window start positions (`w in (1, 2)`, each a 4-period window) which happens to enforce "max 3 consecutive" for a 5-period session. It must become a formula in terms of `N = config.max_heavy_consecutive`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_scheduler.py` near `test_heavy_subject_run_of_3_cap`:

```python
def test_heavy_subject_consecutive_cap_stricter_than_default():
    # N=2: 1 rồi 2 (heavy) đã đủ; tiết thứ 3 liên tiếp (heavy) phải bị chặn.
    subjects = [
        Subject(1, "Toan", ROLE_NANG), Subject(2, "Ly", ROLE_NANG), Subject(3, "HDTN", ROLE_HDTN),
    ]
    role_index = resolve_roles(subjects)
    config = SchedulingConfig(max_heavy_consecutive=2)
    state = _State(remaining_need={(1, 1): 10, (2, 1): 10}, busy=set())

    ts1 = TimeSlot(1, 2, "S", 1)
    assert _feasible(1, ts1, 1, 100, state, role_index, config=config) is True
    _put_at(state, Slot(1, 1, ts1), 1, 100, role_index)

    ts2 = TimeSlot(2, 2, "S", 2)
    assert _feasible(1, ts2, 2, 101, state, role_index, config=config) is True
    _put_at(state, Slot(2, 1, ts2), 2, 101, role_index)

    ts3 = TimeSlot(3, 2, "S", 3)
    assert _feasible(1, ts3, 1, 100, state, role_index, config=config) is False


def test_heavy_subject_consecutive_cap_looser_than_default():
    # N=4: chuỗi 4 tiết heavy liên tiếp phải được phép (mặc định N=3 sẽ chặn ở đây).
    subjects = [
        Subject(1, "Toan", ROLE_NANG), Subject(2, "Ly", ROLE_NANG),
        Subject(3, "Hoa", ROLE_NANG), Subject(4, "HDTN", ROLE_HDTN),
    ]
    role_index = resolve_roles(subjects)
    config = SchedulingConfig(max_heavy_consecutive=4)
    state = _State(remaining_need={(1, 1): 10, (2, 1): 10, (3, 1): 10}, busy=set())

    ts1 = TimeSlot(1, 2, "S", 1)
    _put_at(state, Slot(1, 1, ts1), 1, 100, role_index)
    ts2 = TimeSlot(2, 2, "S", 2)
    _put_at(state, Slot(2, 1, ts2), 2, 101, role_index)
    ts3 = TimeSlot(3, 2, "S", 3)
    _put_at(state, Slot(3, 1, ts3), 3, 102, role_index)

    ts4 = TimeSlot(4, 2, "S", 4)
    assert _feasible(1, ts4, 1, 100, state, role_index, config=config) is True


def test_heavy_subject_run_of_3_cap_unchanged_with_default_config():
    # Regression: gọi lại y hệt test_heavy_subject_run_of_3_cap nhưng truyền config mặc định
    # tường minh -- phải cho kết quả giống hệt không truyền config.
    subjects = [
        Subject(1, "Toan", ROLE_NANG), Subject(2, "Ly", ROLE_NANG),
        Subject(3, "Hoa", ROLE_NANG), Subject(4, "Sinh", ROLE_NANG), Subject(5, "HDTN", ROLE_HDTN),
    ]
    role_index = resolve_roles(subjects)
    config = SchedulingConfig()
    state = _State(remaining_need={(1, 1): 10, (2, 1): 10, (3, 1): 10, (4, 1): 10}, busy=set())
    _put_at(state, Slot(1, 1, TimeSlot(1, 2, "S", 1)), 1, 100, role_index)
    _put_at(state, Slot(2, 1, TimeSlot(2, 2, "S", 2)), 2, 101, role_index)
    _put_at(state, Slot(3, 1, TimeSlot(3, 2, "S", 3)), 3, 102, role_index)
    ts4 = TimeSlot(4, 2, "S", 4)
    assert _feasible(1, ts4, 4, 103, state, role_index, config=config) is False
```

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `python -m pytest tests/test_scheduler.py -k "heavy_subject_consecutive" -v`
Expected: FAIL — `test_heavy_subject_consecutive_cap_stricter_than_default` fails because period 3 is still allowed (window logic still hardcodes N=3); `test_heavy_subject_consecutive_cap_looser_than_default` fails because period 4 is still blocked. `test_heavy_subject_run_of_3_cap_unchanged_with_default_config` should already PASS (sanity check that passing an explicit default `config` doesn't change anything yet).

- [ ] **Step 3: Generalize the window logic**

In `core/scheduler.py`, add the import (alongside the existing imports, currently lines 15-16):

```python
from core import frame as frame_mod
from core.models import ScheduleResult, SchedulingConfig, SchedulingInput, Slot, TimeSlot
from core.roles import resolve_roles
```

In `_feasible`, replace the heavy-subject block (originally lines 103-113, immediately before the function's final `return True`):

```python
    if subject_id in role_index.heavy_ids:
        window = config.max_heavy_consecutive + 1
        last_start = frame_mod.MAX_PERIODS_PER_SESSION - config.max_heavy_consecutive
        for w in range(1, last_start + 1):
            if w <= ts.period <= w + window - 1:
                all_heavy = True
                for offset in range(window):
                    pos = w + offset
                    if not (state.heavy_at.get((class_id, ts.weekday, ts.session, pos), False) or pos == ts.period):
                        all_heavy = False
                        break
                if all_heavy:
                    return False
    return True
```

(This replaces the fixed `for w in (1, 2): ... for offset in range(4): ...` with a generic version: window size `N+1`, iterating every start position `w` for which the window still fits inside a `MAX_PERIODS_PER_SESSION`-period session. For `N=3` this produces `w in (1, 2)` with `range(4)` — identical to the code being replaced.)

- [ ] **Step 4: Run tests to verify everything passes**

Run: `python -m pytest tests/test_scheduler.py -v`
Expected: PASS — all 4 new tests plus every pre-existing test (`test_heavy_subject_run_of_3_cap` included, since default `max_heavy_consecutive=3` reproduces the original window exactly).

- [ ] **Step 5: Commit**

```bash
git add core/scheduler.py tests/test_scheduler.py
git commit -m "feat: generalize heavy-subject consecutive-run cap to configurable max_heavy_consecutive"
```

---

## Task 7: Wire `build_scheduling_input()` to attach the real per-school config

**Files:**
- Modify: `data/repository.py:542-...` (`build_scheduling_input`)
- Test: `tests/test_scheduler.py` (end-to-end integration test)

**Interfaces:**
- Consumes: `repo.get_scheduling_config` (Task 2), `SchedulingInput.config` (Task 1), `frame_mod.active_cells(..., reserved_off_weekdays_chieu=...)` (Task 3)
- Produces: `build_scheduling_input(...)` now returns a `SchedulingInput` whose `.config` reflects the school's saved settings, and whose `.slots` already exclude the configured `reserved_off_weekdays_chieu` cells.

This is the task that proves the whole feature works end-to-end: after this task, a school's saved `SchedulingConfig` actually changes what `sched.run()` produces.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_scheduler.py` (uses the same `conn`/fixture pattern as `tests/test_exporter.py` — import `db` and `import_xlsm`):

```python
import os

from data import db
from io_excel.importer import import_xlsm

FIXTURE = os.path.join(os.path.dirname(__file__), "..", "io_excel", "sample_school.xlsm")


def test_build_scheduling_input_respects_saved_scheduling_config(tmp_path):
    conn = db.get_connection(str(tmp_path / "test.db"))
    db.init_db(conn)
    import_xlsm(conn, FIXTURE)
    repo.set_scheduling_config(conn, SchedulingConfig(gdtc_avoid_period=2))

    inp = repo.build_scheduling_input(conn, parity="C")
    assert inp.config.gdtc_avoid_period == 2

    result = sched.run(inp, max_attempts=6000, target_successes=3)
    assert result.success
    gdtc_id = next(s.subject_id for s in inp.subjects if s.role_code == ROLE_GDTC)
    for slot in inp.slots:
        if slot.ts.period == 2:
            assert result.assignment.get(slot.slot_id) != gdtc_id
    conn.close()
```

Add the missing imports at the top of `tests/test_scheduler.py`: `from data import repository as repo` (if not already imported under a different alias — check the existing import block first and reuse it).

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_scheduler.py -k respects_saved_scheduling_config -v`
Expected: FAIL — `inp.config.gdtc_avoid_period` is `5` (the dataclass default), not `2`, because `build_scheduling_input` never reads the saved config yet.

- [ ] **Step 3: Wire the config into `build_scheduling_input`**

In `data/repository.py`, inside `build_scheduling_input` (currently starting line 542), add a line to fetch the config right after the existing `teachers = list_teachers(conn)` line (currently line 546):

```python
    teachers = list_teachers(conn)
    config = get_scheduling_config(conn)
```

Change the `frame_mod.active_cells(...)` call (currently lines 563-566) to pass the configured reserved days:

```python
        for (wd, session, period) in frame_mod.active_cells(
            morning, afternoon, bool(study_sunday), bool(allow_saturday),
            short_weekday, short_morning, short_afternoon,
            reserved_off_weekdays_chieu=config.reserved_off_weekdays_chieu,
        ):
```

At the end of `build_scheduling_input` (currently lines 583-588), add `config=config` to the `return SchedulingInput(...)` call:

```python
    return SchedulingInput(
        classes=classes, subjects=subjects, teachers=teachers, need=need,
        assigned_teacher=assigned_teacher, ban_busy=ban_busy,
        slots=slots, timeslots=timeslots, seed=seed,
        extra_kep_ids=extra_kep_ids, config=config,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_scheduler.py -v`
Expected: PASS — including the full pre-existing suite (default config reproduces identical `active_cells` output, so no regression).

- [ ] **Step 5: Commit**

```bash
git add data/repository.py tests/test_scheduler.py
git commit -m "feat: build_scheduling_input attaches the school's saved SchedulingConfig end-to-end"
```

---

## Task 8: Pass configured `reserved_off_weekdays_chieu` into display/export call sites

**Files:**
- Modify: `pages/00_Trang_chu.py:16-39`, `pages/05_Khung_tiet.py` (6 `frame_mod.*` call sites), `io_excel/exporter.py:251-377` (`export_full_backup_xlsx`)
- Test: `tests/test_exporter.py`

**Interfaces:**
- Consumes: `repo.get_scheduling_config` (Task 2)

Without this task, a school that changes `reserved_off_weekdays_chieu` would get correct scheduling (Task 7) but a Khung tiết page and exported Excel that still assume Thứ 5/6 chiều are blocked — a real, user-visible inconsistency, not just an edge case.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_exporter.py`:

```python
from core.models import SchedulingConfig


def test_export_full_backup_khung_sheet_respects_custom_reserved_off_weekdays_chieu(conn):
    repo.set_scheduling_config(conn, SchedulingConfig(reserved_off_weekdays_chieu=(2, 3)))
    data = export_full_backup_xlsx(conn)
    wb = openpyxl.load_workbook(io.BytesIO(data))
    ws_khung = wb["Khung"]
    ws_nh = wb["TKB_Nhap"]

    # tìm dòng đầu tiên của lớp đầu tiên ứng với (Chiều, tiết 1)
    target_row = None
    for row in range(2, ws_nh.max_row + 1):
        if ws_nh.cell(row, 2).value == "C" and ws_nh.cell(row, 3).value == 1:
            target_row = row
            break
    assert target_row is not None

    thu5_col = 4 + list(WEEKDAYS).index(5)  # cột Thứ 5
    thu2_col = 4 + list(WEEKDAYS).index(2)  # cột Thứ 2
    assert ws_khung.cell(target_row, thu5_col).value == "x"   # Thứ 5 chiều KHÔNG còn bị khoá
    assert ws_khung.cell(target_row, thu2_col).value != "x"   # Thứ 2 chiều giờ bị khoá thay thế
```

`tests/test_exporter.py` currently imports `from io_excel.exporter import export_xlsx, export_xlsx_both_parities` (line 9) and `from data import db, repository as repo` (line 8) — `repo` is already available, but `export_full_backup_xlsx` is not. Extend line 9 to:

```python
from io_excel.exporter import export_full_backup_xlsx, export_xlsx, export_xlsx_both_parities
```

Also add, near the top of the file: `from core.models import WEEKDAYS` (either as its own line, or merged with the `SchedulingConfig` import already shown above into one `from core.models import SchedulingConfig, WEEKDAYS` line).

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_exporter.py -k custom_reserved_off_weekdays_chieu -v`
Expected: FAIL — `ws_khung.cell(target_row, thu5_col).value` is still `None`/empty because the export still uses the hardcoded default.

- [ ] **Step 3: Wire the config into the three call sites**

`io_excel/exporter.py`, inside `export_full_backup_xlsx(conn)` (starting line 251): add a line fetching the config near the top of the function (with the other `conn`-derived lookups), then pass it into the existing `frame_mod.active_cells(...)` call (currently lines 375-377):

```python
    config = repo.get_scheduling_config(conn)
```

```python
        active_set = set(frame_mod.active_cells(
            morning, afternoon, bool(study_sunday), bool(allow_saturday), short_wd, short_m, short_a,
            reserved_off_weekdays_chieu=config.reserved_off_weekdays_chieu,
        ))
```

(Check the top of `io_excel/exporter.py` for its existing `from data import repository as repo` import — add it if not already present.)

`pages/00_Trang_chu.py`: fetch the config once near the top (after the existing `teachers = repo.list_teachers(conn)` line, currently line 19), and pass it into the `frame_mod.total_cells_per_class(...)` call (currently lines 37-39):

```python
    config = repo.get_scheduling_config(conn)
```

```python
    class_totals[c.class_id] = frame_mod.total_cells_per_class(
        m, a, bool(ss), bool(allow_sat), short_wd, short_m, short_a,
        reserved_off_weekdays_chieu=config.reserved_off_weekdays_chieu,
    )
```

`pages/05_Khung_tiet.py`: fetch the config once near the top (after `conn = get_conn(school_slug)`), then pass `reserved_off_weekdays_chieu=config.reserved_off_weekdays_chieu` into each of its 4 `frame_mod` calls (`total_cells_per_class` at what is currently line 33, `check_capacity` at line 69, `total_cells_per_class` at line 78, `is_short_day_config_valid` at lines 87 and 109, `suggest_short_day` at line 113) — add the keyword argument to each call, keeping all existing positional arguments unchanged.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_exporter.py -v`
Expected: PASS — the new test plus the full pre-existing exporter suite (default config reproduces the current Khung sheet exactly).

Run the full suite once more to confirm nothing else regressed: `python -m pytest -v`
Expected: PASS (all tests across the whole repo).

- [ ] **Step 5: Commit**

```bash
git add pages/00_Trang_chu.py pages/05_Khung_tiet.py io_excel/exporter.py tests/test_exporter.py
git commit -m "feat: reflect configured reserved_off_weekdays_chieu in Khung tiết page, dashboard, and Excel export"
```

---

## Task 9: Dynamic sidebar rules text (`ui_common.py`)

**Files:**
- Modify: `ui_common.py:20-41` (`FIXED_SCHEDULING_RULES`, `sidebar_fixed_rules`)
- Modify: `pages/00_Trang_chu.py`, `pages/01_Khai_bao.py`, `pages/02_PhanCong.py`, `pages/03_DinhMuc.py`, `pages/04_GV_Ban.py`, `pages/05_Khung_tiet.py` (each call site of `sidebar_fixed_rules()`)

**Interfaces:**
- Consumes: `repo.get_scheduling_config` (Task 2)
- Produces: `sidebar_fixed_rules(conn)` (was `sidebar_fixed_rules()` — now requires a connection).

No automated test for this task — `ui_common.py` has no dedicated test file in this repo (Streamlit UI/sidebar code is verified manually, matching the project's existing convention). Verify manually in Step 3.

- [ ] **Step 1: Split the rule list into "configurable" and "fixed" and make the function dynamic**

In `ui_common.py`, replace the current `FIXED_SCHEDULING_RULES` list and `sidebar_fixed_rules` function (currently lines 20-41):

```python
# Ràng buộc sư phạm CỐ ĐỊNH (bất biến thuật toán) -- không có trang cấu hình riêng.
CORE_INVARIANT_RULES = [
    "Không xếp trùng giáo viên trong cùng 1 tiết",
    "Tiết kép xếp liền nhau, cùng buổi",
    "Không buổi nào bị xếp đúng 1 tiết lẻ",
]


def sidebar_fixed_rules(conn) -> None:
    from data import repository as repo

    config = repo.get_scheduling_config(conn)
    configurable_rules = [
        f"Môn nặng (Toán/Lý/Hoá) tối đa {config.max_heavy_consecutive} tiết liên tiếp trong 1 buổi",
        f"Thể dục né Tiết {config.gdtc_avoid_period}",
        f"Chào cờ Thứ {config.chao_co_weekday} Tiết {config.chao_co_period}",
        f"Mỗi giáo viên được xếp đúng {config.teacher_off_sessions_per_week} buổi nghỉ/tuần",
        f"Mỗi giáo viên tối đa {config.max_periods_per_session} tiết/buổi",
        "Buổi/ngày không được chọn làm buổi nghỉ GV: "
        + ", ".join(f"Thứ {wd} {'sáng' if s == 'S' else 'chiều'}"
                     for wd, s in sorted(config.forbidden_off_cells)),
        "Buổi chiều luôn để trống toàn trường (ôn bồi dưỡng/phụ đạo): "
        + ", ".join(f"Thứ {wd}" for wd in config.reserved_off_weekdays_chieu),
    ]
    with st.sidebar:
        with st.expander("📐 Quy tắc xếp lịch"):
            st.caption(
                "7 dòng đầu chỉnh được ở trang **Cấu hình xếp lịch**. "
                "3 dòng cuối là ràng buộc cố định của thuật toán."
            )
            for rule in configurable_rules:
                st.markdown(f"- {rule}")
            st.divider()
            for rule in CORE_INVARIANT_RULES:
                st.markdown(f"- {rule}")
```

- [ ] **Step 2: Update every call site to pass `conn`**

In each of `pages/00_Trang_chu.py`, `pages/01_Khai_bao.py`, `pages/02_PhanCong.py`, `pages/03_DinhMuc.py`, `pages/04_GV_Ban.py`, `pages/05_Khung_tiet.py`, change the existing `sidebar_fixed_rules()` call to `sidebar_fixed_rules(conn)` (every one of these pages already has a `conn` variable in scope from `conn = get_conn(school_slug)` near the top of the file).

- [ ] **Step 3: Manually verify**

Run: `streamlit run app.py`

- Log in, open any of the 6 pages listed above.
- Expand "📐 Quy tắc xếp lịch" in the sidebar — confirm it shows 7 lines with the default values (né Tiết 5, Thứ 2 Tiết 1, etc.) followed by the 3 fixed-invariant lines.
- (This will show live values once Task 10's config page exists — for now just confirm no crash and the defaults render correctly.)

- [ ] **Step 4: Run the full test suite to confirm no regression**

Run: `python -m pytest -v`
Expected: PASS (this task touches no function any test calls directly).

- [ ] **Step 5: Commit**

```bash
git add ui_common.py pages/00_Trang_chu.py pages/01_Khai_bao.py pages/02_PhanCong.py pages/03_DinhMuc.py pages/04_GV_Ban.py pages/05_Khung_tiet.py
git commit -m "feat: sidebar scheduling rules reflect live per-school SchedulingConfig"
```

---

## Task 10: New "Cấu hình xếp lịch" page + navigation entry

**Files:**
- Create: `pages/10_Cau_hinh_Xep_lich.py`
- Modify: `app.py` (register the new page)

**Interfaces:**
- Consumes: `repo.get_scheduling_config`/`set_scheduling_config` (Task 2), `frame_mod.MAX_PERIODS_PER_SESSION` (existing), `core.models.WEEKDAYS`/`WEEKDAY_NAMES` (existing)

No automated test — this is a Streamlit form page; verify manually in Step 2 (matches this repo's existing convention: pages have no dedicated test files, only `core`/`data`/`io_excel` do).

- [ ] **Step 1: Create the page**

Create `pages/10_Cau_hinh_Xep_lich.py`:

```python
import streamlit as st

from core import frame as frame_mod
from core.models import SchedulingConfig, WEEKDAY_NAMES, WEEKDAYS
from data import repository as repo
from ui_common import get_conn, require_auth, require_school, sidebar_backup_export, sidebar_fixed_rules, \
    sidebar_school_switcher

require_auth()
school_slug = require_school()
conn = get_conn(school_slug)
st.title("Cấu hình xếp lịch")
st.caption(
    "Các ràng buộc dưới đây là lựa chọn của từng trường, khác trường có thể cấu hình khác. "
    "Giá trị mặc định đúng bằng hành vi trước khi có trang này."
)

config = repo.get_scheduling_config(conn)
max_p = frame_mod.MAX_PERIODS_PER_SESSION

st.subheader("Vị trí cố định")
c1, c2 = st.columns(2)
gdtc_avoid_period = c1.number_input(
    "GDTC né tiết", 1, max_p, config.gdtc_avoid_period,
    help="Thể dục sẽ không bao giờ được xếp vào tiết này.",
)
chao_co_weekday = c2.selectbox(
    "Chào cờ - Thứ", WEEKDAYS, index=WEEKDAYS.index(config.chao_co_weekday),
    format_func=lambda w: WEEKDAY_NAMES[w],
)
chao_co_period = c1.number_input(
    "Chào cờ - Tiết (buổi sáng)", 1, max_p, config.chao_co_period,
)

st.subheader("Ngưỡng số lượng")
c3, c4, c5 = st.columns(3)
max_heavy_consecutive = c3.number_input(
    "Môn nặng: tối đa mấy tiết liên tiếp", 1, max_p, config.max_heavy_consecutive,
    help="Toán/Lý/Hoá (và các môn đánh dấu \"Nặng\") không được xếp quá số tiết này liên tiếp trong 1 buổi.",
)
max_periods_per_session = c4.number_input(
    "Mỗi giáo viên: tối đa mấy tiết/buổi", 1, max_p, config.max_periods_per_session,
)
teacher_off_sessions_per_week = c5.number_input(
    "Mỗi giáo viên: nghỉ mấy buổi/tuần", 0, 3, config.teacher_off_sessions_per_week,
)

st.subheader("Buổi/ngày khoá cứng")
st.caption("Buổi không được chọn làm buổi nghỉ của giáo viên:")
forbidden_selection = st.multiselect(
    "Buổi cấm chọn làm buổi nghỉ GV",
    options=[(wd, s) for wd in WEEKDAYS for s in ("S", "C")],
    default=sorted(config.forbidden_off_cells),
    format_func=lambda cell: f"{WEEKDAY_NAMES[cell[0]]} {'Sáng' if cell[1] == 'S' else 'Chiều'}",
    label_visibility="collapsed",
)
st.caption("Buổi chiều luôn để trống toàn trường (dành ôn bồi dưỡng/phụ đạo, ngoài TKB):")
reserved_weekdays_selection = st.multiselect(
    "Thứ có buổi chiều luôn trống",
    options=list(WEEKDAYS),
    default=list(config.reserved_off_weekdays_chieu),
    format_func=lambda w: WEEKDAY_NAMES[w],
    label_visibility="collapsed",
)

if st.button("💾 Lưu cấu hình", type="primary"):
    new_config = SchedulingConfig(
        gdtc_avoid_period=int(gdtc_avoid_period),
        chao_co_weekday=int(chao_co_weekday),
        chao_co_period=int(chao_co_period),
        max_heavy_consecutive=int(max_heavy_consecutive),
        max_periods_per_session=int(max_periods_per_session),
        teacher_off_sessions_per_week=int(teacher_off_sessions_per_week),
        forbidden_off_cells=frozenset(forbidden_selection),
        reserved_off_weekdays_chieu=tuple(sorted(reserved_weekdays_selection)),
    )
    repo.set_scheduling_config(conn, new_config)
    st.success("Đã lưu cấu hình xếp lịch.")
    st.rerun()

sidebar_backup_export(conn)
sidebar_fixed_rules(conn)
sidebar_school_switcher()
```

- [ ] **Step 2: Register the page in navigation**

In `app.py`, add the new page to the end of the `"Thiết lập dữ liệu"` list (currently lines 12-18):

```python
    "Thiết lập dữ liệu": [
        st.Page("pages/01_Khai_bao.py", title="Khai báo Lớp / Môn / Giáo viên", icon="🏫"),
        st.Page("pages/02_PhanCong.py", title="Phân công chuyên môn", icon="📋"),
        st.Page("pages/03_DinhMuc.py", title="Định mức tiết / tuần", icon="📊"),
        st.Page("pages/04_GV_Ban.py", title="Giáo viên bận", icon="🚫"),
        st.Page("pages/05_Khung_tiet.py", title="Khung tiết", icon="🗓️"),
        st.Page("pages/10_Cau_hinh_Xep_lich.py", title="Cấu hình xếp lịch", icon="⚙️"),
    ],
```

- [ ] **Step 3: Manually verify**

Run: `streamlit run app.py`

- Log in, select/create a school, open "Thiết lập dữ liệu" → "Cấu hình xếp lịch".
- Confirm all 7 fields show the default values (né tiết 5, Thứ 2/Tiết 1, tối đa 3, tối đa 4, nghỉ 1 buổi, cấm sáng T2/5/6 + chiều T5/T6, chiều T5+T6 trống).
- Change "GDTC né tiết" to 3, click "Lưu cấu hình" — confirm the success message and that the page reloads showing 3 (not 5).
- Open the sidebar "📐 Quy tắc xếp lịch" expander on this or any other page — confirm the "Thể dục né Tiết" line now reads "Tiết 3".
- Go to "Xếp & sửa thời khóa biểu" → "Xếp TKB tự động" and run a schedule — confirm it still succeeds, and that GDTC is never placed in period 3 (spot-check the resulting grid).
- Revert the value back to 5 and save again (leave the demo school in its original state).

- [ ] **Step 4: Run the full test suite one final time**

Run: `python -m pytest -v`
Expected: PASS — entire suite, no regressions from any of the 10 tasks.

- [ ] **Step 5: Commit**

```bash
git add pages/10_Cau_hinh_Xep_lich.py app.py
git commit -m "feat: add Cấu hình xếp lịch page for editing per-school scheduling rules"
```

---

## Self-Review Notes

- **Spec coverage:** All 7 `SchedulingConfig` fields from the spec table are implemented (Tasks 1, 4, 5, 6) and wired end-to-end (Task 7) into the actual `sched.run()` path, plus reflected in every display/export surface that shows active cells (Task 8) and the fixed-rules sidebar (Task 9), with a dedicated editing UI (Task 10). Storage follows the spec's `app_meta` pattern (Task 2). Explicitly out-of-scope items (SHL weekday, algorithm tuning constants, core invariants) are called out in Global Constraints and untouched by every task.
- **Placeholder scan:** No task step defers logic to "later" or references undefined names — every code block is complete, copy-pasteable Python, verified against the actual current file contents (including `_build_input`/`_make_timeslots` in `tests/test_scheduler.py:271-287` and the real end of `build_scheduling_input` in `data/repository.py:583-588`, both read directly rather than guessed).
- **Type consistency:** `SchedulingConfig` field names are identical across every task (`gdtc_avoid_period`, `chao_co_weekday`, `chao_co_period`, `max_heavy_consecutive`, `max_periods_per_session`, `teacher_off_sessions_per_week`, `forbidden_off_cells`, `reserved_off_weekdays_chieu`) — verified against the Task 1 dataclass definition each time they're used in Tasks 2, 4, 5, 6, 7, 8, 9, 10. `_feasible`'s new `config` parameter and `_assign_off_slots`'s new `forbidden_off_cells` parameter keep the same name and position (trailing, optional) everywhere they're threaded.
