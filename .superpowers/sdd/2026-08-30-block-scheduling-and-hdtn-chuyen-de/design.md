# Design: Mandatory Block Scheduling, HDTN Thematic Week, Heavy-Subject Morning Constraint

Tóm tắt (Vietnamese summary): Spec này gộp 3 yêu cầu Kiên nêu ra trong buổi rà soát
ngày 2026-08-30: (1) môn "kép" phải thực sự ghép đôi liền kề thay vì chỉ được-phép-ghép
như hiện tại; (2) 1 cờ "tuần chuyên đề" áp dụng toàn trường, dồn cả 3 tiết HDTN thành
1 khối liền kề, bỏ ghim chào cờ/SHL tuần đó; (3) môn "Nặng" bị cấm cứng xếp vào buổi
chiều (nhưng môn không-Nặng KHÔNG bị cấm xếp sáng — chỉ là ưu tiên chiều khi còn chỗ).

- **Feature slug**: block-scheduling-and-hdtn-chuyen-de
- **Date**: 2026-08-30
- **Branch/Target**: main
- **Status**: DESIGN (awaiting spec review before writing-plans)

---

## 1. Background

Kiên tested the scheduler and reported two symptoms:

1. Afternoon sessions still contain heavy subjects (Toán, Anh, LS&ĐL) and mornings
   still contain light subjects (Nghệ thuật, HDTN, GDCD, Tin) — the opposite of what
   he wants.
2. Selecting subjects that "need 2 tiết kép liền kề" (double periods) via the
   per-week picker on `pages/06_Xep_TKB.py` does not produce paired results.

Root-cause investigation (see conversation) found:

- The morning/afternoon soft preference config (`heavy_subject_priority_periods`,
  `afternoon_preferred_subject_ids`) was never saved for this school — it defaults to
  off. Even when on, it is only a ±30-point soft nudge that the +1,000,000-point
  "keep old subject" bonus (`core/scheduler.py:270-271`) drowns out on any week that
  already has `tkb_nhap` data (this DB has 336 rows; `run_log` shows only 12-28% of
  cells change per run).
- The "kép" constraint (`role_index.kep_ids`, and the per-run `extra_kep_ids`) is
  *permissive* only: `_feasible()` allows up to 2 same-subject periods per day and
  requires the 2nd to be adjacent to the 1st IF a 2nd one happens to get placed, but
  nothing in the scorer favors completing a pair over leaving periods scattered as
  singles. Confirmed by `tests/test_scheduler.py:622-658`, which only asserts
  adjacency-if-paired, never asserts full pairing.
- Actual DB role_code data (`schools/truong-thcs.db`) only has Toán and Ngữ văn as
  Nặng+Kép (role_code=3); Ngoại ngữ is Nặng only (1); Vật lý/Hoá học/Sinh học/Lịch
  sử/Địa lý are Thường (0) — not matching the 7-subject kép list Kiên described.

Given this, Kiên decided (via the clarifying-question rounds captured in §12) to
escalate from "soft preference" to hard constraints, and added two more requirements
mid-conversation: an HDTN "thematic week" toggle, and a hard heavy-subject
morning-only rule.

---

## 2. Requirements

**R1 — Mandatory block pairing for "kép" subjects.**
For every (subject, class) where the subject requires a block size N ≥ 2 this run
(permanent role_code Kép/Nặng+Kép, or the existing "chỉ tuần này" picker), periods
must be grouped into contiguous same-session blocks of exactly N wherever the weekly
total allows it. When the weekly total isn't a multiple of N, at most one leftover
period may remain ungrouped (a single). This applies to all classes uniformly (kép
subjects are the same set for every class).

Kiên's own list of subjects intended to carry this (as permanent role_code, done by
Kiên himself in the Khai báo UI — no code change needed for the data half): Hoá học,
Vật lý, Sinh học, Toán học, Ngoại ngữ, Ngữ văn, Lịch sử, Địa lý → role_code = 3
(Nặng+Kép), matching Toán/Ngữ văn's current value.

**R2 — HDTN "tuần chuyên đề" (thematic week) toggle.**
A single whole-school, per-run boolean (not per-class). When on for a run:
- HDTN's weekly need (always 3 periods/week per class) becomes a mandatory
  block of size 3 (same session, 3 contiguous periods), same mechanism as R1
  generalized to N=3.
- The existing hard pins for chào cờ (Monday period 1) and SHL (last morning period
  Friday/Saturday) are skipped entirely for that run — HDTN is placed freely by the
  general block-aware greedy fill like any other block-subject.

**R3 — Heavy subjects morning-only (one-directional hard constraint).**
Subjects in `role_index.heavy_ids` (role_code Nặng or Nặng+Kép) may never be placed
in an afternoon ("C") slot — hard rejection in `_feasible`. Non-heavy subjects are
NOT banned from morning slots; they simply are not specially constrained (the
existing soft afternoon-preference mechanism, if configured, continues to nudge them
toward afternoon when morning is contested). Chào cờ and SHL (both HDTN, non-heavy)
remain their existing fixed morning slots as an explicit exception in a normal week;
in an R2 thematic week those pins don't exist, so this exception doesn't need special
handling — see §8.

---

## 3. Current architecture (files/lines this design touches)

- `core/models.py` — `RoleIndex`, `SchedulingConfig`, `SchedulingInput`.
- `core/roles.py` — `resolve_roles()`.
- `core/scheduler.py` — `_feasible()`, `_pick_best_scored()`, `_put_at`/`_remove_at`,
  the chào cờ pin block (`run():514-525`), the SHL reservation blocks
  (`run():429-453, 527-539, 570-587`), `_repair_lone_periods`/`_has_lone_period`
  (pattern to mirror for the new kép-repair/validation).
- `data/repository.py` — `build_scheduling_input()`, `get_scheduling_config()` /
  `set_scheduling_config()`.
- `pages/06_Xep_TKB.py` — per-run pickers (extra_kep_ids already here; R2's toggle
  goes here too).
- `pages/10_Cau_hinh_Xep_lich.py` — permanent config (R3's toggle goes here).

---

## 4. Data findings that shape this design (see conversation for full detail)

- Across all 8 classes × both parities, weekly period totals split into heavy total
  = 18 and non-heavy total = 11, against morning capacity 20 and afternoon capacity
  9 (computed via `frame_mod.active_cells`). This is **exact-fit, zero slack** once
  chào cờ+SHL (2 of the 11 non-heavy periods) are treated as morning exceptions.
  Confirms R3 must stay one-directional (non-heavy not banned from morning) —
  bidirectional would make the schedule provably infeasible in thematic weeks (see
  §12 decision log).
- 52 of 128 (subject, class, parity) combinations for the 7 kép subjects have an odd
  weekly count; Ngoại ngữ is odd (3) in every single one of its 16 combinations.
  Confirms R1 must allow exactly one leftover single, never demand 100% pairing.

---

## 5. Design

### 5.1 Unified "N-period contiguous block" mechanism

R1 and R2 are the same underlying constraint at different N and different scope
(R1: N=2, all classes, subject-driven; R2: N=3, all classes, single subject HDTN,
gated by a run-level toggle). Model both through one generalization instead of two
parallel code paths.

`RoleIndex` gains a new field:

```python
block_size: dict[int, int] = field(default_factory=dict)  # subject_id -> N (>=2); absent = no block requirement
```

`resolve_roles(subjects, extra_kep_ids, hdtn_thematic_week=False)`:
- For every subject_id currently landing in `kep_ids` (role_code Kép/Nặng+Kép, union
  `extra_kep_ids`), also set `block_size[subject_id] = 2`.
- If `hdtn_thematic_week` is True, set `block_size[hdtn_id] = 3` (overrides any
  accidental 2 from `extra_kep_ids` — see §8 for why HDTN should also be dropped from
  the extra_kep_ids picker options).
- `kep_ids` stays as-is for any caller that only needs "is this a block subject"
  (existing tests keep passing); `block_size` is the new source of truth for N.

### 5.2 `_feasible()` generalization (replaces the current kep cap/adjacency block)

Current code (`core/scheduler.py:115-122`):
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

Generalized:
```python
positions = state.placed[(class_id, subject_id, ts.weekday)]
cap_d = role_index.block_size.get(subject_id, 1)
if len(positions) >= cap_d:
    return False
if positions:
    sessions = {p[0] for p in positions}
    if sessions != {ts.session}:
        return False
    periods = sorted(p[1] for p in positions)
    if ts.period not in (periods[0] - 1, periods[-1] + 1):
        return False
```
(Same session check now handles N>2 explicitly instead of relying on cap_d==2 to make
a single stored position sufficient; new period must extend either end of the
existing contiguous run.)

### 5.3 R3 — heavy-afternoon hard rejection

One new line in `_feasible()`, gated by a new config flag (see §6):951
```python
if config.heavy_subjects_morning_only and subject_id in role_index.heavy_ids and ts.session == "C":
    return False
```

### 5.4 Mandatory pairing: scoring + repair + validation

- **Scoring**: add `BLOCK_COMPLETE_BONUS` (same order of magnitude as
  `IDLE_DAY_BONUS`/`HEAVY_MORNING_BONUS`, e.g. 40) in `_pick_best_scored` when the
  candidate subject already has 1+ contiguous periods placed today (i.e. picking it
  again continues/completes the block). This is an efficiency nudge only —
  correctness comes from the validation+retry step below, not from this bonus.
- **Repair pass** `_repair_unpaired_blocks()` (new function, run after
  `_repair_lone_periods` in `run()`): for each (class, subject) with
  `block_size.get(subject_id, 1) >= 2`, collect weekdays where the subject's placed
  count is >0 but <N ("partial" days). If the number of partial days exceeds the
  allowed remainder (`need % N`, 0 or the leftover count), try to merge two partial
  days into one full block:
  - Remove the subject's period(s) from the shorter/lower-priority partial day.
  - Try to place them adjacent to the other partial day's existing run (mirrors
    `_try_swap_repair`: if the target adjacent slot is occupied by a different
    subject, remove that occupant first, check feasibility, place, then try to
    refill the displaced occupant elsewhere via `_pick_best_simple`; roll back the
    whole attempt if any step fails).
  - If a day's slot(s) end up freed and unfillable, leave them `-1` (intentionally
    empty) exactly like the existing lone-period repair does, when there's slack;
    otherwise the attempt fails at the validation step below and best-of-N retries.
- **Validation** `_has_unpaired_block(inp, state, role_index)` (mirrors
  `_has_lone_period`): for each (class, subject) with block_size ≥ 2, count partial
  days; if that count exceeds the allowed remainder, return True. `run()` treats this
  exactly like `_has_lone_period` — sets `done = False` and lets the existing
  best-of-N attempt loop (up to `SO_LAN_THU` = 6000) try a different random order.

**Addendum (post-implementation finding, still 2026-08-30):** the above
(scoring + post-hoc repair + reject/retry) was implemented exactly as specified
and unit-tested clean, but running it against the real `sample_school.xlsm`
fixture — 16 simultaneous (subject, class) kép combinations, all with an even
weekly count (zero tolerance for a leftover single, everywhere at once) —
produced a **deterministic 0/6000 success rate** (confirmed 0/4000 and 0/300 in
extended repro). Root cause: post-hoc repair can only re-shuffle periods that
are *already* placed; by the time it runs, the greedy fill has often already
scattered too many kép subjects as singles with no adjacent slack cell left to
consolidate into. This is a scale limitation of the repair-based design, not an
implementation bug — see `.superpowers/sdd/2026-08-30-block-scheduling-and-hdtn-chuyen-de-plan/task-4-report.md`
for the full investigation.

Presented with this, Kiên chose to keep R1's 100%-hard requirement rather than
loosen it (see §12). The fix, added on top of the above rather than replacing
it: **`_try_place_block_atomically()`**, tried immediately before
`_pick_best_scored` for every empty slot in `run()`'s main loop. For a subject
that could start a *fresh* N-period block at this exact slot (enough
`remaining_need` for a full block — not just the eventual single leftover — and
no placement yet today), it atomically claims the whole forward window (this
slot plus the next N-1) only if every slot in it is currently free and
individually `_feasible`; otherwise it fully rolls back and falls through to
the unchanged single-slot path. This prevents a block from ever being *started*
unless it can be *completed* in the same action — the guarantee post-hoc repair
could not provide — while leaving `_repair_unpaired_blocks`/`_has_unpaired_block`
in place as a backstop for whatever a still-competing block subject or
constraint interaction leaves behind. See the implementation notes in the
plan's Task 4 (`.superpowers/sdd/2026-08-30-block-scheduling-and-hdtn-chuyen-de-plan/2026-08-30-block-scheduling-and-hdtn-chuyen-de-plan.md`)
and its ledger for the exact code and the controller's ruling.

### 5.5 R2 — skipping chào cờ/SHL pins for a thematic week

In `run()`, wrap the chào cờ pin block (`514-525`) and the entire SHL
reservation/placement machinery (`429-453`, `527-539`, `570-587`) in
`if not inp.hdtn_thematic_week: ...` (`inp` is the `SchedulingInput`, per §6 — this
is a per-run field, not part of `SchedulingConfig`). `role_index` must also be built
via `resolve_roles(inp.subjects, inp.extra_kep_ids, inp.hdtn_thematic_week)` instead
of today's 2-argument call (`run():418`) so `block_size[hdtn_id]` gets set. When
chào cờ/SHL are skipped, HDTN's 3 periods flow through the general greedy loop like
any other block_size-aware subject, using the same repair/validation as R1.

---

## 6. Data model changes

`core/models.py`:
```python
@dataclass
class RoleIndex:
    heavy_ids: set = field(default_factory=set)
    kep_ids: set = field(default_factory=set)
    block_size: dict = field(default_factory=dict)   # NEW — subject_id -> N (R1 §5.1)
    gdtc_id: Optional[int] = None
    hdtn_id: Optional[int] = None
```

```python
@dataclass
class SchedulingConfig:
    ...
    heavy_subjects_morning_only: bool = False   # NEW — R3, default off (behavior-preserving)
```

`SchedulingInput` gains one new per-run field (parallel to `extra_kep_ids`, not a
permanent config — it's a per-run toggle exactly like the existing kép picker):
```python
hdtn_thematic_week: bool = False   # NEW — R2, "chỉ tuần này"
```

`core/roles.py`: `resolve_roles(subjects, extra_kep_ids=frozenset(), hdtn_thematic_week=False)`
as described in §5.1.

`data/repository.py`:
- `get_scheduling_config`/`set_scheduling_config`: add `sched_heavy_subjects_morning_only`
  meta key, same pattern as the other booleans/ints already there.
- `build_scheduling_input(conn, parity, seed, extra_kep_ids, hdtn_thematic_week=False)`:
  thread the new parameter to `SchedulingInput`.

---

## 7. UI changes

`pages/10_Cau_hinh_Xep_lich.py` (permanent, school-level — R3): one new checkbox
near "Ngưỡng số lượng", e.g. "Môn Nặng: bắt buộc xếp buổi sáng (không được xếp
chiều)", default off (unchanged behavior until Kiên opts in).

`pages/01_Khai_bao.py`: no code change — Kiên updates role_code for the 6 subjects
himself via the existing "Vai trò" dropdown (already offers "Nặng+Kép").

`pages/06_Xep_TKB.py` (per-run — R2): one new checkbox next to the existing
"Môn cần xếp 2 tiết liền kề (kép) CHỈ cho tuần này" multiselect: "Tuần này tổ chức
chuyên đề (HDTN dồn 3 tiết liền kề toàn trường, bỏ ghim chào cờ + SHL)". Also fixes
a pre-existing latent quirk while touching this file: `extra_kep_options` currently
includes HDTN as a selectable option (`role_code not in (ROLE_KEP, ROLE_NANG_KEP)`
doesn't exclude `ROLE_HDTN`) — exclude `role_index.hdtn_id`/`ROLE_HDTN` explicitly
now that HDTN has its own dedicated toggle, to avoid undefined double-booking of
block_size for the same subject_id.

---

## 8. Interactions & edge cases

- **R2 × R3 in a thematic week**: with chào cờ/SHL pins off, HDTN (non-heavy) has no
  morning exception left — but R3 is one-directional (§2), so this is not a
  conflict: HDTN's 3-block can land in either session depending on where the greedy
  fill finds room (morning has 2 slack slots in the normal-week arithmetic once
  chào cờ/SHL stop consuming them; afternoon also has room since those 2 periods are
  no longer double-counted into the 11-non-heavy afternoon bucket). No infeasibility
  by construction — this was the reason R3 was pinned down as one-directional in
  §12's second decision.
- **R1 × R3**: heavy+kép subjects (Toán, Văn, Anh, Lý, Hoá, Sinh, Sử, Địa after
  Kiên's role_code update) must place their 2-blocks in morning sessions only (R3
  hard rule applies per-period, so both periods of a pair are already same-session
  by the block mechanism — no extra interaction needed).
- **extra_kep_ids including HDTN**: fixed by the UI change in §7 (exclude HDTN from
  that picker now that R2 owns HDTN's block requirement).
- **Odd remainders**: R1's "≤1 leftover single" already covers HDTN too when R2 is
  off (need=3, block_size defaults to 1 in that case — unaffected, current
  chào cờ/SHL/chủ đề-day behavior unchanged when the thematic toggle is off).

---

## 9. Out of scope / Non-goals

- No change to `subject_class_allowed_cells` (per-subject/class slot-allowlist
  feature) — R1/R2/R3 must simply compose with it as an existing hard constraint;
  if a school's allowlist rule doesn't leave room for a block or for heavy-morning,
  that's an existing "rule too strict" failure mode, not something this design needs
  to special-case.
- No per-class thematic week (confirmed whole-school only, §12).
- No change to the existing soft `heavy_subject_priority_periods` /
  `afternoon_preferred_subject_ids` mechanism — R3 is additive (a new hard
  toggle), not a replacement. A school can enable R3 and leave the soft prefs off,
  or use both together.
- No UI for viewing/debugging why a given attempt failed block validation — same
  level of diagnostics as today (`FAILURE_MESSAGE`), extended with a 6th bullet
  point per §11.

---

## 10. Risks

- **Attempt count / outright failure risk**: R1+R2+R3 together are meaningfully
  more constrained than today. `SO_LAN_THU` (6000) may need raising, or schools with
  tight data (e.g. many classes doing R2 simultaneously — moot now since R2 is
  whole-school only, but combined with R1's block competition for limited
  same-session adjacent slots) may see `success=False` more often than before. This
  is the explicitly-accepted trade-off from §12. **Materialized and resolved**:
  this risk was not hypothetical — it produced a deterministic 0/6000 failure on
  the real school fixture (16 simultaneous zero-tolerance kép constraints). Fixed
  by adding `_try_place_block_atomically()` (§5.4 addendum) rather than by raising
  `SO_LAN_THU`, since the failure was structural (0 successes across thousands of
  attempts), not merely rare.
- **Repair complexity**: `_repair_unpaired_blocks()` (§5.4) is the most complex new
  code in this file — a cascading remove/place/refill/rollback chain. Needs thorough
  unit coverage (§11) before trusting it in the full run loop. It turned out to be
  necessary but insufficient alone — see the §5.4 addendum; it now serves as a
  backstop behind `_try_place_block_atomically()`, which does most of the real work.
- **role_code data step is manual**: R1 depends on Kiên updating 6 subjects'
  role_code himself; until he does, R1's mechanism will simply have nothing to act
  on for those subjects (safe no-op, not a bug).

---

## 11. Testing plan

- `core/roles.py`: unit tests for `resolve_roles()`'s new `block_size` output
  (kép→2, extra_kep_ids→2, hdtn_thematic_week→3, HDTN excluded from kép picker
  path).
- `core/scheduler.py` `_feasible()`: table-style tests for block_size N=2 and N=3
  (extend-either-end-of-run logic), and for the new R3 heavy-afternoon rejection
  (both `heavy_subjects_morning_only` on and off, to prove the flag is
  behavior-preserving when off).
- `_repair_unpaired_blocks()` / `_has_unpaired_block()`: unit tests mirroring the
  existing `_repair_lone_periods`/`_has_lone_period` test style — construct a state
  with 2 partial days for the same subject, assert repair merges them; construct an
  unrepairable case, assert validation flags it.
- Full-run regression test using a fixture shaped like the real data found in §4:
  odd weekly counts (an Ngoại-ngữ-like 3/week subject), a thematic-week run, and
  `heavy_subjects_morning_only=True`, asserting: heavy subjects never appear in a
  "C" session slot; kép subjects' placements are all full blocks except ≤1 single;
  HDTN's 3 periods form one contiguous run when thematic week is on.
- Full test suite (`pytest`) must stay green; specifically confirm
  `test_extra_kep_ids_forces_adjacency_in_full_run` and
  `test_full_run_succeeds_with_both_soft_subject_preferences_enabled` still pass
  unchanged (regression guard for existing soft-preference behavior).

---

## 12. Decision log (from clarifying-question rounds this session)

1. **HDTN's "3 tiết kép liền kề"** — initially ambiguous against the fixed chào
   cờ/SHL architecture. Resolved: not a permanent architecture change; it's the R2
   per-run thematic-week toggle, whole-school (not per-class).
2. **Kép enforcement strength** — chose "ép cứng bắt buộc" (mandatory) over keeping
   it soft/permissive.
3. **Odd-count handling for kép** — chose "pair maximally, allow exactly 1 leftover
   single" over "100% mandatory" (which would make Ngoại ngữ unschedulable every
   week, every class — proven via §4's data) or dropping Ngoại ngữ from the kép list.
4. **role_code update for the 6 missing subjects** — Kiên does this himself via the
   existing Khai báo UI; confirmed no code change needed for that half.
5. **Approach for kép enforcement** — chose the more complex "dồn ghép" active-repair
   approach (§5.4) over a spike-first validate-only/no-repair approach, accepting
   more implementation risk for a higher expected solve rate.
6. **Heavy-morning/light-afternoon** — escalated from existing soft preference to a
   hard rule (R3).
7. **Chào cờ/SHL exception under R3** — confirmed they stay morning exceptions in a
   normal week (not forced afternoon), consistent with the existing fixed
   architecture.
8. **R3 directionality** — confirmed one-directional (heavy banned from afternoon;
   non-heavy NOT banned from morning) after showing that the bidirectional reading
   makes R2's thematic week provably infeasible (§4's exact-fit capacity numbers).
9. **Repair-based R1 hit a real wall on real data** (0/6000 success on the actual
   school fixture, §5.4 addendum) — offered loosen-R1 / invest-in-a-stronger-
   algorithm / revert-to-soft as options; Kiên chose to invest in a stronger
   algorithm and keep the 100%-hard requirement. Resulted in
   `_try_place_block_atomically()` (§5.4 addendum).
