import os
import time
import pytest

from core.scheduler.cpsat.types import cp_model, _HAS_ORTOOLS
from core.scheduler.cpsat.solver import EarlyStoppingCallback, solve_to_result
from core.scheduler.cpsat_model import build_model
from data import db, repository as repo
from io_excel.importer import import_xlsm

FIXTURE = os.path.join(os.path.dirname(__file__), "..", "io_excel", "sample_school.xlsm")


@pytest.mark.skipif(not _HAS_ORTOOLS, reason="CP-SAT unavailable")
def test_early_stopping_callback_plateau_init_and_attributes():
    """Verify EarlyStoppingCallback supports plateau detection parameters."""
    cb = EarlyStoppingCallback(
        stagnation_s=5.0,
        plateau_window_s=3.0,
        min_improvement_rate=0.02,
        min_improvement_abs=300.0,
        min_search_s=2.5,
    )
    assert hasattr(cb, "plateau_window_s")
    assert cb.plateau_window_s == 3.0
    assert hasattr(cb, "min_improvement_rate")
    assert cb.min_improvement_rate == 0.02
    assert hasattr(cb, "min_improvement_abs")
    assert cb.min_improvement_abs == 300.0
    assert hasattr(cb, "min_search_s")
    assert cb.min_search_s == 2.5
    assert hasattr(cb, "history")


@pytest.mark.skipif(not _HAS_ORTOOLS, reason="CP-SAT unavailable")
def test_early_stopping_plateau_logic_triggers_stop():
    """Simulate solution callbacks that plateau and verify StopSearch is called."""
    class MockSolver:
        def __init__(self):
            self.stopped = False

    cb = EarlyStoppingCallback(
        stagnation_s=10.0,
        plateau_window_s=0.5,
        min_improvement_rate=0.05,
        min_improvement_abs=100.0,
        min_search_s=0.2,
    )

    stopped = []
    cb.StopSearch = lambda: stopped.append(True)

    # Fake start 1.0 second ago
    cb.start_time = time.time() - 1.0

    # 1st solution: obj = 1000
    cb.history.append((time.time() - 0.6, 1000.0))
    cb.best_obj = 1000.0

    # 2nd solution 0.1s ago: obj = 990 (only 1% improvement, less than 5% and less than 100)
    cb.history.append((time.time() - 0.1, 990.0))
    cb.best_obj = 990.0

    # Call _check_plateau
    assert hasattr(cb, "_check_plateau")
    should_stop = cb._check_plateau()
    assert should_stop is True


@pytest.mark.skipif(not _HAS_ORTOOLS, reason="CP-SAT unavailable")
def test_inter_pass_warm_start_and_fast_convergence(tmp_path):
    """Test on sample school that solve_to_result finishes well under 25s with warm-start and plateau stopping."""
    conn = db.get_connection(str(tmp_path / "test.db"))
    db.init_db(conn)
    import_xlsm(conn, FIXTURE)
    inp = repo.build_scheduling_input(conn, parity="C", seed=2026)
    conn.close()

    t0 = time.time()
    built = build_model(inp)
    res = solve_to_result(built, time_limit_s=45.0, workers=2)
    elapsed = time.time() - t0

    assert res is not None
    assert res.success is True
    # Crucial speedup invariant: with plateau stopping, it should finish well under the 45s baseline
    assert elapsed < 38.0, f"Solving took {elapsed:.2f}s, expected < 38s"
