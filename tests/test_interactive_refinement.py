import pytest
from core.models import (
    ROLE_HDTN, ROLE_THUONG, ClassRoom, SchedulingConfig, SchedulingInput,
    Slot, Subject, Teacher, TimeSlot,
)
from core.scheduler import cpsat_model as cpsat
from core.scheduler.refinement import compute_candidate_metrics, validate_and_swap_slots
from data.repositories.builder import build_scheduling_input
from data.db import init_db, get_connection
import sqlite3


@pytest.fixture
def mem_conn():
    conn = get_connection(":memory:")
    init_db(conn)
    return conn


def _setup_tiny_input(locked_slots=None, reference_assignment=None):
    ts = [TimeSlot(i + 1, wd, "S", 1) for i, wd in enumerate([2, 3, 4, 5, 6, 7])]
    slots = [Slot(i + 1, 101, t) for i, t in enumerate(ts)]
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]
    return SchedulingInput(
        classes=[ClassRoom(101, "6A1")],
        subjects=subjects,
        teachers=[Teacher(10, "GV A"), Teacher(20, "GV B")],
        need={(1, 101): 3, (2, 101): 3},
        assigned_teacher={(1, 101): 10, (2, 101): 20},
        ban_busy=set(), slots=slots, timeslots=ts,
        config=SchedulingConfig(),
        locked_slots=locked_slots or {},
        reference_assignment=reference_assignment or {},
    )


def test_locked_slots_enforced_in_cpsat():
    # Khóa slot 3 (Thứ 4 sáng tiết 1) cố định cho môn Toán (id=1)
    inp = _setup_tiny_input(locked_slots={3: 1})
    built = cpsat.build_model(inp)
    assignment = cpsat.solve(built, time_limit_s=10.0)
    assert assignment is not None
    assert assignment[3] == 1, "Slot 3 bị khóa phải luôn được gán môn Toán (id=1)"

    # Khóa slot 3 (Thứ 4 sáng tiết 1) cố định cho môn HDTN (id=2)
    inp2 = _setup_tiny_input(locked_slots={3: 2})
    built2 = cpsat.build_model(inp2)
    assignment2 = cpsat.solve(built2, time_limit_s=10.0)
    assert assignment2 is not None
    assert assignment2[3] == 2, "Slot 3 bị khóa phải luôn được gán môn HDTN (id=2)"


def test_build_scheduling_input_passes_locked_and_reference(mem_conn):
    locked = {1: 1, 2: 2}
    ref = {1: 1, 2: 2, 3: 1}
    inp = build_scheduling_input(
        mem_conn,
        locked_slots=locked,
        reference_assignment=ref,
    )
    assert inp.locked_slots == locked
    assert inp.reference_assignment == ref


def test_compute_candidate_metrics():
    inp = _setup_tiny_input()
    built = cpsat.build_model(inp)
    res = cpsat.solve_to_result(built, time_limit_s=10.0)
    metrics = compute_candidate_metrics(inp, res)
    assert "health_score" in metrics
    assert "hole_periods" in metrics
    assert "is_valid" in metrics
    assert metrics["is_valid"] is True


def test_smart_swap_validation():
    inp = _setup_tiny_input()
    # Giả lập assignment: slot 1 -> Toan (1), slot 2 -> HDTN (2)
    assignment = {1: 1, 2: 2, 3: 1, 4: 2, 5: 1, 6: 2}
    
    # 1. Đổi hợp lệ giữa slot 1 và slot 2
    ok, msg, new_ass = validate_and_swap_slots(assignment, 1, 2, inp)
    assert ok is True
    assert new_ass[1] == 2
    assert new_ass[2] == 1

    # 2. Không đổi khi 1 ô bị khóa
    inp.locked_slots = {1: 1}
    ok, msg, _ = validate_and_swap_slots(assignment, 1, 2, inp)
    assert ok is False
    assert "bị khóa" in msg

    # 3. Không đổi khi GV bị bận
    inp.locked_slots = {}
    # GV Toán (id=10) bận tại timeslot của slot 2 (ts_id=2)
    inp.ban_busy = {(10, 2)}
    ok, msg, _ = validate_and_swap_slots(assignment, 1, 2, inp)
    assert ok is False
    assert "báo bận" in msg


def test_must_monday_enforced_and_respects_busy():
    ts = [
        TimeSlot(1, 2, "S", 1),  # T2 P1 (HĐTN chào cờ)
        TimeSlot(2, 2, "S", 2),  # T2 P2
        TimeSlot(3, 3, "S", 1),
        TimeSlot(4, 4, "S", 1),
        TimeSlot(5, 5, "S", 1),
        TimeSlot(6, 6, "S", 1),
        TimeSlot(7, 7, "S", 1),
    ]
    slots = [Slot(i + 1, 101, t) for i, t in enumerate(ts)]
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]
    
    # 1. GV A (id=10) có must_monday=True -> Bắt buộc phải có tiết sáng Thứ 2 (slot 2)
    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1")],
        subjects=subjects,
        teachers=[Teacher(10, "GV A", must_monday=True), Teacher(20, "GV B", must_monday=False)],
        need={(1, 101): 3, (2, 101): 4},
        assigned_teacher={(1, 101): 10, (2, 101): 20},
        ban_busy=set(), slots=slots, timeslots=ts,
        config=SchedulingConfig(),
    )
    built = cpsat.build_model(inp)
    assignment = cpsat.solve(built, time_limit_s=10.0)
    assert assignment is not None
    assert assignment[2] == 1, "GV A có must_monday=True phải được xếp tiết sáng Thứ 2 (slot 2)"

    # 2. GV A có must_monday=True nhưng bị bận toàn bộ slot có thể dạy sáng T2 (ts_id=2)
    # -> Tôn trọng GV_Ban, không bị lỗi infeasible và không ép xếp vào slot bận
    inp_busy = SchedulingInput(
        classes=[ClassRoom(101, "6A1")],
        subjects=subjects,
        teachers=[Teacher(10, "GV A", must_monday=True), Teacher(20, "GV B", must_monday=False)],
        need={(1, 101): 3, (2, 101): 4},
        assigned_teacher={(1, 101): 10, (2, 101): 20},
        ban_busy={(10, 2)},  # GV A bận slot 2
        slots=slots, timeslots=ts,
        config=SchedulingConfig(),
    )
    built_busy = cpsat.build_model(inp_busy)
    assignment_busy = cpsat.solve(built_busy, time_limit_s=10.0)
    assert assignment_busy is not None
    assert assignment_busy[2] == 2, "GV A bận slot 2 thì tôn trọng lịch bận, xếp môn khác"


def test_find_valid_swap_candidates():
    from core.scheduler.refinement import find_valid_swap_candidates
    inp = _setup_tiny_input()
    assignment = {1: 1, 2: 2, 3: 1, 4: 2, 5: 1, 6: 2}
    # Tìm các ứng viên có thể đổi với slot 1 (Toan)
    candidates = find_valid_swap_candidates(assignment, 1, inp)
    assert len(candidates) > 0
    # Các ứng viên phải có môn khác (HDTN id=2)
    for c in candidates:
        assert c["subject_id"] == 2
        assert c["slot_id"] in [2, 4, 6]



