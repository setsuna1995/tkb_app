import pytest
from core.models import SchedulingConfig, Slot, Teacher, TimeSlot
from core.rules.detectors import (
    detect_teacher_lone_days,
    detect_teacher_lone_sessions,
    detect_teacher_split_days,
)
from tests.rule_helpers import view_and_params


def test_lone_session_on_mandatory_morning_is_accepted():
    """Giáo viên có 1 tiết vào Sáng Thứ 2 (sáng bắt buộc có mặt) -> CHẤP NHẬN, không phạt II.4."""
    # Slot 1: Monday morning period 1 (wd=2, session=S, period=1)
    slot_mon = Slot(1, 101, TimeSlot(1, 2, "S", 1))
    teacher = Teacher(10, "GV Hồng", must_monday=True)
    cfg = SchedulingConfig(
        min_weekly_periods_for_lone_penalty=0,
        strict_morning_weekdays=(2,),
        mandatory_morning_weekdays=(2,),
        min_weekly_periods_for_mandatory_morning=1,
        avoid_teacher_lone_periods=True,
        allow_lone_period_on_mandatory_mornings=True,
    )
    view, params = view_and_params(
        [slot_mon], {1: 1},
        assigned_teacher={(1, 101): 10},
        teachers=[teacher],
        config=cfg,
    )

    # detect_teacher_lone_sessions should NOT report violation on Monday morning
    violations = detect_teacher_lone_sessions(view, params)
    assert violations == [], f"Sáng Thứ 2 bắt buộc có mặt nên chấp nhận 1 tiết lẻ, nhưng lại bị phạt: {violations}"

    # detect_teacher_lone_days should also NOT report violation for Monday
    day_violations = detect_teacher_lone_days(view, params)
    assert day_violations == [], f"Ngày Thứ 2 chỉ có 1 tiết để có mặt chào cờ nên chấp nhận, nhưng lại bị phạt: {day_violations}"


def test_lone_session_on_non_mandatory_session_is_still_violation():
    """Các buổi khác không bắt buộc có mặt (vd Thứ 3) có 1 tiết lẻ thì VẪN PHẠT bình thường."""
    # Slot 1: Tuesday morning period 1 (wd=3)
    slot_tue = Slot(1, 101, TimeSlot(1, 3, "S", 1))
    teacher = Teacher(10, "GV Hồng", must_monday=True)
    cfg = SchedulingConfig(
        min_weekly_periods_for_lone_penalty=0,
        strict_morning_weekdays=(2,),
        mandatory_morning_weekdays=(2,),
        min_weekly_periods_for_mandatory_morning=1,
        avoid_teacher_lone_periods=True,
        allow_lone_period_on_mandatory_mornings=True,
    )
    view, params = view_and_params(
        [slot_tue], {1: 1},
        assigned_teacher={(1, 101): 10},
        teachers=[teacher],
        config=cfg,
    )

    violations = detect_teacher_lone_sessions(view, params)
    assert len(violations) == 1
    assert violations[0].weekday == 3
    assert violations[0].session == "S"

    day_violations = detect_teacher_lone_days(view, params)
    assert len(day_violations) == 1
    assert day_violations[0].weekday == 3


def test_lone_session_on_mandatory_morning_flag_disabled():
    """Nếu tắt cấu hình allow_lone_period_on_mandatory_mornings thì vẫn phạt lẻ Thứ 2."""
    slot_mon = Slot(1, 101, TimeSlot(1, 2, "S", 1))
    teacher = Teacher(10, "GV Hồng", must_monday=True)
    cfg = SchedulingConfig(
        min_weekly_periods_for_lone_penalty=0,
        strict_morning_weekdays=(2,),
        avoid_teacher_lone_periods=True,
        allow_lone_period_on_mandatory_mornings=False,
    )
    view, params = view_and_params(
        [slot_mon], {1: 1},
        assigned_teacher={(1, 101): 10},
        teachers=[teacher],
        config=cfg,
    )

    violations = detect_teacher_lone_sessions(view, params)
    assert len(violations) == 1
    assert violations[0].weekday == 2

    day_violations = detect_teacher_lone_days(view, params)
    assert len(day_violations) == 1
    assert day_violations[0].weekday == 2


def test_split_day_on_mandatory_morning_is_accepted():
    """Giáo viên dạy sáng Thứ 2 (1 tiết) + chiều Thứ 2 (1 tiết) khi bật allow_lone_period_on_mandatory_mornings -> HỢP LỆ, không phạt II.8."""
    slot_s = Slot(1, 101, TimeSlot(1, 2, "S", 1))
    slot_c = Slot(2, 101, TimeSlot(2, 2, "C", 1))
    teacher = Teacher(10, "GV Hồng", must_monday=True)
    cfg = SchedulingConfig(
        min_weekly_periods_for_lone_penalty=0,
        strict_morning_weekdays=(2,),
        mandatory_morning_weekdays=(2,),
        min_weekly_periods_for_mandatory_morning=1,
        avoid_teacher_lone_periods=True,
        allow_lone_period_on_mandatory_mornings=True,
    )
    view, params = view_and_params(
        [slot_s, slot_c], {1: 1, 2: 1},
        assigned_teacher={(1, 101): 10, (2, 101): 10},
        teachers=[teacher],
        config=cfg,
    )

    violations = detect_teacher_split_days(view, params)
    assert violations == [], f"Sáng Thứ 2 bắt buộc có mặt nên ngày chia lẻ S1+C1 được chấp nhận, nhưng lại bị phạt: {violations}"


def test_split_day_on_mandatory_morning_flag_disabled():
    """Nếu tắt allow_lone_period_on_mandatory_mornings thì ngày chia lẻ S1+C1 Thứ 2 vẫn bị phạt II.8."""
    slot_s = Slot(1, 101, TimeSlot(1, 2, "S", 1))
    slot_c = Slot(2, 101, TimeSlot(2, 2, "C", 1))
    teacher = Teacher(10, "GV Hồng", must_monday=True)
    cfg = SchedulingConfig(
        min_weekly_periods_for_lone_penalty=0,
        strict_morning_weekdays=(2,),
        mandatory_morning_weekdays=(2,),
        min_weekly_periods_for_mandatory_morning=1,
        avoid_teacher_lone_periods=True,
        allow_lone_period_on_mandatory_mornings=False,
    )
    view, params = view_and_params(
        [slot_s, slot_c], {1: 1, 2: 1},
        assigned_teacher={(1, 101): 10, (2, 101): 10},
        teachers=[teacher],
        config=cfg,
    )

    violations = detect_teacher_split_days(view, params)
    assert len(violations) == 1
    assert violations[0].weekday == 2


def test_two_shift_school_morning_only_math_literature_no_lone_explosion():
    """Khi trường học 2 buổi ép Toán và Văn chỉ học sáng, CP-SAT không được timeout sớm và không bị bùng nổ buổi lẻ."""
    import sqlite3
    import dataclasses
    from data import repository as repo
    from core.scheduler import cpsat_model
    from core.rules.detectors import detect_teacher_lone_sessions
    from core.rules.view import build_schedule_view
    from core.rules.params import resolve_effective_params

    conn = sqlite3.connect("schools/truong-thcs-2-buoi.db")
    conn.row_factory = sqlite3.Row
    inp = repo.build_scheduling_input(conn, parity="all", week_no=6)
    inp_test = dataclasses.replace(inp, config=dataclasses.replace(inp.config, morning_only_subject_ids=frozenset({1, 2})))

    built = cpsat_model.build_model(inp_test)
    res = cpsat_model.solve_to_result(built, time_limit_s=45.0, workers=4)

    assert res is not None and res.success
    # Pass 1 phải FEASIBLE, không được để II.4 bị nới lỏng do timeout
    assert res.diagnostics.get("pass1_status") == "FEASIBLE"
    assert not any(r["rule_id"] == "II.4" for r in res.relaxed_rules)

    # Kiểm tra số buổi lẻ thực tế: không có vi phạm II.4
    view = build_schedule_view(inp_test, res.assignment)
    params = resolve_effective_params(inp_test)
    lones = detect_teacher_lone_sessions(view, params)
    assert lones == [], f"Phải sạch hoàn toàn vi phạm buổi lẻ II.4, nhưng lại có: {lones}"

