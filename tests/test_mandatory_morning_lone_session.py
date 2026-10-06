import pytest
from core.models import SchedulingConfig, Slot, Teacher, TimeSlot
from core.rules.detectors import detect_teacher_lone_days, detect_teacher_lone_sessions
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
