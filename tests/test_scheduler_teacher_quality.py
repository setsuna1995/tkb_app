import random
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
    offs = sched._assign_off_slots(
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
