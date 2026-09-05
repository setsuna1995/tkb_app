"""Integration tests for CP-SAT solver wired into core.scheduler.engine.run() (Task 8)."""
import os
import pytest

pytestmark = pytest.mark.slow

from core import scheduler as sched
from core.models import SchedulingConfig
from core.validation import (
    compute_quota_diff,
    find_consecutive_subject_days,
    find_invalid_gdtc_periods,
    find_max_heavy_violations,
    find_morning_only_violations,
    find_subject_class_rule_violations,
    find_teacher_conflicts,
    find_teacher_day_cap_violations,
    find_teacher_unavailability_violations,
)
from core.scheduler.quality import (
    _count_teacher_missing_mandatory_mornings,
    _count_teacher_lone_sessions,
    _count_teacher_split_sessions,
    _count_teacher_gaps,
    _count_teacher_4_consecutive_mornings,
)
from data import db, repository as repo
from io_excel.importer import import_xlsm

FIXTURE = os.path.join(os.path.dirname(__file__), "..", "io_excel", "sample_school.xlsm")


@pytest.fixture()
def conn(tmp_path):
    connection = db.get_connection(str(tmp_path / "test.db"))
    db.init_db(connection)
    import_xlsm(connection, FIXTURE)
    yield connection
    connection.close()


@pytest.mark.slow
def test_use_cpsat_false_preserves_legacy_engine_behavior(conn):
    """Test 1 (Task 8): use_cpsat=False không đổi gì so với engine cũ."""
    inp = repo.build_scheduling_input(conn, parity="C", seed=2026)
    inp.config.use_cpsat = False
    result = sched.run(inp)

    assert result.success is True
    assert result.solver_name == "heuristic"
    assert result.attempts_tried >= 1


@pytest.mark.slow
def test_cpsat_solution_passes_all_validation_functions(conn):
    """Test 2 (Task 8): use_cpsat=True cho lời giải hợp lệ qua toàn bộ core/validation.py."""
    inp = repo.build_scheduling_input(conn, parity="C", seed=2026)
    inp.config.use_cpsat = True
    inp.config.cpsat_time_limit_seconds = 5
    result = sched.run(inp)

    assert result.success is True, result.failure_reason
    assert result.solver_name == "cpsat"

    # 1. Quota
    ppw_for_parity = {(s, c, p): n for (s, c, p), n in repo.get_periods_per_week(conn).items()}
    diff = compute_quota_diff(inp.slots, result.assignment, ppw_for_parity, "C")
    bad_quota = {k: v for k, v in diff.items() if v != 0}
    assert bad_quota == {}, f"Quota diff violations: {bad_quota}"

    # 2. Teacher conflicts
    conflicts = find_teacher_conflicts(inp.slots, result.assignment, inp.assigned_teacher)
    assert conflicts == [], f"Teacher conflicts: {conflicts}"

    # 3. Teacher unavailability
    unavail = find_teacher_unavailability_violations(inp.slots, result.assignment, inp.assigned_teacher, inp.ban_busy)
    assert unavail == [], f"Unavailability violations: {unavail}"

    # 4. Teacher day cap
    day_cap = find_teacher_day_cap_violations(
        inp.slots, result.assignment, inp.assigned_teacher, inp.config.max_teacher_periods_per_day
    )
    assert day_cap == [], f"Day cap violations: {day_cap}"

    # 5. GDTC periods
    gdtc_id = next((s.subject_id for s in inp.subjects if s.role_code == 4), None)
    if gdtc_id is not None:
        gdtc_violations = find_invalid_gdtc_periods(
            inp.slots, result.assignment, gdtc_id,
            morning_allowed=inp.config.gdtc_morning_allowed_periods,
            afternoon_allowed=inp.config.gdtc_afternoon_allowed_periods,
        )
        assert gdtc_violations == [], f"GDTC period violations: {gdtc_violations}"

    # 6. Morning only
    morning_only_ids = set(inp.config.morning_only_subject_ids)
    if inp.config.heavy_subjects_morning_only:
        morning_only_ids |= {s.subject_id for s in inp.subjects if s.role_code in (1, 3)}
    morning_violations = find_morning_only_violations(
        inp.slots, result.assignment, morning_only_ids
    )
    assert morning_violations == [], f"Morning only violations: {morning_violations}"

    # 7. Max heavy
    heavy_ids = {s.subject_id for s in inp.subjects if s.role_code in (1, 3)}
    heavy_violations = find_max_heavy_violations(
        inp.slots, result.assignment, heavy_ids,
        max_consecutive=inp.config.max_heavy_consecutive,
    )
    assert heavy_violations == [], f"Max heavy violations: {heavy_violations}"

    # 8. Consecutive days
    consec_violations = find_consecutive_subject_days(
        inp.slots, result.assignment, target_subject_ids=set(inp.config.non_consecutive_subject_ids)
    )
    assert consec_violations == [], f"Consecutive days violations: {consec_violations}"

    # 9. Subject class rules
    rules = repo.list_subject_class_rules(conn)
    sub_cls_violations = find_subject_class_rule_violations(
        inp.slots, result.assignment, rules
    )
    assert sub_cls_violations == [], f"Subject class rule violations: {sub_cls_violations}"


@pytest.mark.slow
def test_cpsat_does_not_lose_to_legacy_engine_on_any_metric(conn):
    """Test 3 (Task 8): CP-SAT có tổng điểm phạt chất lượng thấp hơn vượt trội so với engine cũ."""
    from core.scheduler.quality import _teacher_quality_penalty

    inp_legacy = repo.build_scheduling_input(conn, parity="C", seed=2026)
    inp_legacy.config.use_cpsat = False
    res_legacy = sched.run(inp_legacy)
    assert res_legacy.success is True

    inp_cpsat = repo.build_scheduling_input(conn, parity="C", seed=2026)
    inp_cpsat.config.use_cpsat = True
    inp_cpsat.config.cpsat_time_limit_seconds = 15
    res_cpsat = sched.run(inp_cpsat)
    assert res_cpsat.success is True
    assert res_cpsat.solver_name == "cpsat"

    from core.scheduler.placement import _build_effective_assigned_teacher
    eff_assigned = _build_effective_assigned_teacher(inp_cpsat)
    slot_teacher_legacy = {s.slot_id: eff_assigned.get((res_legacy.assignment.get(s.slot_id), s.class_id))
                          for s in inp_legacy.slots if s.slot_id in res_legacy.assignment}
    slot_teacher_cpsat = {s.slot_id: eff_assigned.get((res_cpsat.assignment.get(s.slot_id), s.class_id))
                         for s in inp_cpsat.slots if s.slot_id in res_cpsat.assignment}

    cfg = inp_cpsat.config
    pen_legacy = _teacher_quality_penalty(inp_legacy.slots, res_legacy.assignment, slot_teacher_legacy, cfg)
    pen_cpsat = _teacher_quality_penalty(inp_cpsat.slots, res_cpsat.assignment, slot_teacher_cpsat, cfg)
    assert pen_cpsat < pen_legacy, f"Tổng điểm phạt CP-SAT ({pen_cpsat}) không tốt hơn legacy ({pen_legacy})"

    # Các tiêu chí HĐSP chính CP-SAT đều vượt trội so với engine cũ
    assert _count_teacher_gaps(inp_cpsat.slots, res_cpsat.assignment, slot_teacher_cpsat) <= \
           _count_teacher_gaps(inp_legacy.slots, res_legacy.assignment, slot_teacher_legacy)
    assert _count_teacher_4_consecutive_mornings(inp_cpsat.slots, res_cpsat.assignment, slot_teacher_cpsat) <= \
           _count_teacher_4_consecutive_mornings(inp_legacy.slots, res_legacy.assignment, slot_teacher_legacy)


def test_fallback_when_ortools_unavailable(conn, monkeypatch):
    """Test 4 (Task 8): Khi ortools không khả dụng -> fallback êm sang engine cũ."""
    from core.scheduler import cpsat_model
    monkeypatch.setattr(cpsat_model, "_HAS_ORTOOLS", False)

    inp = repo.build_scheduling_input(conn, parity="C", seed=2026)
    inp.config.use_cpsat = True
    result = sched.run(inp)

    assert result.success is True
    assert result.solver_name == "heuristic"


def test_fallback_when_timeout(conn):
    """Test 5 (Task 8): Khi đặt thời gian quá ngắn (0s) -> fallback êm sang engine cũ."""
    inp = repo.build_scheduling_input(conn, parity="C", seed=2026)
    inp.config.use_cpsat = True
    inp.config.cpsat_time_limit_seconds = 0
    result = sched.run(inp)

    assert result.success is True
    assert result.solver_name == "heuristic"
