# Final fix-wave report — hard-gate-hdsp-rules

- **Base HEAD**: `05c01c7` (state the final whole-branch review saw)
- **Worktree**: `C:\Users\Kien\tkb_app\.claude\worktrees\hard-gate-hdsp-rules`
- **Branch**: `worktree-hard-gate-hdsp-rules`
- **Brief**: `final-fix-wave-brief.md` (same directory)
- **Scope**: Critical #1, Important #2+#3 (paired), #4, #5, #6, #8. Important #7 and
  all Minors (#9-18) are explicitly out of scope and were not touched.
- **Commits** (5, one per logical item/pair, oldest first):
  1. `ad3430a` — fix: close batch-flow hard-gate bypass, fix relaxed-fallback banner ordering (Items 1+4)
  2. `c34ae0d` — fix: rank relaxed candidates by violation count, not distinct rule count (Items 2+3)
  3. `34e8aa1` — fix: exempt low-load teachers from the lone-session repair budget (Item 6)
  4. `d84fcb5` — fix: use explicit is-not-None check for int config fields whose default changed (Item 8)
  5. `e103b8e` — test: add end-to-end coverage for off_slot_shortfall -> relaxed_rules wiring (Item 5)

Commit order followed implementation order (1+4, 2+3, 6, 8, 5), not the brief's
listed order — Item 5 (a pure test addition, no source change) was done last
since it had no dependency on the others and slotted cleanly at the end.

---

## Item 1 (Critical) + Item 4 (Important) — combined

**Why combined**: both items touch the exact same results-rendering flow in the
same file (`pages/06_Xep_TKB.py`), and the brief itself instructs building the
batch flow's Item 4 fix in from the start rather than as an afterthought
("Apply the analogous fix in the batch-flow code you write for Item 1... build
it right the first time"). Splitting them into two commits would have required
artificially partial-staging interleaved hunks of the same rendering block, so
they were implemented and committed together, with the commit message covering
both.

### What changed

**File**: `pages/06_Xep_TKB.py`

Single-week flow:
- The top result banner now branches on `result.successes_found`: `st.success`
  when `> 0` (unchanged wording), `st.warning` when `== 0` (the relaxed-fallback
  path — the only other case `result.success` is `True`), with wording that
  makes clear the schedule is not fully HĐSP-compliant.
- The `if result.relaxed_rules: st.warning(...)` block (previously rendered
  ~275 lines below, after the hard-gate violations block) was moved to render
  immediately after the banner, unchanged in content. `teacher_map` (needed by
  the block's `off_slot_shortfall` branch) is now computed right after the
  `else:` so it's available at that earlier point; the pre-existing later
  redefinitions of `teacher_map` (lines ~135, ~328, ~342 in the old file) were
  left untouched (harmless, idempotent, matches this file's existing style of
  redefining it several times).

Batch flow (`for wn, (b_seed, b_parity, b_inp, b_result) in list(batch_results.items()):`):
- Added a full mirror of the single-week hard-gate block: `b_hard_rule_violations`
  computed via the same 4 `find_*` calls (`find_teacher_missing_mandatory_morning_violations`,
  `find_teacher_lone_session_violations` + `find_teacher_lone_day_violations`,
  `find_teacher_split_day_violations`, `find_teacher_4_consecutive_morning_violations`),
  gated by the same config toggles (`avoid_teacher_lone_periods`,
  `avoid_teacher_4_consecutive_morning`; II.3 unconditional), rendered the same
  way (`st.error` + per-rule `st.expander`).
- Added a per-week `b_proceed_with_hard_violations` checkbox, keyed
  `batch_proceed_with_hard_violations_{wn}` (per-week key, since multiple weeks
  render in the same rerun — the single-week flow's bare `"proceed_with_hard_violations"`
  key would collide across weeks).
- Added `disabled=bool(b_hard_rule_violations) and not b_proceed_with_hard_violations`
  to the `st.button(f"✅ Chấp nhận & Lưu Tuần {wn}", ...)` call — previously this
  button had no `disabled=` condition at all.
- Applied Item 4's fix to the batch banner too: branches on
  `b_result.successes_found`, with the `b_result.relaxed_rules` block rendered
  immediately after (before the tabs/grids), same pattern as the single-week fix.
- Did not extract a shared helper function — a straight mirror was used, per
  the brief's explicit permission ("a straight copy-adapt is acceptable and
  matches this file's existing style").

### Deviation from the brief

None in substance. One incidental finding, **not fixed** (out of scope, not
one of the 6 items): `pages/06_Xep_TKB.py` references `batch_hdtn_thematic_week`
at the `sched.run(b_inp)` call site (`hdtn_thematic_week=batch_hdtn_thematic_week`),
but no checkbox or other assignment defines this name anywhere in the current
file — confirmed via `grep -n "hdtn_thematic_week" pages/06_Xep_TKB.py`, which
shows only the single-week checkbox (`hdtn_thematic_week`, no `batch_` prefix)
and this one batch-flow usage. This is a pre-existing `NameError` that predates
this branch (traced via `git log -p` to commit `a143d89`, "implement 35-week
teacher workload tracking and modernization of DinhMuc UI" — an unrelated
plan) and would crash the batch "🚀 Xếp các tuần đã chọn" button before it ever
reaches the code this fix wave added. It is not one of the review's 18 findings
and not in this fix wave's scope, so it was left untouched. **Recommend as a
follow-up**: define `batch_hdtn_thematic_week` via a checkbox near
`batch_extra_kep_names`, mirroring the single-week flow's `hdtn_thematic_week`
checkbox.

### Tests

Per the brief, this is a Streamlit page with no unit-test harness (confirmed:
no file under `tests/` imports `pages.06_Xep_TKB` — `grep -rl "06_Xep_TKB" tests/`
returns nothing). Verification performed:
- `python -c "import ast; ast.parse(open('pages/06_Xep_TKB.py', encoding='utf-8').read())"` → `SYNTAX_OK`.
- Full manual diff self-review against the single-week block it mirrors (see
  the diff excerpt in the commit `ad3430a`), confirming: identical 4 `find_*`
  calls with identical config-toggle guards, identical `st.error`/`st.expander`
  rendering, identical `relaxed_rules` rendering (byte-for-byte, only variable
  names `b_`-prefixed), and the new `disabled=` condition matching the
  single-week button's condition shape exactly.
- **Not** verified live via Playwright. The pre-existing `batch_hdtn_thematic_week`
  NameError (see above) would make a live batch-flow run crash immediately,
  unrelated to this fix wave's own code — live verification was not attempted
  for this reason, and per the brief's own instruction ("a narrative claim
  without artifacts is not accepted as verification"), no unverified live-test
  claim is made here. Static/diff review is the verification basis for this
  item, as anticipated by the brief itself.

---

## Item 2 + 3 (Important, paired) — relaxed-candidate ranking key

### What changed

**File**: `core/scheduler/engine.py`

- `_check_hard_post_generation_rules` now returns `tuple[list, int]`
  (`violated_rule_ids, total`) instead of just `list`. `total` accumulates the
  actual violation-instance count from each counter (`missing`,
  `lone_sessions + lone_days`, `split`, `consecutive`), while `violated`
  keeps its original meaning (distinct rule IDs, unconditionally appended once
  per rule that fires at all).
- The call site (previously `hard_gate_violations = _check_hard_post_generation_rules(...)`)
  now unpacks `hard_gate_violations, hard_gate_total = ...`, and the relaxed
  ranking key changed from `(len(hard_gate_violations), teacher_penalty, cells_changed)`
  to `(hard_gate_total, teacher_penalty, cells_changed)`.
- `best_relaxed_violations` still stores the plain distinct-rule-ID list
  (unchanged shape for the `relaxed_rules = [{"rule_id": rid} for rid in ...]`
  consumer at the bottom of `run()`), per the brief's explicit instruction not
  to change that consumer's shape.
- II.8's hard-gate check itself was **not** touched (still runs, still uses the
  same `min_weekly_periods_for_lone_penalty` threshold) — per the ledger's
  ruling, the ranking-key fix alone resolves both #2 and #3.

### Files touched

`core/scheduler/engine.py`, `tests/test_engine_hard_gate.py`.

### Tests

Updated the 3 pre-existing tests that asserted on the old list-only return
(all in `tests/test_engine_hard_gate.py`):
- `test_check_hard_post_generation_rules_flags_lone_session` — now unpacks
  `violations, _total = ...`.
- `test_check_hard_post_generation_rules_split_session_respects_lone_penalty_exemption` —
  both call sites inside its `build()` helper's two scenarios updated to unpack
  the tuple (the low-load scenario additionally asserts `total == 0`).
- `test_check_hard_post_generation_rules_empty_when_compliant` — unpacks and
  additionally asserts `total == 0`.

Added a new test, `test_check_hard_post_generation_rules_ranks_by_total_violation_count_not_distinct_rule_count`,
reproducing the ledger's worked example with the **real counters** (not
fabricated numbers). Hand-computed fixture numbers were verified against the
actual counters via a standalone script before writing the assertions:
- Candidate A: 2 isolated lone-session teacher-days (only II.4, 1 distinct
  rule) → confirmed `(['II.4'], 4)` — 4, not 2, because each isolated lone
  morning session is *both* a lone SESSION and a lone DAY by the counters' own
  definitions (a discovery made by actually running the counters, not assumed
  from the brief's more abstract "3 vs 2" illustration).
- Candidate B: 1 split day (II.4 + II.8, 2 distinct rules) → confirmed
  `(['II.4', 'II.8'], 3)` — the split day's own total is 2 (not 1), so it does
  not double as a lone day.
- Asserts the OLD-buggy-key sanity check (`len(violations_a) < len(violations_b)`,
  i.e. A would have won under the old key) and the FIXED behavior
  (`total_b < total_a`, i.e. B — the objectively better candidate — wins under
  the new key).

**Deviation from brief**: the brief's illustrative numbers were "3 lone-session
instances" vs "1 lone+1 split" (implying totals 3 vs 2). The real counters
produce 4 vs 3 for the cleanest reproducible fixture, because an isolated lone
morning session is inherently double-counted (lone session + lone day) while a
split day's lone sides are not also lone days (day total = 2). This was
confirmed empirically before finalizing the test (see command below) rather
than assumed — the qualitative bug reproduction (old key picks the worse
candidate, new key picks the better one) is preserved exactly; only the
specific numbers differ from the brief's illustration.

```
$ python -c "... (verification script building both candidates via the real counters) ..."
A: (['II.4'], 4)
B: (['II.4', 'II.8'], 3)
```

Test run:
```
$ python -m pytest tests/test_engine_hard_gate.py -v
tests/test_engine_hard_gate.py::test_check_hard_post_generation_rules_flags_lone_session PASSED
tests/test_engine_hard_gate.py::test_check_hard_post_generation_rules_split_session_respects_lone_penalty_exemption PASSED
tests/test_engine_hard_gate.py::test_check_hard_post_generation_rules_empty_when_compliant PASSED
tests/test_engine_hard_gate.py::test_check_hard_post_generation_rules_ranks_by_total_violation_count_not_distinct_rule_count PASSED
4 passed in 0.12s
```

Also confirmed no other call sites needed updating:
`grep -rn "_check_hard_post_generation_rules" --include=*.py .` shows only
`core/scheduler/engine.py`'s own definition + call site and the 3 tests above
— no other production or test code calls this function.

---

## Item 4 — see "Item 1 + Item 4" section above

Item 4 was implemented together with Item 1 (same file, same rendering flow,
built together per the brief's own instruction). See above for what changed
and why it's combined.

---

## Item 5 (Important) — off_slot_shortfall → relaxed_rules integration test

### What changed

**File**: `tests/test_engine_hard_gate.py` (new test added; no source changes
— this item is purely a coverage gap).

Added `test_run_surfaces_off_slot_shortfall_into_relaxed_rules_end_to_end`,
calling `core.scheduler.run(inp)` (the public entrypoint, matching
`pages/06_Xep_TKB.py`'s own `from core import scheduler as sched; sched.run(inp)`
usage) on a minimal synthetic `SchedulingInput`:
- 1 class, 1 real subject ("Toan", morning-only, 5 slots across weekdays 2-6),
  1 required HDTN subject (zero need — satisfies `resolve_roles`'s hard
  requirement without being scheduled or interfering with anything).
- 1 teacher, `role="Hiệu trưởng"` (forbidden all mornings for **off-slot**
  eligibility only, per `tests/test_teacher_off.py`'s existing precedent —
  unrelated to their ability to actually teach mornings, which this fixture
  relies on).
- `config.teacher_off_sessions_per_week=5` — the same value
  `test_teacher_off.py`'s own shortfall test uses to reliably exceed the 4
  eligible afternoon off-cells left after `FORBIDDEN_OFF_CELLS` + the TPT/BGH
  exclusion.

This keeps the teacher's actual teaching slots (morning-only) from ever
colliding with their off-cells (afternoon-only), and keeps their total weekly
load (5 periods) under the II.4 exemption threshold (15) so no other
hard-gate rule can fire and contaminate the `relaxed_rules` assertion — the
only possible entry is the `off_slot_shortfall` one.

Assertions: `result.success is True`; exactly one `relaxed_rules` item with
`rule_id == "II.3"` and `detail == "off_slot_shortfall"`; that item's
`"teachers"` dict contains teacher id `1` with `(assigned_count, required_count)`
where `assigned_count < required_count`.

### Tests

```
$ python -m pytest tests/test_engine_hard_gate.py::test_run_surfaces_off_slot_shortfall_into_relaxed_rules_end_to_end -v
tests/test_engine_hard_gate.py::test_run_surfaces_off_slot_shortfall_into_relaxed_rules_end_to_end PASSED
1 passed in 0.08s
```

Verified determinism across 7 different seeds (1, 2, 3, 42, 999, 2026, 0) via
a standalone script — every seed produced `success=True`, `successes_found=25`
(full-compliance return path, not the relaxed-fallback path — confirms this
test also exercises `engine.py`'s *other* `relaxed_rules.append(...)` call site,
lines ~314-316), and identical shortfall `{1: (4, 5)}` every time.

---

## Item 6 (Important) — lone-session repair budget exemption

### What changed

**File**: `core/scheduler/swaps.py`

- `_repair_teacher_lone_sessions` gained a `min_weekly_periods: int = 0`
  parameter (0 = no exemption, repair everyone — matches `quality.py`'s
  counters' default-off convention, preserving existing behavior for any
  caller that omits it).
- Each teacher's total weekly period count is computed once, up front (from
  `state.teacher_session_periods`, before the `max_rounds` loop) — valid for
  the whole repair pass because a straight 1-for-1 swap (both of this
  function's strategies) never changes a teacher's total, only its
  distribution across sessions/days.
- `lone_teacher_sessions`'s list comprehension gained an additional filter
  clause: `and (min_weekly_periods <= 0 or teacher_totals[tid] >= min_weekly_periods)`.

**File**: `core/scheduler/engine.py`

- The call site (inside the `if done:` block) now passes
  `min_weekly_periods=getattr(config, "min_weekly_periods_for_lone_penalty", 15)`
  — read the same way the hard gate itself reads this threshold.

Did **not** touch the chain-swap / multi-step algorithm gap Task 6 flagged —
explicitly out of scope per the brief.

### Tests

**File**: `tests/test_scheduler_teacher_quality.py`

Added `test_repair_teacher_lone_sessions_skips_exempt_low_load_teacher`,
placed directly after the existing `test_repair_teacher_lone_sessions_evacuates_or_pairs`
whose exact evacuate-repairable structure it reuses twice: Teacher 10 (total=2,
exempt under `min_weekly_periods=15`) and Teacher 30 (total=18, non-exempt,
reaching that total via 4 full 4-period-per-morning padding blocks on separate
classes/weekdays that cannot register as Strategy-1 evacuation targets — full,
`len(periods) == max_periods_per_session` — or Strategy-2 consolidate targets —
no slot at the lone weekday/session coordinate in those classes).

Assertions: after calling `_repair_teacher_lone_sessions(..., min_weekly_periods=15)`,
Teacher 10's lone sessions (Mon S, Tue S) are left at exactly `len == 1`
(untouched); Teacher 30's are `in (0, 2)` (repaired), matching the precedent
test's own assertion style.

**Regression-proof check** (not part of the committed test, run standalone to
confirm the fixture is genuinely discriminating, not vacuously passing):
calling the identical fixture with `min_weekly_periods=0` (old/default
behavior) shows Teacher 10 **does** get repaired too (`Mon: 0, Tue: 2`),
proving the exemption filter — not some unrelated structural block — is what
leaves Teacher 10 untouched when `min_weekly_periods=15` is passed.

```
$ python -m pytest tests/test_scheduler_teacher_quality.py::test_repair_teacher_lone_sessions_skips_exempt_low_load_teacher -v
tests/test_scheduler_teacher_quality.py::test_repair_teacher_lone_sessions_skips_exempt_low_load_teacher PASSED
1 passed in 0.11s

$ python -m pytest tests/test_scheduler_teacher_quality.py tests/test_engine_hard_gate.py -q
19 passed in 0.05s
```

---

## Item 8 (Important) — config falsy-check audit

### Investigation before fixing (per the brief's explicit instruction)

Read `get_meta`'s implementation (`data/repositories/config.py:14-19`):
```python
def get_meta(conn, key, default=None):
    try:
        row = conn.execute("SELECT value FROM app_meta WHERE key=?", (str(key),)).fetchone()
        return row["value"] if row else default
    except Exception:
        return default
```
It returns **either** `None` (key never saved / any DB error) **or the exact
stored string**, verbatim — it never normalizes or strips a stored value to
`""`. Cross-checked every writer: `set_scheduling_config`'s int-field writes
are all `set_meta(conn, "...", str(config.X))`, and `str()` of any Python int
is never `""`.

**Finding**: given this exact contract, the originally-hypothesized bug
("`get_meta` returns `''` for a validly-saved `0`, causing `int(get_meta(...)
or default...)` to silently fall through to default") is **not reachable**
via this app's own write path — `bool("0") is True` in Python, so
`"0" or default` already correctly evaluates to `"0"` today. Confirmed
empirically: the new tests below (see command output) **pass against the
pre-fix code too**, for the specific "0" input.

### What changed anyway, and why

**File**: `data/repositories/config.py`

Despite the above, the brief's instruction to apply the `is not None`
explicit-check idiom to `min_weekly_periods_for_lone_penalty` was
unconditional (not gated on confirming an actively-reachable bug) — it's a
defensive-correctness hardening, matching the idiom already used correctly
elsewhere in this same function for boolean fields (`hdtn_period2_afternoon`,
`avoid_heavy_afternoon_period3`, `avoid_teacher_4_consecutive_morning`), so
the code's correctness no longer depends on an incidental Python-string-
truthiness quirk that a future `get_meta` refactor (e.g. one that normalizes
missing values to `""` instead of `None`) could silently break.

Changed:
- `min_weekly_periods_for_lone_penalty` (explicitly named in the brief).
- `heavy_subject_priority_periods` — audited and fixed too, because it shares
  the *identical* risk story: its code-level default also changed (0 → 4) in
  Task 1, so an old DB with an explicitly-saved `0` (meaningfully different
  from the new default) is exactly the same category of concern.

Left unchanged (`int(get_meta(...) or default...)` idiom retained):
- `max_teacher_periods_per_day`, `max_heavy_per_session`, and the other
  `int(...)`-wrapped fields in this function (`gdtc_avoid_period`,
  `chao_co_weekday`, `chao_co_period`, `max_heavy_consecutive`,
  `max_periods_per_session`, `teacher_off_sessions_per_week`) — confirmed via
  `git log -p -- core/models.py` that none of these fields' code-level
  defaults were ever changed, so there is no "an old explicitly-saved value
  now silently means something different" scenario motivating the fix, and 0
  is not a meaningful configured value for any of them (e.g. "0 max periods
  per day" is degenerate, not a real "explicit off" choice).

### Tests

**File**: `tests/test_repository.py`

Added 3 tests, following the file's existing `set_then_get_scheduling_config_round_trips_*`
pattern:
- `test_set_then_get_scheduling_config_round_trips_explicit_zero_min_weekly_periods_for_lone_penalty`
- `test_set_then_get_scheduling_config_round_trips_explicit_zero_heavy_subject_priority_periods`
- `test_get_scheduling_config_reads_raw_zero_string_saved_via_set_meta` — exercises
  the DB-metadata write path one level lower, via `repo.set_meta(conn, "sched_min_weekly_periods_for_lone_penalty", "0")`
  directly, matching the review's specifically-flagged mechanism.

```
$ python -m pytest tests/test_repository.py -v
... (23 items, all PASSED, including the 3 new ones) ...
23 passed in 1.78s
```

**Transparency check** (run before finalizing, to be honest about what these
tests actually prove): stashed `data/repositories/config.py`'s changes and
re-ran the 3 new tests against the pre-fix code —
```
$ git stash push -- data/repositories/config.py
$ python -m pytest tests/test_repository.py::test_set_then_get_scheduling_config_round_trips_explicit_zero_min_weekly_periods_for_lone_penalty tests/test_repository.py::test_set_then_get_scheduling_config_round_trips_explicit_zero_heavy_subject_priority_periods tests/test_repository.py::test_get_scheduling_config_reads_raw_zero_string_saved_via_set_meta -v
... 3 passed ...
$ git stash pop
```
All 3 passed against the OLD code too, confirming the earlier "not reachable"
finding — these tests lock in the desired round-trip behavior going forward
and document the intent, but they are not literally regression-reproducing
for the originally-hypothesized failure mode, since (per the get_meta audit
above) that failure mode never actually existed for the "0" input in this
codebase's real write path.

---

## Final full-suite run

Split into 2 non-overlapping invocations (bulk vs. the 4 slow real-fixture
files), matching this branch's own established pattern (Task 4 and Task 6
both split the full suite similarly to keep each invocation's wall-clock time
manageable).

**Bulk** (`tests/` minus the 4 slow files below), run twice independently for
cross-confirmation:
```
$ python -m pytest tests/ --ignore=tests/test_mandatory_rules_compliance.py \
    --ignore=tests/test_real_data_schedule.py \
    --ignore=tests/test_regression_hard_gate_2026_09_02.py \
    --ignore=tests/test_weekly_scheduling_integration.py -q
218 passed in 839.64s (0:13:59)      # run 1
218 passed in 940.05s (0:15:40)      # run 2, independent re-run, identical result
```

**Slow real-fixture files**:
```
$ python -m pytest tests/test_mandatory_rules_compliance.py tests/test_real_data_schedule.py \
    tests/test_regression_hard_gate_2026_09_02.py tests/test_weekly_scheduling_integration.py -v
tests/test_mandatory_rules_compliance.py::test_scheduling_config_has_all_hdsp_and_moet_criteria_fields PASSED
tests/test_mandatory_rules_compliance.py::test_teacher_max_periods_per_day_constraint PASSED
tests/test_mandatory_rules_compliance.py::test_class_max_heavy_per_session_constraint PASSED
tests/test_mandatory_rules_compliance.py::test_avoid_heavy_afternoon_period3_constraint PASSED
tests/test_mandatory_rules_compliance.py::test_teacher_lone_period_penalty_exempts_low_workload PASSED
tests/test_mandatory_rules_compliance.py::test_teacher_4_consecutive_mornings_penalty PASSED
tests/test_mandatory_rules_compliance.py::test_hdtn_period2_afternoon_heuristic_scoring PASSED
tests/test_mandatory_rules_compliance.py::test_full_schedule_15_criteria_compliance PASSED
tests/test_real_data_schedule.py::test_real_data_schedules_successfully[C] PASSED
tests/test_real_data_schedule.py::test_real_data_schedules_successfully[L] PASSED
tests/test_real_data_schedule.py::test_real_data_schedules_successfully_with_hdtn_thematic_week[C] PASSED
tests/test_real_data_schedule.py::test_real_data_schedules_successfully_with_hdtn_thematic_week[L] PASSED
tests/test_real_data_schedule.py::test_real_data_schedules_successfully_with_heavy_subjects_morning_only[L] PASSED
tests/test_real_data_schedule.py::test_real_data_schedules_successfully_with_heavy_subjects_morning_only[C] XPASS
tests/test_regression_hard_gate_2026_09_02.py::test_off_slot_shortfall_is_reported_not_silently_dropped PASSED
tests/test_regression_hard_gate_2026_09_02.py::test_full_schedule_never_silently_drops_lone_session_violations PASSED
tests/test_weekly_scheduling_integration.py::test_build_scheduling_input_week_no SKIPPED
tests/test_weekly_scheduling_integration.py::test_compute_quota_diff_with_week_dict PASSED
16 passed, 1 skipped, 1 xpassed in 999.62s (0:16:39)
```

**Grand total**: 218 + 16 = **234 passed**, 1 skipped, 1 xpassed, **0 failed**
across 236 tests.

The 1 skip (`test_build_scheduling_input_week_no`) and 1 xpass
(`test_real_data_schedules_successfully_with_heavy_subjects_morning_only[C]`)
are both pre-existing, unrelated to this fix wave, and already documented in
`progress.md`'s Task 6 entry (same skip, same xpass, same bar Task 6's own
full-suite run reported: "230 total, 228 passed, 1 skipped..., 1 xpassed...").
This fix wave added 6 new tests (2 in `test_engine_hard_gate.py` for Items
2+3 and 5 combined — actually 2 there: the ranking test and the off_shortfall
integration test; 1 in `test_scheduler_teacher_quality.py` for Item 6; 3 in
`test_repository.py` for Item 8), all passing:
230 (prior total) + 6 (new) = 236 total, 228 (prior passed) + 6 (new passed) =
234 passed — reconciles exactly with the numbers above.

No test failures anywhere in the full suite.

---

## Self-review summary

Full diff since `05c01c7` reviewed file-by-file (see `git diff 05c01c7..HEAD`):
- `pages/06_Xep_TKB.py`: 129 insertions, 28 deletions — batch-flow gate +
  banner reordering (both flows). Syntax-checked via `ast.parse`.
- `core/scheduler/engine.py`: ranking-key fix (Items 2+3) + repair-call-site
  threading (Item 6) — two separate, non-overlapping edits to this file,
  committed separately.
- `core/scheduler/swaps.py`: exemption parameter + filter (Item 6).
- `data/repositories/config.py`: 2 fields switched to the `is not None` idiom
  (Item 8).
- `tests/test_engine_hard_gate.py`: 3 pre-existing tests updated for the tuple
  return + 2 new tests (ranking, off_shortfall integration).
- `tests/test_scheduler_teacher_quality.py`: 1 new test (Item 6).
- `tests/test_repository.py`: 3 new tests (Item 8).

One pre-existing, out-of-scope defect found and explicitly **not** fixed (see
Item 1's Deviation note): `batch_hdtn_thematic_week` NameError in the batch
flow, predates this branch, not one of the 6 in-scope items.
