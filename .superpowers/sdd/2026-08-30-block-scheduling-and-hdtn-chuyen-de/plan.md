# Mandatory Block Scheduling, HDTN Thematic Week, Heavy-Morning Constraint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make three scheduling rules hard/configurable instead of soft/absent: (R1)
"kép" subjects must be grouped into full N-period contiguous blocks (max-pairing,
≤1 leftover single), (R2) a whole-school per-run "tuần chuyên đề" toggle that forces
HDTN into one 3-period block and skips the fixed chào cờ/SHL pins for that run, and
(R3) an optional hard rule banning heavy ("Nặng") subjects from afternoon slots.

**Architecture:** Generalize the existing permissive kép cap/adjacency check in
`core/scheduler.py::_feasible()` into an N-sized contiguous-block check driven by a
new `RoleIndex.block_size: dict[subject_id, int]`. Add a best-effort repair pass
(mirroring the existing `_repair_lone_periods`/`_has_lone_period` pattern) that
merges excess partial-block days, plus a validation function that rejects an attempt
(triggering the existing best-of-N retry loop) when repair can't fully resolve it.
R2 reuses this same block mechanism at N=3 for HDTN and conditionally skips two
existing pin blocks in `run()`. R3 is one new hard-rejection branch in `_feasible()`
gated by a config flag, default off (behavior-preserving).

**Tech Stack:** Python 3, pytest, Streamlit (UI pages only, no new test framework).

**Spec:** [.superpowers/sdd/2026-08-30-block-scheduling-and-hdtn-chuyen-de/design.md](design.md)

## Global Constraints

- Every new config field defaults to today's exact behavior (off/False/empty) —
  no existing test may need its expected output changed by these tasks unless that
  test is *specifically* about one of R1/R2/R3.
- `positions` tuples stored in `state.placed[...]` are always `(session, period)` —
  never assume a fixed length of 1 or 2 anywhere new code touches them; a block can
  be N periods.
- Vietnamese identifiers stay out of code (existing convention); Vietnamese only in
  comments/docstrings/UI strings, matching every existing file in `core/` and `pages/`.
- Run `python -m pytest` from the repo root (`c:\Users\Kien\tkb_app`) after every task.

---

### Task 1: `RoleIndex.block_size` and `resolve_roles()` thematic-week parameter

**Files:**
- Modify: `core/models.py` (`RoleIndex` dataclass)
- Modify: `core/roles.py` (`resolve_roles()`)
- Test: `tests/test_scheduler.py` (new tests near the existing `resolve_roles` tests,
  around `test_resolve_roles_without_extra_kep_ids_is_unchanged`)

**Interfaces:**
- Consumes: nothing new (pure extension of existing `RoleIndex`/`resolve_roles`).
- Produces: `RoleIndex.block_size: dict` — `subject_id -> int` (block size, only
  present for subjects with a block requirement ≥ 2). `resolve_roles(subjects,
  extra_kep_ids=frozenset(), hdtn_thematic_week=False) -> RoleIndex`. Tasks 2, 4, 5
  read `role_index.block_size.get(subject_id, 1)`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_scheduler.py` right after `test_resolve_roles_without_extra_kep_ids_is_unchanged`:

```python
def test_resolve_roles_block_size_for_kep_subjects():
    subjects = [Subject(1, "Van", ROLE_KEP), Subject(2, "Toan", ROLE_NANG_KEP),
                Subject(3, "Su", ROLE_THUONG), Subject(4, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    assert role_index.block_size == {1: 2, 2: 2}


def test_resolve_roles_block_size_includes_extra_kep_ids():
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects, extra_kep_ids=frozenset({1}))
    assert role_index.block_size == {1: 2}


def test_resolve_roles_hdtn_thematic_week_sets_block_size_3():
    subjects = [Subject(1, "Van", ROLE_KEP), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects, hdtn_thematic_week=True)
    assert role_index.block_size == {1: 2, 2: 3}


def test_resolve_roles_hdtn_thematic_week_off_by_default():
    subjects = [Subject(1, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    assert role_index.block_size == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_scheduler.py -k "block_size" -v`
Expected: FAIL — `RoleIndex` has no attribute `block_size` (AttributeError) or the
new `hdtn_thematic_week` kwarg is unexpected (TypeError).

- [ ] **Step 3: Add `block_size` to `RoleIndex`**

In `core/models.py`, change:

```python
@dataclass
class RoleIndex:
    heavy_ids: set = field(default_factory=set)
    kep_ids: set = field(default_factory=set)
    gdtc_id: Optional[int] = None
    hdtn_id: Optional[int] = None
```

to:

```python
@dataclass
class RoleIndex:
    heavy_ids: set = field(default_factory=set)
    kep_ids: set = field(default_factory=set)
    block_size: dict = field(default_factory=dict)  # subject_id -> N (contiguous periods required, >=2)
    gdtc_id: Optional[int] = None
    hdtn_id: Optional[int] = None
```

- [ ] **Step 4: Populate `block_size` in `resolve_roles()`**

In `core/roles.py`, change the signature and tail of `resolve_roles`:

```python
def resolve_roles(subjects: list, extra_kep_ids: frozenset = frozenset()) -> RoleIndex:
```
to:
```python
def resolve_roles(subjects: list, extra_kep_ids: frozenset = frozenset(),
                   hdtn_thematic_week: bool = False) -> RoleIndex:
```

and change:

```python
    idx.kep_ids |= set(extra_kep_ids)
    if idx.hdtn_id is None:
        raise MissingHDTNError(
            "Không tìm thấy môn có MÃ = 5 (HDTN). Hãy điền số 5 vào cột MÃ VAI TRÒ "
            "tại dòng 'Hoạt động trải nghiệm, hướng nghiệp'."
        )
    return idx
```

to:

```python
    idx.kep_ids |= set(extra_kep_ids)
    if idx.hdtn_id is None:
        raise MissingHDTNError(
            "Không tìm thấy môn có MÃ = 5 (HDTN). Hãy điền số 5 vào cột MÃ VAI TRÒ "
            "tại dòng 'Hoạt động trải nghiệm, hướng nghiệp'."
        )
    # Môn kép (cố định hoặc "chỉ tuần này") cần khối 2 tiết liền kề. "Tuần chuyên đề"
    # (spec 2026-08-30) ghi đè HDTN riêng thành khối 3 -- không cộng dồn với kep_ids.
    for subject_id in idx.kep_ids:
        idx.block_size[subject_id] = 2
    if hdtn_thematic_week:
        idx.block_size[idx.hdtn_id] = 3
    return idx
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_scheduler.py -k "block_size" -v`
Expected: 4 passed.

- [ ] **Step 6: Run the full suite to check for regressions**

Run: `python -m pytest`
Expected: all previously-passing tests still pass (this task only adds a field and
two new lines that don't change any existing branch).

- [ ] **Step 7: Commit**

```bash
git add core/models.py core/roles.py tests/test_scheduler.py
git commit -m "feat: add RoleIndex.block_size and hdtn_thematic_week to resolve_roles"
```

---

### Task 2: Generalize `_feasible()`'s block cap/adjacency check to arbitrary N

**Files:**
- Modify: `core/scheduler.py` (`_feasible()`)
- Test: `tests/test_scheduler.py` (new tests near `test_kep_double_period_adjacency_and_cap`)

**Interfaces:**
- Consumes: `RoleIndex.block_size` (Task 1).
- Produces: `_feasible()` now enforces "at most N same-subject periods per
  (class, weekday), each new one adjacent to either end of the existing run,
  same session" for any subject with a `block_size` entry — replaces the old
  hardcoded N=2 behavior. Subjects absent from `block_size` behave exactly as
  before (`cap_d` defaults to 1, i.e. one period per subject per day).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_scheduler.py` right after `test_kep_second_period_must_be_adjacent`:

```python
def test_block_size_3_allows_extending_either_end_of_the_run():
    subjects = [Subject(1, "HDTN_CD", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects, hdtn_thematic_week=False)
    role_index.block_size[1] = 3
    state = _State(remaining_need={(1, 1): 10}, busy=set())

    ts2 = TimeSlot(1, 2, "S", 2)
    _put_at(state, Slot(1, 1, ts2), 1, 100, role_index)

    # extend forward (period 3) -- still under cap (2 placed, N=3)
    ts3 = TimeSlot(2, 2, "S", 3)
    assert _feasible(1, ts3, 1, 100, state, role_index) is True
    _put_at(state, Slot(2, 1, ts3), 1, 100, role_index)

    # cap reached (2,3 placed, N=3) -- extending backward (period 1) still allowed,
    # it completes the block at exactly 3
    state.occupied[(1, 2, "S", 1)] = True  # satisfy lien-mach for a period-1 placement (always true)
    ts1 = TimeSlot(3, 2, "S", 1)
    assert _feasible(1, ts1, 1, 100, state, role_index) is True
    _put_at(state, Slot(3, 1, ts1), 1, 100, role_index)

    # cap_d=3 reached -- a 4th period the same day is blocked regardless of adjacency
    state.occupied[(1, 2, "S", 4)] = True
    ts4 = TimeSlot(4, 2, "S", 4)
    assert _feasible(1, ts4, 1, 100, state, role_index) is False


def test_block_size_3_rejects_non_adjacent_extension():
    subjects = [Subject(1, "HDTN_CD", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    role_index.block_size[1] = 3
    state = _State(remaining_need={(1, 1): 10}, busy=set())

    ts2 = TimeSlot(1, 2, "S", 2)
    _put_at(state, Slot(1, 1, ts2), 1, 100, role_index)
    ts3 = TimeSlot(2, 2, "S", 3)
    _put_at(state, Slot(2, 1, ts3), 1, 100, role_index)

    # period 5 is not adjacent to the (2,3) run -- must be rejected
    state.occupied[(1, 2, "S", 4)] = True
    ts5 = TimeSlot(3, 2, "S", 5)
    assert _feasible(1, ts5, 1, 100, state, role_index) is False


def test_block_size_defaults_to_one_when_absent():
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    assert role_index.block_size == {}
    state = _State(remaining_need={(1, 1): 10}, busy=set())
    ts1 = TimeSlot(1, 2, "S", 1)
    _put_at(state, Slot(1, 1, ts1), 1, 100, role_index)
    state.occupied[(1, 2, "S", 2)] = True
    ts2 = TimeSlot(2, 2, "S", 2)
    assert _feasible(1, ts2, 1, 100, state, role_index) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_scheduler.py -k "block_size" -v`
Expected: the 3 new tests FAIL (current code caps at 2 regardless of
`role_index.block_size`).

- [ ] **Step 3: Generalize the cap/adjacency block in `_feasible()`**

In `core/scheduler.py`, change:

```python
    positions = state.placed[(class_id, subject_id, ts.weekday)]
    cap_d = 2 if subject_id in role_index.kep_ids else 1
    if len(positions) >= cap_d:
        return False
    if len(positions) == 1:
        p_session, p_period = positions[0]
        if p_session != ts.session or abs(p_period - ts.period) != 1:
            return False
```

to:

```python
    positions = state.placed[(class_id, subject_id, ts.weekday)]
    cap_d = role_index.block_size.get(subject_id, 1)
    if len(positions) >= cap_d:
        return False
    if positions:
        if any(p_session != ts.session for p_session, _p_period in positions):
            return False
        periods = sorted(p_period for _p_session, p_period in positions)
        if ts.period not in (periods[0] - 1, periods[-1] + 1):
            return False
```

(`positions` only ever holds same-session entries in practice since every prior
placement already passed this same check, but checking explicitly here is cheap and
keeps this function correct in isolation without relying on that invariant holding
elsewhere.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_scheduler.py -k "block_size" -v`
Expected: 3 passed (plus the 4 from Task 1 still passing).

- [ ] **Step 5: Run the full suite to check for regressions**

Run: `python -m pytest`
Expected: all tests pass, specifically confirm by name:
`python -m pytest tests/test_scheduler.py -k "kep" -v` — every existing kép test
(`test_kep_double_period_adjacency_and_cap`, `test_kep_second_period_must_be_adjacent`,
`test_extra_kep_ids_makes_normal_subject_require_adjacency_this_run_only`,
`test_extra_kep_ids_forces_adjacency_in_full_run`) still passes unchanged — they
exercise N=2 through `role_index.kep_ids`, which Task 1 already mirrors into
`block_size[sid] = 2`, so behavior is identical.

- [ ] **Step 6: Commit**

```bash
git add core/scheduler.py tests/test_scheduler.py
git commit -m "feat: generalize _feasible block cap/adjacency to arbitrary N via block_size"
```

---

### Task 3: R3 — `heavy_subjects_morning_only` hard config flag

**Files:**
- Modify: `core/models.py` (`SchedulingConfig`)
- Modify: `core/scheduler.py` (`_feasible()`)
- Modify: `data/repository.py` (`get_scheduling_config`, `set_scheduling_config`)
- Test: `tests/test_scheduler.py` (near `test_gdtc_avoid_period_configurable`)
- Test: `tests/test_repository.py` (config round-trip — check this file's existing
  pattern first, see Step 1 note)

**Interfaces:**
- Consumes: `role_index.heavy_ids` (already exists).
- Produces: `SchedulingConfig.heavy_subjects_morning_only: bool` (default `False`).
  `_feasible()` rejects any heavy subject at an afternoon ("C") slot when this flag
  is on. `get_scheduling_config`/`set_scheduling_config` persist it via app_meta key
  `sched_heavy_subjects_morning_only`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_scheduler.py`, add after `test_gdtc_avoid_period_configurable`:

```python
def test_heavy_subjects_morning_only_off_by_default_allows_afternoon():
    subjects = [Subject(1, "Toan", ROLE_NANG), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    state = _State(remaining_need={(1, 1): 10}, busy=set())
    ts_afternoon = TimeSlot(1, 2, "C", 1)
    assert _feasible(1, ts_afternoon, 1, 100, state, role_index) is True


def test_heavy_subjects_morning_only_rejects_afternoon_when_on():
    subjects = [Subject(1, "Toan", ROLE_NANG), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    state = _State(remaining_need={(1, 1): 10}, busy=set())
    config = SchedulingConfig(heavy_subjects_morning_only=True)
    ts_afternoon = TimeSlot(1, 2, "C", 1)
    assert _feasible(1, ts_afternoon, 1, 100, state, role_index, config=config) is False
    ts_morning = TimeSlot(2, 2, "S", 1)
    assert _feasible(1, ts_morning, 1, 100, state, role_index, config=config) is True


def test_heavy_subjects_morning_only_does_not_restrict_non_heavy_subjects():
    subjects = [Subject(1, "Nhac", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    state = _State(remaining_need={(1, 1): 10}, busy=set())
    config = SchedulingConfig(heavy_subjects_morning_only=True)
    ts_afternoon = TimeSlot(1, 2, "C", 1)
    assert _feasible(1, ts_afternoon, 1, 100, state, role_index, config=config) is True
```

Add to `tests/test_repository.py`, after `test_set_then_get_scheduling_config_round_trips_soft_bias_fields`:

```python
def test_set_then_get_scheduling_config_round_trips_heavy_subjects_morning_only(conn):
    custom = SchedulingConfig(heavy_subjects_morning_only=True)
    repo.set_scheduling_config(conn, custom)
    assert repo.get_scheduling_config(conn) == custom
    assert repo.get_scheduling_config(conn).heavy_subjects_morning_only is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_scheduler.py -k "heavy_subjects_morning_only" tests/test_repository.py -k "heavy_subjects_morning_only" -v`
Expected: FAIL — `SchedulingConfig` has no field `heavy_subjects_morning_only`.

- [ ] **Step 3: Add the config field**

In `core/models.py`, in `SchedulingConfig`, add a new field after
`afternoon_preferred_subject_ids`:

```python
    afternoon_preferred_subject_ids: frozenset = field(default_factory=frozenset)  # rỗng = tắt
    heavy_subjects_morning_only: bool = False   # True = môn Nặng cấm cứng xếp buổi chiều (R3, spec 2026-08-30)
```

- [ ] **Step 4: Add the hard rejection in `_feasible()`**

In `core/scheduler.py`, change:

```python
    if subject_id == role_index.gdtc_id and ts.period == config.gdtc_avoid_period:
        return False
```

to:

```python
    if subject_id == role_index.gdtc_id and ts.period == config.gdtc_avoid_period:
        return False
    if config.heavy_subjects_morning_only and subject_id in role_index.heavy_ids and ts.session == "C":
        return False
```

- [ ] **Step 5: Wire persistence in `data/repository.py`**

In `get_scheduling_config`, change the closing `return SchedulingConfig(...)` call
to add one more kwarg (keep every existing kwarg exactly as-is, just add this line
before the closing `)`):

```python
        afternoon_preferred_subject_ids=(
            _parse_id_set(afternoon_preferred_raw) if afternoon_preferred_raw
            else default.afternoon_preferred_subject_ids
        ),
        heavy_subjects_morning_only=bool(int(get_meta(conn, "sched_heavy_subjects_morning_only") or 0)),
    )
```

In `set_scheduling_config`, add one more line at the end, before the function's
closing (after the existing `set_meta(conn, "sched_afternoon_preferred_subject_ids", ...)` line):

```python
    set_meta(conn, "sched_afternoon_preferred_subject_ids", _format_id_set(config.afternoon_preferred_subject_ids))
    set_meta(conn, "sched_heavy_subjects_morning_only", str(int(config.heavy_subjects_morning_only)))
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_scheduler.py -k "heavy_subjects_morning_only" tests/test_repository.py -k "heavy_subjects_morning_only" -v`
Expected: all new tests pass.

- [ ] **Step 7: Run the full suite to check for regressions**

Run: `python -m pytest`
Expected: all tests pass (the flag defaults to `False`, so every existing
`_feasible()` call site and every existing config round-trip test is unaffected).

- [ ] **Step 8: Commit**

```bash
git add core/models.py core/scheduler.py data/repository.py tests/test_scheduler.py tests/test_repository.py
git commit -m "feat: add heavy_subjects_morning_only hard scheduling config flag"
```

---

### Task 4: Mandatory block-pairing — scoring bonus, repair pass, validation

**Files:**
- Modify: `core/scheduler.py` (new constant, `_pick_best_scored()`, new
  `_repair_unpaired_blocks()` / `_merge_one_block_period()` / `_has_unpaired_block()`,
  `run()` wiring)
- Test: `tests/test_scheduler.py` (unit tests for the new functions, plus one
  full-run regression test)

**Interfaces:**
- Consumes: `role_index.block_size` (Task 1/2), `state.placed`, `_remove_at`,
  `_put_at`, `_feasible`, `_pick_best_simple` (all pre-existing).
- Produces:
  - `_repair_unpaired_blocks(inp: SchedulingInput, state: _State, role_index,
    assigned_teacher: dict, slot_by_coord: dict, day_capacity: Optional[dict],
    config: Optional[SchedulingConfig], subject_class_allowed_cells: Optional[dict]) -> None`
  - `_has_unpaired_block(inp: SchedulingInput, state: _State, role_index) -> bool`
  - `run()` now builds `slot_by_coord: dict[(class_id, weekday, session, period), Slot]`
    once per call, and calls the two functions above once per successful attempt
    (mirrors `_repair_lone_periods`/`_has_lone_period`).

- [ ] **Step 1: Write the failing unit tests for the repair/validation functions**

Add to `tests/test_scheduler.py` (a new section after the existing
`_repair_lone_periods`/`_has_lone_period` tests — search the file for
`_has_lone_period` to find that section and add these tests right after it):

```python
def _slot_by_coord(slots):
    return {(s.class_id, s.ts.weekday, s.ts.session, s.ts.period): s for s in slots}


def test_has_unpaired_block_false_when_fully_paired():
    classes = [ClassRoom(1, "6A")]
    subjects = [Subject(1, "Van", ROLE_KEP), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    timeslots = _make_timeslots(morning=5, afternoon=0)
    inp = _build_input(classes, subjects, [Teacher(1, "GV1"), Teacher(2, "GV2")],
                        {(1, 1): 2, (2, 1): 3}, {(1, 1): 1, (2, 1): 2}, timeslots)
    state = _State(remaining_need={}, busy=set())
    ts1 = TimeSlot(1, 2, "S", 1)
    ts2 = TimeSlot(2, 2, "S", 2)
    _put_at(state, Slot(1, 1, ts1), 1, 100, role_index)
    _put_at(state, Slot(2, 1, ts2), 1, 100, role_index)
    assert sched._has_unpaired_block(inp, state, role_index) is False


def test_has_unpaired_block_true_when_two_lone_days_exceed_allowance():
    classes = [ClassRoom(1, "6A")]
    subjects = [Subject(1, "Van", ROLE_KEP), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    timeslots = _make_timeslots(morning=5, afternoon=0)
    inp = _build_input(classes, subjects, [Teacher(1, "GV1"), Teacher(2, "GV2")],
                        {(1, 1): 2, (2, 1): 3}, {(1, 1): 1, (2, 1): 2}, timeslots)
    state = _State(remaining_need={}, busy=set())
    # 2 periods needed (block_size=2), but placed as 2 separate lone days -- excess
    ts_mon = TimeSlot(1, 2, "S", 1)
    ts_tue = TimeSlot(2, 3, "S", 1)
    _put_at(state, Slot(1, 1, ts_mon), 1, 100, role_index)
    _put_at(state, Slot(2, 1, ts_tue), 1, 100, role_index)
    assert sched._has_unpaired_block(inp, state, role_index) is True


def test_has_unpaired_block_allows_exactly_one_leftover_single():
    # N=2, total_placed=3 (odd) -- 1 full pair + 1 leftover single is fine.
    classes = [ClassRoom(1, "6A")]
    subjects = [Subject(1, "Anh", ROLE_KEP), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    timeslots = _make_timeslots(morning=5, afternoon=0)
    inp = _build_input(classes, subjects, [Teacher(1, "GV1"), Teacher(2, "GV2")],
                        {(1, 1): 3, (2, 1): 3}, {(1, 1): 1, (2, 1): 2}, timeslots)
    state = _State(remaining_need={}, busy=set())
    ts_mon1 = TimeSlot(1, 2, "S", 1)
    ts_mon2 = TimeSlot(2, 2, "S", 2)
    ts_tue = TimeSlot(3, 3, "S", 1)
    _put_at(state, Slot(1, 1, ts_mon1), 1, 100, role_index)
    _put_at(state, Slot(2, 1, ts_mon2), 1, 100, role_index)
    _put_at(state, Slot(3, 1, ts_tue), 1, 100, role_index)
    assert sched._has_unpaired_block(inp, state, role_index) is False


def test_merge_one_block_period_merges_two_lone_days_into_a_pair():
    classes = [ClassRoom(1, "6A")]
    subjects = [Subject(1, "Van", ROLE_KEP), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    timeslots = _make_timeslots(morning=5, afternoon=0)
    inp = _build_input(classes, subjects, [Teacher(1, "GV1"), Teacher(2, "GV2")],
                        {(1, 1): 2, (2, 1): 3}, {(1, 1): 1, (2, 1): 2}, timeslots)
    slot_by_coord = _slot_by_coord(inp.slots)
    state = _State(remaining_need={(1, 1): 0, (2, 1): 0}, busy=set())
    ts_mon = TimeSlot(1, 2, "S", 1)
    ts_tue = TimeSlot(2, 3, "S", 3)
    _put_at(state, Slot(1, 1, ts_mon), 1, 100, role_index)
    _put_at(state, Slot(2, 1, ts_tue), 1, 100, role_index)

    ok = sched._merge_one_block_period(1, 1, 3, 2, state, role_index, subjects,
                                        {(1, 1): 100, (2, 1): 101}, slot_by_coord, None, None, None)
    assert ok is True
    assert state.placed[(1, 1, 3)] == []
    positions = sorted(state.placed[(1, 1, 2)])
    assert positions == [("S", 1), ("S", 2)]


def test_repair_unpaired_blocks_resolves_three_lone_hdtn_days_into_one_block():
    classes = [ClassRoom(1, "6A")]
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects, hdtn_thematic_week=True)
    teachers = [Teacher(1, "GVToan"), Teacher(2, "GVCN")]
    need = {(1, 1): 2, (2, 1): 3}
    assigned_teacher = {(1, 1): 1, (2, 1): 2}
    timeslots = _make_timeslots(morning=5, afternoon=0)
    inp = _build_input(classes, subjects, teachers, need, assigned_teacher, timeslots)
    slot_by_coord = _slot_by_coord(inp.slots)
    state = _State(remaining_need={(1, 1): 0, (2, 1): 0}, busy=set())
    for wd, period in ((2, 1), (3, 1), (4, 1)):
        _put_at(state, Slot(wd, 1, TimeSlot(wd, wd, "S", period)), 2, assigned_teacher[(2, 1)], role_index)
    assert sched._has_unpaired_block(inp, state, role_index) is True

    sched._repair_unpaired_blocks(inp, state, role_index, assigned_teacher, slot_by_coord, None, None, None)

    assert sched._has_unpaired_block(inp, state, role_index) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_scheduler.py -k "unpaired_block or merge_one_block" -v`
Expected: FAIL — `sched._has_unpaired_block`, `sched._merge_one_block_period`,
`sched._repair_unpaired_blocks` don't exist yet.

- [ ] **Step 3: Add the scoring bonus constant**

In `core/scheduler.py`, change:

```python
AFTERNOON_MISMATCH_PENALTY = 30   # điểm phạt khi môn KHÔNG nằm trong config.afternoon_preferred_subject_ids
                                  # rơi vào buổi chiều (rỗng = tắt -- không phạt gì)
```

to:

```python
AFTERNOON_MISMATCH_PENALTY = 30   # điểm phạt khi môn KHÔNG nằm trong config.afternoon_preferred_subject_ids
                                  # rơi vào buổi chiều (rỗng = tắt -- không phạt gì)
BLOCK_COMPLETE_BONUS = 40         # điểm thưởng khi tiếp tục/hoàn thành 1 khối N tiết liền kề (role_index.block_size)
                                  # -- gợi ý hiệu quả, không phải nguồn đúng đắn: _has_unpaired_block +
                                  # best-of-N mới là cơ chế đảm bảo (xem _repair_unpaired_blocks)
```

- [ ] **Step 4: Add the bonus to `_pick_best_scored`**

In `core/scheduler.py`, change:

```python
        if (ts.session == "C" and config.afternoon_preferred_subject_ids
                and subj.subject_id not in config.afternoon_preferred_subject_ids):
            score -= AFTERNOON_MISMATCH_PENALTY
        if slot.old_subject_id == subj.subject_id and rng.random() > pu:
```

to:

```python
        if (ts.session == "C" and config.afternoon_preferred_subject_ids
                and subj.subject_id not in config.afternoon_preferred_subject_ids):
            score -= AFTERNOON_MISMATCH_PENALTY
        if role_index.block_size.get(subj.subject_id, 1) >= 2 and state.placed[(class_id, subj.subject_id, ts.weekday)]:
            score += BLOCK_COMPLETE_BONUS
        if slot.old_subject_id == subj.subject_id and rng.random() > pu:
```

- [ ] **Step 5: Add `_merge_one_block_period`, `_repair_unpaired_blocks`, `_has_unpaired_block`**

In `core/scheduler.py`, add these three functions right after `_has_lone_period`
(before `_pick_best_scored`):

```python
def _merge_one_block_period(class_id: int, subject_id: int, wd_from: int, wd_to: int,
                             state: _State, role_index, subjects: list, assigned_teacher: dict,
                             slot_by_coord: dict, day_capacity: Optional[dict],
                             config: Optional[SchedulingConfig],
                             subject_class_allowed_cells: Optional[dict]) -> bool:
    """Move exactly one already-placed period of (subject_id, class_id) from the
    partial day wd_from onto the open end of wd_to's existing run, extending it by
    one. Mirrors _try_swap_repair's remove/place/refill/rollback shape: if the
    target cell is occupied by a different subject, that subject is displaced and
    re-homed at the vacated source cell (or left as slack -1, or the whole merge is
    rolled back to its original state). Returns False, with state fully restored,
    if no adjacent target cell works.
    """
    from_positions = state.placed[(class_id, subject_id, wd_from)]
    to_positions = state.placed[(class_id, subject_id, wd_to)]
    if not from_positions or not to_positions:
        return False
    session_from, period_from = from_positions[-1]
    session_to = to_positions[0][0]
    to_periods = sorted(p_period for _p_session, p_period in to_positions)
    source = slot_by_coord[(class_id, wd_from, session_from, period_from)]
    teacher_id = assigned_teacher[(subject_id, class_id)]

    for target_period in (to_periods[-1] + 1, to_periods[0] - 1):
        target = slot_by_coord.get((class_id, wd_to, session_to, target_period))
        if target is None:
            continue
        occupant = state.assigned.get(target.slot_id)
        if occupant == -1:
            continue
        displaced_subject, displaced_teacher = (None, None)
        if occupant is not None:
            displaced_subject, displaced_teacher = _remove_at(state, target, role_index)
        _remove_at(state, source, role_index)
        if _feasible(class_id, target.ts, subject_id, teacher_id, state, role_index, day_capacity, config,
                      subject_class_allowed_cells):
            _put_at(state, target, subject_id, teacher_id, role_index)
            if displaced_subject is None:
                return True
            if _feasible(class_id, source.ts, displaced_subject, displaced_teacher, state, role_index,
                          day_capacity, config, subject_class_allowed_cells):
                _put_at(state, source, displaced_subject, displaced_teacher, role_index)
                return True
            pick = _pick_best_simple(class_id, source, state, role_index, subjects, assigned_teacher,
                                      day_capacity, config, subject_class_allowed_cells)
            if pick is not None:
                _put_at(state, source, pick[0], pick[1], role_index)
                return True
            if state.rem_slot_count[class_id] > state.rem_need_count[class_id]:
                state.assigned[source.slot_id] = -1
                state.rem_slot_count[class_id] -= 1
                return True
            # no refill found and no slack -- roll back this whole merge attempt
            _remove_at(state, target, role_index)
            _put_at(state, source, subject_id, teacher_id, role_index)
            _put_at(state, target, displaced_subject, displaced_teacher, role_index)
            return False
        # target infeasible for our subject -- restore source and target, try the other end
        _put_at(state, source, subject_id, teacher_id, role_index)
        if displaced_subject is not None:
            _put_at(state, target, displaced_subject, displaced_teacher, role_index)
    return False


def _repair_unpaired_blocks(inp: SchedulingInput, state: _State, role_index,
                             assigned_teacher: dict, slot_by_coord: dict,
                             day_capacity: Optional[dict], config: Optional[SchedulingConfig] = None,
                             subject_class_allowed_cells: Optional[dict] = None) -> None:
    """Best-effort: for every (class, block subject) with more partial (0 < count <
    N) days than the weekly total allows (at most one, and only when the total
    isn't a multiple of N), merge two partial days into a fuller one via
    _merge_one_block_period until no more excess remains or no merge succeeds.
    _has_unpaired_block is the authoritative check run afterwards in case a merge
    isn't found here.
    """
    for cls in inp.classes:
        class_id = cls.class_id
        for subject_id, block_n in role_index.block_size.items():
            if block_n < 2:
                continue
            total_placed = sum(len(state.placed[(class_id, subject_id, wd)]) for wd in WEEKDAYS)
            if total_placed == 0:
                continue
            allowed_partial_days = 1 if total_placed % block_n else 0
            partial_days = [wd for wd in WEEKDAYS
                             if 0 < len(state.placed[(class_id, subject_id, wd)]) < block_n]
            while len(partial_days) > allowed_partial_days:
                merged = False
                for wd_a in partial_days:
                    for wd_b in partial_days:
                        if wd_b == wd_a:
                            continue
                        if len(state.placed[(class_id, subject_id, wd_b)]) >= block_n:
                            continue
                        if _merge_one_block_period(class_id, subject_id, wd_a, wd_b, state, role_index,
                                                    inp.subjects, assigned_teacher, slot_by_coord,
                                                    day_capacity, config, subject_class_allowed_cells):
                            merged = True
                            break
                    if merged:
                        break
                if not merged:
                    break
                partial_days = [wd for wd in WEEKDAYS
                                 if 0 < len(state.placed[(class_id, subject_id, wd)]) < block_n]


def _has_unpaired_block(inp: SchedulingInput, state: _State, role_index) -> bool:
    """True if any (class, block subject) has more partial-day placements left than
    its weekly total allows (see _repair_unpaired_blocks's docstring for the rule).
    """
    for cls in inp.classes:
        class_id = cls.class_id
        for subject_id, block_n in role_index.block_size.items():
            if block_n < 2:
                continue
            total_placed = sum(len(state.placed[(class_id, subject_id, wd)]) for wd in WEEKDAYS)
            if total_placed == 0:
                continue
            allowed_partial_days = 1 if total_placed % block_n else 0
            partial_days = sum(
                1 for wd in WEEKDAYS if 0 < len(state.placed[(class_id, subject_id, wd)]) < block_n
            )
            if partial_days > allowed_partial_days:
                return True
    return False
```

- [ ] **Step 6: Run the new unit tests to verify they pass**

Run: `python -m pytest tests/test_scheduler.py -k "unpaired_block or merge_one_block" -v`
Expected: all pass.

- [ ] **Step 7: Wire `slot_by_coord` and the repair/validation calls into `run()`**

In `core/scheduler.py`, inside `run()`, find the loop that builds `slots_by_class`
etc.:

```python
    for slot in inp.slots:
        slot_cls_n[slot.class_id] += 1
        slots_by_ts[slot.ts.ts_id].append(slot)
        slots_by_class[slot.class_id].append(slot)
        day_capacity[(slot.class_id, slot.ts.weekday)] += 1
```

change to (adds `slot_by_coord` construction to the same loop, plus its
initialization above it):

```python
    slot_by_coord = {}
    for slot in inp.slots:
        slot_cls_n[slot.class_id] += 1
        slots_by_ts[slot.ts.ts_id].append(slot)
        slots_by_class[slot.class_id].append(slot)
        day_capacity[(slot.class_id, slot.ts.weekday)] += 1
        slot_by_coord[(slot.class_id, slot.ts.weekday, slot.ts.session, slot.ts.period)] = slot
```

Then find the existing lone-period repair/validation block inside the per-attempt
loop:

```python
        if done:
            _repair_lone_periods(inp, state, role_index, assigned_teacher, slots_by_class, day_capacity, config,
                                  subject_class_allowed_cells)
            if _has_lone_period(inp, state):
                done = False
```

change to:

```python
        if done:
            _repair_lone_periods(inp, state, role_index, assigned_teacher, slots_by_class, day_capacity, config,
                                  subject_class_allowed_cells)
            if _has_lone_period(inp, state):
                done = False

        if done:
            _repair_unpaired_blocks(inp, state, role_index, assigned_teacher, slot_by_coord, day_capacity, config,
                                     subject_class_allowed_cells)
            if _has_unpaired_block(inp, state, role_index):
                done = False
```

- [ ] **Step 8: Write a full-run regression test with a real odd-count scenario**

Add to `tests/test_scheduler.py` after `test_extra_kep_ids_forces_adjacency_in_full_run`:

```python
def test_full_run_kep_subject_with_odd_weekly_count_pairs_maximally():
    # Mirrors the real school data found during root-cause investigation: Ngoại ngữ
    # is a kép subject with an odd weekly count (3) in every class -- must place as
    # 1 full pair + exactly 1 leftover single, never scattered as 3 separate days.
    classes = [ClassRoom(1, "6A")]
    subjects = [
        Subject(1, "Ngoai ngu", ROLE_NANG_KEP, 1),
        Subject(2, "HDTN", ROLE_HDTN, 2),
    ]
    teachers = [Teacher(1, "GVAnh"), Teacher(2, "GVCN", is_gvcn=True)]
    need = {(1, 1): 3, (2, 1): 3}
    assigned_teacher = {(1, 1): 1, (2, 1): 2}
    timeslots = _make_timeslots(morning=5, afternoon=0)
    inp = _build_input(classes, subjects, teachers, need, assigned_teacher, timeslots, seed=7)

    result = sched.run(inp, max_attempts=6000, target_successes=5)
    assert result.success is True

    placed = defaultdict(list)
    for slot in inp.slots:
        if result.assignment.get(slot.slot_id) == 1:
            placed[slot.ts.weekday].append(slot.ts.period)
    day_counts = sorted(len(v) for v in placed.values())
    assert day_counts == [1, 2], day_counts
    paired_day = [wd for wd, periods in placed.items() if len(periods) == 2][0]
    p1, p2 = sorted(placed[paired_day])
    assert p2 - p1 == 1
```

This test is written after Steps 3-7 already implement the mechanism it exercises
(unlike Steps 1-2's unit tests, it can't meaningfully drive implementation from RED
— its purpose is to confirm the pieces compose correctly at full-`run()` scale, the
same role Task 7's combined test plays). Confirm it's actually exercising the new
code, not passing by luck of the random seed, per Step 9.

- [ ] **Step 9: Confirm the test is meaningful, then run it**

Run: `python -m pytest tests/test_scheduler.py::test_full_run_kep_subject_with_odd_weekly_count_pairs_maximally -v`
Expected: PASS. To confirm this isn't a coincidence of the `seed=7` value, temporarily
comment out the two lines added in Step 7 (the `_repair_unpaired_blocks`/
`_has_unpaired_block` call), rerun the same command, and confirm it now FAILS
(`day_counts` comes back `[1, 1, 1]` instead of `[1, 2]`) — then restore the two
lines before continuing.

- [ ] **Step 10: Run the full suite to check for regressions**

Run: `python -m pytest`
Expected: all tests pass, including every existing kép/full-run test
(`test_small_synthetic_schedule_succeeds_and_meets_quotas`,
`test_extra_kep_ids_forces_adjacency_in_full_run`,
`test_full_run_succeeds_with_both_soft_subject_preferences_enabled`,
`test_full_run_succeeds_with_teacher_pinned_and_override_off_days`,
`test_subject_class_allowed_cells_holds_across_every_placement_in_a_real_run`) — if
any of these starts failing or needs a materially higher `max_attempts` to pass
reliably, treat that as this task's expected trade-off (§10 of the spec) only if
it's an *attempt-count* regression, not a *correctness* regression; if a previously
`ROLE_THUONG`/non-block subject's test starts failing, that's a real bug in Task 2
or Task 4 — stop and re-investigate before continuing.

- [ ] **Step 11: Commit**

```bash
git add core/scheduler.py tests/test_scheduler.py
git commit -m "feat: enforce mandatory block pairing via repair pass and validation"
```

---

### Task 5: R2 — HDTN "tuần chuyên đề" per-run toggle

**Files:**
- Modify: `core/models.py` (`SchedulingInput`)
- Modify: `core/scheduler.py` (`run()`)
- Modify: `data/repository.py` (`build_scheduling_input`)
- Modify: `tests/test_scheduler.py` (`_build_input` helper)
- Test: `tests/test_scheduler.py` (new full-run test)

**Interfaces:**
- Consumes: `role_index.block_size` (Task 1/2/4's repair+validation).
- Produces: `SchedulingInput.hdtn_thematic_week: bool` (default `False`).
  `repo.build_scheduling_input(conn, parity, seed=0, extra_kep_ids=frozenset(),
  hdtn_thematic_week=False)`. When `True`, `run()` skips the chào cờ pin and the
  SHL reservation/placement blocks entirely, and HDTN's 3 weekly periods flow
  through the general block-aware greedy fill (N=3) instead.

- [ ] **Step 1: Write the failing full-run test**

Add to `tests/test_scheduler.py` after `test_shl_pinned_last_morning_period_2buoi`
(search for that test name to find the right neighborhood — it's the existing SHL
pin test this new test intentionally contrasts with):

```python
def test_hdtn_thematic_week_forms_one_block_and_skips_chao_co_shl_pins():
    classes = [ClassRoom(1, "6A")]
    subjects = [Subject(1, "Toan", ROLE_THUONG, 1), Subject(2, "HDTN", ROLE_HDTN, 2)]
    teachers = [Teacher(1, "GVToan"), Teacher(2, "GVCN", is_gvcn=True)]
    need = {(1, 1): 4, (2, 1): 3}
    assigned_teacher = {(1, 1): 1, (2, 1): 2}
    timeslots = _make_timeslots(morning=5, afternoon=0, weekdays=(2, 3, 4, 5, 6, 7))
    inp = _build_input(classes, subjects, teachers, need, assigned_teacher, timeslots,
                        seed=3, hdtn_thematic_week=True)

    result = sched.run(inp, max_attempts=6000, target_successes=5)
    assert result.success is True

    placed = defaultdict(list)
    for slot in inp.slots:
        if result.assignment.get(slot.slot_id) == 2:
            placed[slot.ts.weekday].append(slot.ts.period)
    # All 3 periods land on a single weekday, contiguous -- this alone proves the
    # chào cờ (Monday period 1) and SHL (Friday/Saturday last period) pins were
    # skipped: those two pins anchor HDTN to two *different*, non-adjacent
    # weekdays, which would make a single 3-period contiguous block impossible.
    assert len(placed) == 1, placed
    (_weekday, periods), = placed.items()
    periods = sorted(periods)
    assert periods == [periods[0], periods[0] + 1, periods[0] + 2]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_scheduler.py::test_hdtn_thematic_week_forms_one_block_and_skips_chao_co_shl_pins -v`
Expected: FAIL — `_build_input()` raises `TypeError` (`hdtn_thematic_week` unknown
kwarg) or, once that's patched locally, `SchedulingInput` rejects the field.

- [ ] **Step 3: Add the field to `SchedulingInput`**

In `core/models.py`, change:

```python
    extra_kep_ids: frozenset = field(default_factory=frozenset)  # subject_id cần xếp kép CHỈ tuần này
    config: SchedulingConfig = field(default_factory=SchedulingConfig)
```

to:

```python
    extra_kep_ids: frozenset = field(default_factory=frozenset)  # subject_id cần xếp kép CHỈ tuần này
    hdtn_thematic_week: bool = False   # True = tuần chuyên đề CHỈ tuần này (R2, spec 2026-08-30):
                                        # HDTN dồn 3 tiết liền kề, bỏ ghim chào cờ + SHL
    config: SchedulingConfig = field(default_factory=SchedulingConfig)
```

- [ ] **Step 4: Add the kwarg to the `_build_input` test helper**

In `tests/test_scheduler.py`, change:

```python
def _build_input(classes, subjects, teachers, need, assigned_teacher, timeslots,
                  seed=12345, ban_busy=None, old_subject=None, extra_kep_ids=frozenset()):
    slots = []
    slot_id = 0
    for c in classes:
        for ts in timeslots:
            slot_id += 1
            old = None
            if old_subject:
                old = old_subject.get((c.class_id, ts.weekday, ts.session, ts.period))
            slots.append(Slot(slot_id, c.class_id, ts, old_subject_id=old))
    return SchedulingInput(
        classes=classes, subjects=subjects, teachers=teachers, need=need,
        assigned_teacher=assigned_teacher, ban_busy=ban_busy or set(),
        slots=slots, timeslots=timeslots, seed=seed,
        extra_kep_ids=extra_kep_ids,
    )
```

to:

```python
def _build_input(classes, subjects, teachers, need, assigned_teacher, timeslots,
                  seed=12345, ban_busy=None, old_subject=None, extra_kep_ids=frozenset(),
                  hdtn_thematic_week=False):
    slots = []
    slot_id = 0
    for c in classes:
        for ts in timeslots:
            slot_id += 1
            old = None
            if old_subject:
                old = old_subject.get((c.class_id, ts.weekday, ts.session, ts.period))
            slots.append(Slot(slot_id, c.class_id, ts, old_subject_id=old))
    return SchedulingInput(
        classes=classes, subjects=subjects, teachers=teachers, need=need,
        assigned_teacher=assigned_teacher, ban_busy=ban_busy or set(),
        slots=slots, timeslots=timeslots, seed=seed,
        extra_kep_ids=extra_kep_ids, hdtn_thematic_week=hdtn_thematic_week,
    )
```

- [ ] **Step 5: Thread `hdtn_thematic_week` into `resolve_roles()` inside `run()`**

In `core/scheduler.py`, change:

```python
    role_index = resolve_roles(inp.subjects, inp.extra_kep_ids)
```

to:

```python
    role_index = resolve_roles(inp.subjects, inp.extra_kep_ids, inp.hdtn_thematic_week)
```

- [ ] **Step 6: Skip chào cờ pin and SHL reservation for a thematic-week run**

In `core/scheduler.py`, find the SHL setup block:

```python
    shl_target_slot = {}    # class_id -> Slot (ô tiết cuối sáng T6/T7)
    for cls in inp.classes:
        target_wd = 6 if class_has_chieu[cls.class_id] else 7
        day_slots = [s for s in morning_slots_by_class[cls.class_id] if s.ts.weekday == target_wd]
        if day_slots:
            shl_target_slot[cls.class_id] = max(day_slots, key=lambda s: s.ts.period)
    classes_with_shl_target = set(shl_target_slot)
    shl_days = {(cid, slot.ts.weekday) for cid, slot in shl_target_slot.items()}

    gvcn_shl_cell = {}      # teacher_id -> (weekday, "S") ô SHL của lớp GVCN đó
    for cls in inp.classes:
        homeroom_teacher = assigned_teacher.get((role_index.hdtn_id, cls.class_id))
        target = shl_target_slot.get(cls.class_id)
        if homeroom_teacher is not None and target is not None:
            gvcn_shl_cell[homeroom_teacher] = (target.ts.weekday, target.ts.session)
```

change to (adds two resets at the end, when thematic week is on):

```python
    shl_target_slot = {}    # class_id -> Slot (ô tiết cuối sáng T6/T7)
    for cls in inp.classes:
        target_wd = 6 if class_has_chieu[cls.class_id] else 7
        day_slots = [s for s in morning_slots_by_class[cls.class_id] if s.ts.weekday == target_wd]
        if day_slots:
            shl_target_slot[cls.class_id] = max(day_slots, key=lambda s: s.ts.period)
    classes_with_shl_target = set(shl_target_slot)
    shl_days = {(cid, slot.ts.weekday) for cid, slot in shl_target_slot.items()}

    gvcn_shl_cell = {}      # teacher_id -> (weekday, "S") ô SHL của lớp GVCN đó
    for cls in inp.classes:
        homeroom_teacher = assigned_teacher.get((role_index.hdtn_id, cls.class_id))
        target = shl_target_slot.get(cls.class_id)
        if homeroom_teacher is not None and target is not None:
            gvcn_shl_cell[homeroom_teacher] = (target.ts.weekday, target.ts.session)

    if inp.hdtn_thematic_week:
        # Tuần chuyên đề (R2): không có ô SHL cố định nào bị giữ chỗ, nên (1) đừng
        # cấm HDTN đặt vào "ngày SHL" (không còn ngày đó nữa), và (2) đừng cấm GVCN
        # chọn ô cuối sáng T6/T7 làm buổi nghỉ (không còn gì đặc biệt ở đó nữa).
        shl_days = set()
        gvcn_shl_cell = {}
```

Then find the chào cờ pin block:

```python
        # Pin Monday-session-S-period-1 to HDTN (chào cờ) for every class, if quota remains.
        for slot in inp.slots:
            if (slot.ts.weekday == config.chao_co_weekday and slot.ts.session == "S"
                    and slot.ts.period == config.chao_co_period):
                key = (role_index.hdtn_id, slot.class_id)
                if state.remaining_need.get(key, 0) > 0:
                    teacher_id = assigned_teacher.get(key)
                    if teacher_id is not None and _feasible(slot.class_id, slot.ts, role_index.hdtn_id,
                                                              teacher_id, state, role_index, day_capacity, config,
                                                              subject_class_allowed_cells):
                        _put_at(state, slot, role_index.hdtn_id, teacher_id, role_index)
                        state.pinned[slot.slot_id] = True
```

change to:

```python
        # Pin Monday-session-S-period-1 to HDTN (chào cờ) for every class, if quota
        # remains -- skipped entirely during a tuần chuyên đề (R2): HDTN's periods
        # all flow through the general block-aware greedy fill instead (N=3).
        if not inp.hdtn_thematic_week:
            for slot in inp.slots:
                if (slot.ts.weekday == config.chao_co_weekday and slot.ts.session == "S"
                        and slot.ts.period == config.chao_co_period):
                    key = (role_index.hdtn_id, slot.class_id)
                    if state.remaining_need.get(key, 0) > 0:
                        teacher_id = assigned_teacher.get(key)
                        if teacher_id is not None and _feasible(slot.class_id, slot.ts, role_index.hdtn_id,
                                                                  teacher_id, state, role_index, day_capacity,
                                                                  config, subject_class_allowed_cells):
                            _put_at(state, slot, role_index.hdtn_id, teacher_id, role_index)
                            state.pinned[slot.slot_id] = True
```

Then find the SHL reservation block:

```python
        reserved_shl = []
        for cid in classes_with_shl_target:
            key = (role_index.hdtn_id, cid)
            if state.remaining_need.get(key, 0) > 0:
                target = shl_target_slot[cid]
                state.assigned[target.slot_id] = -1
                state.rem_slot_count[cid] -= 1
                state.remaining_need[key] -= 1
                state.rem_need_count[cid] -= 1
                reserved_shl.append((cid, target))
```

change to:

```python
        reserved_shl = []
        if not inp.hdtn_thematic_week:
            for cid in classes_with_shl_target:
                key = (role_index.hdtn_id, cid)
                if state.remaining_need.get(key, 0) > 0:
                    target = shl_target_slot[cid]
                    state.assigned[target.slot_id] = -1
                    state.rem_slot_count[cid] -= 1
                    state.remaining_need[key] -= 1
                    state.rem_need_count[cid] -= 1
                    reserved_shl.append((cid, target))
```

(The later `for cid, target in reserved_shl:` placement block needs no change — it
already becomes a no-op when `reserved_shl` stays `[]`.)

- [ ] **Step 7: Run the new test to verify it passes**

Run: `python -m pytest tests/test_scheduler.py::test_hdtn_thematic_week_forms_one_block_and_skips_chao_co_shl_pins -v`
Expected: PASS.

- [ ] **Step 8: Wire `hdtn_thematic_week` into `repo.build_scheduling_input`**

In `data/repository.py`, change:

```python
def build_scheduling_input(conn: sqlite3.Connection, parity: str, seed: int = 0,
                            extra_kep_ids: frozenset = frozenset()) -> SchedulingInput:
```

to:

```python
def build_scheduling_input(conn: sqlite3.Connection, parity: str, seed: int = 0,
                            extra_kep_ids: frozenset = frozenset(),
                            hdtn_thematic_week: bool = False) -> SchedulingInput:
```

and change the closing `return SchedulingInput(...)` call:

```python
    return SchedulingInput(
        classes=classes, subjects=subjects, teachers=teachers, need=need,
        assigned_teacher=assigned_teacher, ban_busy=ban_busy,
        slots=slots, timeslots=timeslots, seed=seed,
        extra_kep_ids=extra_kep_ids, config=config,
        subject_class_allowed_cells=subject_class_allowed_cells,
    )
```

to:

```python
    return SchedulingInput(
        classes=classes, subjects=subjects, teachers=teachers, need=need,
        assigned_teacher=assigned_teacher, ban_busy=ban_busy,
        slots=slots, timeslots=timeslots, seed=seed,
        extra_kep_ids=extra_kep_ids, hdtn_thematic_week=hdtn_thematic_week, config=config,
        subject_class_allowed_cells=subject_class_allowed_cells,
    )
```

- [ ] **Step 9: Run the full suite to check for regressions**

Run: `python -m pytest`
Expected: all tests pass — every existing test either doesn't pass
`hdtn_thematic_week` (defaults `False`, so `resolve_roles` gets `hdtn_thematic_week=False`
exactly as before, and every `if not inp.hdtn_thematic_week:` branch is `True`,
preserving today's chào cờ/SHL behavior byte-for-byte), specifically re-confirm:
`python -m pytest tests/test_scheduler.py -k "shl or chao_co" -v`.

- [ ] **Step 10: Commit**

```bash
git add core/models.py core/scheduler.py data/repository.py tests/test_scheduler.py
git commit -m "feat: add hdtn_thematic_week per-run toggle skipping chao co/SHL pins"
```

---

### Task 6: UI — R2 toggle and R3 checkbox

**Files:**
- Modify: `pages/06_Xep_TKB.py` (single-run and batch-run sections)
- Modify: `pages/10_Cau_hinh_Xep_lich.py`

**Interfaces:**
- Consumes: `repo.build_scheduling_input(..., hdtn_thematic_week=...)` (Task 5),
  `SchedulingConfig.heavy_subjects_morning_only` (Task 3).
- Produces: no new Python interfaces (UI-only); manual verification only, no
  automated test (this repo has no Streamlit page test harness — confirmed absent
  from `tests/`).

- [ ] **Step 1: Exclude HDTN from the "kép chỉ tuần này" picker and add the R2 checkbox**

In `pages/06_Xep_TKB.py`, change the imports line:

```python
from core.models import ROLE_KEP, ROLE_NANG_KEP, WEEKDAY_NAMES, WEEKDAYS
```

to:

```python
from core.models import ROLE_HDTN, ROLE_KEP, ROLE_NANG_KEP, WEEKDAY_NAMES, WEEKDAYS
```

Change:

```python
extra_kep_options = [s.name for s in subjects if s.role_code not in (ROLE_KEP, ROLE_NANG_KEP)]
extra_kep_names = st.multiselect(
    "Môn cần xếp 2 tiết liền kề (kép) CHỈ cho tuần này",
    extra_kep_options,
    help="Không đổi vĩnh viễn phân loại môn học -- chỉ áp dụng cho lần chạy xếp TKB này.",
)
extra_kep_ids = frozenset(s.subject_id for s in subjects if s.name in extra_kep_names)
```

to (excludes HDTN from this list — it now has its own dedicated toggle below, and
double-booking both would leave `block_size[hdtn_id]` ambiguous between 2 and 3):

```python
extra_kep_options = [s.name for s in subjects if s.role_code not in (ROLE_KEP, ROLE_NANG_KEP, ROLE_HDTN)]
extra_kep_names = st.multiselect(
    "Môn cần xếp 2 tiết liền kề (kép) CHỈ cho tuần này",
    extra_kep_options,
    help="Không đổi vĩnh viễn phân loại môn học -- chỉ áp dụng cho lần chạy xếp TKB này.",
)
extra_kep_ids = frozenset(s.subject_id for s in subjects if s.name in extra_kep_names)

hdtn_thematic_week = st.checkbox(
    "Tuần này tổ chức chuyên đề (HDTN dồn 3 tiết liền kề toàn trường, bỏ ghim chào cờ + SHL)",
    help="Áp dụng cho toàn trường, chỉ lần chạy xếp TKB này -- không đổi vĩnh viễn.",
)
```

Change the single-run button handler:

```python
if st.button("🚀 Chạy xếp TKB", disabled=bool(over) and not proceed_anyway):
    inp = repo.build_scheduling_input(conn, parity=parity, seed=seed, extra_kep_ids=extra_kep_ids)
```

to:

```python
if st.button("🚀 Chạy xếp TKB", disabled=bool(over) and not proceed_anyway):
    inp = repo.build_scheduling_input(conn, parity=parity, seed=seed, extra_kep_ids=extra_kep_ids,
                                       hdtn_thematic_week=hdtn_thematic_week)
```

- [ ] **Step 2: Add the same toggle to the batch-run section**

In `pages/06_Xep_TKB.py`, change:

```python
    batch_extra_kep_names = st.multiselect(
        "Môn cần xếp 2 tiết liền kề (kép) CHỈ cho các tuần này",
        extra_kep_options,
        key="batch_extra_kep_select",
    )
    batch_extra_kep_ids = frozenset(s.subject_id for s in subjects if s.name in batch_extra_kep_names)
```

to:

```python
    batch_extra_kep_names = st.multiselect(
        "Môn cần xếp 2 tiết liền kề (kép) CHỈ cho các tuần này",
        extra_kep_options,
        key="batch_extra_kep_select",
    )
    batch_extra_kep_ids = frozenset(s.subject_id for s in subjects if s.name in batch_extra_kep_names)
    batch_hdtn_thematic_week = st.checkbox(
        "Các tuần này tổ chức chuyên đề (HDTN dồn 3 tiết liền kề toàn trường, bỏ ghim chào cờ + SHL)",
        key="batch_hdtn_thematic_week",
    )
```

Change:

```python
            b_inp = repo.build_scheduling_input(conn, parity=b_parity, seed=b_seed, extra_kep_ids=batch_extra_kep_ids)
```

to:

```python
            b_inp = repo.build_scheduling_input(conn, parity=b_parity, seed=b_seed,
                                                 extra_kep_ids=batch_extra_kep_ids,
                                                 hdtn_thematic_week=batch_hdtn_thematic_week)
```

- [ ] **Step 3: Add the R3 checkbox to the config page**

In `pages/10_Cau_hinh_Xep_lich.py`, change:

```python
heavy_subject_priority_periods = st.number_input(
    "Môn nặng: ưu tiên (không bắt buộc) mấy tiết đầu buổi sáng (0 = tắt)", 0, max_p,
    config.heavy_subject_priority_periods,
    help="Chỉ là gợi ý cho thuật toán -- không cấm tuyệt đối, không làm hỏng khả năng tìm lời giải.",
)
st.caption(
    "Ưu tiên mềm này thể hiện rõ nhất khi xếp TKB tự động trên tuần TRỐNG (chưa có dữ liệu cũ). "
    "Khi xếp lại đè lên TKB đã có sẵn, cơ chế \"giữ nguyên tiết cũ\" luôn được ưu tiên hơn nên hiệu ứng sẽ khó thấy."
)
```

to:

```python
heavy_subject_priority_periods = st.number_input(
    "Môn nặng: ưu tiên (không bắt buộc) mấy tiết đầu buổi sáng (0 = tắt)", 0, max_p,
    config.heavy_subject_priority_periods,
    help="Chỉ là gợi ý cho thuật toán -- không cấm tuyệt đối, không làm hỏng khả năng tìm lời giải.",
)
st.caption(
    "Ưu tiên mềm này thể hiện rõ nhất khi xếp TKB tự động trên tuần TRỐNG (chưa có dữ liệu cũ). "
    "Khi xếp lại đè lên TKB đã có sẵn, cơ chế \"giữ nguyên tiết cũ\" luôn được ưu tiên hơn nên hiệu ứng sẽ khó thấy."
)
heavy_subjects_morning_only = st.checkbox(
    "Môn Nặng: bắt buộc xếp buổi sáng (không được xếp chiều)",
    config.heavy_subjects_morning_only,
    help="Ràng buộc CỨNG (khác ô ưu tiên phía trên) -- môn không Nặng KHÔNG bị cấm xếp sáng, "
         "chỉ môn Nặng bị cấm xếp chiều. Có thể khiến thuật toán khó/không tìm được lời giải nếu "
         "khối tiết sáng/chiều của trường quá chật.",
)
```

Change the config-save block:

```python
    new_config = SchedulingConfig(
        gdtc_avoid_period=int(gdtc_avoid_period),
        chao_co_weekday=int(chao_co_weekday),
        chao_co_period=int(chao_co_period),
        max_heavy_consecutive=int(max_heavy_consecutive),
        max_periods_per_session=int(max_periods_per_session),
        teacher_off_sessions_per_week=int(teacher_off_sessions_per_week),
        forbidden_off_cells=frozenset(forbidden_selection),
        reserved_off_weekdays_chieu=tuple(sorted(reserved_weekdays_selection)),
        heavy_subject_priority_periods=int(heavy_subject_priority_periods),
        afternoon_preferred_subject_ids=frozenset(afternoon_preferred_selection),
    )
```

to:

```python
    new_config = SchedulingConfig(
        gdtc_avoid_period=int(gdtc_avoid_period),
        chao_co_weekday=int(chao_co_weekday),
        chao_co_period=int(chao_co_period),
        max_heavy_consecutive=int(max_heavy_consecutive),
        max_periods_per_session=int(max_periods_per_session),
        teacher_off_sessions_per_week=int(teacher_off_sessions_per_week),
        forbidden_off_cells=frozenset(forbidden_selection),
        reserved_off_weekdays_chieu=tuple(sorted(reserved_weekdays_selection)),
        heavy_subject_priority_periods=int(heavy_subject_priority_periods),
        afternoon_preferred_subject_ids=frozenset(afternoon_preferred_selection),
        heavy_subjects_morning_only=bool(heavy_subjects_morning_only),
    )
```

- [ ] **Step 4: Manually verify both pages in the browser**

Run: `python -m streamlit run app.py` (repo root), then in the browser:
1. Open **Cấu hình xếp lịch** — confirm the new "Môn Nặng: bắt buộc xếp buổi sáng"
   checkbox appears, toggling and saving it round-trips (reload the page, value
   persists).
2. Open **Xếp thời khóa biểu** — confirm HDTN no longer appears in the "Môn cần xếp
   2 tiết liền kề (kép)" multiselect options, and the new "Tuần này tổ chức chuyên
   đề" checkbox appears in both the single-run section and the "Xếp nhiều tuần cùng
   lúc" expander.
3. Enable the R3 checkbox on the config page, then run a schedule from the Xếp TKB
   page on an empty/current week and confirm it still succeeds (or check
   `result.failure_reason` if not, per the accepted infeasibility risk in the spec).
4. Stop the Streamlit server (Ctrl+C) when done.

- [ ] **Step 5: Commit**

```bash
git add pages/06_Xep_TKB.py pages/10_Cau_hinh_Xep_lich.py
git commit -m "feat: add UI for tuần chuyên đề toggle and heavy-morning-only config"
```

---

### Task 7: Combined full-run regression + final verification

**Files:**
- Test: `tests/test_scheduler.py` (one new combined full-run test)

**Interfaces:**
- Consumes: everything from Tasks 1-5.
- Produces: nothing new — this task is verification-only.

- [ ] **Step 1: Write the combined regression test**

Add to `tests/test_scheduler.py` after the test added in Task 4 Step 8
(`test_full_run_kep_subject_with_odd_weekly_count_pairs_maximally`):

```python
def test_full_run_all_three_rules_combined():
    # R1 (mandatory kép pairing, odd count) + R2 (HDTN thematic week) + R3 (heavy
    # afternoon ban) together, shaped after the real school data found during
    # root-cause investigation (Ngoại ngữ-like odd kép subject, HDTN 3/week).
    classes = [ClassRoom(1, "6A")]
    subjects = [
        Subject(1, "Ngoai ngu", ROLE_NANG_KEP, 1),   # heavy + kep, odd weekly count
        Subject(2, "Nhac", ROLE_THUONG, 2),           # non-heavy, no session restriction
        Subject(3, "HDTN", ROLE_HDTN, 3),
    ]
    teachers = [Teacher(1, "GVAnh"), Teacher(2, "GVNhac"), Teacher(3, "GVCN", is_gvcn=True)]
    need = {(1, 1): 3, (2, 1): 2, (3, 1): 3}
    assigned_teacher = {(1, 1): 1, (2, 1): 2, (3, 1): 3}
    timeslots = _make_timeslots(morning=4, afternoon=3, weekdays=(2, 3, 4, 5, 6))
    inp = _build_input(classes, subjects, teachers, need, assigned_teacher, timeslots,
                        seed=11, hdtn_thematic_week=True)
    inp.config = SchedulingConfig(heavy_subjects_morning_only=True)

    result = sched.run(inp, max_attempts=6000, target_successes=5)
    assert result.success is True

    # R3: Ngoại ngữ (heavy) never lands in an afternoon slot
    for slot in inp.slots:
        if result.assignment.get(slot.slot_id) == 1:
            assert slot.ts.session == "S", (slot.ts.weekday, slot.ts.session, slot.ts.period)

    # R1: Ngoại ngữ's 3 periods pair maximally (1 pair + 1 single, never 3 singles)
    placed_ngoai_ngu = defaultdict(list)
    for slot in inp.slots:
        if result.assignment.get(slot.slot_id) == 1:
            placed_ngoai_ngu[slot.ts.weekday].append(slot.ts.period)
    assert sorted(len(v) for v in placed_ngoai_ngu.values()) == [1, 2]

    # R2: HDTN's 3 periods form a single contiguous block
    placed_hdtn = defaultdict(list)
    for slot in inp.slots:
        if result.assignment.get(slot.slot_id) == 3:
            placed_hdtn[slot.ts.weekday].append(slot.ts.period)
    assert len(placed_hdtn) == 1, placed_hdtn
    (_wd, periods), = placed_hdtn.items()
    periods = sorted(periods)
    assert periods == [periods[0], periods[0] + 1, periods[0] + 2]
```

- [ ] **Step 2: Run it to verify it fails on a pre-Task-1 checkout, passes now**

Run: `python -m pytest tests/test_scheduler.py::test_full_run_all_three_rules_combined -v`
Expected: PASS now (all 3 rules were implemented in Tasks 1-5). If it fails, that
means one of R1/R2/R3 doesn't compose correctly with the other two — do not weaken
this test to make it pass; go back to the relevant task and fix the root cause
(this is exactly the kind of interaction bug §8 of the spec calls out as a risk).

- [ ] **Step 3: Run the complete test suite**

Run: `python -m pytest -v`
Expected: every test in the suite passes, with no test needing its expected
behavior changed except the ones this plan's tasks explicitly added.

- [ ] **Step 4: Commit**

```bash
git add tests/test_scheduler.py
git commit -m "test: add combined full-run regression for kép blocks, thematic week, heavy-morning"
```
