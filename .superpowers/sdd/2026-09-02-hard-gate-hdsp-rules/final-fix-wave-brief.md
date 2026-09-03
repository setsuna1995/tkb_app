# Final whole-branch review — fix wave brief

Plan: hard-gate-hdsp-rules (6 tasks, all complete — see `progress.md`).
This is the **one fix wave** after the final whole-branch review (opus,
2026-09-03). Per `progress.md`'s "Final Whole-Branch Review" section, 6
items are in scope; 1 Important (#7) and all Minors (#9-18) are explicitly
OUT of scope — do not touch them.

Work in this worktree: `C:\Users\Kien\tkb_app\.claude\worktrees\hard-gate-hdsp-rules`,
branch `worktree-hard-gate-hdsp-rules`. Current HEAD before this dispatch: `05c01c7`.

Run tests with targeted invocations (`pytest tests/test_X.py tests/test_Y.py -v`),
not the full suite on every edit — the suite takes ~2 minutes per full pass
(real-fixture scheduling tests are slow). Run the full suite once before
your final commit.

---

## Item 1 (Critical) — batch multi-week flow bypasses the entire hard gate

**File:** `pages/06_Xep_TKB.py`

The single-week flow (around line 340-441) runs the full HĐSP hard-gate
check after scheduling: it builds `hard_rule_violations` via
`find_teacher_missing_mandatory_morning_violations`,
`find_teacher_lone_session_violations` + `find_teacher_lone_day_violations`
(II.4), `find_teacher_split_day_violations` (II.8),
`find_teacher_4_consecutive_morning_violations` (II.14), gated by the same
config toggles the engine's own gate respects
(`avoid_teacher_lone_periods` for II.4/II.8, `avoid_teacher_4_consecutive_morning`
for II.14, II.3 always unconditional); renders `result.relaxed_rules`; and
disables the save button (`disabled=bool(hard_rule_violations) and not
proceed_with_hard_violations`) unless the operator checks an explicit
override checkbox.

The batch flow (`if st.button("🚀 Xếp các tuần đã chọn", ...)` around line
507, results rendered in the loop starting around line 530) does **none of
this**. It runs `sched.run(b_inp)` per week, shows a plain `st.success(...)`
banner, and the per-week save button
(`st.button(f"✅ Chấp nhận & Lưu Tuần {wn}", key=f"batch_accept_{wn}")`
around line 580) has no `disabled=` condition at all — an admin can batch-
save 35 weeks of non-compliant timetables with zero warning.

**Fix:** inside the batch results loop (the `for wn, (b_seed, b_parity,
b_inp, b_result) in list(batch_results.items()):` block), after the
existing `st.success(...)` block and before the per-week save button, apply
the *same* hard-gate check + `relaxed_rules` rendering + save-block pattern
the single-week flow uses at lines ~340-403 — but using `b_inp`/`b_result`
and **per-week Streamlit widget keys** (the single-week flow's checkbox key
`"proceed_with_hard_violations"` is a bare string; the batch flow needs one
key per week, e.g. `key=f"batch_proceed_with_hard_violations_{wn}"`, since
multiple weeks render in the same rerun). Concretely, for each week:

1. Compute `b_hard_rule_violations` the same way `hard_rule_violations` is
   computed (same 4 `find_*` calls, same config-toggle guards, same
   `teacher_map` — reuse `b_inp.assigned_teacher`/`b_inp.teachers`).
2. Render it with `st.error(...)` + `st.expander(...)` per rule, same
   structure as the single-week block.
3. Render `b_result.relaxed_rules` with the same `st.warning(...)` +
   per-item loop (including the `off_slot_shortfall` special-case branch),
   same as the single-week block — reuse `RULES` from
   `core.rules_registry` (already imported at the top of the file).
4. Compute a per-week `b_proceed_with_hard_violations` checkbox (default
   `True` when there are no violations, same pattern as line 397-402), keyed
   per-week.
5. Add `disabled=bool(b_hard_rule_violations) and not
   b_proceed_with_hard_violations` to the `st.button(f"✅ Chấp nhận & Lưu
   Tuần {wn}", ...)` call.

Do not refactor the single-week block into a shared helper function unless
it comes out trivially — a straight copy-adapt is acceptable and matches
this file's existing style (the batch flow already duplicates the single-
week rendering patterns for the grid/quota-diff sections). If duplicating
inline feels too large, extracting a small helper
`_render_hard_gate_and_get_proceed(inp, result, teacher_map, key_suffix)`
returning `(hard_rule_violations, proceed)` is fine too — your call, but
keep it minimal.

**Test:** this is a Streamlit page, not a pure function — there is no
existing unit-test harness for `pages/06_Xep_TKB.py`'s Streamlit widgets in
this repo (confirm by checking `tests/` for any file importing
`pages.06_Xep_TKB` — there is none). Verify by reading your own diff
carefully against the single-week block it mirrors, and note in your report
whether you could exercise it via Playwright (the project has used
Playwright for UI verification in Task 5 — see `task-5-report.md`'s second
fix round for the pattern). If you do verify live, include concrete
evidence (selector/command transcript or accessibility-snapshot refs) —
per this ledger's Task 5 fix-round-1 ruling, a narrative claim without
artifacts is not accepted as verification.

---

## Item 2 + 3 (Important, paired — same root cause) — relaxed-candidate ranking uses distinct-rule count, not violation count

**File:** `core/scheduler/engine.py`

`_check_hard_post_generation_rules` (lines 32-54) returns `violated: list`
— a list of *distinct* violated rule-ID strings, e.g. `["II.4", "II.8"]`,
never a count of actual violation instances. At line 282:

```python
relaxed_score = (len(hard_gate_violations), teacher_penalty, cells_changed)
```

`len(hard_gate_violations)` is the number of distinct rule types violated
(0-4), not the number of actual violations. A candidate with 3 lone-session
teachers but only 1 distinct rule type (`["II.4"]`, len 1) loses to a
candidate with 1 lone-session + 1 split-day teacher (`["II.4", "II.8"]`,
len 2) even though the first candidate is objectively better (fewer real
violations) — because `(1, ...) < (2, ...)` is backwards here: lower is
supposed to mean "better", but `len()` conflates "how many kinds of
problems" with "how many problems".

This also makes II.8 actively harmful to the ranking: since II.8 (split
day) is now gated by the same `min_weekly_periods_for_lone_penalty`
threshold as II.4 (both check `_count_teacher_split_sessions`/
`_count_teacher_lone_sessions` with the same `min_lone_load`), any teacher
with `S==1 or C==1` on a split day is *by definition* also flagged for a
lone session in one of those two sessions — II.8 firing essentially always
co-occurs with II.4 firing for the same teacher, so it never adds real
independent information, only inflates the distinct-rule-count that the
broken ranking above uses.

**Fix:** change `_check_hard_post_generation_rules` to also return the
total violation-instance count, and use that (not `len(violated)`) as the
ranking key. Suggested shape (keep the return type change minimal and
update every caller):

```python
def _check_hard_post_generation_rules(inp, state, config) -> tuple[list, int]:
    """... (existing docstring) ... Returns (violated_rule_ids, total_violation_count)."""
    violated = []
    total = 0
    mand_morns = getattr(config, "mandatory_morning_weekdays", (2, 5, 6))
    missing = _count_teacher_missing_mandatory_mornings(inp.slots, state.assigned, state.slot_teacher, mand_morns)
    if missing > 0:
        violated.append("II.3")
        total += missing
    if getattr(config, "avoid_teacher_lone_periods", True):
        min_lone_load = getattr(config, "min_weekly_periods_for_lone_penalty", 15)
        lone_sessions = _count_teacher_lone_sessions(inp.slots, state.assigned, state.slot_teacher, min_weekly_periods=min_lone_load)
        lone_days = _count_teacher_lone_days(inp.slots, state.assigned, state.slot_teacher, min_weekly_periods=min_lone_load)
        if lone_sessions > 0 or lone_days > 0:
            violated.append("II.4")
        total += lone_sessions + lone_days
        split = _count_teacher_split_sessions(inp.slots, state.assigned, state.slot_teacher, min_weekly_periods=min_lone_load)
        if split > 0:
            violated.append("II.8")
        total += split
    if getattr(config, "avoid_teacher_4_consecutive_morning", True):
        consecutive = _count_teacher_4_consecutive_mornings(inp.slots, state.assigned, state.slot_teacher, max_load_for_penalty=20)
        if consecutive > 0:
            violated.append("II.14")
        total += consecutive
    return violated, total
```

Then at the call site (line 270):

```python
hard_gate_violations, hard_gate_total = _check_hard_post_generation_rules(inp, state, config)

if not hard_gate_violations:
    ...
else:
    relaxed_score = (hard_gate_total, teacher_penalty, cells_changed)
    if best_relaxed_score is None or relaxed_score < best_relaxed_score:
        best_relaxed_score = relaxed_score
        best_relaxed_changed = cells_changed
        best_relaxed_assignment = dict(state.assigned)
        best_relaxed_violations = hard_gate_violations
```

`best_relaxed_violations` stays a plain list of distinct rule IDs (used
later at line 298 to build `relaxed_rules = [{"rule_id": rid} for rid in
best_relaxed_violations]` — do not change that consumer's shape).

**Do NOT** remove or weaken the II.8 check itself — the ruling in
`progress.md` is explicit that fixing the ranking key (not touching II.8's
gate) is the correct fix for both #2 and #3 together.

**Existing tests that WILL break and must be updated** (same interface-
change pattern as Task 2's tuple-return fix earlier in this branch —
search for other call sites too, don't assume this list is exhaustive):
`tests/test_engine_hard_gate.py` has 3 tests calling
`_check_hard_post_generation_rules(...)` and asserting on the return value
directly as a list (`violations == ["II.4"]`, `"II.8" in violations`,
`violations == []`). Update each to unpack the tuple, e.g.:
```python
violations, _total = _check_hard_post_generation_rules(inp, state, inp.config)
assert violations == ["II.4"]
```

**New test to add** (in `tests/test_engine_hard_gate.py` or a new test in
the same style): construct two synthetic `hard_gate_violations` scenarios
via the real counters (or directly test `_check_hard_post_generation_rules`'s
`total` return) that reproduce the ledger's worked example — a scenario
with 3 lone-session instances and a single distinct rule (`II.4` only)
must rank strictly better (lower `total`) than a scenario with 1
lone-session + 1 split-day instance (`II.4` + `II.8`, 2 distinct rules) —
i.e. assert `total_a < total_b` where scenario A has more raw violations
concentrated in fewer rule types is no longer being unfairly penalized...
**actually confirm the direction with the real ledger example**: 3
lone-session-only violations (total=3, distinct=1) vs 1 lone+1 split
(total=2, distinct=2) — under the OLD buggy ranking `(1, ...) < (2, ...)`,
the 3-violation candidate wins (wrongly, since it's worse); under the FIXED
ranking `(3, ...)` vs `(2, ...)`, the 2-violation candidate correctly wins.
Write the test to assert the FIXED behavior: given the two synthetic
states, the one with fewer total violation instances must produce the
lower `relaxed_score` tuple, regardless of how many distinct rule types
each spans.

---

## Item 4 (Important) — success banner shown even on relaxed-fallback (successes_found == 0)

**File:** `pages/06_Xep_TKB.py` (single-week flow; check whether the batch
flow you're adding in Item 1 has the same bug newly introduced — build the
batch version correctly from the start instead).

Find where the single-week flow renders its main result banner after
`result = sched.run(inp)` (search for `st.success(` near the top of the
results-rendering section — it currently fires unconditionally when
`result.success` is true, which is also true for the relaxed-fallback path
per `core/scheduler/engine.py`'s `successes == 0` branch, since that branch
still returns `success=True`). The `relaxed_rules` warning (`st.warning(...)`
at what is currently line ~382-395) renders far below (after the hard-gate
error block, teacher-day-cap checks, etc.) — buried where an operator
scanning top-to-bottom may not reach it before clicking save.

**Fix:**
1. Branch the top banner: if `result.success and result.successes_found >
   0`, keep the existing `st.success(...)`. If `result.success and
   result.successes_found == 0` (relaxed fallback — this is the only other
   case where `result.success` is true, per engine.py), show `st.warning(...)`
   instead, with wording that makes clear this is NOT a fully-compliant
   schedule (e.g. "Lịch được tạo là phương án khả thi tốt nhất (một số ràng
   buộc HĐSP đã phải nới lỏng — xem chi tiết bên dưới)." — match the
   existing Vietnamese tone/style used elsewhere in this file).
2. Move the existing `if result.relaxed_rules: st.warning(...)` block (the
   one at line ~382-395 rendering each relaxed rule with the
   `off_slot_shortfall` special case) to appear immediately after this
   banner, instead of after the hard-gate violations block. Keep its
   contents unchanged — only reposition it earlier in the render order.

Apply the analogous fix in the batch-flow code you write for Item 1 (i.e.
build it right the first time; the batch flow's `st.success(...)` at line
~535 has the identical bug — branch it the same way against
`b_result.successes_found`).

**Test:** same as Item 1 — this is Streamlit rendering, verify by reading
the diff; live Playwright verification is a bonus, not required, but must
carry real evidence if claimed.

---

## Item 5 (Important) — zero test coverage for the off_shortfall → relaxed_rules integration path

**File:** new test, likely `tests/test_engine_hard_gate.py` or
`tests/test_regression_hard_gate_2026_09_02.py` (follow whichever file's
existing fixture-building pattern is closer to what you need).

`core/scheduler/teacher_off.py`'s shortfall detection has unit coverage
(`tests/test_teacher_off.py`, 3 tests) at the `_assign_off_slots` level.
But nothing tests that `core/scheduler/engine.py`'s `run()` actually
surfaces a shortfall into `ScheduleResult.relaxed_rules` end-to-end — i.e.
that the wiring at engine.py lines 299-300 and 315-316
(`relaxed_rules.append({"rule_id": "II.3", "detail": "off_slot_shortfall",
"teachers": off_shortfall})`) actually fires when a real `run()` call
produces a shortfall.

**Fix:** add an integration test that builds a minimal `SchedulingInput`
(look at `tests/test_engine_hard_gate.py`'s existing fixture-construction
style using `ClassRoom`, `Teacher`, `TimeSlot`, `Slot`, `SchedulingConfig`,
or the real-fixture pattern in `tests/test_regression_hard_gate_2026_09_02.py`
if that's easier to adapt) with:
- a teacher role that is heavily excluded from off-cells (per
  `tests/test_teacher_off.py`'s pattern: a teacher with `role="Hiệu
  trưởng"` forbids all mornings, leaving few eligible afternoon cells), and
- `config.teacher_off_sessions_per_week` (or the equivalent per-teacher
  override field — check `SchedulingConfig`/`Teacher` in `core/models.py`
  for the exact field name used to reach `_assign_off_slots`'s
  `off_slot_count` parameter) set high enough that shortfall is
  structurally guaranteed (mirror `off_slot_count=5` from
  `test_assign_off_slots_reports_shortfall_when_teacher_over_excluded`).

Call `core.scheduler.engine.run(inp)` (or `core.scheduler.run` — check
which is the public entrypoint used elsewhere, e.g.
`from core import scheduler as sched; sched.run(inp)` per
`pages/06_Xep_TKB.py`'s import) and assert:
- `result.success` is True (either fallback path returns `success=True`)
- `result.relaxed_rules` contains an item with
  `item["rule_id"] == "II.3"` and `item["detail"] == "off_slot_shortfall"`
- that item's `"teachers"` dict contains the excluded teacher's ID with an
  `(assigned_count, required_count)` tuple where `assigned_count <
  required_count`

Keep the fixture as small as possible (few classes/slots) so the test runs
fast — this does not need a full real-fixture schedule, just enough slots
for the engine to complete at least one attempt.

---

## Item 6 (Important) — teacher lone-session repair wastes budget on exempt teachers

**File:** `core/scheduler/swaps.py`, function `_repair_teacher_lone_sessions`
(currently lines 78-104 for the signature/filter; the full function
continues past line 160 — read all of it before editing).

The function's `min_weekly_periods_for_lone_penalty` exemption (used by
`quality.py`'s counters and `engine.py`'s hard gate) means a teacher whose
total weekly load is below the configured threshold (default 15) is NOT
counted as a violation for having a lone session — they're structurally
too low-load to avoid it. But `_repair_teacher_lone_sessions`'s candidate
selection (lines 100-104):

```python
lone_teacher_sessions = [
    (tid, wd, sess)
    for (tid, wd, sess), periods in list(state.teacher_session_periods.items())
    if len(periods) == 1 and tid > 0
]
```

considers **every** teacher's lone sessions, including exempt ones. Since
the repair loop is bounded (`max_rounds = 3`, first-improving-move only —
see the docstring and loop structure), spending repair attempts on exempt
teachers reduces how many rounds are available for teachers who actually
count toward the hard gate. Task 6's diagnosis flagged 2 real-fixture
teachers (Thành id=7, Trung id=11, both at exactly the 15-period boundary)
as still violating II.4 after all repairs — this finding proposes that
mis-targeted repair effort is a concrete, testable contributor.

**Fix:**
1. Add a `min_weekly_periods: int = 0` parameter to
   `_repair_teacher_lone_sessions`'s signature (same default-off
   convention as `quality.py`'s counters — 0 means "no exemption, repair
   everyone", preserving existing behavior for any caller that doesn't
   pass it).
2. Compute each teacher's total weekly period count once at the top of the
   function (before the `max_rounds` loop, since it doesn't change across
   rounds within one repair pass) — sum `len(periods)` across all
   `state.teacher_session_periods` entries keyed by that `tid` (matches
   `quality.py`'s `teacher_totals[tid] += 1` per assigned slot semantics;
   using `teacher_session_periods` avoids re-scanning `inp.slots`).
3. Filter `lone_teacher_sessions` to only include `tid`s whose computed
   total is `>= min_weekly_periods` when `min_weekly_periods > 0`.
4. At the call site in `core/scheduler/engine.py` (currently lines
   247-249, inside the `if done:` block that calls
   `_repair_teacher_lone_sessions(inp, state, role_index,
   assigned_teacher, slots_by_class, day_capacity, config,
   subject_class_allowed_cells, slot_by_coord)`), thread
   `config.min_weekly_periods_for_lone_penalty` through as the new
   parameter — read the config default the same way `engine.py`'s hard
   gate does (`getattr(config, "min_weekly_periods_for_lone_penalty", 15)`).

**Test:** add a test in `tests/test_scheduler_teacher_quality.py` (existing
file for this kind of test, per its name and Task 1/4's precedent of
adding tests there) that constructs a state with two teachers with lone
sessions — one below the exemption threshold, one at/above it — and
verifies the exempt teacher's lone session is left untouched by
`_repair_teacher_lone_sessions` (not consumed by a wasted repair attempt)
while the non-exempt teacher's is still attempted. If an existing test in
that file or `tests/test_engine_hard_gate.py` already exercises
`_repair_teacher_lone_sessions` directly, follow its exact construction
pattern rather than inventing a new one.

**Do not** attempt the "leans toward algorithm gap" chain-swap
improvement Task 6 flagged (multi-step swap chains) — that's explicitly
out of scope for this fix wave (it's a bigger feature, not this bug).
This item is *only* about not wasting repair budget on exempt teachers.

---

## Item 8 (Important) — `SchedulingConfig` field defaulting silently resets to old default when saved value is `"0"`

**File:** `data/repositories/config.py`, function that loads
`SchedulingConfig` from the DB (the one containing lines like, currently
around 205-206):

```python
min_weekly_periods_for_lone_penalty=int(
    get_meta(conn, "sched_min_weekly_periods_for_lone_penalty") or default.min_weekly_periods_for_lone_penalty
),
```

`get_meta(...)` returns a string (or `None` if unset). `"0" or X` evaluates
to `X` in Python because the non-empty string `"0"` is falsy-checked by
`or`... **no — the reverse**: `"0"` is a *non-empty string*, which Python
considers **truthy** (`bool("0") is True`). So `get_meta(...) or default...`
evaluates to `get_meta(...)` (i.e. `"0"`) whenever the key is set to any
non-empty string, including `"0"` — that part is actually fine. The real
bug: if `get_meta(...)` returns `None` (key never saved) OR returns the
empty string `""`, the `or` falls through to `default...`. Confirm which
of these is the actual failure mode by reading `get_meta`'s exact
return contract (check `data/repositories/config.py` or wherever
`get_meta`/`set_meta` are defined) — **the ledger's own description
suggests the risk is specifically**: a DB that saved this field as the
string `"0"` *before* Task 1 changed the code-level default from `0` to
`15` would need `get_meta(...)` to reliably return `"0"` (not `None`) for
the `or` to correctly keep it — but if `set_meta` or `get_meta` ever
normalizes/strips "0" to empty or if there's any other falsy-string edge
case in this codebase's `get_meta` implementation, `"0"` could still get
silently overridden back to `default.min_weekly_periods_for_lone_penalty`
(now 15), defeating an explicitly-configured "no exemption" choice.

**Before writing the fix, read `get_meta`'s implementation** (likely in
the same file or a shared DB-metadata helper module) to pin down exactly
which return values are possible (`None` only? or can it return `""`?).
Then apply the same pattern used correctly elsewhere in this same function
for exactly this reason — e.g. lines 193-196 and 201-204 already use the
correct idiom for boolean fields:
```python
hdtn_period2_afternoon=(
    bool(int(get_meta(conn, "sched_hdtn_period2_afternoon"))) if get_meta(conn, "sched_hdtn_period2_afternoon") is not None
    else default.hdtn_period2_afternoon
),
```
Apply the equivalent `is not None` explicit-check idiom to the
`min_weekly_periods_for_lone_penalty` line (and audit the *other* `int(...
or default...)`-style lines in this same function — e.g.
`heavy_subject_priority_periods` at line ~144-146,
`max_teacher_periods_per_day`, `max_heavy_per_session` — for the identical
bug pattern; fix all of them the same way if they share the flaw. Use your
own judgment on which are actually affected once you've confirmed
`get_meta`'s return contract — don't fix fields that aren't actually
vulnerable).

**Test:** add a test (likely in a `tests/test_config_defaults.py`-adjacent
file — check if one already exists covering `get_scheduling_config`/
`set_scheduling_config` round-trips) that: sets
`sched_min_weekly_periods_for_lone_penalty` to the string `"0"` directly
via whatever the DB-metadata write path is (`set_meta` or via
`set_scheduling_config` with a config where this field is `0`), then reads
the config back, and asserts the loaded value is `0` (not silently reset
to the code default of 15).

---

## Report

Write your full report to:
`C:\Users\Kien\tkb_app\.claude\worktrees\hard-gate-hdsp-rules\.superpowers\sdd\2026-09-02-hard-gate-hdsp-rules\final-fix-wave-report.md`

Structure it per-item (Item 1 through Item 8, skipping 7/9-18 since they're
out of scope) with: what you changed, files touched, tests added/updated,
test command + output for each item's covering tests, and a final full-
suite run before your last commit. Note any item where you deviated from
this brief's suggested approach and why.

Commit granularity: group commits by item (or pair 2+3 as the brief does),
matching this branch's existing convention of one focused commit per
logical change — see `git log --oneline` on this branch for the style
(`feat: ...` / `fix: ...` short imperative subject, body explaining why).

Then reply with the standard short contract: Status (DONE |
DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT), commits created, one-line
test summary, concerns, report file path.
