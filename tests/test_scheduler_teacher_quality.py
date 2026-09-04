import random
from collections import defaultdict
import pytest

from core import scheduler as sched
from core.models import (
    ROLE_GDTC, ROLE_HDTN, ROLE_KEP, ROLE_THUONG, ClassRoom,
    SchedulingConfig, SchedulingInput, Slot, Subject, Teacher, TimeSlot,
)
from core.roles import resolve_roles


def test_gdtc_auto_non_consecutive_days():
    """GDTC of a class must never be placed on 2 consecutive days."""
    ts_mon = TimeSlot(1, 2, "S", 2)
    ts_tue = TimeSlot(2, 3, "S", 2)
    ts_wed = TimeSlot(3, 4, "S", 2)

    subjects = [
        Subject(1, "GDTC", ROLE_GDTC),
        Subject(2, "HDTN", ROLE_HDTN),
    ]
    role_index = resolve_roles(subjects)
    state = sched._State(remaining_need={(1, 101): 2}, busy=set())

    # Place GDTC on Monday
    state.placed[(101, 1, 2)].append(("S", 2))
    state.occupied[(101, 3, "S", 1)] = True
    state.occupied[(101, 4, "S", 1)] = True

    # Check feasibility for Tuesday (day 3, consecutive to Monday day 2) -> must be False
    config = SchedulingConfig(avoid_gdtc_consecutive_days=True)
    assert sched._feasible(101, ts_tue, 1, 10, state, role_index, config=config) is False

    # Check feasibility for Wednesday (day 4, non-consecutive to Monday day 2) -> must be True
    assert sched._feasible(101, ts_wed, 1, 10, state, role_index, config=config) is True


def test_mandatory_morning_weekdays_strictly_enforced():
    """All teachers must not have off-slots on mandatory mornings (default T2, T5, T6)."""
    rng = random.Random(42)
    teachers_by_id = {
        1: Teacher(1, "GV 1", pinned_full_day_off=2),  # tries to pin Mon
        2: Teacher(2, "GV 2", pinned_full_day_off=5),  # tries to pin Thu
        3: Teacher(3, "GV 3", pinned_afternoon_off=4),
        4: Teacher(4, "GV 4", off_sessions_override=2),
    }
    config = SchedulingConfig(mandatory_morning_weekdays=(2, 5, 6))
    offs, _shortfall = sched._assign_off_slots(
        set(teachers_by_id.keys()),
        teachers_by_id,
        rng,
        off_slot_count=1,
        forbidden_off_cells=config.forbidden_off_cells,
        mandatory_morning_weekdays=config.mandatory_morning_weekdays,
    )
    for tid, cells in offs.items():
        assert (2, "S") not in cells, f"Teacher {tid} was assigned off on Monday morning!"
        assert (5, "S") not in cells, f"Teacher {tid} was assigned off on Thursday morning!"
        assert (6, "S") not in cells, f"Teacher {tid} was assigned off on Friday morning!"


def test_avoid_teacher_gaps_penalty():
    """A slot creating a gap in a teacher's session receives a penalty compared to adjacent slots."""
    ts1 = TimeSlot(1, 2, "S", 1)
    ts2 = TimeSlot(2, 2, "S", 2)
    ts4 = TimeSlot(4, 2, "S", 4)

    subjects = [
        Subject(1, "Toan", ROLE_THUONG),
        Subject(2, "HDTN", ROLE_HDTN),
    ]
    role_index = resolve_roles(subjects)
    assigned_teacher = {(1, 101): 10, (1, 102): 10}

    state = sched._State(remaining_need={(1, 101): 5, (1, 102): 5}, busy=set())
    # Teacher 10 already teaches period 1 on Monday Morning for class 101
    state.placed[(101, 1, 2)].append(("S", 1))
    state.teacher_session_periods = {(10, 2, "S"): {1}}

    # Placing period 2 (adjacent to 1) should be scored much higher than period 4 (which creates gap 2-3)
    # We test helper function or scoring delta
    penalty_adjacent = sched._calculate_teacher_gap_penalty(10, 2, "S", 2, state)
    penalty_gap = sched._calculate_teacher_gap_penalty(10, 2, "S", 4, state)
    assert penalty_adjacent <= 0
    assert penalty_gap > 0


def test_quality_metrics_helpers():
    """Verify metrics for counting teacher gaps, lone days, and split sessions."""
    state = sched._State(remaining_need={}, busy=set())
    # Teacher 1: teaches period 1 and period 4 on Monday morning (gap = 2)
    # Teacher 1: teaches only period 1 on Tuesday morning and 0 in afternoon (lone day = 1)
    # Teacher 2: teaches period 1 morning and period 1 afternoon on Wednesday (split day = 1)
    state.slot_teacher = {1: 1, 2: 1, 3: 1, 4: 2, 5: 2}
    slot1 = Slot(1, 101, TimeSlot(1, 2, "S", 1))
    slot2 = Slot(2, 102, TimeSlot(2, 2, "S", 4))
    slot3 = Slot(3, 101, TimeSlot(3, 3, "S", 1))
    slot4 = Slot(4, 101, TimeSlot(4, 4, "S", 1))
    slot5 = Slot(5, 101, TimeSlot(5, 4, "C", 1))

    state.assigned = {1: 10, 2: 10, 3: 10, 4: 20, 5: 20}
    slots = [slot1, slot2, slot3, slot4, slot5]

    gaps = sched._count_teacher_gaps(slots, state.assigned, state.slot_teacher)
    lone_days = sched._count_teacher_lone_days(slots, state.assigned, state.slot_teacher)
    split_days = sched._count_teacher_split_sessions(slots, state.assigned, state.slot_teacher)

    assert gaps >= 1
    assert lone_days >= 1
    assert split_days >= 1


def test_teacher_lone_period_and_split_day_scoring():
    """Verify session pair bonus and split-day penalty in _pick_best_scored."""
    ts_morning = TimeSlot(1, 3, "S", 2)
    ts_afternoon = TimeSlot(2, 3, "C", 1)

    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    # Teacher 10 teaches Subject 1 for both class 101 and class 102
    assigned_teacher = {(1, 101): 10, (1, 102): 10}

    # State with teacher 10 already having 1 period in morning on Wednesday (day 3) in class 101
    state = sched._State(remaining_need={(1, 101): 5, (1, 102): 5}, busy=set())
    state.placed[(101, 1, 3)].append(("S", 1))
    state.occupied[(101, 3, "S", 1)] = True
    state.occupied[(102, 3, "S", 1)] = True
    state.teacher_session_periods[(10, 3, "S")] = [1]
    state.session_count[(10, 3, "S")] = 1

    config = SchedulingConfig(avoid_teacher_lone_periods=True)
    rng = random.Random(1)

    # 1. Picking morning period 2 for class 102 (which gives teacher 10 their 2nd period in morning session -> avoids lone period)
    slot_morning2 = Slot(10, 102, ts_morning)
    pick_m = sched._pick_best_scored(102, slot_morning2, state, role_index, subjects, assigned_teacher, 0.0, rng, config=config)
    assert pick_m is not None
    assert pick_m[0] == 1

    # 2. Picking afternoon period 1 when morning has only 1 period -> penalized by TEACHER_SPLIT_DAY_PENALTY
    # Compare with another subject whose teacher doesn't have 1 morning period
    subjects2 = [Subject(1, "Toan", ROLE_THUONG), Subject(3, "Ly", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]
    assigned_teacher2 = {(1, 101): 10, (3, 101): 20}
    state.remaining_need[(3, 101)] = 5
    slot_afternoon1 = Slot(11, 101, ts_afternoon)
    pick_c = sched._pick_best_scored(101, slot_afternoon1, state, role_index, subjects2, assigned_teacher2, 0.0, rng, config=config)
    # Teacher 20 (who has no morning period) is preferred over Teacher 10 (who would get 1S + 1C split day)
    assert pick_c is not None
    assert pick_c[0] == 3  # Subject 3 (Teacher 20) preferred over Subject 1 (Teacher 10)


def test_validation_helpers():
    from core import validation as val
    slot1 = Slot(1, 101, TimeSlot(1, 2, "S", 1))
    slot2 = Slot(2, 101, TimeSlot(2, 2, "S", 4))  # creates gap 2-3 for Teacher 10
    slot3 = Slot(3, 101, TimeSlot(3, 3, "S", 1))  # Subject 100 on Tuesday (day 3)
    slot4 = Slot(4, 101, TimeSlot(4, 4, "S", 1))  # Subject 100 on Wednesday (day 4) -> consecutive!

    slots = [slot1, slot2, slot3, slot4]
    assignment = {1: 100, 2: 100, 3: 100, 4: 100}
    assigned_teacher = {(100, 101): 10}

    # Find teacher gaps
    gaps = val.find_teacher_gaps(slots, assignment, assigned_teacher)
    assert len(gaps) == 1
    assert gaps[0][0] == 10  # Teacher 10
    assert gaps[0][3] == [1, 4]

    # Find consecutive subject days (days 2, 3, 4 -> pairs (2,3) and (3,4))
    consec = val.find_consecutive_subject_days(slots, assignment, {100})
    assert len(consec) == 2
    assert consec[0] == (101, 100, 2, 3)
    assert consec[1] == (101, 100, 3, 4)

    # Teacher unavailability violations
    ban_busy = {(10, 1)}  # Teacher 10 is busy at ts_id 1
    unav_violations = val.find_teacher_unavailability_violations(slots, assignment, assigned_teacher, ban_busy)
    assert len(unav_violations) == 1
    assert unav_violations[0] == (10, 101, 2, "S", 1)

    # GDTC invalid periods
    gdtc_slots = [
        Slot(1, 101, TimeSlot(1, 2, "S", 2)),  # S2 -> Valid
        Slot(2, 101, TimeSlot(2, 2, "S", 4)),  # S4 -> Valid (in 1..4)
        Slot(3, 101, TimeSlot(3, 2, "S", 5)),  # S5 -> Invalid (outside 1..4)
        Slot(4, 101, TimeSlot(4, 3, "C", 1)),  # C1 -> Invalid (outside 2..3)
        Slot(5, 101, TimeSlot(5, 3, "C", 2)),  # C2 -> Valid
    ]
    gdtc_assign = {1: 100, 2: 100, 3: 100, 4: 100, 5: 100}
    invalid_gdtc = val.find_invalid_gdtc_periods(gdtc_slots, gdtc_assign, 100, (1, 2, 3, 4), (2, 3))
    assert len(invalid_gdtc) == 2
    assert (101, 2, "S", 5) in invalid_gdtc
    assert (101, 3, "C", 1) in invalid_gdtc


def test_gdtc_allowed_periods_feasibility():
    """Verify that _feasible rejects GDTC outside morning 1-4 and afternoon 2-3."""
    subjects = [Subject(1, "GDTC", ROLE_GDTC), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    config = SchedulingConfig(
        gdtc_morning_allowed_periods=(1, 2, 3, 4),
        gdtc_afternoon_allowed_periods=(2, 3),
    )

    def _state_for_period(session, period):
        st = sched._State(remaining_need={(1, 101): 2}, busy=set())
        for p in range(1, period):
            st.occupied[(101, 2, session, p)] = True
        return st

    # Morning tests
    ts_s1 = TimeSlot(1, 2, "S", 1)
    ts_s2 = TimeSlot(2, 2, "S", 2)
    ts_s3 = TimeSlot(3, 2, "S", 3)
    ts_s4 = TimeSlot(4, 2, "S", 4)
    ts_s5 = TimeSlot(5, 2, "S", 5)

    assert sched._feasible(101, ts_s1, 1, 10, _state_for_period("S", 1), role_index, config=config) is True
    assert sched._feasible(101, ts_s2, 1, 10, _state_for_period("S", 2), role_index, config=config) is True
    assert sched._feasible(101, ts_s3, 1, 10, _state_for_period("S", 3), role_index, config=config) is True
    assert sched._feasible(101, ts_s4, 1, 10, _state_for_period("S", 4), role_index, config=config) is True
    assert sched._feasible(101, ts_s5, 1, 10, _state_for_period("S", 5), role_index, config=config) is False

    # Afternoon tests
    ts_c1 = TimeSlot(6, 2, "C", 1)
    ts_c2 = TimeSlot(7, 2, "C", 2)
    ts_c3 = TimeSlot(8, 2, "C", 3)
    ts_c4 = TimeSlot(9, 2, "C", 4)

    assert sched._feasible(101, ts_c1, 1, 10, _state_for_period("C", 1), role_index, config=config) is False
    assert sched._feasible(101, ts_c2, 1, 10, _state_for_period("C", 2), role_index, config=config) is True
    assert sched._feasible(101, ts_c3, 1, 10, _state_for_period("C", 3), role_index, config=config) is True
    assert sched._feasible(101, ts_c4, 1, 10, _state_for_period("C", 4), role_index, config=config) is False


def test_single_pair_overrides_role_kep():
    """When a subject is listed in single_pair_subject_ids, it should be treated as single_pair (1 pair only)
    even if its role_code was set to ROLE_KEP (2) or ROLE_NANG_KEP (3)."""
    subjects = [
        Subject(1, "Van", ROLE_KEP),
        Subject(2, "HDTN", ROLE_HDTN),
    ]
    # Without single_pair_subject_ids: subject 1 is in kep_ids
    role_idx_default = resolve_roles(subjects)
    assert 1 in role_idx_default.kep_ids
    assert 1 not in role_idx_default.single_pair_ids

    # With single_pair_subject_ids={1}: subject 1 MUST be moved to single_pair_ids
    role_idx_single_pair = resolve_roles(subjects, single_pair_subject_ids=frozenset({1}))
    assert 1 in role_idx_single_pair.single_pair_ids
    assert 1 not in role_idx_single_pair.kep_ids
    assert role_idx_single_pair.block_size[1] == 2


def test_balance_afternoon_teachers_penalty():
    """When balance_afternoon_teachers is True, teachers who teach classes with afternoon slots
    but are assigned zero afternoon periods in the entire week should incur a quality penalty."""
    config_on = SchedulingConfig(balance_afternoon_teachers=True)
    config_off = SchedulingConfig(balance_afternoon_teachers=False)

    # Class 101 has afternoon slots (slot 5 is in session "C")
    slot1 = Slot(1, 101, TimeSlot(1, 2, "S", 1))
    slot2 = Slot(2, 101, TimeSlot(2, 3, "S", 1))
    slot3 = Slot(3, 101, TimeSlot(3, 4, "S", 1))
    slot4 = Slot(4, 101, TimeSlot(4, 5, "S", 1))
    slot5 = Slot(5, 101, TimeSlot(5, 2, "C", 1))

    # Teacher 10 teaches class 101 (4 periods in morning, 0 in afternoon)
    # Teacher 20 teaches class 101 at slot 5 (afternoon)
    slots = [slot1, slot2, slot3, slot4, slot5]
    assigned = {1: 100, 2: 100, 3: 100, 4: 100, 5: 101}
    slot_teacher = {1: 10, 2: 10, 3: 10, 4: 10, 5: 20}

    # Calling _teacher_quality_penalty:
    pen_on = sched._teacher_quality_penalty(slots, assigned, slot_teacher, config_on)
    pen_off = sched._teacher_quality_penalty(slots, assigned, slot_teacher, config_off)

    assert pen_on > pen_off, f"Expected pen_on ({pen_on}) > pen_off ({pen_off})"


def test_validation_new_helpers():
    from core import validation as val

    # 1. Test find_morning_only_violations
    slot_s = Slot(1, 101, TimeSlot(1, 2, "S", 1))
    slot_c = Slot(2, 101, TimeSlot(2, 2, "C", 1))
    assign = {1: 10, 2: 10} # Subject 10 placed in morning and afternoon
    morning_violations = val.find_morning_only_violations([slot_s, slot_c], assign, {10})
    assert len(morning_violations) == 1
    assert morning_violations[0] == (101, 10, 2, "C", 1)

    # 2. Test find_max_heavy_violations
    # 4 consecutive heavy periods in Morning
    heavy_slots = [
        Slot(1, 101, TimeSlot(1, 2, "S", 1)),
        Slot(2, 101, TimeSlot(2, 2, "S", 2)),
        Slot(3, 101, TimeSlot(3, 2, "S", 3)),
        Slot(4, 101, TimeSlot(4, 2, "S", 4)),
    ]
    heavy_assign = {1: 10, 2: 10, 3: 11, 4: 11} # Subjects 10 & 11 are heavy
    heavy_violations = val.find_max_heavy_violations(heavy_slots, heavy_assign, {10, 11}, max_consecutive=3)
    assert len(heavy_violations) == 1
    assert heavy_violations[0] == (101, 2, "S", 1, 4)

    # 3. Test find_subject_class_rule_violations
    # Subject 10 in class 101 allowed ONLY on (2, "S")
    rules = [
        {"subject_id": 10, "class_ids": [101], "cells": {(2, "S")}}
    ]
    # Placed on (2, "S") -> Valid, Placed on (3, "S") -> Violation
    rule_slots = [
        Slot(1, 101, TimeSlot(1, 2, "S", 1)),
        Slot(2, 101, TimeSlot(2, 3, "S", 1)),
    ]
    rule_assign = {1: 10, 2: 10}
    rule_violations = val.find_subject_class_rule_violations(rule_slots, rule_assign, rules)
    assert len(rule_violations) == 1
    assert rule_violations[0] == (101, 10, 3, "S", 1)


def test_greedy_prefers_pairing_over_lone_session():
    """_pick_best_scored should strongly prefer assigning to a teacher who already has 1 period
    in the session (creating a 2-period pair) over a teacher who currently has 0 periods in this session."""
    ts_s2 = TimeSlot(2, 3, "S", 2)
    slot_s2 = Slot(2, 102, ts_s2)

    subj1 = Subject(1, "Toan", ROLE_THUONG)
    subj2 = Subject(2, "Van", ROLE_THUONG)
    subj_hdtn = Subject(3, "HDTN", ROLE_HDTN)
    subjects = [subj1, subj2, subj_hdtn]
    role_index = resolve_roles(subjects)

    # Teacher 10 teaches Toan for class 101 & 102 (has 1 period on Wed S1 for class 101)
    # Teacher 20 teaches Van for class 102 (has 0 periods on Wed S)
    assigned_teacher = {(1, 101): 10, (1, 102): 10, (2, 102): 20}

    state = sched._State(remaining_need={(1, 101): 2, (1, 102): 3, (2, 102): 3}, busy=set())
    state.placed[(101, 1, 3)].append(("S", 1))
    state.occupied[(101, 3, "S", 1)] = True
    state.occupied[(102, 3, "S", 1)] = True
    state.teacher_session_periods[(10, 3, "S")] = [1]
    state.session_count[(10, 3, "S")] = 1

    config = SchedulingConfig(avoid_teacher_lone_periods=True)
    rng = random.Random(42)

    pick = sched._pick_best_scored(102, slot_s2, state, role_index, subjects, assigned_teacher, 0.0, rng, config=config)
    assert pick is not None
    # Must pick Subject 1 (Teacher 10) to pair and avoid lone period!
    assert pick[0] == 1, f"Expected Subject 1 (pair for Teacher 10), but got Subject {pick[0]}"


def test_repair_teacher_lone_sessions_evacuates_or_pairs():
    """_repair_teacher_lone_sessions should eliminate 1-period sessions for teachers by moving or pairing."""
    # Create a 2-session scenario for Class 101:
    # Mon S: Slot 1 (S1: Toan by Teacher 10) - lone period for Teacher 10!
    # Tue S: Slot 2 (S1: Van by Teacher 20), Slot 3 (S2: Toan by Teacher 10) - Teacher 10 has 1 period here
    # Teacher 20 also teaches Van on Mon S? No, let's say Slot 1 is Toan (T10), Slot 2 is Van (T20)
    # If we swap Toan at Mon S1 with Van at Tue S1 -> then Tue has both Toan & Toan (or Toan & Van),
    # eliminating the Mon S1 lone period for Teacher 10!
    ts_mon_s1 = TimeSlot(1, 2, "S", 1)
    ts_tue_s1 = TimeSlot(2, 3, "S", 1)
    ts_tue_s2 = TimeSlot(3, 3, "S", 2)

    slot1 = Slot(1, 101, ts_mon_s1)
    slot2 = Slot(2, 101, ts_tue_s1)
    slot3 = Slot(3, 102, ts_tue_s2)

    subj1 = Subject(1, "Toan", ROLE_THUONG)
    subj2 = Subject(2, "Van", ROLE_THUONG)
    subj_hdtn = Subject(3, "HDTN", ROLE_HDTN)
    subjects = [subj1, subj2, subj_hdtn]
    role_index = resolve_roles(subjects)

    assigned_teacher = {(1, 101): 10, (1, 102): 10, (2, 101): 20}
    slots_by_class = {101: [slot1, slot2], 102: [slot3]}
    slot_by_coord = {
        (101, 2, "S", 1): slot1,
        (101, 3, "S", 1): slot2,
        (102, 3, "S", 2): slot3,
    }

    state = sched._State(remaining_need={(1, 101): 1, (1, 102): 1, (2, 101): 1}, busy=set())
    # Place Toan (T10) at slot1 (Mon S1)
    sched._put_at(state, slot1, 1, 10, role_index)
    # Place Van (T20) at slot2 (Tue S1)
    sched._put_at(state, slot2, 2, 20, role_index)
    # Place Toan (T10) at slot3 (Tue S2)
    sched._put_at(state, slot3, 1, 10, role_index)

    # Initial state: Teacher 10 has 1 period on Mon S (lone period!) and 1 period on Tue S (lone period!)
    assert len(state.teacher_session_periods[(10, 2, "S")]) == 1
    assert len(state.teacher_session_periods[(10, 3, "S")]) == 1

    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1"), ClassRoom(102, "6A2")],
        subjects=subjects,
        teachers=[Teacher(10, "GV Toan"), Teacher(20, "GV Van")],
        need={(1, 101): 1, (1, 102): 1, (2, 101): 1},
        assigned_teacher=assigned_teacher,
        ban_busy=set(),
        slots=[slot1, slot2, slot3],
        timeslots=[ts_mon_s1, ts_tue_s1, ts_tue_s2],
    )

    sched._repair_teacher_lone_sessions(
        inp, state, role_index, assigned_teacher, slots_by_class,
        config=SchedulingConfig(), slot_by_coord=slot_by_coord,
    )

    mon_count = len(state.teacher_session_periods.get((10, 2, "S"), []))
    tue_count = len(state.teacher_session_periods.get((10, 3, "S"), []))
    assert mon_count in (0, 2), f"Mon count should be 0 or 2, got {mon_count}"
    assert tue_count in (0, 2), f"Tue count should be 0 or 2, got {tue_count}"


def test_repair_teacher_lone_sessions_skips_exempt_low_load_teacher():
    """Fix-wave Important #6 (2026-09-03): _repair_teacher_lone_sessions must not
    spend its bounded repair budget (max_rounds=3, first-improving-move only) on a
    teacher whose total weekly load is below min_weekly_periods_for_lone_penalty --
    that teacher is exempt from the II.4 hard gate anyway (see engine.py/
    quality.py's counters), so their lone session must be left completely
    untouched, not consumed by a wasted repair attempt.

    Two teachers get the IDENTICAL evacuate-repairable lone-session structure from
    test_repair_teacher_lone_sessions_evacuates_or_pairs above (Mon S1 lone,
    Tue S1/S2 swap partner); only their total weekly load differs. Teacher 10
    (total=2, well under the 15-period threshold) must be left exactly as placed;
    Teacher 30 (total=18, padded with 4 full 4-period mornings on separate classes/
    weekdays so as to not create any extra lone sessions of its own) must still
    get repaired, proving the exemption is selective, not a global no-op."""
    ts_mon_s1 = TimeSlot(1, 2, "S", 1)
    ts_tue_s1 = TimeSlot(2, 3, "S", 1)
    ts_tue_s2 = TimeSlot(3, 3, "S", 2)
    slot1 = Slot(1, 101, ts_mon_s1)
    slot2 = Slot(2, 101, ts_tue_s1)
    slot3 = Slot(3, 102, ts_tue_s2)

    ts_mon_s1_b = TimeSlot(4, 2, "S", 1)
    ts_tue_s1_b = TimeSlot(5, 3, "S", 1)
    ts_tue_s2_b = TimeSlot(6, 3, "S", 2)
    slot4 = Slot(4, 201, ts_mon_s1_b)
    slot5 = Slot(5, 201, ts_tue_s1_b)
    slot6 = Slot(6, 202, ts_tue_s2_b)

    # Padding for Teacher 30: 4 full (max_periods_per_session=4) mornings on
    # weekdays 4-7, in their OWN classes (203-206) that never touch (wd 2, "S")
    # or (wd 3, "S") -- so they never qualify as a Strategy 1 evacuation target
    # (len(periods) == max_periods_per_session there, excluded) and never expose
    # a Strategy 2 consolidate target either (no slot at wd_lone/sess_lone in
    # those classes). Pushes Teacher 30's total from 2 to 18 (>= 15) without
    # creating any extra lone sessions.
    padding_slots = []
    padding_ts = []
    slot_id = 7
    for cid, wd in ((203, 4), (204, 5), (205, 6), (206, 7)):
        for p in range(1, 5):
            ts = TimeSlot(slot_id, wd, "S", p)
            padding_slots.append(Slot(slot_id, cid, ts))
            padding_ts.append(ts)
            slot_id += 1

    subj1 = Subject(1, "Toan", ROLE_THUONG)
    subj2 = Subject(2, "Van", ROLE_THUONG)
    subj_hdtn = Subject(3, "HDTN", ROLE_HDTN)
    subjects = [subj1, subj2, subj_hdtn]
    role_index = resolve_roles(subjects)

    assigned_teacher = {
        (1, 101): 10, (1, 102): 10, (2, 101): 20,
        (1, 201): 30, (1, 202): 30, (2, 201): 40,
        (1, 203): 30, (1, 204): 30, (1, 205): 30, (1, 206): 30,
    }
    slots_by_class = {
        101: [slot1, slot2], 102: [slot3],
        201: [slot4, slot5], 202: [slot6],
        203: [s for s in padding_slots if s.class_id == 203],
        204: [s for s in padding_slots if s.class_id == 204],
        205: [s for s in padding_slots if s.class_id == 205],
        206: [s for s in padding_slots if s.class_id == 206],
    }
    slot_by_coord = {
        (101, 2, "S", 1): slot1, (101, 3, "S", 1): slot2, (102, 3, "S", 2): slot3,
        (201, 2, "S", 1): slot4, (201, 3, "S", 1): slot5, (202, 3, "S", 2): slot6,
    }
    for s in padding_slots:
        slot_by_coord[(s.class_id, s.ts.weekday, s.ts.session, s.ts.period)] = s

    remaining_need = {
        (1, 101): 1, (1, 102): 1, (2, 101): 1,
        (1, 201): 1, (1, 202): 1, (2, 201): 1,
        (1, 203): 4, (1, 204): 4, (1, 205): 4, (1, 206): 4,
    }
    state = sched._State(remaining_need=remaining_need, busy=set())
    sched._put_at(state, slot1, 1, 10, role_index)
    sched._put_at(state, slot2, 2, 20, role_index)
    sched._put_at(state, slot3, 1, 10, role_index)
    sched._put_at(state, slot4, 1, 30, role_index)
    sched._put_at(state, slot5, 2, 40, role_index)
    sched._put_at(state, slot6, 1, 30, role_index)
    for s in padding_slots:
        sched._put_at(state, s, 1, 30, role_index)

    # Sanity check on the constructed fixture before repair.
    assert len(state.teacher_session_periods[(10, 2, "S")]) == 1
    assert len(state.teacher_session_periods[(10, 3, "S")]) == 1
    assert len(state.teacher_session_periods[(30, 2, "S")]) == 1
    assert len(state.teacher_session_periods[(30, 3, "S")]) == 1
    teacher_10_total = sum(len(v) for (tid, wd, sess), v in state.teacher_session_periods.items() if tid == 10)
    teacher_30_total = sum(len(v) for (tid, wd, sess), v in state.teacher_session_periods.items() if tid == 30)
    assert teacher_10_total == 2
    assert teacher_30_total == 18

    classes = [
        ClassRoom(101, "6A1"), ClassRoom(102, "6A2"),
        ClassRoom(201, "7A1"), ClassRoom(202, "7A2"),
        ClassRoom(203, "7A3"), ClassRoom(204, "7A4"), ClassRoom(205, "7A5"), ClassRoom(206, "7A6"),
    ]
    inp = SchedulingInput(
        classes=classes,
        subjects=subjects,
        teachers=[Teacher(10, "GV Toan"), Teacher(20, "GV Van"), Teacher(30, "GV Ly"), Teacher(40, "GV Hoa")],
        need={},
        assigned_teacher=assigned_teacher,
        ban_busy=set(),
        slots=[slot1, slot2, slot3, slot4, slot5, slot6] + padding_slots,
        timeslots=[ts_mon_s1, ts_tue_s1, ts_tue_s2, ts_mon_s1_b, ts_tue_s1_b, ts_tue_s2_b] + padding_ts,
    )

    sched._repair_teacher_lone_sessions(
        inp, state, role_index, assigned_teacher, slots_by_class,
        config=SchedulingConfig(), slot_by_coord=slot_by_coord,
        min_weekly_periods=15,
    )

    # Teacher 10 (exempt, total=2 < 15): left EXACTLY as originally placed -- not
    # consumed by a wasted repair attempt.
    assert len(state.teacher_session_periods.get((10, 2, "S"), [])) == 1
    assert len(state.teacher_session_periods.get((10, 3, "S"), [])) == 1

    # Teacher 30 (non-exempt, total=18 >= 15): must still get repaired.
    mon_count_30 = len(state.teacher_session_periods.get((30, 2, "S"), []))
    tue_count_30 = len(state.teacher_session_periods.get((30, 3, "S"), []))
    assert mon_count_30 in (0, 2), f"Mon count for Teacher 30 should be 0 or 2, got {mon_count_30}"
    assert tue_count_30 in (0, 2), f"Tue count for Teacher 30 should be 0 or 2, got {tue_count_30}"


def test_repair_teacher_missing_mandatory_mornings_fills_via_same_class_swap():
    """_repair_teacher_missing_mandatory_mornings should fill a teacher's missing
    mandatory morning (Fri, wd 6) by swapping one of their periods on a
    non-mandatory day (Tue, wd 3) into the missing mandatory-morning slot,
    same class, trading places with whoever else is teaching there."""
    ts_mon = TimeSlot(1, 2, "S", 1)
    ts_thu = TimeSlot(2, 5, "S", 1)
    ts_tue = TimeSlot(3, 3, "S", 1)   # source: teacher 10's period to move
    ts_fri = TimeSlot(4, 6, "S", 1)   # destination: currently teacher 20

    slot_mon = Slot(1, 101, ts_mon)
    slot_thu = Slot(2, 101, ts_thu)
    slot_tue = Slot(3, 101, ts_tue)
    slot_fri = Slot(4, 101, ts_fri)

    subj1 = Subject(1, "Toan", ROLE_THUONG)
    subj2 = Subject(2, "Van", ROLE_THUONG)
    subj_hdtn = Subject(3, "HDTN", ROLE_HDTN)
    subjects = [subj1, subj2, subj_hdtn]
    role_index = resolve_roles(subjects)

    # Padding so teacher 10's total weekly load hits the II.3 threshold (>=10)
    # without touching any mandatory morning (wd 2, 5, 6) or class 101.
    padding_slots = []
    padding_ts = []
    slot_id = 5
    for cid, wd, periods in ((102, 4, range(1, 5)), (103, 7, range(1, 4))):
        for p in periods:
            ts = TimeSlot(slot_id, wd, "S", p)
            padding_slots.append(Slot(slot_id, cid, ts))
            padding_ts.append(ts)
            slot_id += 1

    assigned_teacher = {(1, 101): 10, (2, 101): 20, (1, 102): 10, (1, 103): 10}
    slots_by_class = {
        101: [slot_mon, slot_thu, slot_tue, slot_fri],
        102: [s for s in padding_slots if s.class_id == 102],
        103: [s for s in padding_slots if s.class_id == 103],
    }

    state = sched._State(remaining_need=defaultdict(int), busy=set())
    sched._put_at(state, slot_mon, 1, 10, role_index)
    sched._put_at(state, slot_thu, 1, 10, role_index)
    sched._put_at(state, slot_tue, 1, 10, role_index)
    sched._put_at(state, slot_fri, 2, 20, role_index)
    for s in padding_slots:
        sched._put_at(state, s, 1, 10, role_index)

    teacher_10_total = sum(len(v) for (tid, _wd, _sess), v in state.teacher_session_periods.items() if tid == 10)
    assert teacher_10_total == 10  # exactly at the II.3 threshold

    # Sanity check before repair: Friday morning (wd 6) is missing for teacher 10.
    assert len(state.teacher_session_periods.get((10, 6, "S"), [])) == 0

    classes = [ClassRoom(101, "6A1"), ClassRoom(102, "6A2"), ClassRoom(103, "6A3")]
    inp = SchedulingInput(
        classes=classes, subjects=subjects,
        teachers=[Teacher(10, "GV Toan"), Teacher(20, "GV Van")],
        need={}, assigned_teacher=assigned_teacher, ban_busy=set(),
        slots=[slot_mon, slot_thu, slot_tue, slot_fri] + padding_slots,
        timeslots=[ts_mon, ts_thu, ts_tue, ts_fri] + padding_ts,
    )

    sched._repair_teacher_missing_mandatory_mornings(
        inp, state, role_index, assigned_teacher, slots_by_class,
        config=SchedulingConfig(), min_weekly_periods=10,
    )

    # Friday morning is now covered, via a swap (Tue is now empty for teacher 10).
    assert len(state.teacher_session_periods.get((10, 6, "S"), [])) == 1
    assert len(state.teacher_session_periods.get((10, 3, "S"), [])) == 0
    assert state.assigned[slot_fri.slot_id] == 1  # Toan now taught by teacher 10 on Fri
    assert state.assigned[slot_tue.slot_id] == 2  # Van (teacher 20) moved into Tue
    assert state.pinned.get(slot_fri.slot_id) is True

    # A straight swap must not change the teacher's total weekly load.
    teacher_10_total_after = sum(len(v) for (tid, _wd, _sess), v in state.teacher_session_periods.items() if tid == 10)
    assert teacher_10_total_after == 10


def test_repair_teacher_missing_mandatory_mornings_skips_exempt_low_load_teacher():
    """Same as II.4's exemption precedent (test_repair_teacher_lone_sessions_
    skips_exempt_low_load_teacher above): a teacher below min_weekly_periods
    (the II.3 threshold, default 10) must be left completely untouched even
    when the identical fillable structure is present, while a teacher at/above
    the threshold with the same structure must still get repaired -- proving
    the exemption is selective, not a global no-op."""
    # Teacher 10 (total=9, exempt): class 101, same Mon/Thu/Tue/Fri shape as
    # the test above, padded to 9 (not 10).
    ts_mon_a = TimeSlot(1, 2, "S", 1)
    ts_thu_a = TimeSlot(2, 5, "S", 1)
    ts_tue_a = TimeSlot(3, 3, "S", 1)
    ts_fri_a = TimeSlot(4, 6, "S", 1)
    slot_mon_a = Slot(1, 101, ts_mon_a)
    slot_thu_a = Slot(2, 101, ts_thu_a)
    slot_tue_a = Slot(3, 101, ts_tue_a)
    slot_fri_a = Slot(4, 101, ts_fri_a)

    # Teacher 30 (total=10, non-exempt): identical shape, class 201.
    ts_mon_b = TimeSlot(5, 2, "S", 1)
    ts_thu_b = TimeSlot(6, 5, "S", 1)
    ts_tue_b = TimeSlot(7, 3, "S", 1)
    ts_fri_b = TimeSlot(8, 6, "S", 1)
    slot_mon_b = Slot(5, 201, ts_mon_b)
    slot_thu_b = Slot(6, 201, ts_thu_b)
    slot_tue_b = Slot(7, 201, ts_tue_b)
    slot_fri_b = Slot(8, 201, ts_fri_b)

    subj1 = Subject(1, "Toan", ROLE_THUONG)
    subj2 = Subject(2, "Van", ROLE_THUONG)
    subj_hdtn = Subject(3, "HDTN", ROLE_HDTN)
    subjects = [subj1, subj2, subj_hdtn]
    role_index = resolve_roles(subjects)

    padding_slots = []
    padding_ts = []
    slot_id = 9
    # Teacher 10: 3 real periods + 6 padding = 9 (< 10, exempt).
    padding_specs = [
        (102, 4, range(1, 5), 10),   # +4 -> teacher 10 total = 3+4+2 = 9 (with next line)
        (103, 7, range(1, 3), 10),   # +2
        (202, 4, range(1, 5), 30),   # +4 -> teacher 30 total = 3+4+3 = 10 (with next line)
        (203, 7, range(1, 4), 30),   # +3
    ]
    for cid, wd, periods, tid in padding_specs:
        for p in periods:
            ts = TimeSlot(slot_id, wd, "S", p)
            padding_slots.append((Slot(slot_id, cid, ts), tid))
            padding_ts.append(ts)
            slot_id += 1

    assigned_teacher = {
        (1, 101): 10, (2, 101): 20, (1, 102): 10, (1, 103): 10,
        (1, 201): 30, (2, 201): 40, (1, 202): 30, (1, 203): 30,
    }
    slots_by_class = {
        101: [slot_mon_a, slot_thu_a, slot_tue_a, slot_fri_a],
        201: [slot_mon_b, slot_thu_b, slot_tue_b, slot_fri_b],
        102: [s for s, tid in padding_slots if s.class_id == 102],
        103: [s for s, tid in padding_slots if s.class_id == 103],
        202: [s for s, tid in padding_slots if s.class_id == 202],
        203: [s for s, tid in padding_slots if s.class_id == 203],
    }

    state = sched._State(remaining_need=defaultdict(int), busy=set())
    sched._put_at(state, slot_mon_a, 1, 10, role_index)
    sched._put_at(state, slot_thu_a, 1, 10, role_index)
    sched._put_at(state, slot_tue_a, 1, 10, role_index)
    sched._put_at(state, slot_fri_a, 2, 20, role_index)
    sched._put_at(state, slot_mon_b, 1, 30, role_index)
    sched._put_at(state, slot_thu_b, 1, 30, role_index)
    sched._put_at(state, slot_tue_b, 1, 30, role_index)
    sched._put_at(state, slot_fri_b, 2, 40, role_index)
    for s, tid in padding_slots:
        sched._put_at(state, s, 1, tid, role_index)

    teacher_10_total = sum(len(v) for (tid, _wd, _sess), v in state.teacher_session_periods.items() if tid == 10)
    teacher_30_total = sum(len(v) for (tid, _wd, _sess), v in state.teacher_session_periods.items() if tid == 30)
    assert teacher_10_total == 9
    assert teacher_30_total == 10

    classes = [
        ClassRoom(101, "6A1"), ClassRoom(102, "6A2"), ClassRoom(103, "6A3"),
        ClassRoom(201, "7A1"), ClassRoom(202, "7A2"), ClassRoom(203, "7A3"),
    ]
    inp = SchedulingInput(
        classes=classes, subjects=subjects,
        teachers=[Teacher(10, "GV A"), Teacher(20, "GV B"), Teacher(30, "GV C"), Teacher(40, "GV D")],
        need={}, assigned_teacher=assigned_teacher, ban_busy=set(),
        slots=[slot_mon_a, slot_thu_a, slot_tue_a, slot_fri_a,
               slot_mon_b, slot_thu_b, slot_tue_b, slot_fri_b] + [s for s, _t in padding_slots],
        timeslots=[ts_mon_a, ts_thu_a, ts_tue_a, ts_fri_a,
                   ts_mon_b, ts_thu_b, ts_tue_b, ts_fri_b] + padding_ts,
    )

    sched._repair_teacher_missing_mandatory_mornings(
        inp, state, role_index, assigned_teacher, slots_by_class,
        config=SchedulingConfig(), min_weekly_periods=10,
    )

    # Teacher 10 (exempt, total=9 < 10): left EXACTLY as originally placed.
    assert len(state.teacher_session_periods.get((10, 6, "S"), [])) == 0
    assert len(state.teacher_session_periods.get((10, 3, "S"), [])) == 1
    assert state.assigned[slot_tue_a.slot_id] == 1
    assert state.assigned[slot_fri_a.slot_id] == 2

    # Teacher 30 (non-exempt, total=10 >= 10): must still get repaired.
    assert len(state.teacher_session_periods.get((30, 6, "S"), [])) == 1
    assert len(state.teacher_session_periods.get((30, 3, "S"), [])) == 0


def test_repair_teacher_missing_mandatory_mornings_survives_lone_session_repair():
    """The pin guard must actually work: after _repair_teacher_missing_mandatory_
    mornings fills a teacher's missing Friday morning, _repair_teacher_lone_sessions
    (which runs right after it in engine.py's real call order) must NOT be able to
    evacuate that newly-filled period, even when the teacher's total load (>=15)
    makes them non-exempt from II.4 and an evacuate target genuinely exists."""
    ts_mon = TimeSlot(1, 2, "S", 1)
    ts_thu = TimeSlot(2, 5, "S", 1)
    ts_tue = TimeSlot(3, 3, "S", 1)     # source for II.3 repair
    ts_fri = TimeSlot(4, 6, "S", 1)     # destination for II.3 repair
    ts_sat1 = TimeSlot(5, 7, "S", 1)    # teacher 10's existing 1-period Sat session
    ts_sat2 = TimeSlot(6, 7, "S", 2)    # Strategy-1 evacuate swap partner (teacher 50)

    slot_mon = Slot(1, 101, ts_mon)
    slot_thu = Slot(2, 101, ts_thu)
    slot_tue = Slot(3, 101, ts_tue)
    slot_fri = Slot(4, 101, ts_fri)
    slot_sat1 = Slot(5, 101, ts_sat1)
    slot_sat2 = Slot(6, 101, ts_sat2)

    subj1 = Subject(1, "Toan", ROLE_THUONG)
    subj2 = Subject(2, "Van", ROLE_THUONG)
    subj3 = Subject(3, "Ly", ROLE_THUONG)
    subj_hdtn = Subject(4, "HDTN", ROLE_HDTN)
    subjects = [subj1, subj2, subj3, subj_hdtn]
    role_index = resolve_roles(subjects)

    # Padding so teacher 10's total reaches the II.4 threshold too (>=15), not
    # just the II.3 threshold (>=10) -- otherwise they'd be exempt from II.4's
    # lone-session gate and the scenario this test guards against couldn't arise.
    padding_slots = []
    padding_ts = []
    slot_id = 7
    for cid, wd, periods in ((102, 4, range(1, 6)), (103, 4, range(1, 6))):
        for p in periods:
            ts = TimeSlot(slot_id, wd, "S", p)
            padding_slots.append(Slot(slot_id, cid, ts))
            padding_ts.append(ts)
            slot_id += 1

    assigned_teacher = {
        (1, 101): 10, (2, 101): 20, (3, 101): 50, (1, 102): 10, (1, 103): 10,
    }
    slots_by_class = {
        101: [slot_mon, slot_thu, slot_tue, slot_fri, slot_sat1, slot_sat2],
        102: [s for s in padding_slots if s.class_id == 102],
        103: [s for s in padding_slots if s.class_id == 103],
    }

    state = sched._State(remaining_need=defaultdict(int), busy=set())
    sched._put_at(state, slot_mon, 1, 10, role_index)
    sched._put_at(state, slot_thu, 1, 10, role_index)
    sched._put_at(state, slot_tue, 1, 10, role_index)
    sched._put_at(state, slot_fri, 2, 20, role_index)
    sched._put_at(state, slot_sat1, 1, 10, role_index)
    sched._put_at(state, slot_sat2, 3, 50, role_index)
    for s in padding_slots:
        sched._put_at(state, s, 1, 10, role_index)

    teacher_10_total = sum(len(v) for (tid, _wd, _sess), v in state.teacher_session_periods.items() if tid == 10)
    assert teacher_10_total == 14  # Mon1+Thu1+Tue1+Sat1 + 10 padding

    classes = [ClassRoom(101, "6A1"), ClassRoom(102, "6A2"), ClassRoom(103, "6A3")]
    inp = SchedulingInput(
        classes=classes, subjects=subjects,
        teachers=[Teacher(10, "GV Toan"), Teacher(20, "GV Van"), Teacher(50, "GV Ly")],
        need={}, assigned_teacher=assigned_teacher, ban_busy=set(),
        slots=[slot_mon, slot_thu, slot_tue, slot_fri, slot_sat1, slot_sat2] + padding_slots,
        timeslots=[ts_mon, ts_thu, ts_tue, ts_fri, ts_sat1, ts_sat2] + padding_ts,
    )

    config = SchedulingConfig()

    # Exact order used in engine.py's run(): II.3 repair first, then II.4 repair.
    sched._repair_teacher_missing_mandatory_mornings(
        inp, state, role_index, assigned_teacher, slots_by_class,
        config=config, min_weekly_periods=10,
    )
    assert len(state.teacher_session_periods.get((10, 6, "S"), [])) == 1  # II.3 fix landed
    assert state.pinned.get(slot_fri.slot_id) is True

    sched._repair_teacher_lone_sessions(
        inp, state, role_index, assigned_teacher, slots_by_class,
        config=config, min_weekly_periods=15,
    )

    # The pin must have protected Friday morning from being evacuated by the
    # II.4 repair pass, even though teacher 10 is non-exempt (total >= 15) and
    # an evacuate target (Sat, 1 period, room to grow) genuinely exists.
    assert len(state.teacher_session_periods.get((10, 6, "S"), [])) == 1


def test_missing_mandatory_mornings_ignores_low_load_teachers():
    """Teachers with low workload (< 10 periods/week, e.g. 4-6 periods) must NOT be penalized
    for not having classes on all 3 mandatory mornings, because forcing them would fragment into 1-period sessions."""
    slot1 = Slot(1, 101, TimeSlot(1, 2, "S", 1)) # Mon S1
    slot2 = Slot(2, 101, TimeSlot(2, 2, "S", 2)) # Mon S2
    slot3 = Slot(3, 101, TimeSlot(3, 3, "S", 1)) # Tue S1
    slot4 = Slot(4, 101, TimeSlot(4, 3, "S", 2)) # Tue S2

    # Teacher 10 has 4 periods total (all on Mon & Tue, absent on Thu & Fri morning)
    slots = [slot1, slot2, slot3, slot4]
    assigned = {1: 100, 2: 100, 3: 100, 4: 100}
    slot_teacher = {1: 10, 2: 10, 3: 10, 4: 10}

    # Should count 0 missing mandatory mornings for teacher with total=4 (< 10)
    missing = sched._count_teacher_missing_mandatory_mornings(slots, assigned, slot_teacher, mandatory_mornings=(2, 5, 6))
    assert missing == 0


def test_teacher_lone_sessions_heavy_penalty():
    """Lone period sessions for teachers should receive a heavier penalty of 500 per session."""
    slot1 = Slot(1, 101, TimeSlot(1, 2, "S", 1)) # Lone period session for Teacher 10!
    slots = [slot1]
    assigned = {1: 100}
    slot_teacher = {1: 10}
    # min_weekly_periods_for_lone_penalty explicitly 0 here: this test verifies the
    # RAW penalty weights (500/lone-session, 250/lone-day), not the >=15-period
    # exemption (default since Task 1 of 2026-09-02-hard-gate-hdsp-rules) -- the
    # 1-period fixture below is intentionally far under that threshold.
    config = SchedulingConfig(avoid_teacher_lone_periods=True, min_weekly_periods_for_lone_penalty=0)

    pen = sched._teacher_quality_penalty(slots, assigned, slot_teacher, config)
    # 1 lone session (* 500) + 1 lone day (* 250) = 750
    assert pen >= 750, f"Expected penalty >= 750 with 500 lone session weight, got {pen}"



