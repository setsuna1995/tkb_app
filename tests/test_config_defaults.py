from core.models import ScheduleResult, SchedulingConfig


def test_min_weekly_periods_for_lone_penalty_defaults_to_15():
    """II.4's <15 tiết/tuần exemption must be ON by default, not OFF (0)."""
    config = SchedulingConfig()
    assert config.min_weekly_periods_for_lone_penalty == 15


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
