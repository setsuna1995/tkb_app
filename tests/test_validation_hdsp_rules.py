from core.models import Slot, TimeSlot
from core.validation import (
    find_teacher_4_consecutive_morning_violations, find_teacher_lone_day_violations,
    find_teacher_lone_session_violations, find_teacher_missing_mandatory_morning_violations,
    find_teacher_split_day_violations,
)


def _slots_for(weekday_period_pairs, class_id=101, session="S"):
    return [Slot(i + 1, class_id, TimeSlot(i + 1, wd, session, p)) for i, (wd, p) in enumerate(weekday_period_pairs)]


def test_find_teacher_missing_mandatory_morning_violations():
    # Teacher 1 has 12 periods total but zero on Thursday (wd=5) morning.
    pairs = [(2, p) for p in range(1, 5)] + [(4, p) for p in range(1, 5)] + [(6, p) for p in range(1, 5)]
    slots = _slots_for(pairs)
    assignment = {s.slot_id: 1 for s in slots}
    assigned_teacher = {(1, 101): 1}
    violations = find_teacher_missing_mandatory_morning_violations(slots, assignment, assigned_teacher)
    assert (1, 5) in violations


def test_find_teacher_lone_session_violations_exempts_low_load():
    # Teacher 1: single lone session, but total load (1) < default threshold (15) -> exempt.
    slots = _slots_for([(2, 1)])
    assignment = {s.slot_id: 1 for s in slots}
    assigned_teacher = {(1, 101): 1}
    assert find_teacher_lone_session_violations(slots, assignment, assigned_teacher, min_weekly_periods=15) == []
    assert find_teacher_lone_session_violations(slots, assignment, assigned_teacher, min_weekly_periods=0) == [(1, 2, "S")]


def test_find_teacher_lone_day_violations():
    slots = _slots_for([(2, 1)])
    assignment = {s.slot_id: 1 for s in slots}
    assigned_teacher = {(1, 101): 1}
    assert find_teacher_lone_day_violations(slots, assignment, assigned_teacher, min_weekly_periods=0) == [(1, 2)]


def test_find_teacher_split_day_violations_exempts_low_load():
    # Teacher 1: split day (1 AM + 1 PM), but total load (2) < default threshold (15) -> exempt.
    slots = _slots_for([(2, 1)], session="S") + _slots_for([(2, 2)], session="C")
    for i, s in enumerate(slots):
        s.slot_id = i + 1
    assignment = {s.slot_id: 1 for s in slots}
    assigned_teacher = {(1, 101): 1}
    assert find_teacher_split_day_violations(slots, assignment, assigned_teacher, min_weekly_periods=15) == []
    assert find_teacher_split_day_violations(slots, assignment, assigned_teacher, min_weekly_periods=0) == [(1, 2)]


def test_find_teacher_split_day_violations_catches_asymmetric_split():
    # Teacher 1: 1 AM period + 3 PM periods on the same day (still a "split day" per
    # II.8's actual definition -- one session is a lone period while the other also
    # has periods -- NOT limited to the exact 1-AM-and-1-PM case).
    am_slots = _slots_for([(2, 1)], session="S")
    pm_slots = [Slot(90 + i, 101, TimeSlot(90 + i, 2, "C", p)) for i, p in enumerate((1, 2, 3))]
    slots = am_slots + pm_slots
    for i, s in enumerate(slots):
        s.slot_id = i + 1
    assignment = {s.slot_id: 1 for s in slots}
    assigned_teacher = {(1, 101): 1}
    # 4 total periods, still below default 15 -> exempt by default
    assert find_teacher_split_day_violations(slots, assignment, assigned_teacher, min_weekly_periods=15) == []
    # With the exemption disabled, the asymmetric split must be caught
    assert find_teacher_split_day_violations(slots, assignment, assigned_teacher, min_weekly_periods=0) == [(1, 2)]


def test_find_teacher_lone_session_violations_honors_exempt_teacher_ids():
    # Teacher 1: lone session, load (1) already above min_weekly_periods=0, so it
    # would be flagged -- UNLESS the teacher is on the config's exempt list, mirroring
    # how CP-SAT/engine.py/quality.py all skip exempted teachers for II.4/II.8
    # (2026-09-05 root-cause fix: this function used to silently ignore the exempt
    # list, disagreeing with the solver's own "no violation" verdict).
    slots = _slots_for([(2, 1)])
    assignment = {s.slot_id: 1 for s in slots}
    assigned_teacher = {(1, 101): 1}
    assert find_teacher_lone_session_violations(slots, assignment, assigned_teacher, min_weekly_periods=0) == [(1, 2, "S")]
    assert find_teacher_lone_session_violations(
        slots, assignment, assigned_teacher, min_weekly_periods=0, exempt_teacher_ids=frozenset({1})
    ) == []


def test_find_teacher_lone_day_violations_honors_exempt_teacher_ids():
    slots = _slots_for([(2, 1)])
    assignment = {s.slot_id: 1 for s in slots}
    assigned_teacher = {(1, 101): 1}
    assert find_teacher_lone_day_violations(slots, assignment, assigned_teacher, min_weekly_periods=0) == [(1, 2)]
    assert find_teacher_lone_day_violations(
        slots, assignment, assigned_teacher, min_weekly_periods=0, exempt_teacher_ids=frozenset({1})
    ) == []


def test_find_teacher_split_day_violations_honors_exempt_teacher_ids():
    slots = _slots_for([(2, 1)], session="S") + _slots_for([(2, 2)], session="C")
    for i, s in enumerate(slots):
        s.slot_id = i + 1
    assignment = {s.slot_id: 1 for s in slots}
    assigned_teacher = {(1, 101): 1}
    assert find_teacher_split_day_violations(slots, assignment, assigned_teacher, min_weekly_periods=0) == [(1, 2)]
    assert find_teacher_split_day_violations(
        slots, assignment, assigned_teacher, min_weekly_periods=0, exempt_teacher_ids=frozenset({1})
    ) == []


def test_find_teacher_4_consecutive_morning_violations():
    pairs = [(2, p) for p in range(1, 5)]  # 4 periods on one morning, total load = 4 (<=20)
    slots = _slots_for(pairs)
    assignment = {s.slot_id: 1 for s in slots}
    assigned_teacher = {(1, 101): 1}
    assert find_teacher_4_consecutive_morning_violations(slots, assignment, assigned_teacher, max_load_for_penalty=20) == [(1, 2)]
    assert find_teacher_4_consecutive_morning_violations(slots, assignment, assigned_teacher, max_load_for_penalty=2) == []
