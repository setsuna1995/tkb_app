from core.models import ScheduleResult, SchedulingConfig


def test_min_weekly_periods_for_lone_penalty_defaults_to_8():
    """II.4's low-load exemption must be ON by default, but narrow: lowered from
    15 to 8 (user decision 2026-09-04) after a real exported timetable showed 26
    lone sessions of which only 3 were counted as violations -- 11 of the
    school's 17 teachers carry 10-14 periods/week, so a threshold of 15 exempted
    two thirds of the staff and let II.4 pass on schedules the school considers
    unacceptable. 8 still exempts genuinely unavoidable cases (a specialist
    teaching 4 periods/week cannot avoid a lone session)."""
    config = SchedulingConfig()
    assert config.min_weekly_periods_for_lone_penalty == 8


def test_heavy_subject_priority_periods_defaults_to_4():
    """II.5 (GDTC+Toán+Văn ưu tiên sáng) must have the morning-priority
    bonus enabled by default, covering the whole typical morning session."""
    config = SchedulingConfig()
    assert config.heavy_subject_priority_periods == 4


def test_schedule_result_has_relaxed_rules_field():
    result = ScheduleResult(success=True)
    assert result.relaxed_rules == []

    result_with_relaxation = ScheduleResult(success=True, relaxed_rules=[{"rule_id": "II.3"}])
    assert result_with_relaxation.relaxed_rules == [{"rule_id": "II.3"}]
