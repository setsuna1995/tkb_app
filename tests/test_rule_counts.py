import pytest

from core.models import SchedulingConfig, Slot, Subject, TimeSlot
from tests.rule_helpers import make_input, violations_of

cpsat = pytest.importorskip("core.scheduler.cpsat_model")

QUIET_CONFIG = dict(teacher_off_sessions_per_week=0, mandatory_morning_weekdays=())


def test_rule_counts_match_what_the_detector_finds_for_a_forced_lone_session():
    slots = [Slot(1, 101, TimeSlot(1, 3, "S", 1))]
    inp = make_input(slots, assigned_teacher={(1, 101): 10}, need={(1, 101): 1},
                     config=SchedulingConfig(min_weekly_periods_for_lone_penalty=1, **QUIET_CONFIG))
    result = cpsat.solve_to_result(cpsat.build_model(inp), time_limit_s=10.0)
    assert result.rule_counts["II.4"] == 2  # 1 buổi lẻ + 1 ngày lẻ
    assert result.rule_counts["II.4"] == len(violations_of("II.4", inp, result.assignment))


def test_academic_underload_bucket_uses_the_registry_rule_id():
    slots = [Slot(i, 101, TimeSlot(i, 2, "S", i)) for i in (1, 2, 3)]
    inp = make_input(slots, subjects=[Subject(1, "Toán học"), Subject(2, "Âm nhạc")],
                     assigned_teacher={(1, 101): 10, (2, 101): 20}, need={(1, 101): 1, (2, 101): 1},
                     config=SchedulingConfig(**QUIET_CONFIG))
    built = cpsat.build_model(inp)
    assert "ACAD.MIN" in built.penalty_terms
    assert "_morning_academic_underload" not in built.penalty_terms
