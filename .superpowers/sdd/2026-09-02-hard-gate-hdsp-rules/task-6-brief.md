# Task 6: End-to-End Assertions, Regression Fixtures & Profiling

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove the whole feature works together against real school data
(`io_excel/sample_school.xlsm`, the same fixture `test_full_schedule_15_criteria_compliance`
already uses), establish a measured performance baseline (none existed
before — the "<4 minutes" figure in `.superpowers/sdd/2026-09-01-rules-audit-v2/task-1-report.md`
was an unverified estimate), and add regression coverage tying directly back
to the two bugs the user (Kien) originally reported on 2026-09-02.

**Prerequisite:** Tasks 1-5 all complete.

**Files:**
- Modify: `tests/test_mandatory_rules_compliance.py` (extend `test_full_schedule_15_criteria_compliance`)
- Test: `tests/test_regression_hard_gate_2026_09_02.py` (new file)

**Interfaces:**
- Consumes: everything produced by Tasks 1-5 (`ScheduleResult.relaxed_rules`,
  the 5 new `core/validation.py` finders, `core/scheduler/engine.py`'s gate).

---

- [ ] **Step 1: Extend the existing end-to-end compliance test**

In `tests/test_mandatory_rules_compliance.py`, `test_full_schedule_15_criteria_compliance`
(around line 196-270): extend the import block (lines 201-205) to add the 5
new finders:

```python
    from core.validation import (
        compute_quota_diff, find_consecutive_subject_days, find_heavy_afternoon_period3_violations,
        find_invalid_gdtc_periods, find_max_heavy_violations, find_teacher_conflicts,
        find_teacher_day_cap_violations, find_teacher_gaps,
        find_teacher_4_consecutive_morning_violations, find_teacher_lone_day_violations,
        find_teacher_lone_session_violations, find_teacher_missing_mandatory_morning_violations,
        find_teacher_split_day_violations,
    )
```

Then insert this block right before `connection.close()` at the end of the
test function (currently the last line of the test body):

```python
    # 9-12. Tiêu chí II.3, II.4, II.8, II.14 (hard-gated 2026-09-02): mọi vi phạm phải
    # được engine tự tránh, HOẶC được báo cáo minh bạch qua relaxed_rules -- không được
    # có vi phạm "câm" (tồn tại nhưng không báo cáo). Đây chính là bug gốc gây ra báo cáo
    # của người dùng ngày 2026-09-02 ("vẫn có người được nghỉ sáng T2, vẫn nhiều buổi lẻ").
    relaxed_ids = {item.get("rule_id") for item in result.relaxed_rules}

    missing_morning = find_teacher_missing_mandatory_morning_violations(inp.slots, result.assignment, inp.assigned_teacher)
    assert not missing_morning or "II.3" in relaxed_ids, f"Unreported II.3 violations: {missing_morning}"

    min_lone_load = config.min_weekly_periods_for_lone_penalty
    lone_sessions = find_teacher_lone_session_violations(inp.slots, result.assignment, inp.assigned_teacher, min_lone_load)
    lone_days = find_teacher_lone_day_violations(inp.slots, result.assignment, inp.assigned_teacher, min_lone_load)
    assert not (lone_sessions or lone_days) or "II.4" in relaxed_ids, f"Unreported II.4 violations: {lone_sessions + lone_days}"

    split_days = find_teacher_split_day_violations(inp.slots, result.assignment, inp.assigned_teacher)
    assert not split_days or "II.8" in relaxed_ids, f"Unreported II.8 violations: {split_days}"

    consecutive_morning = find_teacher_4_consecutive_morning_violations(inp.slots, result.assignment, inp.assigned_teacher)
    assert not consecutive_morning or "II.14" in relaxed_ids, f"Unreported II.14 violations: {consecutive_morning}"

    connection.close()
```

(Remove the old standalone `connection.close()` line right above where you
inserted this, so it isn't called twice.)

- [ ] **Step 2: Run the extended test and record the outcome**

Run: `python -m pytest tests/test_mandatory_rules_compliance.py::test_full_schedule_15_criteria_compliance -v --timeout=600`

Three possible outcomes, all informative:
- **PASS with `result.relaxed_rules == []`**: the real fixture is fully
  compliant with all hard-gated rules. Best case.
- **PASS with `result.relaxed_rules` non-empty**: the real fixture cannot
  fully satisfy every hard rule (e.g. a genuinely over-constrained teacher),
  but the engine is being honest about it instead of hiding it — this is the
  intended fallback behavior, not a bug. Record which rules/teachers in
  `task-6-report.md`.
- **FAIL** (an `assert ... Unreported` fires): a real correctness bug in
  Task 4's gate wiring — a violation exists that the engine did not detect
  and did not report. Do not weaken the assertion to make it pass; fix the
  root cause in `engine.py` (likely a gap between `_check_hard_post_generation_rules`
  and these validators — compare their logic line by line) and re-run.

- [ ] **Step 3: Write the regression test for both original root-cause bugs**

Create `tests/test_regression_hard_gate_2026_09_02.py`:

```python
"""Regression coverage for the two bugs the user (Kien) reported on
2026-09-02: teacher off-slot shortfall was silently swallowed (root cause of
"vẫn có người được nghỉ sáng T2"), and teacher lone-session repair was never
verified (root cause of "vẫn nhiều buổi lẻ 1 tiết"). See
.superpowers/sdd/2026-09-02-hard-gate-hdsp-rules/progress.md.
"""
import os
import random

from core.models import SchedulingConfig, Teacher
from core.scheduler import run
from core.scheduler.teacher_off import _assign_off_slots
from core.validation import find_teacher_lone_day_violations, find_teacher_lone_session_violations
from data import db, repository as repo
from io_excel.importer import import_xlsm


def test_off_slot_shortfall_is_reported_not_silently_dropped():
    """Root cause #1: a heavily-excluded teacher (Hiệu trưởng/TPT/BGH role forbids
    all mornings) asked for more off-sessions than eligible cells remain must be
    REPORTED as shortfall, never silently given fewer with no trace."""
    teachers_by_id = {1: Teacher(teacher_id=1, name="Hieu Truong", role="Hiệu trưởng")}
    rng = random.Random(2026)
    gv_off_slots, shortfall = _assign_off_slots({1}, teachers_by_id, rng, off_slot_count=5)
    assert 1 in shortfall, "Regression: shortfall must be reported, not silently absorbed"
    assigned_count, required_count = shortfall[1]
    assert assigned_count == len(gv_off_slots[1])
    assert assigned_count < required_count


def test_full_schedule_never_silently_drops_lone_session_violations(tmp_path):
    """Root cause #2: after _repair_teacher_lone_sessions runs, any teacher lone
    session/day that survives repair must show up in result.relaxed_rules under
    'II.4' -- never silently accepted as if it were fully compliant."""
    fixture_path = os.path.join(os.path.dirname(__file__), "..", "io_excel", "sample_school.xlsm")
    connection = db.get_connection(str(tmp_path / "test_regression.db"))
    db.init_db(connection)
    import_xlsm(connection, fixture_path)

    config = SchedulingConfig(avoid_teacher_lone_periods=True, min_weekly_periods_for_lone_penalty=15)
    repo.set_scheduling_config(connection, config)
    inp = repo.build_scheduling_input(connection, parity="L", seed=2026)
    result = run(inp)

    assert result.success is True, f"Schedule generation failed: {result.failure_reason}"

    min_lone_load = config.min_weekly_periods_for_lone_penalty
    lone_sessions = find_teacher_lone_session_violations(inp.slots, result.assignment, inp.assigned_teacher, min_lone_load)
    lone_days = find_teacher_lone_day_violations(inp.slots, result.assignment, inp.assigned_teacher, min_lone_load)

    if lone_sessions or lone_days:
        relaxed_ids = {item.get("rule_id") for item in result.relaxed_rules}
        assert "II.4" in relaxed_ids, (
            f"Regression: found unreported lone-session/day violations "
            f"{lone_sessions + lone_days} with empty/non-matching relaxed_rules {result.relaxed_rules}"
        )

    connection.close()
```

- [ ] **Step 4: Run the regression tests**

Run: `python -m pytest tests/test_regression_hard_gate_2026_09_02.py -v --timeout=600`
Expected: both PASS. If either fails, it means the corresponding fix from
Task 2 or Task 4 has a gap — debug via `superpowers:systematic-debugging`
before proceeding; do not adjust the test to hide the failure.

- [ ] **Step 5: Profile the real fixture and (re)tune `NGUONG_KHOA` if needed**

Run this ad-hoc timing check (not a committed test, just a manual
measurement — use the Bash/PowerShell tool directly):

```python
import time, os
from data import db, repository as repo
from io_excel.importer import import_xlsm
from core.scheduler import run

connection = db.get_connection(":memory:")
db.init_db(connection)
import_xlsm(connection, os.path.join("io_excel", "sample_school.xlsm"))
inp = repo.build_scheduling_input(connection, parity="L", seed=2026)

start = time.time()
result = run(inp)
elapsed = time.time() - start
print(f"success={result.success} relaxed={len(result.relaxed_rules)} "
      f"attempts={result.attempts_tried} successes={result.successes_found} "
      f"elapsed={elapsed:.1f}s")
```

Run it 3 times (seeds vary since `inp.seed` isn't fixed unless the fixture
sets one) and record the range of `elapsed` in `task-6-report.md`. If any run
exceeds ~5 minutes, that's a real regression against the (previously
unverified) "~4 min" expectation — try raising `NGUONG_KHOA` back up in
increments (e.g. 20 → 35 → 50) and re-measure, since Task 4's Step 10 chose
20 as a reasoned-but-unverified starting point, not a proven optimum. Record
the final chosen value and rationale in the report; update
`core/scheduler/constants.py:8` again if you change it from Task 4's value.

- [ ] **Step 6: Run the FULL test suite one last time**

Run: `python -m pytest tests/ -v --timeout=900`
Expected: all tests pass (aside from any pre-existing, unrelated failures
noted in Task 1's report — confirm those are unchanged, not new). This is
the final verification gate for the whole feature.

- [ ] **Step 7: Commit**

```bash
git add tests/test_mandatory_rules_compliance.py tests/test_regression_hard_gate_2026_09_02.py core/scheduler/constants.py
git commit -m "test: end-to-end + regression coverage for II.3/II.4/II.8/II.14 hard gate"
```

- [ ] **Step 8: Write task-6-report.md and update progress.md**

Report (Vietnamese) should cover: extended end-to-end test outcome (Step 2),
regression test results (Step 4), the 3 profiling runs' timings and final
`NGUONG_KHOA` value (Step 5), and full-suite pass/fail summary (Step 6).
Mark all 6 tasks `[x]` complete in `progress.md` and change its `Status:`
line from `in-progress` to `complete`.
