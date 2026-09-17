"""Integration tests for CP-SAT solver wired into core.scheduler.engine.run() (Task 8)."""
import os
import pytest

pytestmark = pytest.mark.slow

from core import scheduler as sched
from core.models import SchedulingConfig
from core.validation import compute_quota_diff
from tests.rule_helpers import violations_of
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
def test_sched_run_exclusively_uses_cpsat(conn):
    """Test 1: sched.run() luôn sử dụng solver CP-SAT làm động cơ độc quyền."""
    inp = repo.build_scheduling_input(conn, parity="C", seed=2026)
    result = sched.run(inp)

    assert result.success is True
    assert result.solver_name == "cpsat"


@pytest.mark.slow
def test_cpsat_solution_passes_all_validation_functions(conn):
    """Test 2: CP-SAT cho lời giải hợp lệ qua toàn bộ core/validation.py."""
    inp = repo.build_scheduling_input(conn, parity="C", seed=2026)
    inp.config.cpsat_time_limit_seconds = 15
    result = sched.run(inp)

    assert result.success is True, result.failure_reason
    assert result.solver_name == "cpsat"

    # 1. Quota
    ppw_for_parity = {(s, c, p): n for (s, c, p), n in repo.get_periods_per_week(conn).items()}
    diff = compute_quota_diff(inp.slots, result.assignment, ppw_for_parity, "C")
    bad_quota = {k: v for k, v in diff.items() if v != 0}
    assert bad_quota == {}, f"Quota diff violations: {bad_quota}"

    # 2-9. Mọi ràng buộc cứng mô hình ép phải không có vi phạm hậu kiểm
    for rule_id in ("T.CONFLICT", "T.BUSY", "T.DAY_CAP", "C.GDTC_PERIOD", "C.MORNING_ONLY",
                    "C.HEAVY_CONSEC", "C.NON_CONSEC_DAYS", "C.SUBJECT_CELLS"):
        found = violations_of(rule_id, inp, result.assignment)
        assert found == [], f"{rule_id} violations: {found}"


def test_when_ortools_unavailable_returns_clear_failure(conn, monkeypatch):
    """Test 3: Khi ortools không khả dụng -> trả về ScheduleResult failure rõ ràng."""
    from core.scheduler import cpsat_model
    monkeypatch.setattr(cpsat_model, "_HAS_ORTOOLS", False)

    inp = repo.build_scheduling_input(conn, parity="C", seed=2026)
    result = sched.run(inp)

    assert result.success is False
    assert result.solver_name == "cpsat"
    assert "ortools" in result.failure_reason


def test_when_timeout_zero_returns_failure(conn):
    """Test 4: Khi đặt thời gian quá ngắn (0s) -> trả về ScheduleResult failure từ CP-SAT."""
    inp = repo.build_scheduling_input(conn, parity="C", seed=2026)
    inp.config.cpsat_time_limit_seconds = 0
    result = sched.run(inp)

    assert result.success is False
    assert result.solver_name == "cpsat"
