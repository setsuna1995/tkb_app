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


def test_check_hard_post_generation_rules_split_session_respects_lone_penalty_exemption():
    """II.8 (AM+PM split day) must share II.4's min_weekly_periods_for_lone_penalty
    exemption (fix-round ruling, 2026-09-02): a teacher whose total weekly load is
    below the threshold must NOT be flagged for a split day, while the identical
    split-day pattern for a teacher at/above the threshold must be flagged."""
    def build(extra_low_load_slots):
        slots = []
        slot_id = 1
        for wd, sess, p in extra_low_load_slots:
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
    # periods, well under the 15-period threshold -> fully exempt, no violations.
    low_load_split_day = [(3, "S", 1), (3, "C", 1)]
    assert build(low_load_split_day) == []

    # High load: 5 full mornings of 3 periods each (wd 2,4,5,6,7; all mandatory
    # mornings covered so II.3 doesn't trigger; 3 not 4 periods so II.14 doesn't
    # trigger) = 15, plus the same split day on weekday 3 = 17 total (>= 15) ->
    # the split day must now be flagged as II.8 (co-occurring with II.4 is
    # expected/inherent: a split day's "lone" side is by definition also a lone
    # session, see progress.md fix-round ruling).
    high_load_full_mornings = [
        (wd, "S", p) for wd in (2, 4, 5, 6, 7) for p in (1, 2, 3)
    ]
    high_load_split_day = high_load_full_mornings + [(3, "S", 1), (3, "C", 1)]
    violations = build(high_load_split_day)
    assert "II.8" in violations


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
