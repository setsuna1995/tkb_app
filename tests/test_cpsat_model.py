import pytest

from core.models import (
    ROLE_GDTC, ROLE_HDTN, ROLE_NANG, ROLE_THUONG, ClassRoom, SchedulingConfig,
    SchedulingInput, Slot, Subject, Teacher, TimeSlot,
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
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]
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
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]
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


# ---------------------------------------------------------------------------
# Task 3: ràng buộc MÔN HỌC (task-3-brief.md). Mỗi test ép đúng 1 luật cắn bằng
# cách cho môn "khan hiếm" (need nhỏ) và môn "lấp chỗ" (need lớn) cùng tranh
# một tập ô vừa khít -- không có ràng buộc thì bộ giải tự nhiên dồn môn khan
# hiếm vào ô cuối cùng được tạo, đúng ô mà luật đang kiểm cấm. Xác nhận bằng
# hàm thẩm định của core/validation.py theo đúng bảng trong brief.
# ---------------------------------------------------------------------------


def test_morning_only_subject_never_scheduled_afternoon():
    """Luật 1: môn bắt buộc buổi sáng. 4 ô sáng (tiết 1-4) + 1 ô chiều (tiết 1)
    của Thứ 2. Môn Văn (morning-only) cần 1 tiết, môn Toán cần 4 -- vừa khít 5
    ô. Không ràng buộc thì bộ giải dồn Văn (need nhỏ) vào ô cuối (ô chiều)."""
    ts = [TimeSlot(i + 1, 2, "S", i + 1) for i in range(4)] + [TimeSlot(5, 2, "C", 1)]
    slots = [Slot(i + 1, 101, t) for i, t in enumerate(ts)]
    subjects = [Subject(1, "Van", ROLE_THUONG), Subject(2, "Toan", ROLE_THUONG),
                Subject(3, "HDTN", ROLE_HDTN)]
    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1")], subjects=subjects,
        teachers=[Teacher(10, "GV A"), Teacher(20, "GV B")],
        need={(1, 101): 1, (2, 101): 4},
        assigned_teacher={(1, 101): 10, (2, 101): 20},
        ban_busy=set(), slots=slots, timeslots=ts,
        config=SchedulingConfig(morning_only_subject_ids=frozenset({1})),
    )
    built = cpsat.build_model(inp)
    assignment = cpsat.solve(built, time_limit_s=10.0)
    assert assignment is not None
    from core.validation import find_morning_only_violations
    assert find_morning_only_violations(inp.slots, assignment, {1}) == []


def test_heavy_subject_morning_only_when_enabled():
    """Luật 2 (không có hàm thẩm định riêng -> assert thủ công). Cùng khung ô
    như test luật 1, nhưng môn khan hiếm là môn Nặng và bật
    heavy_subjects_morning_only -- môn Nặng cấm cứng buổi chiều."""
    ts = [TimeSlot(i + 1, 2, "S", i + 1) for i in range(4)] + [TimeSlot(5, 2, "C", 1)]
    slots = [Slot(i + 1, 101, t) for i, t in enumerate(ts)]
    subjects = [Subject(1, "KHTN", ROLE_NANG), Subject(2, "Toan", ROLE_THUONG),
                Subject(3, "HDTN", ROLE_HDTN)]
    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1")], subjects=subjects,
        teachers=[Teacher(10, "GV A"), Teacher(20, "GV B")],
        need={(1, 101): 1, (2, 101): 4},
        assigned_teacher={(1, 101): 10, (2, 101): 20},
        ban_busy=set(), slots=slots, timeslots=ts,
        config=SchedulingConfig(heavy_subjects_morning_only=True),
    )
    built = cpsat.build_model(inp)
    assignment = cpsat.solve(built, time_limit_s=10.0)
    assert assignment is not None
    slot_by_id = {s.slot_id: s for s in inp.slots}
    bad = [(sid, slot_by_id[sid].ts) for sid, subj in assignment.items()
           if subj == 1 and slot_by_id[sid].ts.session == "C"]
    assert bad == [], f"môn Nặng bị xếp buổi chiều dù heavy_subjects_morning_only=True: {bad}"


def test_gdtc_respects_allowed_periods():
    """GDTC chỉ được tiết 1-4 sáng. Cho lớp 5 ô sáng (tiết 1-5) và cần đúng
    1 tiết GDTC -> bộ giải không được chọn tiết 5."""
    ts = [TimeSlot(i + 1, 2, "S", i + 1) for i in range(5)]
    slots = [Slot(i + 1, 101, t) for i, t in enumerate(ts)]
    subjects = [Subject(1, "GDTC", ROLE_GDTC), Subject(2, "HDTN", ROLE_HDTN),
                Subject(3, "Toan", ROLE_THUONG)]
    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1")], subjects=subjects,
        teachers=[Teacher(10, "GV")],
        need={(1, 101): 1, (3, 101): 4},
        assigned_teacher={(1, 101): 10, (3, 101): 10},
        ban_busy=set(), slots=slots, timeslots=ts,
        config=SchedulingConfig(gdtc_morning_allowed_periods=(1, 2, 3, 4),
                                 max_periods_per_session=5),
    )
    built = cpsat.build_model(inp)
    assignment = cpsat.solve(built, time_limit_s=10.0)
    assert assignment is not None
    from core.validation import find_invalid_gdtc_periods
    assert find_invalid_gdtc_periods(inp.slots, assignment, 1,
                                      inp.config.gdtc_morning_allowed_periods,
                                      inp.config.gdtc_afternoon_allowed_periods) == []


def test_subject_not_scheduled_on_consecutive_days():
    """Luật 4: 3 ngày (Thứ 2,3,4), mỗi ngày 1 ô. Văn (non_consecutive) cần 2
    tiết, Toán cần 1 -- vừa khít 3 ô. Không ràng buộc thì bộ giải dồn Toán
    (need nhỏ) vào ngày cuối (Thứ 4), ép Văn vào Thứ 2+Thứ 3 liền kề (vi
    phạm). Với luật 4 bật, cấu hình khả thi duy nhất là Toán->Thứ 3, Văn->Thứ
    2 + Thứ 4 -- hai ngày này CÁCH nhau 1 ngày nên không "liền kề"."""
    ts = [TimeSlot(1, 2, "S", 1), TimeSlot(2, 3, "S", 1), TimeSlot(3, 4, "S", 1)]
    slots = [Slot(i + 1, 101, t) for i, t in enumerate(ts)]
    subjects = [Subject(1, "Van", ROLE_THUONG), Subject(2, "Toan", ROLE_THUONG),
                Subject(3, "HDTN", ROLE_HDTN)]
    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1")], subjects=subjects,
        teachers=[Teacher(10, "GV A"), Teacher(20, "GV B")],
        need={(1, 101): 2, (2, 101): 1},
        assigned_teacher={(1, 101): 10, (2, 101): 20},
        ban_busy=set(), slots=slots, timeslots=ts,
        config=SchedulingConfig(non_consecutive_subject_ids=frozenset({1})),
    )
    built = cpsat.build_model(inp)
    assignment = cpsat.solve(built, time_limit_s=10.0)
    assert assignment is not None
    from core.validation import find_consecutive_subject_days
    assert find_consecutive_subject_days(inp.slots, assignment, {1}) == []


def test_max_heavy_per_session():
    """Luật 5: 4 ô sáng Thứ 2 (tiết 1-4) + 2 ô sáng Thứ 3 (tiết 1-2) = 6 ô. Môn
    Nặng cần 5 tiết, Toán cần 1 -- vừa khít. Không ràng buộc thì Toán (need
    nhỏ) bị dồn vào ô cuối (Thứ 3 tiết 2), ép Nặng chiếm TRỌN 4 ô Thứ 2 (vượt
    trần max_heavy_per_session mặc định = 3)."""
    ts = [TimeSlot(1, 2, "S", 1), TimeSlot(2, 2, "S", 2), TimeSlot(3, 2, "S", 3),
          TimeSlot(4, 2, "S", 4), TimeSlot(5, 3, "S", 1), TimeSlot(6, 3, "S", 2)]
    slots = [Slot(i + 1, 101, t) for i, t in enumerate(ts)]
    subjects = [Subject(1, "KHTN", ROLE_NANG), Subject(2, "Toan", ROLE_THUONG),
                Subject(3, "HDTN", ROLE_HDTN)]
    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1")], subjects=subjects,
        teachers=[Teacher(10, "GV A"), Teacher(20, "GV B")],
        need={(1, 101): 5, (2, 101): 1},
        assigned_teacher={(1, 101): 10, (2, 101): 20},
        ban_busy=set(), slots=slots, timeslots=ts,
        config=SchedulingConfig(),
    )
    built = cpsat.build_model(inp)
    assignment = cpsat.solve(built, time_limit_s=10.0)
    assert assignment is not None
    from core.validation import find_max_heavy_violations
    assert find_max_heavy_violations(inp.slots, assignment, {1}) == []


def test_max_heavy_consecutive_sliding_window():
    """Luật 6 (không có hàm thẩm định riêng -> assert thủ công). 5 ô sáng Thứ
    2 (tiết 1-5), max_heavy_per_session=5 (không chặn ở luật 5) và
    max_heavy_consecutive=2 để luật 6 là luật thực sự bó buộc. Môn Nặng cần 4
    tiết, Toán cần 1. Không ràng buộc thì Toán (need nhỏ) bị dồn vào ô cuối
    (tiết 5), ép Nặng chiếm tiết 1-4 liên tục (4 > 2). Với luật 6, cấu hình
    khả thi DUY NHẤT là Nặng={1,2,4,5}, Toán=tiết 3 (không có 3 tiết Nặng
    liên tiếp nào)."""
    ts = [TimeSlot(i + 1, 2, "S", i + 1) for i in range(5)]
    slots = [Slot(i + 1, 101, t) for i, t in enumerate(ts)]
    subjects = [Subject(1, "KHTN", ROLE_NANG), Subject(2, "Toan", ROLE_THUONG),
                Subject(3, "HDTN", ROLE_HDTN)]
    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1")], subjects=subjects,
        teachers=[Teacher(10, "GV A"), Teacher(20, "GV B")],
        need={(1, 101): 4, (2, 101): 1},
        assigned_teacher={(1, 101): 10, (2, 101): 20},
        ban_busy=set(), slots=slots, timeslots=ts,
        config=SchedulingConfig(max_heavy_per_session=5, max_heavy_consecutive=2),
    )
    built = cpsat.build_model(inp)
    assignment = cpsat.solve(built, time_limit_s=10.0)
    assert assignment is not None
    slot_by_id = {s.slot_id: s for s in inp.slots}
    heavy_periods = sorted(slot_by_id[sid].ts.period for sid, subj in assignment.items() if subj == 1)
    window = inp.config.max_heavy_consecutive + 1
    last_start = 5 - inp.config.max_heavy_consecutive
    violations = [w for w in range(1, last_start + 1)
                  if all(p in heavy_periods for p in range(w, w + window))]
    assert violations == [], f"có cửa sổ {window} tiết liên tiếp toàn môn Nặng: {violations}"


def test_heavy_subject_avoids_afternoon_period3():
    """Luật 7: 3 ô sáng Thứ 2 (tiết 1-3) + 1 ô chiều Thứ 2 (tiết 3) = 4 ô. Môn
    Nặng cần 1 tiết, Toán cần 3 -- vừa khít. Không ràng buộc thì Nặng (need
    nhỏ) bị dồn vào ô cuối (chiều tiết 3), đúng ô luật 7 cấm."""
    ts = [TimeSlot(1, 2, "S", 1), TimeSlot(2, 2, "S", 2), TimeSlot(3, 2, "S", 3),
          TimeSlot(4, 2, "C", 3)]
    slots = [Slot(i + 1, 101, t) for i, t in enumerate(ts)]
    subjects = [Subject(1, "KHTN", ROLE_NANG), Subject(2, "Toan", ROLE_THUONG),
                Subject(3, "HDTN", ROLE_HDTN)]
    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1")], subjects=subjects,
        teachers=[Teacher(10, "GV A"), Teacher(20, "GV B")],
        need={(1, 101): 1, (2, 101): 3},
        assigned_teacher={(1, 101): 10, (2, 101): 20},
        ban_busy=set(), slots=slots, timeslots=ts,
        config=SchedulingConfig(),
    )
    built = cpsat.build_model(inp)
    assignment = cpsat.solve(built, time_limit_s=10.0)
    assert assignment is not None
    from core.validation import find_heavy_afternoon_period3_violations
    assert find_heavy_afternoon_period3_violations(inp.slots, assignment, {1}) == []


def test_subject_class_allowed_cells_rule():
    """Luật 8: lớp chỉ được xếp môn Văn vào Thứ 3 sáng (không được Thứ 2
    sáng). Ô Thứ 3 (cho phép) tạo TRƯỚC, ô Thứ 2 (cấm) tạo SAU -- không ràng
    buộc thì bộ giải dồn tiết Văn duy nhất vào ô cuối (Thứ 2, ô bị cấm)."""
    ts = [TimeSlot(1, 3, "S", 1), TimeSlot(2, 2, "S", 1)]
    slots = [Slot(i + 1, 101, t) for i, t in enumerate(ts)]
    subjects = [Subject(1, "Van", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]
    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1")], subjects=subjects,
        teachers=[Teacher(10, "GV A")],
        need={(1, 101): 1},
        assigned_teacher={(1, 101): 10},
        ban_busy=set(), slots=slots, timeslots=ts,
        config=SchedulingConfig(),
        subject_class_allowed_cells={(1, 101): frozenset({(3, "S")})},
    )
    built = cpsat.build_model(inp)
    assignment = cpsat.solve(built, time_limit_s=10.0)
    assert assignment is not None
    from core.validation import find_subject_class_rule_violations
    rules = [{"subject_id": 1, "class_ids": [101], "cells": [(3, "S")]}]
    assert find_subject_class_rule_violations(inp.slots, assignment, rules) == []
