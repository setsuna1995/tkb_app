import pytest
from core.models import (
    ClassRoom, SchedulingConfig, SchedulingInput, Slot, Subject, Teacher, TimeSlot, ROLE_HDTN
)
import core.scheduler.cpsat_model as cpsat


def test_teacher_normal_load_cannot_exceed_single_off_session():
    """GV tải 12 tiết với config off=1 không được nghỉ > 1 buổi trong các buổi trường học,
    phải dạy ít nhất 7 buổi trong 8 buổi trường học, và không được trống cả sáng T5 lẫn sáng T6."""
    slots = []
    ts_list = []
    slot_id = 1
    # 5 sáng (T2..T6, 4 tiết/buổi) + 3 chiều (T2..T4, 3 tiết/buổi) = 29 slots
    for wd in range(2, 7):
        for p in range(1, 5):
            ts = TimeSlot(ts_id=slot_id, weekday=wd, session="S", period=p)
            ts_list.append(ts)
            slots.append(Slot(slot_id=slot_id, class_id=1, ts=ts))
            slot_id += 1
    for wd in (2, 3, 4):
        for p in range(1, 4):
            ts = TimeSlot(ts_id=slot_id, weekday=wd, session="C", period=p)
            ts_list.append(ts)
            slots.append(Slot(slot_id=slot_id, class_id=1, ts=ts))
            slot_id += 1

    subjects = [
        Subject(1, "M1"), Subject(2, "M2"), Subject(3, "M3"),
        Subject(4, "M4"), Subject(5, "M5"), Subject(6, "M6"), Subject(7, "M7"),
        Subject(99, "HĐTN", role_code=ROLE_HDTN),
    ]
    # M1, M2, M3 cho Thầy Khu (12 tiết)
    # M4, M5, M6, M7 cho GV 1 (17 tiết)
    need = {(1, 1): 4, (2, 1): 4, (3, 1): 4, (4, 1): 4, (5, 1): 4, (6, 1): 4, (7, 1): 5, (99, 1): 0}
    assigned_teacher = {
        (1, 1): 13, (2, 1): 13, (3, 1): 13,
        (4, 1): 1, (5, 1): 1, (6, 1): 1, (7, 1): 1,
        (99, 1): 1
    }
    teachers = [Teacher(1, "GV 1"), Teacher(13, "Thầy Khu")]
    config = SchedulingConfig(
        teacher_off_sessions_per_week=1,
        teacher_off_sessions_mode="hard",
        reserved_off_weekdays_chieu=(5, 6),
        strict_morning_weekdays=(2,),
    )
    inp = SchedulingInput(
        classes=[ClassRoom(1, "6A")],
        subjects=subjects,
        teachers=teachers,
        slots=slots,
        timeslots=ts_list,
        need=need,
        assigned_teacher=assigned_teacher,
        ban_busy=set(),
        config=config,
    )
    built = cpsat.build_model(inp)
    res = cpsat.solve_to_result(built, time_limit_s=10.0)
    assert res is not None and res.success is True

    # Lấy các ô mà Thầy Khu (GV 13) được phân công
    khu_slots = [s for s in slots if assigned_teacher.get((res.assignment.get(s.slot_id), 1)) == 13]
    khu_sessions = sorted({(s.ts.weekday, s.ts.session) for s in khu_slots})

    # Thầy Khu không được trống cả sáng T5 lẫn sáng T6
    assert (5, "S") in khu_sessions or (6, "S") in khu_sessions, (
        f"Thầy Khu bị trống cả sáng T5 và sáng T6! Các buổi dạy: {khu_sessions}"
    )
    # Thầy Khu không được nghỉ quá 1 buổi trong 8 buổi trường học (chỉ nghỉ tối đa 1 buổi)
    # Tức là phải dạy ít nhất 7 buổi!
    assert len(khu_sessions) >= 7, (
        f"Thầy Khu chỉ dạy {len(khu_sessions)} buổi (phải dạy >= 7 buổi do chỉ được nghỉ tối đa 1 buổi)! Các buổi dạy: {khu_sessions}"
    )
