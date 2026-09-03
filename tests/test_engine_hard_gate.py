from core.models import (
    ROLE_HDTN, ROLE_THUONG, ClassRoom, SchedulingConfig, SchedulingInput, Slot, Subject, Teacher, TimeSlot,
)
from core.scheduler import run
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

    violations, _total = _check_hard_post_generation_rules(inp, state, inp.config)
    assert violations == ["II.4"]


def test_check_hard_post_generation_rules_gates_ii8_split_day_again():
    """User decision 2026-09-03 (second revision, same day): II.8 (AM+PM split
    day) is back to hard-gate ("là bắt buộc") after being briefly demoted to
    soft earlier the same day. It shares II.4's min_weekly_periods_for_lone_penalty
    exemption (2026-09-02 fix-round ruling, unaffected by this back-and-forth):
    a teacher whose total weekly load is below the threshold must NOT be
    flagged for a split day, while the identical split-day pattern for a
    teacher at/above the threshold must be flagged."""
    def build(extra_slots):
        slots = []
        slot_id = 1
        for wd, sess, p in extra_slots:
            slots.append(Slot(slot_id, 101, TimeSlot(slot_id, wd, sess, p)))
            slot_id += 1
        inp = SchedulingInput(
            classes=[ClassRoom(101, "6A1")], subjects=[], teachers=[Teacher(1, "GV A")],
            need={}, assigned_teacher={}, ban_busy=set(), slots=slots, timeslots=[],
            config=SchedulingConfig(min_weekly_periods_for_lone_penalty=15),
        )
        state = _State(remaining_need={}, busy=set())
        for slot in slots:
            state.assigned[slot.slot_id] = 1
            state.slot_teacher[slot.slot_id] = 1
        return _check_hard_post_generation_rules(inp, state, inp.config)

    # Low load: just the split day itself (1 AM + 1 PM on weekday 3) = 2 total
    # periods, well under the 15-period threshold -> exempt from both II.4 and
    # II.8, no violations.
    low_load_split_day = [(3, "S", 1), (3, "C", 1)]
    low_violations, low_total = build(low_load_split_day)
    assert low_violations == []
    assert low_total == 0

    # High load: 5 full mornings of 3 periods each (wd 2,4,5,6,7; 3 not 4 periods
    # so II.14-shaped placement never matters here since II.14 isn't checked by
    # this gate) = 15, plus the same split day on weekday 3 = 17 total (>= 15) ->
    # II.8 must be flagged again (co-occurring with II.4 is expected/inherent: a
    # split day's "lone" side is by definition also a lone session).
    high_load_full_mornings = [
        (wd, "S", p) for wd in (2, 4, 5, 6, 7) for p in (1, 2, 3)
    ]
    high_load_split_day = high_load_full_mornings + [(3, "S", 1), (3, "C", 1)]
    violations, _total = build(high_load_split_day)
    assert "II.8" in violations


def test_check_hard_post_generation_rules_never_gates_ii3_missing_mandatory_morning():
    """User decision 2026-09-03: II.3 (missing mandatory-morning teaching presence)
    is demoted from hard-gate to soft. A teacher with a heavy load (>=10 periods,
    the _count_teacher_missing_mandatory_mornings threshold) and ZERO periods on
    any mandatory morning (wd 2, 5, 6) must previously have been flagged II.3;
    now it must never appear, and with no lone/split/consecutive-morning shape in
    this fixture, the gate must report fully compliant."""
    slots = []
    slot_id = 1
    # 12 periods on weekday 3 (not a mandatory morning) across 4 sessions of 3
    # each, spread over S/C so no session/day is ever lone and II.14 never
    # triggers (never >=4 consecutive AM periods in one day here).
    for wd, sess in ((3, "S"), (3, "C"), (4, "S"), (4, "C")):
        for p in (1, 2, 3):
            slots.append(Slot(slot_id, 101, TimeSlot(slot_id, wd, sess, p)))
            slot_id += 1
    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1")], subjects=[], teachers=[Teacher(1, "GV A")],
        need={}, assigned_teacher={}, ban_busy=set(), slots=slots, timeslots=[],
        config=SchedulingConfig(),
    )
    state = _State(remaining_need={}, busy=set())
    for slot in slots:
        state.assigned[slot.slot_id] = 1
        state.slot_teacher[slot.slot_id] = 1

    violations, total = _check_hard_post_generation_rules(inp, state, inp.config)
    assert violations == []
    assert total == 0


def test_check_hard_post_generation_rules_never_gates_ii14_four_consecutive_mornings():
    """User decision 2026-09-03: II.14 (4+ consecutive morning periods) is demoted
    from hard-gate to soft. A low-load teacher (<=20 periods, the
    _count_teacher_4_consecutive_mornings default max_load_for_penalty) with 4
    consecutive morning periods in one day must previously have been flagged
    II.14; now it must never appear."""
    slots = [Slot(i, 101, TimeSlot(i, 2, "S", p)) for i, p in enumerate((1, 2, 3, 4), start=1)]
    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1")], subjects=[], teachers=[Teacher(1, "GV A")],
        need={}, assigned_teacher={}, ban_busy=set(), slots=slots, timeslots=[],
        config=SchedulingConfig(),
    )
    state = _State(remaining_need={}, busy=set())
    for slot in slots:
        state.assigned[slot.slot_id] = 1
        state.slot_teacher[slot.slot_id] = 1

    violations, total = _check_hard_post_generation_rules(inp, state, inp.config)
    assert violations == []
    assert total == 0


def test_check_hard_post_generation_rules_empty_when_compliant():
    slots = [Slot(1, 101, TimeSlot(1, 2, "S", 1))]
    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1")], subjects=[], teachers=[Teacher(1, "GV A")],
        need={}, assigned_teacher={}, ban_busy=set(), slots=slots, timeslots=[],
        config=SchedulingConfig(),
    )
    state = _State(remaining_need={}, busy=set())
    # No assignments at all -> nothing to violate
    violations, total = _check_hard_post_generation_rules(inp, state, inp.config)
    assert violations == []
    assert total == 0


def test_check_hard_post_generation_rules_ranks_by_total_violation_count_not_distinct_rule_count():
    """Fix-wave Important #2/#3 (2026-09-03): the relaxed-candidate ranking key in
    engine.py must use the TOTAL violation-instance count, not len(violated_rule_ids)
    (the number of DISTINCT rule types violated). Reproduces the ledger's worked
    example with the real counters (not fabricated numbers): a candidate with 2
    isolated lone-session teacher-days (only II.4, 1 distinct rule, but 4 total
    violation instances -- each isolated lone morning session is BOTH a lone
    SESSION and a lone DAY by the counters' own definitions) must be ranked WORSE
    than a candidate with just 1 split day (II.4 + II.8, 2 distinct rules, but only
    3 total violation instances -- a split day's two 1-period sides each count once
    as a lone SESSION, but the day's own total is 2 so it does NOT also count as a
    lone DAY). Under the OLD buggy ranking key len(violated) -- (1, ...) for the
    first candidate vs (2, ...) for the second -- the first (objectively worse, 4
    raw violations) candidate would incorrectly win; under the FIXED key (total:
    4 vs 3), the second (objectively better, 3 raw violations) candidate correctly
    wins, regardless of it spanning more distinct rule types. (II.8 is hard-gated
    again as of the second 2026-09-03 revision, so this is back to its original
    two-distinct-rule form.)"""

    def build(extra_slots):
        slots = []
        slot_id = 1
        # 3 full mornings (wd 2, 5, 6 -- all 3 mandatory mornings covered, so II.3
        # never triggers) of 3 periods each (< 4, so II.14 never triggers either).
        for wd in (2, 5, 6):
            for p in (1, 2, 3):
                slots.append(Slot(slot_id, 101, TimeSlot(slot_id, wd, "S", p)))
                slot_id += 1
        for wd, sess, p in extra_slots:
            slots.append(Slot(slot_id, 101, TimeSlot(slot_id, wd, sess, p)))
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
        return _check_hard_post_generation_rules(inp, state, inp.config)

    # Candidate A: 2 isolated lone-session teacher-days (wd 3, wd 4 -- 1 period
    # each, no afternoon activity that day) + padding (wd2/wd5 afternoons, no
    # lone/split risk there since neither session's count == 1) to reach the
    # >=15-period exemption threshold. Only II.4 fires (1 distinct rule), but 4
    # total instances (2 lone sessions + 2 lone days).
    candidate_a_extra = [
        (2, "C", 1), (2, "C", 2), (2, "C", 3),   # padding, wd2 afternoon (S=3,C=3: no split)
        (5, "C", 1), (5, "C", 2),                 # padding, wd5 afternoon (S=3,C=2: no split)
        (3, "S", 1),                              # isolated lone session+day #1
        (4, "S", 1),                              # isolated lone session+day #2
    ]
    violations_a, total_a = build(candidate_a_extra)
    assert violations_a == ["II.4"]
    assert total_a == 4

    # Candidate B: 1 split day (wd 3: 1 AM + 1 PM) + the SAME padding as A. Both
    # II.4 and II.8 fire (2 distinct rules), but only 3 total instances (2 lone
    # sessions from the split day's two 1-period sides + 1 split; the day's own
    # total is 2, so it is NOT also counted as a lone day).
    candidate_b_extra = [
        (2, "C", 1), (2, "C", 2), (2, "C", 3),
        (5, "C", 1), (5, "C", 2),
        (3, "S", 1), (3, "C", 1),                 # split day
    ]
    violations_b, total_b = build(candidate_b_extra)
    assert set(violations_b) == {"II.4", "II.8"}
    assert total_b == 3

    # Sanity check: A spans fewer distinct rule types than B (this is exactly the
    # OLD ranking key -- len(violated) -- that used to decide "better").
    assert len(violations_a) < len(violations_b)

    # FIXED ranking: candidate B (fewer raw violations, 3) must rank strictly
    # better (lower total) than candidate A (more raw violations, 4), even though
    # B spans MORE distinct rule types (2) than A (1) -- the old len()-based key
    # got this backwards.
    assert total_b < total_a


def test_run_never_reports_off_slot_shortfall_into_relaxed_rules():
    """User decision 2026-09-03 (second revision, same day): the requirement
    that "each teacher gets exactly N off-slots/week" is dropped entirely --
    core/scheduler/teacher_off.py's shortfall detection still runs internally
    (unit-tested at the _assign_off_slots level in tests/test_teacher_off.py,
    unaffected), but core/scheduler/engine.py's run() must no longer surface
    it into ScheduleResult.relaxed_rules. This reverses fix-wave Important #5
    (2026-09-03, first revision), which added exactly this reporting because
    the original 2026-09-02 root-cause narrative wrongly attributed the user's
    "vẫn có người được nghỉ sáng T2" complaint to this mechanism (the final
    whole-branch review corrected that: the actual fix is II.3's mandatory-
    morning-teaching gate, unrelated to and untouched by this change).

    Same minimal fixture as before: a single class with ONE morning-only
    subject taught entirely by a "Hiệu trưởng" teacher (forbidden ALL mornings
    for OFF-SLOT purposes, per test_teacher_off.py's precedent) with
    teacher_off_sessions_per_week=5 -- reliably exceeds the 4 eligible
    afternoon off-cells left after FORBIDDEN_OFF_CELLS + the TPT/BGH
    exclusion, guaranteeing a shortfall occurs internally even though it must
    no longer be reported."""
    subj_toan = Subject(1, "Toan", ROLE_THUONG)
    subj_hdtn = Subject(2, "HDTN", ROLE_HDTN)  # required by resolve_roles; zero need, never scheduled
    subjects = [subj_toan, subj_hdtn]

    teacher = Teacher(1, "Hieu Truong", role="Hiệu trưởng")

    slots = []
    for slot_id, wd in enumerate((2, 3, 4, 5, 6), start=1):
        slots.append(Slot(slot_id, 101, TimeSlot(slot_id, wd, "S", 1)))
    timeslots = [s.ts for s in slots]

    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1")],
        subjects=subjects,
        teachers=[teacher],
        need={(1, 101): 5},
        assigned_teacher={(1, 101): 1},
        ban_busy=set(),
        slots=slots,
        timeslots=timeslots,
        seed=2026,
        config=SchedulingConfig(teacher_off_sessions_per_week=5),
    )

    result = run(inp)

    assert result.success is True, f"Schedule generation failed: {result.failure_reason}"

    shortfall_items = [
        item for item in result.relaxed_rules
        if item.get("detail") == "off_slot_shortfall"
    ]
    assert shortfall_items == [], f"off_slot_shortfall must never be reported anymore, got: {shortfall_items}"
