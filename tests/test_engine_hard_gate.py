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


def test_check_hard_post_generation_rules_never_gates_ii8_split_day():
    """User decision 2026-09-03: II.8 (AM+PM split day) is demoted from hard-gate
    to soft -- it never blocks save or rejects an attempt, regardless of teacher
    load. It stays fully scored via quality.py's soft penalty (unaffected by this
    change), so the engine still tries to avoid it when possible; this test only
    proves the post-generation REJECT gate no longer includes it. A split day's
    1-period side is inherently also a lone SESSION, so a high-load split day
    still surfaces as II.4 -- just never as II.8."""
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
    # periods, well under the 15-period threshold -> exempt from II.4 too, no violations.
    low_load_split_day = [(3, "S", 1), (3, "C", 1)]
    low_violations, low_total = build(low_load_split_day)
    assert low_violations == []
    assert low_total == 0

    # High load: 5 full mornings of 3 periods each (wd 2,4,5,6,7; all mandatory
    # mornings covered so II.3 would never have triggered anyway; 3 not 4 periods
    # so II.14 would never have triggered anyway) = 15, plus the same split day on
    # weekday 3 = 17 total (>= 15) -> II.8 must NEVER appear (demoted to soft), but
    # II.4 must still catch it (the split day's two 1-period sides are each a lone
    # session in their own right).
    high_load_full_mornings = [
        (wd, "S", p) for wd in (2, 4, 5, 6, 7) for p in (1, 2, 3)
    ]
    high_load_split_day = high_load_full_mornings + [(3, "S", 1), (3, "C", 1)]
    violations, _total = build(high_load_split_day)
    assert "II.8" not in violations
    assert violations == ["II.4"]


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
    (the number of DISTINCT rule types violated). Originally reproduced using II.4
    co-occurring with II.8; since II.8 was demoted to soft (2026-09-03 user
    decision), only II.4 can ever appear in `violated` now -- which makes
    len(violated) permanently stuck at 0 or 1, unable to distinguish severity AT
    ALL between "1 lone session" and "4 lone sessions/days". This is exactly why
    `total` (not `len(violated)`) must be the ranking key going forward: candidate
    A has 4 raw II.4 instances (2 isolated lone session+day pairs), candidate B
    has only 2 (a single split day, whose two 1-period sides each count once as a
    lone SESSION but not as a lone DAY, since the day's own total is 2). Under the
    OLD buggy key, both tie at len(['II.4'])==1 and the ranking would silently
    fall through to teacher_penalty/cells_changed, blind to A being objectively
    worse; under the FIXED key (total: 4 vs 2), B correctly ranks better."""

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

    # Candidate B: 1 split day (wd 3: 1 AM + 1 PM) + the SAME padding as A. Only
    # II.4 fires (II.8 is soft, never checked here), with 2 total instances (the
    # split day's two 1-period sides, each a lone SESSION; the day's own total is
    # 2, so it is NOT also counted as a lone day).
    candidate_b_extra = [
        (2, "C", 1), (2, "C", 2), (2, "C", 3),
        (5, "C", 1), (5, "C", 2),
        (3, "S", 1), (3, "C", 1),                 # split day (II.8 no longer checked)
    ]
    violations_b, total_b = build(candidate_b_extra)
    assert violations_b == ["II.4"]
    assert total_b == 2

    # Sanity check: with II.8 demoted to soft, both candidates span the SAME
    # single distinct rule -- len(violated) is now permanently blind to the real
    # difference between them (this is exactly why it must not be the ranking key).
    assert len(violations_a) == len(violations_b) == 1

    # FIXED ranking: candidate B (fewer raw violations, 2) must rank strictly
    # better (lower total) than candidate A (more raw violations, 4) -- a
    # distinction len(violated) can no longer make on its own.
    assert total_b < total_a


def test_run_surfaces_off_slot_shortfall_into_relaxed_rules_end_to_end():
    """Fix-wave Important #5 (2026-09-03): core/scheduler/teacher_off.py's
    shortfall detection has unit coverage at the _assign_off_slots level
    (tests/test_teacher_off.py), but nothing exercised core/scheduler/engine.py's
    run() actually surfacing a shortfall into ScheduleResult.relaxed_rules
    end-to-end -- i.e. that the wiring at engine.py's
    relaxed_rules.append({"rule_id": "II.3", "detail": "off_slot_shortfall", ...})
    (both the full-success and relaxed-fallback return paths) actually fires when
    a real run() call produces a shortfall.

    Minimal fixture: a single class with ONE morning-only subject taught entirely
    by a "Hiệu trưởng" teacher (forbidden ALL mornings for OFF-SLOT purposes, per
    test_teacher_off.py's precedent -- this is unrelated to whether they can teach
    mornings, which they still can) with teacher_off_sessions_per_week=5 -- the
    same off_slot_count that test_teacher_off.py's own shortfall test uses to
    reliably exceed the 4 eligible afternoon off-cells left after
    FORBIDDEN_OFF_CELLS + the TPT/BGH exclusion. Because all of this teacher's
    actual teaching slots are morning-only, their off-slot cells (afternoon-only)
    never collide with placement, and their total teaching load (5 periods/week)
    sits under min_weekly_periods_for_lone_penalty's default 15-period threshold,
    so the fixture also can't trip any *other* hard-gate rule and mask the
    assertion -- the only relaxed_rules entry possible here is the off_shortfall
    one, whichever of run()'s two success return paths gets taken."""
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
        if item.get("rule_id") == "II.3" and item.get("detail") == "off_slot_shortfall"
    ]
    assert len(shortfall_items) == 1, f"Expected exactly 1 off_slot_shortfall entry, got {result.relaxed_rules}"

    teachers_short = shortfall_items[0]["teachers"]
    assert 1 in teachers_short
    assigned_count, required_count = teachers_short[1]
    assert assigned_count < required_count
