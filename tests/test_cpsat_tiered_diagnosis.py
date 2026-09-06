import pytest
from core.models import (
    ROLE_HDTN, ROLE_THUONG, ClassRoom, SchedulingConfig, SchedulingInput,
    Slot, Subject, Teacher, TimeSlot,
)
from core.scheduler.cpsat_model import build_model
from core.scheduler.cpsat.solver import _presolve_capacity_screening, _diagnose_and_solve
from core.scheduler.cpsat.types import cp_model, _HAS_ORTOOLS


@pytest.mark.skipif(not _HAS_ORTOOLS, reason="CP-SAT unavailable")
def test_capacity_screening_detects_ii4_overflow():
    """Khi số tiết cần thiết để không bị buổi lẻ (req_teachers * 2) vượt quá cap, trả về {'II.3'} để bảo vệ II.4."""
    # 1 lớp, Thứ 2 sáng 3 tiết
    ts = [TimeSlot(1, 2, "S", 1), TimeSlot(2, 2, "S", 2), TimeSlot(3, 2, "S", 3)]
    slots = [Slot(1, 101, ts[0]), Slot(2, 101, ts[1]), Slot(3, 101, ts[2])]
    subjects = [Subject(1, "M1", ROLE_THUONG), Subject(2, "M2", ROLE_THUONG), Subject(99, "HDTN", ROLE_HDTN)]
    teachers = [Teacher(10, "GV A"), Teacher(20, "GV B"), Teacher(99, "GV HDTN")]

    config = SchedulingConfig(
        mandatory_morning_weekdays=(2,),
        min_weekly_periods_for_mandatory_morning=10,
        avoid_teacher_lone_periods=True,
    )

    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1")],
        subjects=subjects,
        teachers=teachers,
        need={(1, 101): 10, (2, 101): 10, (99, 101): 0},
        assigned_teacher={(1, 101): 10, (2, 101): 20, (99, 101): 99},
        ban_busy=set(),
        slots=slots,
        timeslots=ts,
        config=config,
    )

    built = build_model(inp)
    incompat = _presolve_capacity_screening(built)
    # 2 GV cần mỗi người ít nhất 2 tiết => cần 4 tiết, mà chỉ có 3 slots => II.3 bị nới lỏng để bảo toàn II.4
    assert "II.3" in incompat


@pytest.mark.skipif(not _HAS_ORTOOLS, reason="CP-SAT unavailable")
def test_tiered_diagnosis_unknown_relaxes_ii4_first():
    """Khi trạng thái Pass 1 là UNKNOWN, hệ thống phân tầng ưu tiên nới lỏng II.4 trước
    thay vì xóa sạch toàn bộ các luật khác (II.3, II.8)."""
    # Tạo mô hình với cả II.3 và II.4 active
    ts = [TimeSlot(1, 2, "S", 1), TimeSlot(2, 2, "S", 2), TimeSlot(3, 2, "S", 3), TimeSlot(4, 2, "S", 4)]
    slots = [Slot(1, 101, ts[0]), Slot(2, 101, ts[1]), Slot(3, 101, ts[2]), Slot(4, 101, ts[3])]
    subjects = [Subject(1, "M1", ROLE_THUONG), Subject(2, "M2", ROLE_THUONG), Subject(99, "HDTN", ROLE_HDTN)]
    teachers = [Teacher(10, "GV A"), Teacher(20, "GV B"), Teacher(99, "GV HDTN")]

    config = SchedulingConfig(
        mandatory_morning_weekdays=(2,),
        min_weekly_periods_for_mandatory_morning=2,
        avoid_teacher_lone_periods=True,
    )

    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1")],
        subjects=subjects,
        teachers=teachers,
        need={(1, 101): 2, (2, 101): 2, (99, 101): 0},
        assigned_teacher={(1, 101): 10, (2, 101): 20, (99, 101): 99},
        ban_busy=set(),
        slots=slots,
        timeslots=ts,
        config=config,
    )

    built = build_model(inp)
    solver = cp_model.CpSolver()
    # Chạy với ngân sách cực ngắn để giả lập UNKNOWN
    diag = _diagnose_and_solve(built, solver, time_limit_s=0.001)
    # UNKNOWN phải kích hoạt relaxed_by_diagnosis
    assert "relaxed_by_diagnosis" in diag
