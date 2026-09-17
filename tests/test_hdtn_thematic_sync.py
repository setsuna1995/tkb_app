import pytest
from core.models import (
    ClassRoom, Subject, Teacher, TimeSlot, Slot,
    SchedulingInput, SchedulingConfig, ROLE_HDTN, ROLE_THUONG,
)
from core.scheduler import cpsat_model


def _create_multi_class_input(thematic_mode="fixed", thematic_wd=2, thematic_sess="S", thematic_start_p=1, shared_teacher=False):
    # 2 classes: 6A1, 6A2
    classes = [ClassRoom(1, "6A1"), ClassRoom(2, "6A2")]
    subjects = [
        Subject(1, "HDTN", ROLE_HDTN),
        Subject(2, "Toan", ROLE_THUONG),
        Subject(3, "Van", ROLE_THUONG),
    ]
    t1 = Teacher(10, "GV1")
    t2 = Teacher(20, "GV2")
    teachers = [t1, t2]

    # Need: HDTN 3 periods each class, Toan 2 periods, Van 2 periods
    need = {
        (1, 1): 3, (2, 1): 2, (3, 1): 2,
        (1, 2): 3, (2, 2): 2, (3, 2): 2,
    }
    if shared_teacher:
        # Teacher 10 teaches HDTN for BOTH classes
        assigned_teacher = {
            (1, 1): 10, (2, 1): 20, (3, 1): 20,
            (1, 2): 10, (2, 2): 10, (3, 2): 10,
        }
    else:
        assigned_teacher = {
            (1, 1): 10, (2, 1): 20, (3, 1): 20,
            (1, 2): 20, (2, 2): 10, (3, 2): 10,
        }

    # Slots: Monday (2) and Tuesday (3), Morning (S), 5 periods each
    timeslots = []
    ts_id = 1
    for wd in (2, 3):
        for p in range(1, 6):
            timeslots.append(TimeSlot(ts_id, wd, "S", p))
            ts_id += 1

    slots = []
    slot_id = 1
    for cls in classes:
        for ts in timeslots:
            slots.append(Slot(slot_id, cls.class_id, ts))
            slot_id += 1

    inp = SchedulingInput(
        classes=classes,
        subjects=subjects,
        teachers=teachers,
        need=need,
        assigned_teacher=assigned_teacher,
        ban_busy=set(),
        slots=slots,
        timeslots=timeslots,
        hdtn_thematic_week=True,
        hdtn_thematic_mode=thematic_mode,
        hdtn_thematic_weekday=thematic_wd,
        hdtn_thematic_session=thematic_sess,
        hdtn_thematic_start_period=thematic_start_p,
        config=SchedulingConfig(teacher_off_sessions_per_week=0, max_periods_per_session=5),
    )
    return inp


def test_hdtn_thematic_fixed_mode_syncs_all_classes():
    inp = _create_multi_class_input(thematic_mode="fixed", thematic_wd=2, thematic_sess="S", thematic_start_p=1)
    built = cpsat_model.build_model(inp)
    assignment = cpsat_model.solve(built, time_limit_s=10.0)
    assert assignment is not None, "Phải giải được lịch với chế độ cố định"

    slot_by_id = {s.slot_id: s for s in inp.slots}
    c1_hdtn_slots = [slot_by_id[sid] for sid, sub_id in assignment.items() if sub_id == 1 and slot_by_id[sid].class_id == 1]
    c2_hdtn_slots = [slot_by_id[sid] for sid, sub_id in assignment.items() if sub_id == 1 and slot_by_id[sid].class_id == 2]

    assert len(c1_hdtn_slots) == 3
    assert len(c2_hdtn_slots) == 3

    # Check exact slots: Monday morning periods 1, 2, 3
    c1_coords = sorted((s.ts.weekday, s.ts.session, s.ts.period) for s in c1_hdtn_slots)
    c2_coords = sorted((s.ts.weekday, s.ts.session, s.ts.period) for s in c2_hdtn_slots)

    expected = [(2, "S", 1), (2, "S", 2), (2, "S", 3)]
    assert c1_coords == expected
    assert c2_coords == expected


def test_hdtn_thematic_auto_mode_syncs_all_classes():
    inp = _create_multi_class_input(thematic_mode="auto")
    built = cpsat_model.build_model(inp)
    assignment = cpsat_model.solve(built, time_limit_s=10.0)
    assert assignment is not None, "Phải giải được lịch với chế độ tự động đồng bộ"

    slot_by_id = {s.slot_id: s for s in inp.slots}
    c1_hdtn_slots = [slot_by_id[sid] for sid, sub_id in assignment.items() if sub_id == 1 and slot_by_id[sid].class_id == 1]
    c2_hdtn_slots = [slot_by_id[sid] for sid, sub_id in assignment.items() if sub_id == 1 and slot_by_id[sid].class_id == 2]

    assert len(c1_hdtn_slots) == 3
    assert len(c2_hdtn_slots) == 3

    c1_coords = sorted((s.ts.weekday, s.ts.session, s.ts.period) for s in c1_hdtn_slots)
    c2_coords = sorted((s.ts.weekday, s.ts.session, s.ts.period) for s in c2_hdtn_slots)

    # Both classes MUST have the exact same coords
    assert c1_coords == c2_coords, f"Hai lớp phải đồng bộ cùng buổi, thứ, tiết: c1={c1_coords}, c2={c2_coords}"

    # And it must be 3 contiguous periods
    wd, sess, p1 = c1_coords[0]
    assert c1_coords == [(wd, sess, p1), (wd, sess, p1 + 1), (wd, sess, p1 + 2)]


def test_hdtn_thematic_shared_teacher_allowed():
    # 1 teacher teaches HDTN for both classes, both classes sync at the same time
    inp = _create_multi_class_input(thematic_mode="fixed", thematic_wd=2, thematic_sess="S", thematic_start_p=1, shared_teacher=True)
    built = cpsat_model.build_model(inp)
    assignment = cpsat_model.solve(built, time_limit_s=10.0)
    assert assignment is not None, "1 GV phụ trách HĐTN cho nhiều lớp trong sự kiện chung phải giải thành công, không bị coi là xung đột trùng lịch"

    slot_by_id = {s.slot_id: s for s in inp.slots}
    # Check that in Monday morning p=1,2,3 both classes have HDTN (subject_id = 1)
    for sid, sub_id in assignment.items():
        s = slot_by_id[sid]
        if s.ts.weekday == 2 and s.ts.session == "S" and s.ts.period in (1, 2, 3):
            assert sub_id == 1, f"Slot {s.slot_id} của lớp {s.class_id} tại tiết {s.ts.period} phải là HĐTN"

