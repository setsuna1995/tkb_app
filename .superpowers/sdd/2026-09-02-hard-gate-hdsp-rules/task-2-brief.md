# Task 2: Fix `teacher_off.py` Silent Off-Slot Shortfall

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `_assign_off_slots` currently silently assigns FEWER off-sessions
than required when a teacher's eligible cells run out — this is the root
cause of "vẫn có người được nghỉ sáng T2" (a teacher effectively gets no real
off-session at all, because the mechanism meant to guarantee one quietly gave
up). Make the shortfall visible instead of swallowing it.

**Why this is a *report*, not a *retry-until-fixed* fix (Vietnamese below):**
Whether a teacher is short on eligible off-cells depends only on their fixed
config exclusions (GVCN, TPT/BGH, `must_monday`, `pinned_full_day_off`,
`off_sessions_override`, `mandatory_morning_weekdays`) — **not** on the RNG
draw. So if teacher X is short on attempt 1, they are short on *every*
attempt, identically. Rejecting-and-retrying the whole schedule attempt would
therefore burn the entire `SO_LAN_THU=6000` budget for nothing — it can never
fix this specific case. The correct fix is: assign as many off-slots as
possible (unchanged behavior), but report the shortfall explicitly so Task 4
can surface it in `ScheduleResult.relaxed_rules` instead of hiding it.
*(GV bị thiếu buổi nghỉ do exclusion cấu hình cố định — không phải do random
— nên thử lại KHÔNG BAO GIỜ tự sửa được; phải báo cáo minh bạch thay vì lặp
vô ích.)*

**Files:**
- Modify: `core/scheduler/teacher_off.py` (function signature + return value)
- Test: `tests/test_teacher_off.py` (new file)

**Interfaces:**
- Consumes: nothing new (same params as before).
- Produces: `_assign_off_slots(...) -> tuple[dict, dict]` — was
  `-> dict`. First element unchanged (`gv_off_slots: dict[int, set]`). Second
  element is new: `shortfall: dict[int, tuple[int, int]]` mapping
  `teacher_id -> (assigned_count, required_count)` for every teacher who got
  fewer off-slots than `effective_count`. Empty dict when nobody is short.
  **Task 4 depends on this exact return shape** — do not change it without
  updating Task 4's brief.

---

- [ ] **Step 1: Write the failing test**

Create `tests/test_teacher_off.py`:

```python
import random
from core.models import Teacher
from core.scheduler.teacher_off import _assign_off_slots


def test_assign_off_slots_returns_tuple_with_empty_shortfall_when_feasible():
    """A teacher with no unusual exclusions gets their 1 off-slot; shortfall empty."""
    teachers_by_id = {1: Teacher(teacher_id=1, name="GV A")}
    rng = random.Random(42)
    gv_off_slots, shortfall = _assign_off_slots({1}, teachers_by_id, rng, off_slot_count=1)
    assert 1 in gv_off_slots
    assert len(gv_off_slots[1]) == 1
    assert shortfall == {}


def test_assign_off_slots_reports_shortfall_when_teacher_over_excluded():
    """A teacher who is TPT/BGH (forbidden ALL mornings, i.e. only 6 afternoon
    cells eligible: T3,T4,T7 chiều + any not already forbidden) requiring an
    off_slot_count larger than what remains must be reported as short, not
    silently truncated."""
    teachers_by_id = {
        1: Teacher(teacher_id=1, name="Hieu Truong", role="Hiệu trưởng"),
    }
    rng = random.Random(42)
    # TPT/BGH forbids ALL mornings (wd 2-7) plus the standard FORBIDDEN_OFF_CELLS
    # (which already includes T5 chiều, T6 chiều) -- eligible afternoon cells left:
    # T2, T3, T4, T7 chiều = 4 cells. Ask for more off-sessions than that.
    gv_off_slots, shortfall = _assign_off_slots({1}, teachers_by_id, rng, off_slot_count=5)
    assert 1 in shortfall
    assigned_count, required_count = shortfall[1]
    assert required_count == 5
    assert assigned_count < 5
    assert assigned_count == len(gv_off_slots[1])


def test_assign_off_slots_shortfall_is_deterministic_across_rng_seeds():
    """The SAME teacher must be reported short by the SAME (assigned, required)
    counts regardless of which rng seed is used -- shortfall depends only on
    fixed exclusions, never on randomness (only WHICH cells get picked varies)."""
    teachers_by_id = {1: Teacher(teacher_id=1, name="Hieu Truong", role="Hiệu trưởng")}
    seeds_shortfalls = []
    for seed in (1, 2, 3, 999):
        rng = random.Random(seed)
        _, shortfall = _assign_off_slots({1}, teachers_by_id, rng, off_slot_count=5)
        seeds_shortfalls.append(shortfall[1])  # (assigned_count, required_count) tuple
    assert len(set(seeds_shortfalls)) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_teacher_off.py -v`
Expected: FAIL — `ValueError: too many values to unpack (expected 2)` or
similar, since `_assign_off_slots` currently returns a single `dict`.

- [ ] **Step 3: Change `_assign_off_slots` to return `(gv_off_slots, shortfall)`**

In `core/scheduler/teacher_off.py`, replace the whole function body (it
currently ends around line 69) so the `else` branch (lines 65-68) records the
shortfall instead of silently truncating, and the function returns both
dicts:

```python
def _assign_off_slots(teacher_ids: set, teachers_by_id: dict, rng: random.Random,
                       gvcn_shl_cell: Optional[dict] = None,
                       off_slot_count: int = 1,
                       forbidden_off_cells: frozenset = FORBIDDEN_OFF_CELLS,
                       mandatory_morning_weekdays: tuple = (2, 5, 6)) -> tuple:
    """Pick each teacher's off-slot(s) for the week: off_slot_count (weekday, session)
    pairs, each on a DIFFERENT weekday when possible (never 2 off-sessions on the
    same day, i.e. never a full day off), drawn from every cell except
    FORBIDDEN_OFF_CELLS (plus the teacher's own must_monday/is_gvcn exclusions and mandatory_morning_weekdays).

    Returns (gv_off_slots, shortfall):
    - gv_off_slots: teacher_id -> set of (weekday, session) off-cells actually assigned.
    - shortfall: teacher_id -> (assigned_count, required_count) for any teacher whose
      exclusions leave fewer eligible cells than required -- this is a STRUCTURAL fact
      (depends only on config, never on rng), so callers must not retry hoping to fix
      it; they must surface it (see core/scheduler/engine.py's relaxed_rules reporting).
    """
    gvcn_shl_cell = gvcn_shl_cell or {}
    gv_off_slots = {}
    shortfall = {}
    mandatory_mornings = set(mandatory_morning_weekdays)
    for tid in teacher_ids:
        t = teachers_by_id.get(tid)
        must_monday = t.must_monday if t else False
        is_gvcn = t.is_gvcn if t else False
        is_tpt_or_bgh = bool(t and any(k in (t.role or "") for k in ["TPT", "Tổng phụ trách", "Hiệu trưởng", "Phó hiệu trưởng"]))
        forbidden = set(forbidden_off_cells) | {(wd, "S") for wd in mandatory_mornings}
        if is_tpt_or_bgh:
            forbidden |= {(wd, "S") for wd in range(2, 8)}
        if must_monday:
            forbidden.add((2, "C"))
        if is_gvcn:
            forbidden.add(gvcn_shl_cell.get(tid, (7, "C")))

        pinned_cells = set()
        pinned_weekdays = set()
        if t and t.pinned_full_day_off is not None:
            wd = t.pinned_full_day_off
            if wd in WEEKDAYS and (wd, "S") not in forbidden and (wd, "C") not in forbidden:
                pinned_cells |= {(wd, "S"), (wd, "C")}
                pinned_weekdays.add(wd)
        if t and t.pinned_afternoon_off is not None:
            wd = t.pinned_afternoon_off
            if wd in WEEKDAYS and (wd, "C") not in forbidden and wd not in pinned_weekdays:
                pinned_cells.add((wd, "C"))
                pinned_weekdays.add(wd)

        effective_count = t.off_sessions_override if (t and t.off_sessions_override is not None) else off_slot_count
        remaining_count = max(0, effective_count - len(pinned_cells))

        by_weekday = defaultdict(list)
        for wd in (2, 3, 4, 5, 6, 7):
            if wd in pinned_weekdays:
                continue
            for session in ("S", "C"):
                if (wd, session) not in forbidden:
                    by_weekday[wd].append(session)
            eligible_weekdays = [wd for wd, sessions in by_weekday.items() if sessions]

        if len(eligible_weekdays) >= remaining_count:
            chosen_weekdays = rng.sample(eligible_weekdays, remaining_count)
            gv_off_slots[tid] = pinned_cells | {(wd, rng.choice(by_weekday[wd])) for wd in chosen_weekdays}
        else:
            all_eligible_cells = [(wd, s) for wd in eligible_weekdays for s in by_weekday[wd]]
            picks = rng.sample(all_eligible_cells, min(remaining_count, len(all_eligible_cells)))
            gv_off_slots[tid] = pinned_cells | set(picks)
            assigned_total = len(gv_off_slots[tid])
            if assigned_total < effective_count:
                shortfall[tid] = (assigned_total, effective_count)
    return gv_off_slots, shortfall
```

(Only the `else` branch and the final `return` line actually changed — the
rest is unchanged, reproduced here in full because it's a whole-function
replacement.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_teacher_off.py -v`
Expected: all 3 PASS.

- [ ] **Step 5: Fix the one other caller of `_assign_off_slots`**

`_assign_off_slots` is currently called from exactly one place,
`core/scheduler/engine.py` around line 111. **Do not fix the call site in
this task** — Task 4 owns `engine.py` and will update the call site as part
of wiring the shortfall into `relaxed_rules`. For now, run the existing
scheduler test suite to confirm this expected breakage is the ONLY breakage:

Run: `python -m pytest tests/ -v -k "not test_full_schedule_15_criteria_compliance" --timeout=600`
Expected: `core/scheduler/engine.py` will raise
`ValueError: too many values to unpack` wherever `run()` is exercised (i.e.
most scheduler integration tests) — this is expected and will be fixed by
Task 4. Confirm via the traceback that the ONLY failures are this exact
unpacking error inside `engine.py:111`, not something else. Record the
failing test names in `task-2-report.md` for visibility; do not fix them
here.

- [ ] **Step 6: Commit**

```bash
git add core/scheduler/teacher_off.py tests/test_teacher_off.py
git commit -m "fix: report teacher off-slot shortfall instead of silently truncating"
```

- [ ] **Step 7: Write task-2-report.md**

Note (Vietnamese) that `engine.py` is now intentionally broken pending Task
4, and list which test names fail because of it (expected, temporary).
