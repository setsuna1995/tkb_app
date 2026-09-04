import pytest

from core.models import (
    ROLE_HDTN, ROLE_THUONG, ClassRoom, SchedulingConfig, SchedulingInput,
    Slot, Subject, Teacher, TimeSlot,
)
from core.validation import compute_quota_diff

cpsat = pytest.importorskip("core.scheduler.cpsat_model")


def _tiny_input():
    """1 lớp, 6 ô sáng Thứ 2 (tiết 1-3) và Thứ 3 (tiết 1-3), 2 môn cần 3 tiết mỗi môn.
    Vừa khít 6 ô = 6 tiết, nên mọi ô đều phải có môn."""
    ts = [TimeSlot(i + 1, wd, "S", p) for i, (wd, p) in enumerate(
        [(2, 1), (2, 2), (2, 3), (3, 1), (3, 2), (3, 3)])]
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
    )


def test_solution_meets_every_subject_class_quota():
    inp = _tiny_input()
    built = cpsat.build_model(inp)
    assignment = cpsat.solve(built, time_limit_s=10.0)
    assert assignment is not None, "phải giải được bài toán vừa khít này"

    diff = compute_quota_diff(inp.slots, assignment, inp.need)
    bad = {k: v for k, v in diff.items() if v != 0}
    assert bad == {}, f"sai định mức: {bad}"


def test_each_cell_holds_at_most_one_subject():
    inp = _tiny_input()
    built = cpsat.build_model(inp)
    assignment = cpsat.solve(built, time_limit_s=10.0)
    # assignment là dict slot_id -> subject_id nên "tối đa 1" là bất biến của
    # kiểu dữ liệu; điều cần khẳng định là không ô nào bị bỏ sót ở bài vừa khít.
    assert len(assignment) == len(inp.slots)


def test_leaves_cells_empty_when_there_is_slack():
    """Dư địa > 0: chỉ cần 2 tiết cho 6 ô -> 4 ô phải để trống, không được
    nhồi cho đủ. Engine cũ để trống bằng sentinel -1; ở đây ô trống đơn giản
    là không có mặt trong dict kết quả."""
    inp = _tiny_input()
    inp.need = {(1, 101): 2}
    built = cpsat.build_model(inp)
    assignment = cpsat.solve(built, time_limit_s=10.0)
    assert assignment is not None
    assert len(assignment) == 2
    assert all(sid == 1 for sid in assignment.values())


def test_teacher_never_double_booked():
    """2 lớp, cùng 4 ô sáng T2; 1 GV dạy cả 2 lớp mỗi lớp 2 tiết. Nếu thiếu
    ràng buộc trùng giờ, bộ giải có thể xếp GV đó vào cùng ts_id ở 2 lớp."""
    ts = [TimeSlot(i + 1, 2, "S", i + 1) for i in range(4)]
    slots = [Slot(i + 1, 101, t) for i, t in enumerate(ts)] + \
            [Slot(i + 5, 102, t) for i, t in enumerate(ts)]
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]
    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1"), ClassRoom(102, "6A2")],
        subjects=subjects,
        teachers=[Teacher(10, "GV A")],
        need={(1, 101): 2, (1, 102): 2},
        assigned_teacher={(1, 101): 10, (1, 102): 10},
        ban_busy=set(), slots=slots, timeslots=ts, config=SchedulingConfig(),
    )
    built = cpsat.build_model(inp)
    assignment = cpsat.solve(built, time_limit_s=10.0)
    assert assignment is not None
    from core.validation import find_teacher_conflicts
    assert find_teacher_conflicts(inp.slots, assignment, inp.assigned_teacher) == []


def test_teacher_respects_busy_slots():
    """1 lớp, 4 ô sáng T2; 1 GV dạy 1 môn cần 3/4 tiết (dư 1 ô), GV bị khai
    GV_Bận đúng ô đầu tiên (ts thứ 1). Nếu thiếu ràng buộc GV_Bận, bộ giải có
    thể xếp đúng vào ô bận đó vì không có gì ngăn cản."""
    ts = [TimeSlot(i + 1, 2, "S", i + 1) for i in range(4)]
    slots = [Slot(i + 1, 101, t) for i, t in enumerate(ts)]
    subjects = [Subject(1, "Toan", ROLE_THUONG)]
    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1")],
        subjects=subjects,
        teachers=[Teacher(10, "GV A")],
        need={(1, 101): 3},
        assigned_teacher={(1, 101): 10},
        ban_busy={(10, ts[0].ts_id)}, slots=slots, timeslots=ts,
        config=SchedulingConfig(),
    )
    built = cpsat.build_model(inp)
    assignment = cpsat.solve(built, time_limit_s=10.0)
    assert assignment is not None
    from core.validation import find_teacher_unavailability_violations
    assert find_teacher_unavailability_violations(
        inp.slots, assignment, inp.assigned_teacher, inp.ban_busy) == []


def test_teacher_respects_daily_cap():
    """1 lớp, 4 ô: 3 ô sáng T2 (tiết 1-3) + 1 ô sáng T3 (tiết 1); 1 GV dạy 1
    môn cần đúng 3/4 tiết, max_teacher_periods_per_day=2. Nếu thiếu ràng buộc
    trần tiết/ngày, bộ giải có thể dồn cả 3 tiết vào T2, vượt trần 2 tiết/ngày
    -- trong khi vẫn còn ô T3 để dùng thay."""
    ts = [TimeSlot(1, 2, "S", 1), TimeSlot(2, 2, "S", 2), TimeSlot(3, 2, "S", 3),
          TimeSlot(4, 3, "S", 1)]
    slots = [Slot(i + 1, 101, t) for i, t in enumerate(ts)]
    subjects = [Subject(1, "Toan", ROLE_THUONG)]
    config = SchedulingConfig(max_teacher_periods_per_day=2)
    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1")],
        subjects=subjects,
        teachers=[Teacher(10, "GV A")],
        need={(1, 101): 3},
        assigned_teacher={(1, 101): 10},
        ban_busy=set(), slots=slots, timeslots=ts, config=config,
    )
    built = cpsat.build_model(inp)
    assignment = cpsat.solve(built, time_limit_s=10.0)
    assert assignment is not None
    from core.validation import find_teacher_day_cap_violations
    assert find_teacher_day_cap_violations(
        inp.slots, assignment, inp.assigned_teacher, max_per_day=2) == []
