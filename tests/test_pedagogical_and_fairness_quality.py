import pytest
from core.models import (
    ROLE_HDTN, ROLE_THUONG, ClassRoom, SchedulingConfig, SchedulingInput,
    Slot, Subject, Teacher, TimeSlot,
)
from core.scheduler.cpsat_model import build_model
from core.scheduler.cpsat.types import cp_model, _HAS_ORTOOLS


@pytest.mark.skipif(not _HAS_ORTOOLS, reason="CP-SAT unavailable")
def test_subject_dispersion_soft_penalty_presence():
    """Môn 2-3 tiết/tuần khi xếp liền 2 ngày phải sinh penalty term mềm để solver ưu tiên giãn cách."""
    # 1 lớp, các ngày T2, T3, T5 (mỗi ngày 1 tiết sáng)
    ts = [TimeSlot(1, 2, "S", 1), TimeSlot(2, 3, "S", 1), TimeSlot(3, 5, "S", 1)]
    slots = [Slot(1, 101, ts[0]), Slot(2, 101, ts[1]), Slot(3, 101, ts[2])]
    subjects = [Subject(1, "Anh", ROLE_THUONG), Subject(99, "HDTN", ROLE_HDTN)]
    teachers = [Teacher(10, "GV Anh"), Teacher(99, "GV HDTN")]

    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1")],
        subjects=subjects,
        teachers=teachers,
        need={(1, 101): 2, (99, 101): 0},
        assigned_teacher={(1, 101): 10, (99, 101): 99},
        ban_busy=set(),
        slots=slots,
        timeslots=ts,
        config=SchedulingConfig(teacher_off_sessions_per_week=0),
    )

    built = build_model(inp)
    assert "_subject_dispersion" in built.penalty_terms


@pytest.mark.skipif(not _HAS_ORTOOLS, reason="CP-SAT unavailable")
def test_anti_back_to_back_shift_penalty_presence():
    """Khi có slot chiều muộn (tiết 4/5) và sáng hôm sau (tiết 1), kiểm tra có penalty term _back_to_back_shift."""
    ts = [TimeSlot(1, 2, "C", 4), TimeSlot(2, 3, "S", 1)]
    slots = [Slot(1, 101, ts[0]), Slot(2, 101, ts[1])]
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(99, "HDTN", ROLE_HDTN)]
    teachers = [Teacher(10, "GV Toan"), Teacher(99, "GV HDTN")]

    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1")],
        subjects=subjects,
        teachers=teachers,
        need={(1, 101): 2, (99, 101): 0},
        assigned_teacher={(1, 101): 10, (99, 101): 99},
        ban_busy=set(),
        slots=slots,
        timeslots=ts,
        config=SchedulingConfig(teacher_off_sessions_per_week=0),
    )

    built = build_model(inp)
    assert "_back_to_back_shift" in built.penalty_terms


def test_quality_tracking_excess_gaps_and_back_to_back():
    """Kiểm tra các hàm đo lường chất lượng: excess gaps và back-to-back shift."""
    from core.scheduler.quality import (
        _count_teacher_excess_gaps,
        _count_teacher_back_to_back_shifts,
        _count_subject_consecutive_days,
    )

    # 1. Test excess gaps: GV 10 có 1 gap ở T2 (tiết 1, 3 -> span 3, len 2 -> 1 gap)
    # và 1 gap ở T3 (tiết 1, 3 -> span 3, len 2 -> 1 gap) => Tổng 2 gaps (gap thứ 2 = 1, gap thứ 3 = 0)
    slots = [
        Slot(1, 101, TimeSlot(1, 2, "S", 1)),
        Slot(2, 101, TimeSlot(2, 2, "S", 3)),
        Slot(3, 101, TimeSlot(3, 3, "S", 1)),
        Slot(4, 101, TimeSlot(4, 3, "S", 3)),
    ]
    assigned = {1: 1, 2: 1, 3: 1, 4: 1}
    slot_teacher = {1: 10, 2: 10, 3: 10, 4: 10}
    extra1, extra2 = _count_teacher_excess_gaps(slots, assigned, slot_teacher)
    assert extra1 == 1  # Có gap thứ 2
    assert extra2 == 0  # Chưa có gap thứ 3

    # 2. Test back-to-back shift: Chiều T2 tiết 4 và Sáng T3 tiết 1
    slots_b2b = [
        Slot(1, 101, TimeSlot(1, 2, "C", 4)),
        Slot(2, 101, TimeSlot(2, 3, "S", 1)),
    ]
    assigned_b2b = {1: 1, 2: 1}
    slot_teacher_b2b = {1: 10, 2: 10}
    b2b_count = _count_teacher_back_to_back_shifts(slots_b2b, assigned_b2b, slot_teacher_b2b)
    assert b2b_count == 1

    # 3. Test subject consecutive days: Môn 1 học T2 và T3 (liền kề) với need=2
    slots_subj = [
        Slot(1, 101, TimeSlot(1, 2, "S", 1)),
        Slot(2, 101, TimeSlot(2, 3, "S", 1)),
    ]
    assigned_subj = {1: 1, 2: 1}
    need = {(1, 101): 2}
    consec_count = _count_subject_consecutive_days(slots_subj, assigned_subj, need)
    assert consec_count == 1

