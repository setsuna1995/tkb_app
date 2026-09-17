from dataclasses import replace

from core.models import ROLE_GDTC, ROLE_NANG, SchedulingConfig, Slot, Subject, Teacher, TimeSlot
from core.rules import RULES
from core.rules.detectors import (
    DETECTORS, detect_academic_overload, detect_academic_underload, detect_gdtc_periods,
    detect_heavy_afternoon_period3, detect_heavy_consecutive, detect_morning_only,
    detect_non_consecutive_days, detect_rule, detect_single_pair, detect_subject_cells,
    detect_teacher_4_consecutive_mornings, detect_teacher_busy, detect_teacher_conflicts,
    detect_teacher_day_cap, detect_teacher_gaps, detect_teacher_lone_days, detect_teacher_lone_sessions,
    detect_teacher_missing_mandatory_mornings, detect_teacher_split_days,
)
from core.rules.params import RULE_FLAG_NAMES
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


# --- C.* ---

def test_gdtc_outside_allowed_periods():
    slots = [_slot(1, 2, "S", 2), _slot(2, 2, "S", 4), _slot(3, 2, "S", 5), _slot(4, 3, "C", 1), _slot(5, 3, "C", 2)]
    view, params = view_and_params(slots, {s.slot_id: 100 for s in slots}, subjects=[Subject(100, "GDTC", ROLE_GDTC)])
    assert set(pick(detect_gdtc_periods(view, params), "class_id", "weekday", "session", "period")) == {
        (101, 2, "S", 5), (101, 3, "C", 1),
    }


def test_non_consecutive_subject_on_adjacent_days():
    slots = [_slot(1, 2, "S", 1), _slot(2, 2, "S", 4), _slot(3, 3, "S", 1), _slot(4, 4, "S", 1)]
    view, params = view_and_params(slots, {s.slot_id: 100 for s in slots},
                                   config=SchedulingConfig(non_consecutive_subject_ids=frozenset({100})))
    assert pick(detect_non_consecutive_days(view, params), "class_id", "subject_id", "weekday") == [
        (101, 100, 2), (101, 100, 3),
    ]


def test_morning_only_subject_in_afternoon():
    slots = [_slot(1, 2, "S", 1), _slot(2, 2, "C", 1)]
    view, params = view_and_params(slots, {1: 10, 2: 10},
                                   config=SchedulingConfig(morning_only_subject_ids=frozenset({10})))
    assert pick(detect_morning_only(view, params), "class_id", "subject_id", "weekday", "session", "period") == [
        (101, 10, 2, "C", 1),
    ]


def test_heavy_run_longer_than_declared_cap():
    slots = [_slot(i, 2, "S", i) for i in range(1, 5)]
    subjects = [Subject(10, "Lý", ROLE_NANG), Subject(11, "Hóa", ROLE_NANG)]
    view, params = view_and_params(slots, {1: 10, 2: 10, 3: 11, 4: 11}, subjects=subjects)
    assert pick(detect_heavy_consecutive(view, params), "class_id", "weekday", "session", "period", "count") == [
        (101, 2, "S", 1, 4),
    ]


def test_heavy_subject_at_afternoon_period_3():
    slots = [_slot(1, 2, "C", 2), _slot(2, 2, "C", 3)]
    view, params = view_and_params(slots, {1: 10, 2: 10}, subjects=[Subject(10, "Lý", ROLE_NANG)])
    assert pick(detect_heavy_afternoon_period3(view, params), "class_id", "subject_id", "period") == [(101, 10, 3)]


def test_subject_outside_allowed_cells():
    slots = [_slot(1, 2, "S", 1), _slot(2, 3, "S", 1)]
    view, params = view_and_params(slots, {1: 10, 2: 10}, allowed_cells={(10, 101): frozenset({(2, "S")})})
    assert pick(detect_subject_cells(view, params), "class_id", "subject_id", "weekday", "session", "period") == [
        (101, 10, 3, "S", 1),
    ]


def test_single_pair_subject_with_two_pairs():
    config = SchedulingConfig(single_pair_subject_ids=frozenset({10}))
    two_pairs = [_slot(1, 2, "S", 1), _slot(2, 2, "S", 2), _slot(3, 3, "S", 1), _slot(4, 3, "S", 2)]
    one_pair = [_slot(1, 2, "S", 1), _slot(2, 2, "S", 2), _slot(3, 3, "S", 1), _slot(4, 4, "S", 1)]
    two = detect_single_pair(*view_and_params(two_pairs, {s.slot_id: 10 for s in two_pairs}, config=config))
    one = detect_single_pair(*view_and_params(one_pair, {s.slot_id: 10 for s in one_pair}, config=config))
    assert pick(two, "class_id", "subject_id", "count") == [(101, 10, 2)]
    assert one == []


# --- ACAD.* ---

ACADEMIC_AND_LIGHT_SUBJECTS = [
    Subject(1, "Toán học"), Subject(2, "Ngữ văn"), Subject(3, "Ngoại ngữ"), Subject(4, "Khoa học tự nhiên"),
    Subject(5, "Tin học"), Subject(6, "Âm nhạc"), Subject(7, "Mỹ thuật"),
]


def _four_period_mornings(weekdays):
    return [_slot((wd - 2) * 4 + p, wd, "S", p) for wd in weekdays for p in range(1, 5)]


def test_morning_with_more_academic_periods_than_declared_cap():
    assignment = {1: 1, 2: 2, 3: 3, 4: 4, 5: 1, 6: 2, 7: 3, 8: 5}
    view, params = view_and_params(_four_period_mornings((2, 3)), assignment, subjects=ACADEMIC_AND_LIGHT_SUBJECTS)
    overloads = detect_academic_overload(view, params)
    assert pick(overloads, "class_id", "weekday", "count") == [(101, 2, 4)]
    assert "quá tải" in overloads[0].detail


def test_morning_with_fewer_academic_periods_than_declared_floor():
    slots = _four_period_mornings((2, 3)) + [_slot(9, 2, "C", 1), _slot(10, 2, "C", 2), _slot(11, 2, "C", 3)]
    assignment = {1: 1, 2: 5, 3: 6, 4: 7, 5: 1, 6: 2, 7: 5, 8: 6, 9: 5, 10: 6, 11: 7}
    view, params = view_and_params(slots, assignment, subjects=ACADEMIC_AND_LIGHT_SUBJECTS)
    assert pick(detect_academic_underload(view, params), "class_id", "weekday", "count") == [(101, 2, 1)]


# --- dispatch ---

def test_detect_rule_skips_rules_the_school_turned_off():
    slots = [_slot(1, 2, "S", 1), _slot(2, 2, "S", 4)]
    on = view_and_params(slots, {1: 7, 2: 7}, assigned_teacher={(7, 101): 10})
    off = view_and_params(slots, {1: 7, 2: 7}, assigned_teacher={(7, 101): 10},
                          config=SchedulingConfig(avoid_teacher_gaps=False))
    assert len(detect_rule("II.7", *on)) == 1
    assert detect_rule("II.7", *off) == []


def test_every_detected_rule_is_registered_with_a_resolvable_flag():
    assert set(DETECTORS) <= set(RULES)
    assert {rule.config_flag for rule in RULES.values()} - {None} <= set(RULE_FLAG_NAMES)
