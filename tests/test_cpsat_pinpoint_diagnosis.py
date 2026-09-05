import pytest
from core.models import (
    ROLE_HDTN, ROLE_KEP, ROLE_THUONG, ClassRoom, SchedulingConfig, SchedulingInput,
    Slot, Subject, Teacher, TimeSlot,
)

cpsat = pytest.importorskip("core.scheduler.cpsat_model")


def _tiny_input_no_monday():
    """Tạo fixture không có Thứ 2 để ép II.3 vi phạm tất yếu (Deterministic Infeasible).
    Vì strict_morning_weekdays=(2,) mà Thứ 2 không có slot sáng nào cho GV A,
    penalty_terms['II.3'] sẽ chứa NewConstant(1) => gate II.3 = 0 là UNSAT."""
    # Chỉ có Thứ 3 -> Thứ 6 (mỗi ngày 2 tiết sáng)
    ts = []
    slots = []
    slot_id = 1
    for wd in [3, 4, 5, 6]:
        for p in [1, 2]:
            t = TimeSlot(slot_id, wd, "S", p)
            ts.append(t)
            slots.append(Slot(slot_id, 101, t))
            slot_id += 1

    subjects = [
        Subject(1, "Toan", ROLE_THUONG),
        Subject(2, "Ly", ROLE_THUONG),
        Subject(3, "HDTN", ROLE_HDTN),
    ]
    teachers = [
        Teacher(10, "GV A"),
        Teacher(20, "GV B"),
        Teacher(30, "GV C"),
    ]

    config = SchedulingConfig(
        strict_morning_weekdays=(2,),
        avoid_teacher_lone_periods=False,
    )

    return SchedulingInput(
        classes=[ClassRoom(101, "6A1")],
        subjects=subjects,
        teachers=teachers,
        # 4 ngày x 2 tiết = 8 tiết. Mỗi ngày 1 Toán + 1 Lý (hợp lệ với luật trần 1 tiết/môn/ngày)
        need={(1, 101): 4, (2, 101): 4, (3, 101): 0},
        assigned_teacher={(1, 101): 10, (2, 101): 20, (3, 101): 30},
        ban_busy=set(),
        slots=slots,
        timeslots=ts,
        config=config,
    )


def test_diagnose_pass1_optimal_baseline():
    """Khi bài toán hoàn toàn khả thi: Pass 1 thành công ngay, passes_run == 1,
    unsat_core rỗng, không có relaxed_rules."""
    # 6 ngày riêng, mỗi ngày 1 tiết
    ts = [TimeSlot(i + 1, wd, "S", 1) for i, wd in enumerate([2, 3, 4, 5, 6, 7])]
    slots = [Slot(i + 1, 101, t) for i, t in enumerate(ts)]
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]
    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1")],
        subjects=subjects,
        teachers=[Teacher(10, "GV A"), Teacher(20, "GV B")],
        need={(1, 101): 3, (2, 101): 3},
        assigned_teacher={(1, 101): 10, (2, 101): 20},
        ban_busy=set(),
        slots=slots,
        timeslots=ts,
        config=SchedulingConfig(),
    )

    built = cpsat.build_model(inp)
    res = cpsat.solve_to_result(built, time_limit_s=10.0)

    assert res is not None
    assert res.success is True
    assert res.relaxed_rules == []
    assert res.diagnostics.get("pass1_status") in ("OPTIMAL", "FEASIBLE")
    assert res.diagnostics.get("unsat_core") == []
    assert res.diagnostics.get("passes_run") == 1


def test_diagnose_pinpoint_unsat_core_ii3_forced_infeasible():
    """Kiểm tra tripwire: Khi II.3 bị ép bất khả thi, solver phải:
    1. Phát hiện pass1_status == 'INFEASIBLE'.
    2. Trích xuất đúng unsat_core == ['II.3'].
    3. Thư giãn đúng II.3 và đánh dấu proven_infeasible == True trên relaxed_rules.
    4. Trả về ScheduleResult thành công ở Pass 2."""
    inp = _tiny_input_no_monday()
    built = cpsat.build_model(inp)

    # Đảm bảo penalty_terms của II.3 có mặt
    assert "II.3" in built.penalty_terms
    assert len(built.penalty_terms["II.3"]) > 0

    res = cpsat.solve_to_result(built, time_limit_s=10.0)

    assert res is not None
    assert res.success is True
    assert res.diagnostics["pass1_status"] == "INFEASIBLE"
    assert res.diagnostics["unsat_core"] == ["II.3"]
    assert res.diagnostics["passes_run"] == 2

    # relaxed_rules phải có II.3 với proven_infeasible = True
    ii3_relaxed = [r for r in res.relaxed_rules if r.get("rule_id") == "II.3"]
    assert len(ii3_relaxed) == 1
    assert ii3_relaxed[0].get("proven_infeasible") is True


def test_diagnose_multi_gate_keeps_other_gates_hard():
    """Khi II.3 bất khả thi nhưng II.4 khả thi (GV dạy 2 tiết/buổi, không bị buổi lẻ):
    Pass 2 chỉ relax duy nhất II.3, giữ cứng II.4 (vi phạm II.4 vẫn bằng 0)."""
    inp = _tiny_input_no_monday()
    # Với ROLE_KEP, Toán và Lý có thể xếp thành cặp 2 tiết/ngày -> GV A và GV B dạy 2 tiết/buổi (0 buổi lẻ)
    # Lúc này II.4 hoàn toàn khả thi (0 vi phạm), chỉ có II.3 là bị ép vi phạm vì thiếu Thứ 2.
    for s in inp.subjects:
        if s.role_code == ROLE_THUONG:
            s.role_code = ROLE_KEP

    # Bật lại avoid_teacher_lone_periods với ngưỡng tải 4 tiết
    inp.config.avoid_teacher_lone_periods = True
    inp.config.min_weekly_periods_for_lone_penalty = 4

    built = cpsat.build_model(inp)
    assert "II.3" in built.penalty_terms
    assert "II.4" in built.penalty_terms

    res = cpsat.solve_to_result(built, time_limit_s=10.0)

    assert res is not None
    assert res.success is True
    assert res.diagnostics["unsat_core"] == ["II.3"]
    # II.4 không được nằm trong relaxed_rules (vẫn giữ cứng 0 vi phạm)
    relaxed_ids = [r["rule_id"] for r in res.relaxed_rules]
    assert "II.3" in relaxed_ids
    assert "II.4" not in relaxed_ids


def test_diagnose_base_model_infeasible_returns_empty_core_and_none():
    """Khi bài toán bị bất khả thi ngay ở Base Model (ví dụ thiếu slot đáp ứng định mức):
    Solver trả về None, không crash, không lặp vô tận, passes_run <= 4."""
    inp = _tiny_input_no_monday()
    # Ép cần 20 tiết trong khi chỉ có 8 slots
    inp.need = {(1, 101): 20}

    built = cpsat.build_model(inp)
    res = cpsat.solve_to_result(built, time_limit_s=5.0)

    assert res is None
    assignment = cpsat.solve(built, time_limit_s=5.0)
    assert assignment is None


def test_diagnose_timeout_behavior():
    """Khi time_limit_s = 0.0, solver thoát sạch sẽ và trả về None."""
    inp = _tiny_input_no_monday()
    built = cpsat.build_model(inp)
    res = cpsat.solve_to_result(built, time_limit_s=0.0)
    assert res is None
