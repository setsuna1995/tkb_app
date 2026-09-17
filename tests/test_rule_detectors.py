from dataclasses import replace

from core.models import SchedulingConfig, Slot, Teacher, TimeSlot
from core.rules.detectors import (
    detect_teacher_4_consecutive_mornings, detect_teacher_busy, detect_teacher_conflicts,
    detect_teacher_day_cap, detect_teacher_gaps, detect_teacher_lone_days, detect_teacher_lone_sessions,
    detect_teacher_missing_mandatory_mornings, detect_teacher_split_days,
)
from tests.rule_helpers import pick, view_and_params

NO_LONE_THRESHOLD = SchedulingConfig(min_weekly_periods_for_lone_penalty=0)
TWELVE_PERIODS_MISSING_THURSDAY = [(2, p) for p in range(1, 5)] + [(4, p) for p in range(1, 5)] + [(6, p) for p in range(1, 5)]


def _slot(slot_id, weekday, session, period, class_id=101):
    return Slot(slot_id, class_id, TimeSlot(slot_id, weekday, session, period))


def _morning_slots(weekday_period_pairs):
    return [_slot(i + 1, wd, "S", p) for i, (wd, p) in enumerate(weekday_period_pairs)]


def _split_day_slots():
    return [_slot(1, 2, "S", 1), _slot(2, 2, "C", 2)]


def _teacher_1(slots, config=None, **input_kwargs):
    """Teacher 1 teaches subject 1 in class 101 in every given slot."""
    return view_and_params(slots, {s.slot_id: 1 for s in slots},
                           assigned_teacher={(1, 101): 1}, config=config, **input_kwargs)


# --- II.3 ---

def test_missing_mandatory_morning():
    view, params = _teacher_1(_morning_slots(TWELVE_PERIODS_MISSING_THURSDAY))
    assert (1, 5) in pick(detect_teacher_missing_mandatory_mornings(view, params), "teacher_id", "weekday")


def test_missing_mandatory_morning_honours_pinned_full_day_off():
    view, params = _teacher_1(_morning_slots(TWELVE_PERIODS_MISSING_THURSDAY),
                              teachers=[Teacher(1, "GV 1", pinned_full_day_off=5)])
    assert (1, 5) not in pick(detect_teacher_missing_mandatory_mornings(view, params), "teacher_id", "weekday")


def test_missing_mandatory_morning_excuses_teacher_busy_that_morning():
    taught = _morning_slots(TWELVE_PERIODS_MISSING_THURSDAY)
    thursday = [_slot(101, 5, "S", 1), _slot(102, 5, "S", 2)]
    view, params = view_and_params(taught + thursday, {s.slot_id: 1 for s in taught},
                                   assigned_teacher={(1, 101): 1}, ban_busy={(1, 101), (1, 102)})
    assert (1, 5) not in pick(detect_teacher_missing_mandatory_mornings(view, params), "teacher_id", "weekday")


# --- II.4 / II.8 ---

def test_lone_session_respects_load_threshold():
    slots = _morning_slots([(2, 1)])
    assert detect_teacher_lone_sessions(*_teacher_1(slots, SchedulingConfig(min_weekly_periods_for_lone_penalty=15))) == []
    assert pick(detect_teacher_lone_sessions(*_teacher_1(slots, NO_LONE_THRESHOLD)),
                "teacher_id", "weekday", "session") == [(1, 2, "S")]


def test_lone_day():
    violations = detect_teacher_lone_days(*_teacher_1(_morning_slots([(2, 1)]), NO_LONE_THRESHOLD))
    assert pick(violations, "teacher_id", "weekday", "session") == [(1, 2, None)]


def test_split_day_respects_load_threshold():
    slots = _split_day_slots()
    assert detect_teacher_split_days(*_teacher_1(slots, SchedulingConfig(min_weekly_periods_for_lone_penalty=15))) == []
    assert pick(detect_teacher_split_days(*_teacher_1(slots, NO_LONE_THRESHOLD)), "teacher_id", "weekday") == [(1, 2)]


def test_split_day_is_exactly_one_plus_one_not_asymmetric():
    asymmetric = [_slot(1, 2, "S", 1), _slot(2, 2, "C", 1), _slot(3, 2, "C", 2), _slot(4, 2, "C", 3)]
    assert detect_teacher_split_days(*_teacher_1(asymmetric, NO_LONE_THRESHOLD)) == []


def test_exempt_teacher_is_skipped_by_every_lone_rule():
    exempt = SchedulingConfig(min_weekly_periods_for_lone_penalty=0, lone_session_exempt_teacher_ids=frozenset({1}))
    lone = _morning_slots([(2, 1)])
    assert detect_teacher_lone_sessions(*_teacher_1(lone, exempt)) == []
    assert detect_teacher_lone_days(*_teacher_1(lone, exempt)) == []
    assert detect_teacher_split_days(*_teacher_1(_split_day_slots(), exempt)) == []


# --- II.14 / II.7 ---

def test_four_period_morning_only_counts_for_lighter_teachers():
    view, params = _teacher_1(_morning_slots([(2, p) for p in range(1, 5)]))
    assert pick(detect_teacher_4_consecutive_mornings(view, params), "teacher_id", "weekday") == [(1, 2)]
    assert detect_teacher_4_consecutive_mornings(view, replace(params, max_load_for_4consec_penalty=2)) == []


def test_teacher_gap_within_session():
    slots = [_slot(1, 2, "S", 1), _slot(2, 2, "S", 4)]
    view, params = view_and_params(slots, {1: 100, 2: 100}, assigned_teacher={(100, 101): 10})
    gaps = detect_teacher_gaps(view, params)
    assert pick(gaps, "teacher_id", "weekday", "session") == [(10, 2, "S")]
    assert "tiết dạy: 1, 4" in gaps[0].detail


# --- T.* ---

def test_teacher_in_two_classes_at_once():
    shared = TimeSlot(1, 2, "S", 1)
    slots = [Slot(1, 101, shared), Slot(2, 102, shared)]
    view, params = view_and_params(slots, {1: 7, 2: 7}, assigned_teacher={(7, 101): 10, (7, 102): 10})
    assert pick(detect_teacher_conflicts(view, params), "teacher_id", "weekday", "session", "period", "count") == [
        (10, 2, "S", 1, 2),
    ]


def test_teacher_placed_in_busy_slot():
    slots = [_slot(1, 2, "S", 1), _slot(2, 2, "S", 2)]
    view, params = view_and_params(slots, {1: 100, 2: 100}, assigned_teacher={(100, 101): 10}, ban_busy={(10, 1)})
    assert pick(detect_teacher_busy(view, params), "teacher_id", "class_id", "weekday", "session", "period") == [
        (10, 101, 2, "S", 1),
    ]


def test_teacher_over_daily_cap():
    slots = [_slot(i, 2, "S", i) for i in range(1, 4)]
    view, params = _teacher_1(slots, SchedulingConfig(max_teacher_periods_per_day=2))
    assert pick(detect_teacher_day_cap(view, params), "teacher_id", "weekday", "count") == [(1, 2, 3)]
