# Task 4: Generalize the Post-Generation Hard Gate in `engine.py`

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Today only class-level lone-period + non-consecutive-day checks
gate whether a scheduling attempt counts as "successful". Add II.3 (accidental
empty forbidden morning), II.4 (teacher lone session/day, root cause #2), II.8
(AM+PM split), and II.14 (4-consecutive-AM) to that gate — reusing the
EXISTING `quality.py` counter functions as boolean checks instead of writing
new scan logic. Also: wire Task 2's off-slot shortfall into
`ScheduleResult.relaxed_rules`, and add a "best core-invariant-only attempt"
fallback so an over-constrained school gets an explicit relaxation report
instead of a blank "impossible" failure.

**Prerequisite:** Task 1 (config defaults, `ScheduleResult.relaxed_rules`)
and Task 2 (`_assign_off_slots` returns a tuple) must be complete — this task
will not run correctly otherwise.

**Files:**
- Modify: `core/scheduler/engine.py` (imports, new helper function, loop body, final result construction)
- Modify: `core/scheduler/constants.py:8` (`NGUONG_KHOA`)
- Test: `tests/test_engine_hard_gate.py` (new file)

**Interfaces:**
- Consumes: `_assign_off_slots(...) -> tuple[dict, dict]` (Task 2),
  `ScheduleResult.relaxed_rules` field (Task 1), `_count_teacher_*` functions
  from `core/scheduler/quality.py` (all pre-existing, signatures unchanged).
- Produces: new module-level function
  `_check_hard_post_generation_rules(inp: SchedulingInput, state: _State, config) -> list[str]`
  in `core/scheduler/engine.py`, returning a list of violated rule IDs (e.g.
  `["II.4", "II.8"]`) or `[]` when compliant. `ScheduleResult.relaxed_rules`
  is now populated on the actual return paths — Task 5 consumes this list.

---

- [ ] **Step 1: Write the failing test**

Create `tests/test_engine_hard_gate.py`. This constructs a minimal but
realistic scenario where the OLD engine would silently accept a schedule
with a teacher lone-session violation, and asserts the NEW engine either
avoids it or reports it in `relaxed_rules`:

```python
from core.models import ClassRoom, SchedulingConfig, SchedulingInput, Slot, Teacher, TimeSlot
from core.scheduler.engine import _check_hard_post_generation_rules
from core.scheduler.state import _State


def test_check_hard_post_generation_rules_flags_lone_session():
    """A teacher with exactly one period in a session must be flagged as II.4,
    once their total weekly load is >= min_weekly_periods_for_lone_penalty (15).
    Uses 3-period (not 4-period) "full" sessions and all-morning placement so
    II.14 (4-consecutive) and II.8 (AM+PM split) never trigger, isolating II.4."""
    slots = []
    slot_id = 1
    # 5 full mornings of 3 periods each (wd 2,4,5,6,7) + 1 lone session (wd 3, period 1
    # only) = 3*5 + 1 = 16 total periods for teacher 1 (>= the 15-period threshold).
    for wd, period_count in ((2, 3), (4, 3), (5, 3), (6, 3), (7, 3), (3, 1)):
        for p in range(1, period_count + 1):
            slots.append(Slot(slot_id, 101, TimeSlot(slot_id, wd, "S", p)))
            slot_id += 1

    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1")], subjects=[], teachers=[Teacher(1, "GV A")],
        need={}, assigned_teacher={}, ban_busy=set(), slots=slots, timeslots=[],
        config=SchedulingConfig(min_weekly_periods_for_lone_penalty=15),
    )
    state = _State(remaining_need={}, busy=set())
    for slot in slots:
        state.assigned[slot.slot_id] = 1  # subject_id content is irrelevant to this check
        state.slot_teacher[slot.slot_id] = 1

    violations = _check_hard_post_generation_rules(inp, state, inp.config)
    assert violations == ["II.4"]


def test_check_hard_post_generation_rules_empty_when_compliant():
    slots = [Slot(1, 101, TimeSlot(1, 2, "S", 1))]
    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1")], subjects=[], teachers=[Teacher(1, "GV A")],
        need={}, assigned_teacher={}, ban_busy=set(), slots=slots, timeslots=[],
        config=SchedulingConfig(),
    )
    state = _State(remaining_need={}, busy=set())
    # No assignments at all -> nothing to violate
    violations = _check_hard_post_generation_rules(inp, state, inp.config)
    assert violations == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_engine_hard_gate.py -v`
Expected: FAIL with `ImportError: cannot import name '_check_hard_post_generation_rules'`.

- [ ] **Step 3: Add the new imports to `core/scheduler/engine.py`**

Change (near the top, current imports):
```python
from core.models import ScheduleResult, SchedulingInput
```
to:
```python
from core.models import ScheduleResult, SchedulingConfig, SchedulingInput
```

Change:
```python
from core.scheduler.quality import _teacher_quality_penalty
```
to:
```python
from core.scheduler.quality import (
    _count_teacher_4_consecutive_mornings, _count_teacher_lone_days,
    _count_teacher_lone_sessions, _count_teacher_missing_mandatory_mornings,
    _count_teacher_split_sessions, _teacher_quality_penalty,
)
```

- [ ] **Step 4: Add the `_check_hard_post_generation_rules` helper function**

Insert this new function in `core/scheduler/engine.py`, directly above the
`def run(...)` line:

```python
def _check_hard_post_generation_rules(inp: SchedulingInput, state: _State, config: SchedulingConfig) -> list:
    """Post-generation hard gate for the HĐSP rules that need full-schedule
    visibility (see core/rules_registry.py for tier classification: II.3,
    II.4, II.8, II.14 are HARD_POST_GENERATION). Reuses the same per-teacher
    counters quality.py uses for soft scoring, but as boolean reject-or-keep
    gates instead of penalty accumulators. Returns a list of violated rule
    IDs, e.g. ["II.4", "II.8"], or [] when fully compliant."""
    violated = []
    mand_morns = getattr(config, "mandatory_morning_weekdays", (2, 5, 6))
    if _count_teacher_missing_mandatory_mornings(inp.slots, state.assigned, state.slot_teacher, mand_morns) > 0:
        violated.append("II.3")
    if getattr(config, "avoid_teacher_lone_periods", True):
        min_lone_load = getattr(config, "min_weekly_periods_for_lone_penalty", 15)
        lone_sessions = _count_teacher_lone_sessions(inp.slots, state.assigned, state.slot_teacher, min_weekly_periods=min_lone_load)
        lone_days = _count_teacher_lone_days(inp.slots, state.assigned, state.slot_teacher, min_weekly_periods=min_lone_load)
        if lone_sessions > 0 or lone_days > 0:
            violated.append("II.4")
        if _count_teacher_split_sessions(inp.slots, state.assigned, state.slot_teacher) > 0:
            violated.append("II.8")
    if getattr(config, "avoid_teacher_4_consecutive_morning", True):
        if _count_teacher_4_consecutive_mornings(inp.slots, state.assigned, state.slot_teacher, max_load_for_penalty=20) > 0:
            violated.append("II.14")
    return violated
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_engine_hard_gate.py -v`
Expected: both tests PASS (the helper function works standalone even before
it's wired into `run()`).

- [ ] **Step 6: Initialize new tracking variables before the attempt loop**

Change (around line 94-98):
```python
    best_assignment = None
    best_changed = None
    best_quality_score = None
    successes = 0
    attempts_tried = 0
```
to:
```python
    best_assignment = None
    best_changed = None
    best_quality_score = None
    best_relaxed_assignment = None
    best_relaxed_changed = None
    best_relaxed_score = None
    best_relaxed_violations = None
    off_shortfall = {}
    successes = 0
    attempts_tried = 0
```

- [ ] **Step 7: Unpack the new tuple return from `_assign_off_slots`**

Change (around line 111-116):
```python
        state.gv_off_slots = _assign_off_slots(
            all_teacher_ids, teachers_by_id, rng, gvcn_shl_cell,
            off_slot_count=config.teacher_off_sessions_per_week,
            forbidden_off_cells=config.forbidden_off_cells,
            mandatory_morning_weekdays=getattr(config, "mandatory_morning_weekdays", (2, 5, 6)),
        )
```
to:
```python
        state.gv_off_slots, off_shortfall = _assign_off_slots(
            all_teacher_ids, teachers_by_id, rng, gvcn_shl_cell,
            off_slot_count=config.teacher_off_sessions_per_week,
            forbidden_off_cells=config.forbidden_off_cells,
            mandatory_morning_weekdays=getattr(config, "mandatory_morning_weekdays", (2, 5, 6)),
        )
```
(`off_shortfall` is structurally invariant across attempts per Task 2's
brief, so overwriting it each loop iteration is safe — it will hold the same
value every time a given teacher is genuinely short.)

- [ ] **Step 8: Replace the success-scoring block to add the hard gate + relaxed-candidate tracking**

Change (the block starting `if done:` around line 227, through the end of
the `for attempt` loop body around line 243):
```python
        if done:
            cells_changed = 0
            for slot in inp.slots:
                final = state.assigned.get(slot.slot_id)
                if final == -1:
                    final = None
                if final != slot.old_subject_id:
                    cells_changed += 1
            teacher_penalty = _teacher_quality_penalty(inp.slots, state.assigned, state.slot_teacher, config)
            solution_score = (teacher_penalty, cells_changed)
            successes += 1
            if best_quality_score is None or solution_score < best_quality_score:
                best_quality_score = solution_score
                best_changed = cells_changed
                best_assignment = dict(state.assigned)
            if successes >= target_successes:
                break
```
to:
```python
        if done:
            cells_changed = 0
            for slot in inp.slots:
                final = state.assigned.get(slot.slot_id)
                if final == -1:
                    final = None
                if final != slot.old_subject_id:
                    cells_changed += 1
            teacher_penalty = _teacher_quality_penalty(inp.slots, state.assigned, state.slot_teacher, config)
            hard_gate_violations = _check_hard_post_generation_rules(inp, state, config)

            if not hard_gate_violations:
                solution_score = (teacher_penalty, cells_changed)
                successes += 1
                if best_quality_score is None or solution_score < best_quality_score:
                    best_quality_score = solution_score
                    best_changed = cells_changed
                    best_assignment = dict(state.assigned)
                if successes >= target_successes:
                    break
            else:
                relaxed_score = (len(hard_gate_violations), teacher_penalty, cells_changed)
                if best_relaxed_score is None or relaxed_score < best_relaxed_score:
                    best_relaxed_score = relaxed_score
                    best_relaxed_changed = cells_changed
                    best_relaxed_assignment = dict(state.assigned)
                    best_relaxed_violations = hard_gate_violations
```
This attempt is now rejected as a full "success" whenever
`hard_gate_violations` is non-empty (it simply doesn't increment
`successes`, so the loop proceeds to the next attempt exactly like any other
`done=False` case) — but unlike the pre-existing `non_consecutive`/GDTC check
above it, it's remembered as a candidate fallback instead of being discarded
outright.

- [ ] **Step 9: Replace the final result construction to use the fallback + `relaxed_rules`**

Change (from `if successes == 0:` at line 245 through the end of the
function, line 264):
```python
    if successes == 0:
        return ScheduleResult(
            success=False,
            attempts_tried=attempts_tried,
            successes_found=0,
            cells_total=len(inp.slots),
            failure_reason=FAILURE_MESSAGE.format(attempts=attempts_tried),
        )

    final_assignment = {
        slot_id: (None if v == -1 else v) for slot_id, v in best_assignment.items()
    }
    return ScheduleResult(
        success=True,
        assignment=final_assignment,
        cells_changed=best_changed,
        cells_total=len(inp.slots),
        attempts_tried=attempts_tried,
        successes_found=successes,
    )
```
to:
```python
    if successes == 0:
        if best_relaxed_assignment is None:
            return ScheduleResult(
                success=False,
                attempts_tried=attempts_tried,
                successes_found=0,
                cells_total=len(inp.slots),
                failure_reason=FAILURE_MESSAGE.format(attempts=attempts_tried),
            )
        relaxed_rules = [{"rule_id": rid} for rid in best_relaxed_violations]
        if off_shortfall:
            relaxed_rules.append({"rule_id": "II.3", "detail": "off_slot_shortfall", "teachers": off_shortfall})
        final_assignment = {
            slot_id: (None if v == -1 else v) for slot_id, v in best_relaxed_assignment.items()
        }
        return ScheduleResult(
            success=True,
            assignment=final_assignment,
            cells_changed=best_relaxed_changed,
            cells_total=len(inp.slots),
            attempts_tried=attempts_tried,
            successes_found=0,
            relaxed_rules=relaxed_rules,
        )

    relaxed_rules = []
    if off_shortfall:
        relaxed_rules.append({"rule_id": "II.3", "detail": "off_slot_shortfall", "teachers": off_shortfall})
    final_assignment = {
        slot_id: (None if v == -1 else v) for slot_id, v in best_assignment.items()
    }
    return ScheduleResult(
        success=True,
        assignment=final_assignment,
        cells_changed=best_changed,
        cells_total=len(inp.slots),
        attempts_tried=attempts_tried,
        successes_found=successes,
        relaxed_rules=relaxed_rules,
    )
```
Note: `successes_found=0` on the relaxed-fallback path is intentional — it
truthfully reports that zero *fully*-compliant attempts were found, while
`success=True` + non-empty `relaxed_rules` signals "usable schedule, with
named caveats" to the caller (Task 5's UI reads this distinction).

- [ ] **Step 10: Retune `NGUONG_KHOA` in `core/scheduler/constants.py`**

Change (line 8):
```python
NGUONG_KHOA = 60          # attempts before shuffling timeslot order / discounting the "keep old" bonus
```
to:
```python
NGUONG_KHOA = 20          # attempts before shuffling timeslot order / discounting the "keep old" bonus
                          # (lowered from 60 on 2026-09-02: with more HARD_POST_GENERATION gates now
                          # rejecting attempts that reproduce an old, never-validated-against-these-rules
                          # schedule via the keep-old bonus, ~60 near-identical early attempts became
                          # likely to fail identically -- entering exploration mode sooner spends the
                          # SO_LAN_THU budget more usefully. Re-profile in Task 6 and adjust if needed.)
```

- [ ] **Step 11: Run the new test file plus the whole scheduler test suite**

Run: `python -m pytest tests/test_engine_hard_gate.py tests/ -v --timeout=600`
Expected: `test_engine_hard_gate.py` PASSes. Other scheduler tests that were
broken by Task 2's tuple-return change should now PASS again (this task
fixes the one call site). Note any NEW failures (e.g. schedules that used to
succeed but now only reach the relaxed-fallback path, or time out) — these
are expected discovery output for Task 6 to triage, not something to
silently patch here by weakening the gate.

- [ ] **Step 12: Commit**

```bash
git add core/scheduler/engine.py core/scheduler/constants.py tests/test_engine_hard_gate.py
git commit -m "feat: hard-gate II.3/II.4/II.8/II.14 post-generation with relaxed_rules fallback"
```

- [ ] **Step 13: Write task-4-report.md**

Summarize (Vietnamese): what changed, full test suite pass/fail counts
before and after, and specifically list any test or manual scenario where
the engine now returns `relaxed_rules` non-empty instead of a full success —
hand this list to Task 6.
