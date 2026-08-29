from core.models import SchedulingConfig, SchedulingInput


def test_scheduling_config_defaults_match_current_hardcoded_behavior():
    config = SchedulingConfig()
    assert config.gdtc_avoid_period == 5
    assert config.chao_co_weekday == 2
    assert config.chao_co_period == 1
    assert config.max_heavy_consecutive == 3
    assert config.max_periods_per_session == 4
    assert config.teacher_off_sessions_per_week == 1
    assert config.forbidden_off_cells == frozenset({(2, "S"), (5, "S"), (6, "S"), (5, "C"), (6, "C")})
    assert config.reserved_off_weekdays_chieu == (5, 6)
    assert config.heavy_subject_priority_periods == 0
    assert config.afternoon_preferred_subject_ids == frozenset()


def test_scheduling_config_accepts_soft_bias_overrides():
    config = SchedulingConfig(heavy_subject_priority_periods=2, afternoon_preferred_subject_ids=frozenset({3, 7}))
    assert config.heavy_subject_priority_periods == 2
    assert config.afternoon_preferred_subject_ids == frozenset({3, 7})


def test_scheduling_input_defaults_to_default_scheduling_config():
    inp = SchedulingInput(
        classes=[], subjects=[], teachers=[], need={}, assigned_teacher={},
        ban_busy=set(), slots=[], timeslots=[],
    )
    assert inp.config == SchedulingConfig()
