from dataclasses import replace

import pytest

from core.models import ROLE_GDTC, ROLE_NANG, SchedulingConfig, Slot, Subject, Teacher, TimeSlot
from core.rules.params import MAX_LOAD_FOR_4CONSEC_PENALTY, Threshold, resolve_effective_params
from tests.rule_helpers import make_input


def _slots():
    return [
        Slot(1, 101, TimeSlot(1, 2, "S", 1)),
        Slot(2, 101, TimeSlot(2, 2, "C", 1)),
        Slot(3, 102, TimeSlot(3, 2, "S", 1)),
    ]


def test_threshold_refuses_silent_relaxation():
    with pytest.raises(ValueError):
        Threshold(declared=3, effective=4)
    assert Threshold(declared=3, effective=4, reason="lớp 9A cần 4 tiết/buổi").effective == 4


def test_no_threshold_is_relaxed_before_solving():
    params = resolve_effective_params(make_input(_slots()))
    assert set(params.max_heavy_consecutive) == {(101, "S"), (101, "C"), (102, "S")}
    assert set(params.max_academic_per_morning) == {101, 102}
    thresholds = [*params.max_heavy_consecutive.values(), *params.max_academic_per_morning.values()]
    assert all(t.effective == t.declared and t.reason == "" for t in thresholds)


def test_values_come_from_config_not_scattered_defaults():
    config = SchedulingConfig(min_weekly_periods_for_lone_penalty=11, max_heavy_consecutive=2,
                              lone_session_exempt_teacher_ids=frozenset({10}))
    params = resolve_effective_params(make_input(_slots(), config=config))
    assert params.min_weekly_periods_for_lone_penalty == 11
    assert params.max_heavy_consecutive[(101, "S")].declared == 2
    assert params.lone_exempt_ids == frozenset({10})
    assert params.max_load_for_4consec_penalty == MAX_LOAD_FOR_4CONSEC_PENALTY


def test_teacher_facts_are_resolved_once():
    teachers = [Teacher(10, "Hiệu trưởng A", role="Hiệu trưởng", pinned_full_day_off=4), Teacher(20, "GV B")]
    inp = make_input(
        _slots(), teachers=teachers,
        assigned_teacher={(1, 101): 10, (2, 101): 20},
        need={(1, 101): 3, (2, 101): 0, (3, 102): 2},
    )
    params = resolve_effective_params(inp)
    assert params.bgh_ids == frozenset({10})
    assert params.pinned_day_offs == {10: 4}
    # need = 0 không tính tải; môn 3 chưa phân công -> id tổng hợp âm, không phải GV thật
    assert params.teacher_load == {10: 3}


def test_role_driven_subject_sets_follow_their_flags():
    subjects = [Subject(1, "Lý", ROLE_NANG), Subject(2, "Thể dục", ROLE_GDTC)]
    on = SchedulingConfig(heavy_subjects_morning_only=True, morning_only_subject_ids=frozenset({5}),
                          avoid_gdtc_consecutive_days=True)
    off = SchedulingConfig(heavy_subjects_morning_only=False, avoid_gdtc_consecutive_days=False)
    params_on = resolve_effective_params(make_input(_slots(), subjects=subjects, config=on))
    params_off = resolve_effective_params(make_input(_slots(), subjects=subjects, config=off))
    assert params_on.morning_only_subject_ids == frozenset({1, 5})
    assert params_on.non_consecutive_subject_ids == frozenset({2})
    assert params_off.morning_only_subject_ids == frozenset()
    assert params_off.non_consecutive_subject_ids == frozenset()


def test_as_effective_counts_against_what_the_model_enforced():
    params = resolve_effective_params(make_input(_slots()))
    widened = replace(params, max_heavy_consecutive={
        (101, "S"): Threshold(declared=3, effective=4, reason="lý do"),
    })
    assert widened.as_effective().max_heavy_consecutive[(101, "S")] == Threshold.unrelaxed(4)
    assert widened.max_heavy_consecutive[(101, "S")].declared == 3


def test_solver_result_carries_the_params_the_model_was_built_with():
    cpsat = pytest.importorskip("core.scheduler.cpsat_model")
    slots = [Slot(1, 101, TimeSlot(1, 3, "S", 1)), Slot(2, 101, TimeSlot(2, 4, "S", 1))]
    inp = make_input(
        slots, assigned_teacher={(1, 101): 10}, need={(1, 101): 2},
        config=SchedulingConfig(teacher_off_sessions_per_week=0, mandatory_morning_weekdays=(),
                                min_weekly_periods_for_lone_penalty=5),
    )
    built = cpsat.build_model(inp)
    result = cpsat.solve_to_result(built, time_limit_s=10.0)
    assert result.effective_params is built.params
    assert built.params == resolve_effective_params(inp)
