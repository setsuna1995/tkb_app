# SDD ledger — plan: .superpowers/sdd/2026-09-02-hard-gate-hdsp-rules/ (task-1-brief.md .. task-6-brief.md)

# SDD Progress Ledger: Hard-Gate HĐSP Rules (II.3, II.4, II.8, II.14)

- **Date**: 2026-09-02
- **Feature**: `hard-gate-hdsp-rules`
- **Root Context**: git worktree `.claude/worktrees/hard-gate-hdsp-rules`, branch `worktree-hard-gate-hdsp-rules`, branched from main
- **Status**: `complete`
- **Design doc**: plan approved via Claude Code Plan Mode 2026-09-02 (see chat transcript / `C:\Users\Kien\.claude\plans\c-c-i-u-ki-n-b-t-twinkling-cloud.md`)
- **Execution mode**: superpowers:subagent-driven-development. This ledger's per-task
  briefs (`task-N-brief.md`) were written directly during planning (not extracted via
  `scripts/task-brief` from a single monolithic plan file) — matching this project's
  own pre-existing SDD folder convention. Dispatch each implementer with the
  corresponding `task-N-brief.md` path directly.

## Why (Bối cảnh)

Ledger `2026-09-01-mandatory-school-rules-and-moet-standards/progress.md` marked
II.3/II.7/II.8/II.9 "Verified", but "Verified" there only meant a unit test on
the scoring function passes — no full generated schedule was ever checked
end-to-end. Two concrete bugs cause the symptoms the user (Kien) reported on
2026-09-02 ("vẫn có người được nghỉ sáng T2", "vẫn nhiều buổi lẻ 1 tiết"):

1. `core/scheduler/teacher_off.py` silently assigns FEWER off-sessions than
   required (`min(remaining_count, len(all_eligible_cells))`) when a teacher
   has too many exclusions — never surfaced anywhere.
2. `core/scheduler/swaps.py:_repair_teacher_lone_sessions`'s success is never
   verified — unlike the class-level lone-period check, which already gates
   whether an attempt counts as successful.

Rule classification decision (user-confirmed 2026-09-02): II.3, II.4, II.8,
II.14 become hard-gated (with retry, or explicit `relaxed_rules` reporting
when retry structurally cannot help). II.7 and II.9 stay soft — hard-gating
them alongside II.4 is infeasible for teachers whose weekly afternoon load is
exactly 1 period (forces a lone session, i.e. self-contradicts II.4), and the
project's own conflict-audit doc already documents `TEACHER_AFTERNOON_BALANCE_BONUS=0`
as a deliberate choice to avoid this exact trap for II.7.

## Pre-flight Conflict Scan Table

| Tasks | File(s) | What Task A produces | What Task B consumes | Finding |
|---|---|---|---|---|
| 1, 4 | `core/models.py`, `core/scheduler/engine.py` | Task 1 fixes config defaults + adds `ScheduleResult.relaxed_rules` | Task 4 populates `relaxed_rules` on the returned result | Clean — strict order 1 -> 4 |
| 2, 4 | `core/scheduler/teacher_off.py`, `core/scheduler/engine.py` | Task 2 changes `_assign_off_slots` to return `(gv_off_slots, shortfall)` | Task 4 unpacks the new tuple at the call site | Clean — strict order 2 -> 4 (Task 4 will not compile until Task 2 lands) |
| 3, 5 | `core/rules_registry.py`, `pages/06_Xep_TKB.py` | Task 3 defines rule tiers (which IDs block save) | Task 5's UI loop reads tier to decide block vs warn | Clean — strict order 3 -> 5 |
| 4, 5 | `core/scheduler/engine.py`, `core/validation.py` + `pages/06_Xep_TKB.py` | Task 4 adds the post-generation hard gate + `relaxed_rules` | Task 5 adds matching `find_*` validators + renders `relaxed_rules` in the UI | Clean — strict order 4 -> 5 |
| 1, 6 | `tests/test_mandatory_rules_compliance.py` | Task 1 edits lines ~29-31 (config-default assertion) | Task 6 edits a different function later in the same file (extends `test_full_schedule_15_criteria_compliance`) | Clean — non-overlapping regions of the same file, and Task 6 runs strictly after Task 1 per the dependency order below |
| 1-5, 6 | all above | Tasks 1-5 change engine/config/UI behavior | Task 6 asserts the new behavior end-to-end + regression fixtures | Clean — Task 6 must run last |

Tasks 1, 2, 3 have no dependencies on each other and can be implemented in
any order — but per subagent-driven-development's rule to never dispatch
implementers in parallel, they will still run sequentially (1 -> 2 -> 3),
just without needing to wait on each other's *output*, only on the
controller being free. Dispatch order chosen: 1, 2, 3, 4, 5, 6.

No other findings from the scan: no other pair of tasks shares a file not
already listed above; every task's own file list (Files: section in its
brief) matches the files enumerated in this table.

## Execution Log

- Task 1: fix round 1/5 (1 addressed, 0 open — tests/test_models.py:14 stale
  `heavy_subject_priority_periods == 0` assertion missed by original regression
  sweep; commits c87e957..583fcfb)
- Task 1: minor (deferred): task-1-report.md:131 has garbled mixed-script text
  ("нослабленный" instead of Vietnamese "nới lỏng") — cosmetic only, in report
  prose not code, does not block.
- Task 1: complete (commits a143d89..583fcfb, 1 minor deferred, see above)
- Task 2: minor (deferred): task-2-report.md's "engine.py:111 unpack" explanation
  is imprecise (it's a plain assignment, not an unpack; the actual AttributeError
  surfaces later inside feasibility.py:29) — same root cause either way, cosmetic
  report-writing issue only.
- Task 2: complete (commits 583fcfb..f323c56, review clean apart from the minor above)
- Task 3: complete (commits f323c56..de70ebd, review clean)
- Process note: the Task 1 implementer agent (a29d2cecbff724fa8) continued
  running autonomously after its fix-round-1 report and, without being asked,
  found+fixed one more pre-existing regression from the same default-value
  change: `tests/test_scheduler.py::test_pick_best_scored_unbiased_with_default_config`
  assumed `config=None` (default `SchedulingConfig()`) was unbiased between two
  subjects — no longer true now that `heavy_subject_priority_periods` defaults
  to 4 instead of 0. Commit `bc17022` fixes it by explicitly constructing
  `SchedulingConfig(heavy_subject_priority_periods=0)` in the test, restoring
  its original intent (testing unbiased *scoring logic*, not "whatever the
  default happens to be"). Controller-verified (read the diff directly,
  6-line single-file test change, logically sound) rather than sent through a
  full dispatch-a-reviewer cycle, given the size/risk and that it duplicates
  the exact pattern already reviewed and approved twice for Tasks 1's other
  two fixes. Confirmed via `git show --stat` that this commit touched ONLY
  `tests/test_scheduler.py` — no overlap with Task 4's concurrent in-progress
  edits to `engine.py`/`constants.py`, so no corruption risk. Ruling: accept
  this fix as part of Task 1's completed work; do not send agent
  a29d2cecbff724fa8 any further messages (its task is closed).

- Task 4: reported DONE_WITH_CONCERNS (commit `b389052`). Two concerns require
  action before review:
  1. **Ruling — load-bearing plan defect**: `core/scheduler/quality.py:_count_teacher_split_sessions`
     has NO `min_weekly_periods` exemption parameter, unlike its 3 sibling
     counters (`_count_teacher_lone_sessions`, `_count_teacher_lone_days`,
     `_count_teacher_4_consecutive_mornings`). Task 4's brief (written by the
     controller) instructed calling it unconditionally in the new hard gate for
     II.8 — but the classification table in `progress.md` explicitly says II.8
     should "share II.4's exemption/logic." This gap was already latent in the
     pre-existing SOFT scoring (`_teacher_quality_penalty` line 136 also calls
     it with no threshold) but never mattered while it was soft-only; now that
     it's hard-gated, it likely contributes to low-load specialist teachers
     (Âm nhạc, Tin học, etc. — common in real school staffing) being
     structurally unable to avoid an II.8 violation. Ruling: extend
     `_count_teacher_split_sessions` with `min_weekly_periods: int = 0` (same
     convention as its siblings), thread the same `min_weekly_periods_for_lone_penalty`
     threshold through both the hard gate (`engine.py`) and the soft penalty
     (`quality.py:_teacher_quality_penalty`, a welcome consistency fix), and
     update Task 5's not-yet-dispatched brief (`find_teacher_split_day_violations`)
     to accept/pass the same threshold so the UI validator and the gate can
     never disagree. Cost if wrong: a slightly wider exemption than intended
     for II.8 — reversible, low risk, Task 6 will re-profile with this fix in
     place anyway.
  2. **Ruling — Task 2 brief was factually wrong**: it claimed
     `_assign_off_slots` had exactly one caller (`engine.py`) — in fact 11
     pre-existing tests across `tests/test_scheduler.py` and
     `tests/test_scheduler_teacher_quality.py` call it directly and unpack the
     old dict-only return, now broken by Task 2's tuple return. Task 4's
     implementer correctly stayed in scope and did not touch these (brief
     didn't list them). Ruling: fix these 11 call sites now, as part of Task
     4's fix round (directly caused by an interface change Task 4's own work
     depends on) rather than deferring to Task 6 (whose scope is end-to-end
     assertions/regression fixtures/profiling, not pre-existing test repair)
     or leaving the suite red. Cost if wrong: none — this is a mechanical
     unpack fix, not a behavior change.
  3. **Flagged for Task 6 (not resolved now, needs real investigation)**: all
     4 real-fixture scenarios Task 4 measured hit the relaxed-fallback path,
     exhausting the full 6000-attempt budget (~110-155s each) — II.4 and II.8
     were violated in ALL 4 scenarios, II.3 and II.14 in 3/4. Notably II.4
     ALREADY has its exemption applied correctly and is still always violated,
     so the II.8 fix above may not fully resolve this — Task 6 must profile
     WHICH teachers trigger II.4 despite the >=15-period exemption and
     determine whether that's a genuine real-world structural conflict (school
     data truly cannot satisfy it) or a further logic gap. Also flagged: a
     previously-`xfail` test (`test_real_data_schedules_successfully_with_heavy_subjects_morning_only[C]`)
     now XPASSes via the relaxed-fallback path — Task 6 should reassess
     whether that marker is still appropriate.

- Task 4: fix round 1/5 (2 addressed — II.8 exemption gap, 11 broken
  direct-caller tests; commits b389052..41d95b0). Implementer also found and
  fixed, on its own initiative: a 12th test with the identical tuple-unpack
  bug not in the controller's list (was passing for the wrong reason), and
  resolved `test_teacher_lone_sessions_heavy_penalty` (previously flagged for
  Task 6) by restoring its intended threshold via explicit config override,
  matching Task 1's precedent for a sibling test — accepted, small and
  consistent with already-reviewed patterns. `pytest tests/test_scheduler.py
  tests/test_scheduler_teacher_quality.py tests/test_engine_hard_gate.py -v`
  → 96 passed, 0 failed.

- Task 4: review Approved (all 7 correctness-critical points independently
  verified against source, not just the report — gate insertion order,
  tuple-comparison + copy semantics for `best_relaxed_assignment`,
  attempt-invariance of `off_shortfall`, `successes_found=0` semantics, II.8
  exemption default, 12 test unpack-fixes, `NGUONG_KHOA` value — all correct).
  One Important finding, labeled plan-mandated: `relaxed_rules` can contain
  two entries with the same `rule_id: "II.3"` meaning different things (an
  actual hard-gate violation vs. the structural `off_slot_shortfall` case) —
  this is exactly what Task 4's brief (written by the controller) specified
  in Step 9. Ruling: no code change needed — Task 5's brief already
  disambiguates these at render time via the `detail` field
  (`item.get("detail") == "off_slot_shortfall"` branches to a distinct
  message), so the two same-`rule_id` entries never look the same to an end
  user. Verified by re-reading Task 5's brief Step 5 UI code before ruling.
  Cost if wrong: a cosmetic UI ambiguity in an edge case (both II.3 violation
  types occurring simultaneously) — low severity, revisit if it comes up in
  Task 6's real-fixture testing.
- Task 4: complete (commits de70ebd..41d95b0 [b389052, bc17022 unrelated,
  41d95b0], review Approved, 1 plan-mandated Important ruled non-blocking)

- Task 5: reviewer found 1 Critical + 2 Important, all plan-mandated (my brief's
  bug, not the implementer's — they transcribed it faithfully). Rulings:
  1. **Critical**: `find_teacher_split_day_violations`'s brief code used
     `S==1 and C==1` (symmetric-only), but the actual engine logic it must
     mirror (`quality.py:_count_teacher_split_sessions`) is
     `S>0 and C>0 and (S==1 or C==1)` (also catches asymmetric splits like 1
     AM + 3 PM). This is a genuine transcription mistake I made writing the
     brief — verified by re-reading my own original `quality.py` read earlier
     in this session. Fixed `task-5-brief.md`'s function + added a regression
     test for the asymmetric case (previously untested, which is exactly how
     this slipped through). Ruling: real bug, must fix — resumed implementer.
  2. **Important**: the brief's UI wiring block computed II.4/II.8/II.14
     unconditionally, but `engine.py`'s gate respects
     `avoid_teacher_lone_periods` (II.4/II.8) and
     `avoid_teacher_4_consecutive_morning` (II.14) config toggles — a school
     that disabled either toggle would have the UI still block save on rules
     the engine was told to ignore. Fixed `task-5-brief.md` to add the same
     `if getattr(inp.config, ...):` guards around those validator calls
     (II.3 correctly stays unconditional — no engine-side toggle exists for
     it). Ruling: real bug, must fix — resumed implementer.
  3. **Important (process, not code)**: `task-5-report.md`'s claim of live
     Playwright UI verification had no corroborating evidence (no screenshot
     reference, no selector/command transcript) despite specific-sounding
     narrative detail that turned out to all be derivable from reading the
     source rather than actually running it. Ruling: not rejecting the claim
     outright, but asking the implementer to either produce concrete
     artifacts this round or honestly downgrade to "verified by code reading"
     — a report's confidence should match its actual evidence.

- Task 5: fix round 1/5 (3 addressed, 0 open — commits 6175712..f62db02).
  Re-review confirmed the II.8 condition now byte-for-byte matches
  `quality.py`, config toggles correctly gate II.4/II.8/II.14 (II.3 stays
  unconditional, matching engine), and the Playwright evidence this round is
  genuine (literal accessibility-snapshot refs, selector code, JS-eval JSON
  output) — qualitatively different from the first round's narration.
- Task 5: complete (commits 41d95b0..f62db02, review clean after 1 fix round)

- Task 6: complete (commit `05c01c7`, no fix round needed). Extended
  `test_full_schedule_15_criteria_compliance` per brief exactly; PASSED
  (114.56s), confirmed via an independent seeded re-run that it passed via
  the relaxed-fallback path (`relaxed_rules=[II.3, II.4]`, `successes_found=0`
  after all 6000 attempts) -- not full compliance. **Step 2b diagnosis**
  (the task's main deliverable): the 2 teachers still triggering II.4
  (Thành id=7, Trung id=11) both have weekly load of EXACTLY 15 periods --
  right at the `min_weekly_periods_for_lone_penalty=15` boundary, correctly
  NOT exempt (confirms no bug in the exemption/gate wiring, closing the
  question Task 4 left open). Their course loads are structurally
  fragmented (Thành: 9 subject/class pairs across 6 classes, 5 of them
  singleton 1-period/week; Trung: same subject to 5 classes, 3 periods
  each) -- the repair mechanism already resolves 5/7 and 6/7 of their
  weekly sessions, leaving only 1-2/week unresolved. Verdict: inconclusive
  between "genuine structural limit" and "search algorithm gap" but leans
  toward the latter (evidence: `_repair_teacher_lone_sessions` only tries
  single 1-for-1 swaps, stops at first improving move, no multi-step
  chains) -- reported as a follow-up recommendation, NOT fixed (correctly
  out of scope). Both regression tests (Step 3-4) PASSED. Step 5 profiling:
  3 runs at 101.6-102.5s, well under the 5-minute regression threshold --
  `NGUONG_KHOA` kept at 20, `constants.py` untouched. Full suite (split into
  4 non-overlapping invocations per the brief's own "smaller targeted runs"
  guidance, same pattern Task 4 used): 230/230 distinct tests accounted
  for, 228 passed + 1 pre-existing environment-skip + 1 xpassed (the
  previously-flagged `heavy_subjects_morning_only[C]` xfail marker, now
  confirmed still XPASSing -- flagged as a follow-up marker-reassessment
  recommendation, file not in this task's Files scope so left untouched),
  0 failed. Also caught and documented (not fixed, out of scope) a
  pre-existing subtlety in `data/repositories/config.py:152-158`: an
  explicitly-constructed `SchedulingConfig()` passed to
  `set_scheduling_config()` silently resets `morning_only_subject_ids` to
  empty, clobbering the DB's auto-detected Toán/Ngữ-văn-morning-only
  default -- explains why the Step 5 profiling script (no explicit config)
  and Step 2b's diagnostic (explicit config, matching the actual pytest
  test) measured a different relaxed-rule count (4 vs 2) for the nominally
  "same" scenario. No scheduler algorithm file touched.

- Task 6: review Approved, no findings. Diagnostic (Step 2b) independently
  verified by the reviewer against live source (`quality.py`, `engine.py`,
  `swaps.py`, `data/repositories/config.py`) — confirmed: the exemption
  threshold works correctly (the 2 remaining II.4-violating teachers, Thành
  id=7 and Trung id=11, sit at exactly 15 periods/week, the boundary, not a
  bug); `_repair_teacher_lone_sessions` is genuinely single-swap-only with
  no chain-swap capability (supports the "leans toward algorithm gap, not
  proven" hedge); a real, correctly-diagnosed, out-of-scope side-finding in
  `data/repositories/config.py` (`set_scheduling_config` silently clobbers
  the Toán/Văn morning auto-detect default). NGUONG_KHOA correctly left
  unchanged after measurement (101-117s, well under the 5-minute budget).
  Full suite: 230 total, 228 passed, 1 skipped (environment-dependent,
  unrelated), 1 xpassed (flagged for follow-up), 0 failed.
- Task 6: complete (commit f62db02..05c01c7, review clean)

## Task Checklist

- [x] **Task 1**: Config defaults (`min_weekly_periods_for_lone_penalty`→15, `heavy_subject_priority_periods`→4) + `ScheduleResult.relaxed_rules` field (`core/models.py`, `pages/10_Cau_hinh_Xep_lich.py`, `tests/test_mandatory_rules_compliance.py`). Brief: task-1-brief.md
- [x] **Task 2**: Fix `teacher_off.py` silent off-slot shortfall — return `(gv_off_slots, shortfall)` instead of truncating silently (`core/scheduler/teacher_off.py`). Brief: task-2-brief.md
- [x] **Task 3**: New `core/rules_registry.py` — single source of truth for rule tier (which II.x rules are hard-gated vs soft). Brief: task-3-brief.md
- [x] **Task 4**: Generalize the post-generation hard gate in `engine.py` — reject attempts violating II.3(accidental empty forbidden morning)/II.4/II.8/II.14, add a core-invariant-only fallback path returning `relaxed_rules` instead of silent failure, retune `NGUONG_KHOA`. Brief: task-4-brief.md
- [x] **Task 5**: `core/validation.py` new `find_*` wrappers for II.3/II.4/II.8/II.14 + wire save-gate blocking and `relaxed_rules` display into `pages/06_Xep_TKB.py`. Brief: task-5-brief.md
- [x] **Task 6**: Extend `tests/test_mandatory_rules_compliance.py` end-to-end assertions + regression fixtures for both root-cause bugs + profile real fixture before/after. Brief: task-6-brief.md

## Final Whole-Branch Review (2026-09-03)

Dispatched on opus per skill guidance (most capable model for the final pass).
Verdict: **Ready to merge? No** — 1 Critical + 8 Important findings, all
independently verified by the reviewer against live source/scripts, not
taken from the ledger on faith. Full report is in the reviewer's transcript;
key items and rulings:

- **Critical #1 — batch multi-week flow (`pages/06_Xep_TKB.py:507-592`,
  "Xếp nhiều tuần cùng lúc") bypasses the ENTIRE hard-gate mechanism.** No
  `find_teacher_*` HĐSP validators called, `relaxed_rules` never read, save
  button has no `disabled=`/override checkbox. Every per-task review scoped
  only the single-week flow (`:340-441`) — nobody looked at the whole file.
  On real data (always relaxed-fallback per Task 4/6), this means an admin
  batch-scheduling 35 weeks could save 35 non-compliant timetables with zero
  warning — exactly what this whole feature exists to prevent. **Ruling: in
  scope for the one fix wave, must fix before merge.**
- **Important #2 — `relaxed_score` in `engine.py:282` ranks by
  `len(hard_gate_violations)` (distinct rule-ID count) instead of actual
  violation count**, provably selecting objectively worse candidates
  (reviewer's worked example: 3 lone-session teachers loses to 1
  lone-session+1-split teacher because `(1, 2250) < (2, 1100)` even though
  the first has fewer total violations). **Ruling: in scope, fix alongside
  #3 since they're the same root cause.**
- **Important #3 — II.8 is mathematically subsumed by II.4** now that they
  share `min_lone_load` (any `S==1`/`C==1` split day IS a lone session by
  definition) — confirmed by formal argument, not just the reviewer's fuzz
  claim. II.8's hard-gate check currently adds zero independent rejection
  power and only inflates the violation count that #2's broken ranking uses.
  **Ruling: in scope — the real fix for #2 needs to stop using violation
  *count* as a ranking key regardless, which also resolves #3's distortion.**
- **Important #4 — success banner shown even when `successes_found==0`**
  (relaxed-fallback), with the actual `relaxed_rules` warning buried ~275
  lines below. **Ruling: in scope, straightforward fix (branch to
  `st.warning`, move the warning up).**
- **Important #5 — the `off_shortfall` → `relaxed_rules` path has zero test
  coverage** anywhere in the suite. **Ruling: in scope, add a test.**
- **Important #6 — `_repair_teacher_lone_sessions` (`swaps.py:98-104`)
  doesn't know about `min_weekly_periods_for_lone_penalty`**, so it spends
  its limited repair budget (3 rounds, first-improvement) on exempt
  low-load teachers too, diluting effort on the 2 real teachers that
  actually block compliance. Reviewer frames this as a cheaper, untested
  alternative explanation to Task 6's "leans toward algorithm gap"
  diagnosis — Task 6 examined `swaps.py`'s single-swap-only limitation but
  did not check whether the repair pass was even correctly *targeted*.
  **Ruling: in scope for this fix wave (not deferred to backlog like the
  chain-swap idea) — it's a 1-parameter thread-through, low risk, and
  directly tests a concrete hypothesis about the branch's biggest open
  question (why real data never achieves full compliance). This is a
  judgment call given "no second fix wave"; if the implementer finds it
  more invasive than expected, they should report back rather than force it.**
- **Important #7 — redundant full-slot-scan computation** between
  `_teacher_quality_penalty` and `_check_hard_post_generation_rules` (5 of 7
  counters re-run with identical params). Real inefficiency, multiplies
  across the batch flow, but not a correctness bug. **Ruling: OUT of this
  fix wave — defer to backlog, per the reviewer's own suggested
  prioritization ("không cần làm trong branch này" list doesn't include
  this explicitly, but it's the lowest-severity Important and the fix wave
  is already large; revisit if #1 exposes it as newly hot via the batch
  flow's 35x multiplication).**
- **Important #8 — `data/repositories/config.py:205-206`'s
  `int(get_meta(...) or default...)` treats the saved string `"0"` as falsy
  in the wrong way** — actually the reverse bug direction from what a quick
  read suggests: `"0"` is a truthy Python string, so `get_meta(...) or
  default` evaluates to `"0"` (not `default`), and `int("0")=0` — meaning
  any DB that saved this field while the code default was still `0` (before
  Task 1) will be permanently stuck at the old default of `0`, silently
  defeating the exemption. Reviewer checked 2 real DBs — neither has the key
  saved yet, so not actively broken today, but a live risk for any school
  that configures this field before this fix ships. **Ruling: in scope, fix
  the falsy-check bug** (use `get_meta(...) is not None` or equivalent).
- **Minor #9-18**: registry under-enforced (decorative), mismatched cross-
  layer defaults (0 vs 15) that no current call site exercises, II.14 counts
  "≥4 in one morning" not "4 *consecutive*" (matches spec loosely, tightens
  real-world compliance further), raw (not Vietnamese-formatted) violation
  detail rendering, sticky override checkbox, no audit trail on save,
  `off_shortfall` dropped on total-failure path, `off_shortfall` read from
  last-not-best attempt (harmless given proven invariance, but not
  type-enforced), missing `__all__` export, breaking-change-shaped tuple
  return on a nominally-private function. **Ruling: OUT of this fix wave —
  ledgered as deferred minors for a future pass, per the reviewer's own
  explicit recommendation not to expand scope on #9/#11 and by extension
  the rest of this tier.**
- **Plan-level finding (not a code bug — a correction to MY OWN root-cause
  narrative from the very start of this engagement):** the reviewer
  presents a compelling case that Task 2's `_assign_off_slots` shortfall
  fix likely does NOT explain the user's original reported symptom ("vẫn có
  người được nghỉ sáng T2"). Traced through the actual exclusion math at the
  DEFAULT `teacher_off_sessions_per_week=1`: even a TPT/BGH teacher (all
  mornings forbidden) still has 4 eligible afternoon weekdays for 1 needed
  off-slot, so the `else`/shortfall branch in `teacher_off.py` is
  structurally unreachable under realistic settings — it only fires when
  `off_sessions_override` is set unusually high (confirmed: all 3 of Task
  2's own tests needed `off_slot_count=5` to trigger it at all). The
  mechanism that actually produces "GV trống sáng bắt buộc" is ordinary
  greedy placement leaving a teacher with zero periods on a mandatory
  morning — exactly what Task 4's II.3 gate
  (`_count_teacher_missing_mandatory_mornings`) catches, unrelated to the
  off-slot assignment mechanism entirely. **Ruling: accept this correction.**
  Task 2's fix is still legitimate defensive engineering (real for schools
  with unusual per-teacher `off_sessions_override` configs) and stays in the
  branch, but the CAUSAL story should not be presented to the user as "this
  is what fixed your Monday-morning complaint" — Task 4's II.3 gate is the
  actual fix for that. This will be corrected when reporting back to the
  user (see final chat summary), not by editing this historical ledger
  narrative retroactively.

**Fix wave scope decided:** #1 (Critical), #2+#3 (paired), #4, #5, #6, #8.
Explicitly deferred: #7, all Minor #9-18. One fix dispatch, one scoped
re-review, per subagent-driven-development's rule (no second fix wave).

All 6 tasks complete. Status: `complete`.

## Final Fix Wave (resumed 2026-09-03, new controller session)

Session resumed via `/superpowers:subagent-driven-development` with no
plan argument. Recovery note: the main repo root's copy of this plan's
workspace (`C:\Users\Kien\tkb_app\.superpowers\sdd\2026-09-02-hard-gate-hdsp-rules\`)
only has the 6 task briefs + a stale, differently-formatted progress.md —
it is NOT this ledger. The authoritative, complete record (this file, all
task reports, all review diffs) lives only inside this git worktree
(`.claude/worktrees/hard-gate-hdsp-rules`), which is git-ignored and never
shared with the main repo checkout. Confirmed via `git log --oneline
a143d89..05c01c7` (10 commits, matches every Execution Log entry above) and
via `git diff a143d89 8f577b1 --stat` on main (main's HEAD commit message
claims to implement this feature but touches zero files under core/,
pages/, tests/ — it only added planning artifacts + unrelated files). This
worktree/branch has never been merged to main.

FIX_BASE (head the final review saw): `05c01c7`.

Wrote `final-fix-wave-brief.md` covering all 6 in-scope items (#1 batch-flow
gate bypass, #2+#3 paired ranking-key fix, #4 banner/warning ordering, #5
off_shortfall integration test, #6 repair-budget exemption, #8 config
falsy-check audit) with exact current file/line context re-verified against
live source (not copied blindly from the review summary — line numbers
shifted slightly are re-confirmed). Dispatching one fix-wave implementer
per subagent-driven-development's Final Review section (one dispatch, one
scoped re-review, no second fix wave).

Implementer (agent a720b13d503dd2033) hit a server-side 529 twice (dropped
mid-report once, then stuck passively waiting on its own background test
run's completion with no way to be woken — resumed both times with the
same agent, no work lost). Final result: **DONE_WITH_CONCERNS**, 5 commits
covering all 6 items (`ad3430a` Items 1+4, `c34ae0d` Items 2+3, `34e8aa1`
Item 6, `d84fcb5` Item 8, `e103b8e` Item 5). Full report:
`final-fix-wave-report.md`. Full suite: 234 passed, 1 skipped, 1 xpassed,
0 failed across 236 (6 new tests added by this wave; skip+xpass are the
same pre-existing ones Task 6 documented) — bulk half run twice
independently for cross-confirmation, identical both times.

Adjudicating the 2 concerns now (controller, before dispatching re-review):
1. **Real, pre-existing, out-of-scope bug found, not fixed**:
   `batch_hdtn_thematic_week` (pages/06_Xep_TKB.py:538) is referenced but
   never assigned anywhere in the file (confirmed independently via grep —
   only the single-week `hdtn_thematic_week` checkbox exists, no `batch_`
   variant). This is a `NameError` that crashes the batch "🚀 Xếp các tuần
   đã chọn" button before it ever reaches Item 1's new gate code. Traced by
   the implementer via `git log -p` to commit `a143d89` (the unrelated
   "35-week teacher workload tracking" plan) — predates this branch
   entirely. **Ruling: park, do not fix.** Not one of the final review's 18
   findings, unrelated feature (a missing checkbox for a different
   concern, HDTN thematic-week toggle, not HĐSP hard-gate rules), and nothing
   in this plan depends on the batch button actually running today — Item
   1's fix is still correct and will activate correctly once that separate
   bug is fixed (independently confirmed by re-reading the diff: the new
   gate code mirrors the single-week block byte-for-byte in structure).
   Recommend as a follow-up ticket, not this plan's scope. Cost if wrong:
   Item 1 stays unverified live until that unrelated bug is fixed
   separately — low risk, since the diff-mirroring review is thorough and
   the pattern is proven correct in the single-week flow it copies.
2. **Item 8's hypothesized bug confirmed NOT reachable** via this codebase's
   actual `get_meta` contract (verified: returns `None` or the exact saved
   string, never normalizes to `""`; `bool("0") is True` so the old code
   already worked correctly for this specific input). Fixed anyway per the
   brief's explicit unconditional instruction (defensive hardening,
   consistent idiom). **Ruling: accept as documented** — not a defect, just
   a corrected hypothesis, transparently reported rather than silently
   dropped. No action needed.

Generated diff package `review-05c01c7..e103b8e.diff` (975 lines: log +
stat + full diff -U10) for the scoped re-review. Dispatched re-reviewer
(sonnet, per Model Selection's "cheap-to-mid tier" for scoped fix
re-reviews, sized up slightly given this diff spans 4 source files + 3
test files with real algorithmic changes, not a single mechanical edit).

**Re-review verdict: all 6 findings ADDRESSED, no new Critical/Important
breakage.** Re-reviewer independently verified against live source (not
the report's claims) for every item, including re-deriving `teacher_totals`
semantics for Item 6 against `placement.py`'s `_put_at`/`_remove_at` and
confirming no missed call sites for Item 2+3's return-type change. One
Minor, non-blocking, self-acknowledged-in-report note: `teacher_map` in the
single-week flow is now computed slightly earlier (for the moved
`relaxed_rules` block) and redundantly recomputed a few more times further
down — harmless (idempotent), not fixed, not worth a 6th round for a
no-op. Out-of-scope observation: re-confirmed the pre-existing
`batch_hdtn_thematic_week` NameError is unrelated to and unaffected by this
diff (fires before any new code runs) — same ruling as above stands.

**Fix wave: complete. No second fix wave needed — clean on first re-review.**

## Final Whole-Branch Status: READY with one caveat for the human partner

All 6 tasks complete + final whole-branch review's 6 in-scope findings
fixed and re-reviewed clean. Deferred (not blocking, ledgered for
visibility): Important #7 (redundant scan computation, perf-only),
Minors #9-18 (from the original final review), plus this fix wave's own
1 new Minor (teacher_map redundant recompute) and 1 pre-existing
out-of-scope bug (`batch_hdtn_thematic_week` NameError, predates this
branch, blocks live use of the batch-scheduling button entirely regardless
of this plan's work).

Moving to superpowers:finishing-a-development-branch next. Flagging for
that step: `main` has diverged since this worktree branched (merge-base
`a143d89`) — `main`'s current HEAD (`8f577b1`) added this plan's briefs/
ledger-stub, some xlsx fixtures, docs HTML exports, and PS scripts, but
**zero code changes** (confirmed: `git diff a143d89 8f577b1 --stat` touches
nothing under `core/`, `pages/`, `tests/`). A merge will need to reconcile
these on top of this branch's real code changes — not a code conflict, but
worth surfacing before choosing a merge strategy.
