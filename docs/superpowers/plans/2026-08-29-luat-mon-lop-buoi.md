# Luật gán môn/lớp theo buổi cụ thể Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a school define general rules of the shape "subject X, for this set of classes, may ONLY be scheduled in these specific (weekday, session) cells" — a hard constraint, general enough to express "4 tiết Nhạc của khối 6+9 chỉ xếp vào 2 buổi chiều cụ thể" without hardcoding any subject/grade/weekday in code.

**Architecture:** A new table `subject_class_slot_rules` stores each admin-created rule as one row (`subject_id`, a comma-list of `class_ids`, a comma-list of `cells`). `data/repository.py` expands the rule rows into a flat lookup `dict[(subject_id, class_id)] -> frozenset[(weekday, session)]`, attached to a new `SchedulingInput.subject_class_allowed_cells` field. `_feasible()` in `core/scheduler.py` gains one more hard-gate check reading that dict — because every placement path (`_pick_best_scored`, `_pick_best_simple`, `_try_swap_repair`, the chào cờ/SHL pin blocks in `run()`) already funnels through `_feasible()`, threading the new dict through that one function's parameter (and its callers) covers every code path automatically. UI adds an add/list/delete section to the existing "Cấu hình xếp lịch" page, explicitly excluding HDTN from the subject picker (HDTN already has its own fixed chào cờ/SHL placement, incompatible with this general mechanism).

**Tech Stack:** Python 3, Streamlit, SQLite (stdlib `sqlite3`), pytest.

**Spec:** `docs/superpowers/specs/2026-08-29-rang-buoc-xep-lich-v2-design.md` (mục "Kiến trúc" → "3. Yêu cầu #4")

## Global Constraints

- No behavior change for any school that has never created a rule — an empty `subject_class_slot_rules` table must produce `subject_class_allowed_cells == {}`, and `_feasible()` must treat a missing `(subject_id, class_id)` key (or `subject_class_allowed_cells=None`) as "no restriction", identical to today's behavior.
- This is a **hard** constraint (unlike the soft rules from the companion "rang-buoc-mem" plan) — it belongs in `_feasible()`, and therefore must be threaded through **every** function that calls `_feasible()`: `_pick_best_scored`, `_pick_best_simple`, `_try_swap_repair`, `_repair_lone_periods`, and the 2 direct `_feasible()` calls inside `run()` (chào cờ pin, SHL restore).
- HDTN (`role_index.hdtn_id`) must never be selectable as a rule's subject in the UI — it already has fixed chào cờ (Thứ 2 sáng) and SHL (cuối tuần) placement outside this mechanism; a rule restricting HDTN's cells would make those pins permanently infeasible.
- Multiple rules that name the same `(subject_id, class_id)` pair merge by **union** (more permissive), not override — each rule is an independent "this class may also use these slots" statement.
- No changes to any `sched.run(inp)` call site signature — the new data rides on `SchedulingInput`, exactly like `ban_busy`/`config`.
- All existing tests in `tests/test_scheduler.py`, `tests/test_models.py`, `tests/test_repository.py` must keep passing unmodified.
- This plan is written against `core/scheduler.py` as it stands after the companion "rang-buoc-mem-mon-buoi" plan (Plan A) has already been applied — `_pick_best_scored` already carries `config = config or SchedulingConfig()` and the 2 soft-bias score adjustments from that plan. If Plan A has not been applied yet, apply it first, or adjust the "before" code shown in Task 3 to match whatever the current file actually contains before editing.

---

## Task 1: New table + repository CRUD

**Files:**
- Modify: `data/db.py:10-116` (`SCHEMA` — add new table)
- Modify: `data/repository.py:537-542` (add CRUD functions near the other `sched_*`/off-cell helpers)
- Test: `tests/test_repository.py` (extend existing file)

**Interfaces:**
- Produces: `repo.list_subject_class_rules(conn) -> list[dict]` (each `{"rule_id", "subject_id", "class_ids": list[int], "cells": frozenset[(weekday, session)]}`), `repo.upsert_subject_class_rule(conn, subject_id, class_ids, cells, rule_id=None) -> int`, `repo.delete_subject_class_rule(conn, rule_id) -> None`, `repo.get_subject_class_allowed_cells(conn) -> dict[(subject_id, class_id), frozenset]`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_repository.py`, add `ROLE_THUONG` to the existing import line and add the tests:

```python
from core.models import ROLE_THUONG, SchedulingConfig
```

```python
def test_subject_class_rule_crud_round_trips(conn):
    subject_id = repo.upsert_subject(conn, "Nhac", ROLE_THUONG)
    rule_id = repo.upsert_subject_class_rule(conn, subject_id=subject_id, class_ids=[3, 7, 9],
                                              cells={(3, "C"), (6, "C")})
    rules = repo.list_subject_class_rules(conn)
    assert len(rules) == 1
    assert rules[0]["rule_id"] == rule_id
    assert rules[0]["subject_id"] == subject_id
    assert rules[0]["class_ids"] == [3, 7, 9]
    assert rules[0]["cells"] == frozenset({(3, "C"), (6, "C")})


def test_subject_class_rule_update_by_rule_id(conn):
    subject_id = repo.upsert_subject(conn, "Nhac", ROLE_THUONG)
    rule_id = repo.upsert_subject_class_rule(conn, subject_id, [3], {(3, "C")})
    repo.upsert_subject_class_rule(conn, subject_id, [3, 7], {(3, "C"), (4, "C")}, rule_id=rule_id)
    rules = repo.list_subject_class_rules(conn)
    assert len(rules) == 1
    assert rules[0]["class_ids"] == [3, 7]
    assert rules[0]["cells"] == frozenset({(3, "C"), (4, "C")})


def test_subject_class_rule_delete(conn):
    subject_id = repo.upsert_subject(conn, "Nhac", ROLE_THUONG)
    rule_id = repo.upsert_subject_class_rule(conn, subject_id, [3], {(3, "C")})
    repo.delete_subject_class_rule(conn, rule_id)
    assert repo.list_subject_class_rules(conn) == []


def test_get_subject_class_allowed_cells_expands_per_class_and_merges_rules(conn):
    subject_id = repo.upsert_subject(conn, "Nhac", ROLE_THUONG)
    repo.upsert_subject_class_rule(conn, subject_id=subject_id, class_ids=[3, 7], cells={(3, "C")})
    repo.upsert_subject_class_rule(conn, subject_id=subject_id, class_ids=[3], cells={(6, "C")})  # cùng (môn, lớp 3) -> hợp nhất
    allowed = repo.get_subject_class_allowed_cells(conn)
    assert allowed[(subject_id, 3)] == frozenset({(3, "C"), (6, "C")})
    assert allowed[(subject_id, 7)] == frozenset({(3, "C")})
    assert (subject_id, 9) not in allowed


def test_get_subject_class_allowed_cells_empty_when_no_rules(conn):
    assert repo.get_subject_class_allowed_cells(conn) == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_repository.py -v`
Expected: FAIL — `AttributeError: module 'data.repository' has no attribute 'upsert_subject_class_rule'` (and similarly for the other 3 new functions).

- [ ] **Step 3: Add the table and CRUD functions**

In `data/db.py`, add a new table to `SCHEMA` (currently ending with the `app_meta` table at line 115, right before the closing `"""`):

```sql
CREATE TABLE IF NOT EXISTS app_meta (
    key          TEXT PRIMARY KEY,
    value        TEXT
);

CREATE TABLE IF NOT EXISTS subject_class_slot_rules (
    rule_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id   INTEGER NOT NULL REFERENCES subjects(subject_id) ON DELETE CASCADE,
    class_ids    TEXT NOT NULL,
    cells        TEXT NOT NULL
);
"""
```

(`class_ids`/`cells` are comma-delimited text, not normalized FK columns — a "rule" is one admin-managed row, and its class list can't hold a real foreign key by design, matching the spec's `_format_off_cells`-style serialization.)

In `data/repository.py`, add right after the existing `_format_weekday_tuple` helper (currently ending at line 542, immediately before `def get_scheduling_config`):

```python
# ---------------------------------------------------------------------------
# subject_class_slot_rules -- per-(subject, class) hard placement restriction
# ---------------------------------------------------------------------------

def list_subject_class_rules(conn: sqlite3.Connection) -> list:
    rows = conn.execute(
        "SELECT rule_id, subject_id, class_ids, cells FROM subject_class_slot_rules ORDER BY rule_id"
    ).fetchall()
    return [
        {
            "rule_id": r["rule_id"],
            "subject_id": r["subject_id"],
            "class_ids": [int(x) for x in r["class_ids"].split(",") if x.strip()],
            "cells": _parse_off_cells(r["cells"]),
        }
        for r in rows
    ]


def upsert_subject_class_rule(conn: sqlite3.Connection, subject_id: int, class_ids, cells, rule_id=None) -> int:
    class_ids_str = ",".join(str(cid) for cid in sorted(class_ids))
    cells_str = _format_off_cells(cells)
    if rule_id is not None:
        conn.execute(
            "UPDATE subject_class_slot_rules SET subject_id=?, class_ids=?, cells=? WHERE rule_id=?",
            (subject_id, class_ids_str, cells_str, rule_id),
        )
        conn.commit()
        return rule_id
    cur = conn.execute(
        "INSERT INTO subject_class_slot_rules (subject_id, class_ids, cells) VALUES (?, ?, ?)",
        (subject_id, class_ids_str, cells_str),
    )
    conn.commit()
    return cur.lastrowid


def delete_subject_class_rule(conn: sqlite3.Connection, rule_id: int) -> None:
    conn.execute("DELETE FROM subject_class_slot_rules WHERE rule_id=?", (rule_id,))
    conn.commit()


def get_subject_class_allowed_cells(conn: sqlite3.Connection) -> dict:
    result = {}
    for rule in list_subject_class_rules(conn):
        for class_id in rule["class_ids"]:
            key = (rule["subject_id"], class_id)
            result[key] = result.get(key, frozenset()) | rule["cells"]
    return result
```

(`_parse_off_cells`/`_format_off_cells` are the existing helpers used for `forbidden_off_cells` — reused as-is for `cells`, per the spec.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_repository.py -v`
Expected: PASS (all tests, including pre-existing ones)

- [ ] **Step 5: Commit**

```bash
git add data/db.py data/repository.py tests/test_repository.py
git commit -m "feat: add subject_class_slot_rules table and CRUD for per-subject/class slot restrictions"
```

---

## Task 2: `SchedulingInput` field + `build_scheduling_input` wiring

**Files:**
- Modify: `core/models.py:112` (`SchedulingInput` — append 1 field after `config`)
- Modify: `data/repository.py` (`build_scheduling_input` — attach the computed dict)
- Test: `tests/test_models.py`, `tests/test_repository.py`

**Interfaces:**
- Consumes: `repo.get_subject_class_allowed_cells` (Task 1)
- Produces: `SchedulingInput.subject_class_allowed_cells: dict = {}`; `build_scheduling_input(...)` now populates it from the DB.

- [ ] **Step 1: Write the failing tests**

In `tests/test_models.py`, add:

```python
def test_scheduling_input_defaults_subject_class_allowed_cells_to_empty_dict():
    inp = SchedulingInput(
        classes=[], subjects=[], teachers=[], need={}, assigned_teacher={},
        ban_busy=set(), slots=[], timeslots=[],
    )
    assert inp.subject_class_allowed_cells == {}
```

In `tests/test_repository.py`, add:

```python
def test_build_scheduling_input_attaches_subject_class_allowed_cells(conn):
    class_id = repo.upsert_class(conn, "6A")
    subject_id = repo.upsert_subject(conn, "Nhac", ROLE_THUONG)
    repo.upsert_subject_class_rule(conn, subject_id, [class_id], {(3, "C")})

    inp = repo.build_scheduling_input(conn, parity="C")
    assert inp.subject_class_allowed_cells == {(subject_id, class_id): frozenset({(3, "C")})}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_models.py tests/test_repository.py -v`
Expected: FAIL — `test_scheduling_input_defaults_subject_class_allowed_cells_to_empty_dict` fails with `AttributeError: 'SchedulingInput' object has no attribute 'subject_class_allowed_cells'`; `test_build_scheduling_input_attaches_subject_class_allowed_cells` fails the same way.

- [ ] **Step 3: Add the field and wire it in**

In `core/models.py`, append to the end of `SchedulingInput` (currently ending at line 112 with `config: SchedulingConfig = field(default_factory=SchedulingConfig)`):

```python
    config: SchedulingConfig = field(default_factory=SchedulingConfig)
    subject_class_allowed_cells: dict = field(default_factory=dict)  # (subject_id, class_id) -> frozenset[(weekday, session)]
```

In `data/repository.py`, inside `build_scheduling_input` (currently starting around line 601), add a line fetching the dict near the existing `config = get_scheduling_config(conn)` line:

```python
    config = get_scheduling_config(conn)
    subject_class_allowed_cells = get_subject_class_allowed_cells(conn)
```

Add `subject_class_allowed_cells=subject_class_allowed_cells` to the final `return SchedulingInput(...)` call (currently ending with `extra_kep_ids=extra_kep_ids, config=config,`):

```python
    return SchedulingInput(
        classes=classes, subjects=subjects, teachers=teachers, need=need,
        assigned_teacher=assigned_teacher, ban_busy=ban_busy,
        slots=slots, timeslots=timeslots, seed=seed,
        extra_kep_ids=extra_kep_ids, config=config,
        subject_class_allowed_cells=subject_class_allowed_cells,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_models.py tests/test_repository.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add core/models.py data/repository.py tests/test_models.py tests/test_repository.py
git commit -m "feat: attach subject/class slot-allowlist to SchedulingInput end-to-end"
```

---

## Task 3: Thread `subject_class_allowed_cells` through the feasibility chain

**Files:**
- Modify: `core/scheduler.py` (`_feasible`, `_pick_best_scored`, `_pick_best_simple`, `_try_swap_repair`, `_repair_lone_periods`, `run`)
- Test: `tests/test_scheduler.py`

**Interfaces:**
- Consumes: `SchedulingInput.subject_class_allowed_cells` (Task 2)
- Produces: `_feasible(..., subject_class_allowed_cells: Optional[dict] = None)` — every function in the chain gains a trailing `subject_class_allowed_cells` parameter, defaulting to `None` (= no restriction, current behavior).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_scheduler.py`, near the other `_feasible`-focused tests:

```python
def test_feasible_rejects_placement_outside_subject_class_allowed_cells():
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    state = _State(remaining_need={(1, 1): 10}, busy=set())
    allowed = {(1, 1): frozenset({(3, "C")})}
    ts_wrong = TimeSlot(1, 2, "S", 1)
    assert _feasible(1, ts_wrong, 1, 100, state, role_index, subject_class_allowed_cells=allowed) is False
    ts_right = TimeSlot(2, 3, "C", 1)
    assert _feasible(1, ts_right, 1, 100, state, role_index, subject_class_allowed_cells=allowed) is True


def test_feasible_unaffected_when_class_subject_pair_absent_from_allowed_cells():
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    state = _State(remaining_need={(1, 1): 10}, busy=set())
    allowed = {(1, 99): frozenset({(3, "C")})}  # luật chỉ áp dụng cho lớp 99, không phải lớp 1
    ts = TimeSlot(1, 2, "S", 1)
    assert _feasible(1, ts, 1, 100, state, role_index, subject_class_allowed_cells=allowed) is True


def test_feasible_defaults_to_current_behavior_when_subject_class_allowed_cells_omitted():
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    state = _State(remaining_need={(1, 1): 10}, busy=set())
    ts = TimeSlot(1, 2, "S", 1)
    assert _feasible(1, ts, 1, 100, state, role_index) is True
```

Also add a full-run integration test near `test_small_synthetic_schedule_succeeds_and_meets_quotas`, using the existing `_make_timeslots`/`_build_input` helpers (plain module-level functions, `tests/test_scheduler.py:378-407`):

```python
def test_subject_class_rule_thread_through_run():
    classes = [ClassRoom(1, "6A")]
    subjects = [
        Subject(1, "Toan hoc", ROLE_THUONG, 1),
        Subject(2, "Nhac", ROLE_THUONG, 2),
        Subject(3, "HDTN", ROLE_HDTN, 3),
    ]
    teachers = [Teacher(1, "GV1"), Teacher(2, "GV2"), Teacher(3, "GV3")]
    need = {(1, 1): 10, (2, 1): 2, (3, 1): 3}
    assigned_teacher = {(1, 1): 1, (2, 1): 2, (3, 1): 3}
    timeslots = _make_timeslots(morning=5, afternoon=3)
    inp = _build_input(classes, subjects, teachers, need, assigned_teacher, timeslots, seed=42)
    inp.subject_class_allowed_cells = {(2, 1): frozenset({(3, "C"), (6, "C")})}  # Nhạc/6A chỉ (Thứ 3, Thứ 6) chiều

    result = sched.run(inp, max_attempts=6000, target_successes=3)
    assert result.success is True

    for slot in inp.slots:
        if slot.class_id != 1:
            continue
        assigned_subject = result.assignment.get(slot.slot_id)
        if assigned_subject == 2:
            assert (slot.ts.weekday, slot.ts.session) in {(3, "C"), (6, "C")}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_scheduler.py -k "subject_class_allowed_cells or subject_class_rule_thread_through_run" -v`
Expected: FAIL — the first 2 new tests fail with `TypeError: _feasible() got an unexpected keyword argument 'subject_class_allowed_cells'`; `test_feasible_defaults_to_current_behavior_when_subject_class_allowed_cells_omitted` already PASSES (nothing new is exercised) — expected, it's the regression guard. `test_subject_class_rule_thread_through_run` fails because `sched.run()` never reads `inp.subject_class_allowed_cells`, so Nhạc can land anywhere (the assertion inside the loop will trip for at least one placement in most seeds/attempts).

- [ ] **Step 3: Thread the parameter through the whole call chain**

In `core/scheduler.py`, change `_feasible` — add the parameter and the new check right after the existing `config = config or SchedulingConfig()` normalization line:

```python
def _feasible(class_id: int, ts: TimeSlot, subject_id: int, teacher_id: int,
              state: _State, role_index, day_capacity: Optional[dict] = None,
              config: Optional[SchedulingConfig] = None,
              subject_class_allowed_cells: Optional[dict] = None) -> bool:
    config = config or SchedulingConfig()
    if subject_class_allowed_cells is not None:
        allowed = subject_class_allowed_cells.get((subject_id, class_id))
        if allowed is not None and (ts.weekday, ts.session) not in allowed:
            return False
    if (teacher_id, ts.ts_id) in state.busy:
        return False
```

(leave the rest of `_feasible`'s body — session cap, off-slot, GDTC-avoid, day cap, liền mạch, kép cap/adjacency, heavy-run window — untouched).

`_pick_best_scored` — add the parameter, forward it to the `_feasible` call (this function already has `config = config or SchedulingConfig()` and the 2 soft-bias score adjustments from the companion "rang-buoc-mem-mon-buoi" plan; only the signature and the `_feasible` call change here):

```python
def _pick_best_scored(class_id: int, slot: Slot, state: _State, role_index,
                       subjects: list, assigned_teacher: dict, pu: float, rng: random.Random,
                       day_capacity: Optional[dict] = None,
                       config: Optional[SchedulingConfig] = None,
                       subject_class_allowed_cells: Optional[dict] = None) -> Optional[tuple]:
    config = config or SchedulingConfig()
    ts = slot.ts
    best_subject = None
    best_teacher = None
    best_score = -1.0
    for subj in subjects:
        key = (subj.subject_id, class_id)
        if state.remaining_need.get(key, 0) <= 0:
            continue
        if subj.subject_id == role_index.hdtn_id and (class_id, ts.weekday) in state.shl_days:
            continue
        teacher_id = assigned_teacher[key]
        if not _feasible(class_id, ts, subj.subject_id, teacher_id, state, role_index, day_capacity, config,
                          subject_class_allowed_cells):
            continue
```

(the rest of `_pick_best_scored`'s body — score computation, soft-bias adjustments, stickiness bonus, best-tracking — is unchanged; only the signature and the one `_feasible` call shown above change).

`_pick_best_simple` — add the parameter, forward it:

```python
def _pick_best_simple(class_id: int, slot: Slot, state: _State, role_index,
                       subjects: list, assigned_teacher: dict,
                       day_capacity: Optional[dict] = None,
                       config: Optional[SchedulingConfig] = None,
                       subject_class_allowed_cells: Optional[dict] = None) -> Optional[tuple]:
    ts = slot.ts
    best_subject = None
    best_teacher = None
    best_remaining = -1
    for subj in subjects:
        key = (subj.subject_id, class_id)
        remaining = state.remaining_need.get(key, 0)
        if remaining <= 0:
            continue
        if subj.subject_id == role_index.hdtn_id and (class_id, ts.weekday) in state.shl_days:
            continue
        teacher_id = assigned_teacher[key]
        if not _feasible(class_id, ts, subj.subject_id, teacher_id, state, role_index, day_capacity, config,
                          subject_class_allowed_cells):
            continue
        if remaining > best_remaining:
            best_remaining = remaining
            best_subject = subj.subject_id
            best_teacher = teacher_id
    if best_subject is None:
        return None
    return best_subject, best_teacher
```

`_try_swap_repair` — add the parameter, forward it to both its `_feasible` call and its `_pick_best_simple` call:

```python
def _try_swap_repair(class_id: int, slot: Slot, state: _State, role_index,
                      subjects: list, assigned_teacher: dict,
                      slots_by_class: dict, day_capacity: Optional[dict] = None,
                      config: Optional[SchedulingConfig] = None,
                      subject_class_allowed_cells: Optional[dict] = None) -> bool:
    ts = slot.ts
    for other in slots_by_class[class_id]:
        if other.slot_id == slot.slot_id:
            continue
        if state.assigned.get(other.slot_id, None) in (None, -1) or state.pinned.get(other.slot_id):
            continue
        moved_subject, moved_teacher = _remove_at(state, other, role_index)
        if _feasible(class_id, ts, moved_subject, moved_teacher, state, role_index, day_capacity, config,
                      subject_class_allowed_cells):
            _put_at(state, slot, moved_subject, moved_teacher, role_index)
            refill = _pick_best_simple(class_id, other, state, role_index, subjects, assigned_teacher,
                                        day_capacity, config, subject_class_allowed_cells)
            if refill is not None:
                _put_at(state, other, refill[0], refill[1], role_index)
                return True
            _remove_at(state, slot, role_index)
            _put_at(state, other, moved_subject, moved_teacher, role_index)
        else:
            _put_at(state, other, moved_subject, moved_teacher, role_index)
    return False
```

`_repair_lone_periods` — add the parameter, forward it to its `_pick_best_simple` and `_try_swap_repair` calls:

```python
def _repair_lone_periods(inp: SchedulingInput, state: _State, role_index,
                          assigned_teacher: dict, slots_by_class: dict,
                          day_capacity: Optional[dict], config: Optional[SchedulingConfig] = None,
                          subject_class_allowed_cells: Optional[dict] = None) -> None:
    for slot in inp.slots:
        ts = slot.ts
        if ts.period != 2:
            continue
        class_id = slot.class_id
        if not state.occupied.get((class_id, ts.weekday, ts.session, 1), False):
            continue
        current = state.assigned.get(slot.slot_id)
        if current not in (None, -1):
            continue
        if current == -1:
            state.assigned[slot.slot_id] = None
            state.rem_slot_count[class_id] += 1
        pick = _pick_best_simple(class_id, slot, state, role_index, inp.subjects, assigned_teacher,
                                  day_capacity, config, subject_class_allowed_cells)
        if pick is not None:
            _put_at(state, slot, pick[0], pick[1], role_index)
        else:
            _try_swap_repair(class_id, slot, state, role_index, inp.subjects,
                              assigned_teacher, slots_by_class, day_capacity, config, subject_class_allowed_cells)
```

`run()` — after the existing `config = inp.config` line, add:

```python
    config = inp.config
    subject_class_allowed_cells = inp.subject_class_allowed_cells
```

Then update every direct call site inside `run()`:

- Chào cờ pin block:

```python
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

- `_pick_best_scored` call:

```python
                pick = _pick_best_scored(class_id, slot, state, role_index, inp.subjects,
                                          assigned_teacher, pu, rng, day_capacity, config,
                                          subject_class_allowed_cells)
```

- `_try_swap_repair` call:

```python
                    fixed = _try_swap_repair(class_id, slot, state, role_index, inp.subjects,
                                              assigned_teacher, slots_by_class, day_capacity, config,
                                              subject_class_allowed_cells)
```

- SHL restore `_feasible` call:

```python
                if _feasible(cid, target.ts, role_index.hdtn_id, tid, state, role_index, day_capacity, config,
                              subject_class_allowed_cells):
```

- `_repair_lone_periods` call:

```python
            _repair_lone_periods(inp, state, role_index, assigned_teacher, slots_by_class, day_capacity, config,
                                  subject_class_allowed_cells)
```

- [ ] **Step 4: Run tests to verify everything passes**

Run: `python -m pytest tests/test_scheduler.py -v`
Expected: PASS — the 4 new tests plus the entire pre-existing suite (every existing caller of `_feasible`/`_pick_best_scored`/`_pick_best_simple`/`_try_swap_repair`/`_repair_lone_periods` omits the new trailing parameter, hitting the `None` default, i.e. "no restriction").

Run the full suite once more to confirm nothing else regressed:

Run: `python -m pytest -v`
Expected: PASS (entire repo)

- [ ] **Step 5: Commit**

```bash
git add core/scheduler.py tests/test_scheduler.py
git commit -m "feat: enforce subject/class slot-allowlist as a hard constraint through the full feasibility chain"
```

---

## Task 4: `FAILURE_MESSAGE` + UI (Cấu hình xếp lịch page)

**Files:**
- Modify: `core/scheduler.py` (`FAILURE_MESSAGE`)
- Modify: `pages/10_Cau_hinh_Xep_lich.py` (new subheader: add/list/delete rules)

**Interfaces:**
- Consumes: `repo.list_classes`/`list_subjects` (existing), `repo.list_subject_class_rules`/`upsert_subject_class_rule`/`delete_subject_class_rule` (Task 1)

No automated test for the UI — matches this repo's existing convention for Streamlit pages. Verify manually in Step 3.

- [ ] **Step 1: Update `FAILURE_MESSAGE`**

In `core/scheduler.py`, change `FAILURE_MESSAGE` to add a 4th cause:

```python
FAILURE_MESSAGE = (
    "Không xếp được sau {attempts} lần thử. Nguyên nhân hay gặp:\n"
    "(1) GV HDTN (GVCN) trùng nhau giữa 2 lớp - chào cờ & SHL diễn ra đồng thời "
    "nên MỖI LỚP cần GVCN riêng;\n"
    "(2) GV_Bận cấm quá nhiều giờ của GV tải năng;\n"
    "(3) định mức SoTiet vượt khả năng khung tiết;\n"
    "(4) luật gán môn/lớp theo buổi (trang Cấu hình xếp lịch) quá chặt so với số tiết/tuần cần xếp."
)
```

- [ ] **Step 2: Add the rules UI section**

In `pages/10_Cau_hinh_Xep_lich.py`, change the import line to add `ROLE_HDTN`:

```python
from core.models import ROLE_HDTN, SchedulingConfig, WEEKDAY_NAMES, WEEKDAYS
```

At the end of the file (after the existing `if st.button("💾 Lưu cấu hình", ...)` block, before the `sidebar_backup_export(conn)` line), add:

```python
st.subheader("Ràng buộc môn/lớp theo buổi cụ thể (tuỳ chọn)")
st.caption(
    "Ví dụ: 1 môn ở một số lớp CHỈ được xếp vào đúng các (thứ, buổi) đã chọn -- "
    "ràng buộc CỨNG, có thể khiến thuật toán không tìm được lời giải nếu quá chặt."
)
all_classes = repo.list_classes(conn)
all_subjects_for_rules = repo.list_subjects(conn)
rule_subjects = [s for s in all_subjects_for_rules if s.role_code != ROLE_HDTN]
if not rule_subjects or not all_classes:
    st.info("Cần khai báo ít nhất 1 môn (khác HDTN) và 1 lớp trước khi tạo luật.")
else:
    with st.form("add_subject_class_rule", clear_on_submit=True):
        rule_subject_id = st.selectbox(
            "Môn", options=[s.subject_id for s in rule_subjects],
            format_func=lambda sid: next(s.name for s in rule_subjects if s.subject_id == sid),
        )
        rule_class_ids = st.multiselect(
            "Lớp áp dụng", options=[c.class_id for c in all_classes],
            format_func=lambda cid: next(c.name for c in all_classes if c.class_id == cid),
        )
        rule_cells = st.multiselect(
            "Chỉ được xếp vào các (Thứ, Buổi) này",
            options=[(wd, s) for wd in WEEKDAYS for s in ("S", "C")],
            format_func=lambda cell: f"{WEEKDAY_NAMES[cell[0]]} {'Sáng' if cell[1] == 'S' else 'Chiều'}",
        )
        if st.form_submit_button("➕ Thêm luật"):
            if rule_class_ids and rule_cells:
                repo.upsert_subject_class_rule(conn, rule_subject_id, rule_class_ids, rule_cells)
                st.success("Đã thêm luật.")
                st.rerun()
            else:
                st.error("Cần chọn ít nhất 1 lớp và 1 (thứ, buổi).")

existing_rules = repo.list_subject_class_rules(conn)
if existing_rules:
    st.caption("Luật hiện có:")
    subject_names = {s.subject_id: s.name for s in all_subjects_for_rules}
    class_names = {c.class_id: c.name for c in all_classes}
    for rule in existing_rules:
        subj_name = subject_names.get(rule["subject_id"], str(rule["subject_id"]))
        cls_names = ", ".join(class_names.get(cid, str(cid)) for cid in rule["class_ids"])
        cell_names = ", ".join(
            f"{WEEKDAY_NAMES[wd]} {'Sáng' if s == 'S' else 'Chiều'}" for wd, s in sorted(rule["cells"])
        )
        col1, col2 = st.columns([5, 1])
        col1.markdown(f"- **{subj_name}** ({cls_names}) chỉ xếp vào: {cell_names}")
        if col2.button("🗑️", key=f"del_rule_{rule['rule_id']}"):
            repo.delete_subject_class_rule(conn, rule["rule_id"])
            st.rerun()
```

- [ ] **Step 3: Manually verify**

Run: `streamlit run app.py`

- Open "Thiết lập dữ liệu" → "Cấu hình xếp lịch". Scroll to "Ràng buộc môn/lớp theo buổi cụ thể" — confirm the subject dropdown does **not** list the HDTN subject.
- Add a rule: pick "Nhạc" (or any non-HDTN subject), select 2 classes, select 2 (thứ, buổi) cells. Submit — confirm it appears in "Luật hiện có" with the correct subject/class/cell names.
- Click the 🗑️ button on that rule — confirm it disappears and the DB no longer has it (reload the page).
- Re-add the same rule, then go to "Xếp & sửa thời khóa biểu" → "Xếp TKB tự động" and run a schedule — confirm the resulting timetable places that subject, for those classes, only in the selected cells (spot-check the grid).
- Delete the rule again afterward (leave the demo school in its original state).

- [ ] **Step 4: Run the full test suite one final time**

Run: `python -m pytest -v`
Expected: PASS — entire suite, no regressions from any of the 4 tasks.

- [ ] **Step 5: Commit**

```bash
git add core/scheduler.py pages/10_Cau_hinh_Xep_lich.py
git commit -m "feat: add UI for subject/class slot rules and surface as a 4th scheduling-failure cause"
```

---

## Self-Review Notes

- **Spec coverage:** Spec section "3. Yêu cầu #4" is fully covered — the new table + CRUD (Task 1), the `SchedulingInput` field + `build_scheduling_input` wiring (Task 2), the full `_feasible()` call-chain threading the spec calls out by name (Task 3), and the `FAILURE_MESSAGE` 4th cause + UI with the HDTN-exclusion validation note (Task 4).
- **Placeholder scan:** No task defers logic or references undefined names — every code block is complete, copy-pasteable Python/Streamlit verified against the actual current file contents (`data/db.py:10-116`, `data/repository.py:78, 537-650`, `core/models.py:41-112`, `core/scheduler.py` full-file read, `pages/10_Cau_hinh_Xep_lich.py`, `tests/test_repository.py`, `tests/test_scheduler.py:378-407`).
- **Type consistency:** `subject_class_allowed_cells: dict` and its `(subject_id, class_id) -> frozenset[(weekday, session)]` shape is identical across Tasks 2-4 wherever referenced. `_feasible`'s new trailing parameter name and position match every one of its 6 call sites (`_pick_best_scored`, `_pick_best_simple`, `_try_swap_repair`, 2 direct calls in `run()`, plus `_try_swap_repair`'s own `_feasible` call). Task 3 explicitly notes it builds on `_pick_best_scored`'s Plan-A-modified form rather than the pristine original, so the two plans compose correctly regardless of execution order relative to each other (as long as Plan A lands first, per Global Constraints).
