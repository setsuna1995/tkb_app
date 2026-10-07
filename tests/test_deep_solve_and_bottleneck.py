import time

import pytest
from core.models import (
    ROLE_HDTN, ROLE_THUONG, ClassRoom, SchedulingConfig, SchedulingInput,
    Slot, Subject, Teacher, TimeSlot,
)

cpsat = pytest.importorskip("core.scheduler.cpsat_model")
from core.scheduler.cpsat import solver as solver_mod  # noqa: E402


def _tiny_feasible_input():
    ts = [TimeSlot(i + 1, wd, "S", 1) for i, wd in enumerate([2, 3, 4, 5, 6, 7])]
    slots = [Slot(i + 1, 101, t) for i, t in enumerate(ts)]
    return SchedulingInput(
        classes=[ClassRoom(101, "6A1")],
        subjects=[Subject(1, "Toan", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)],
        teachers=[Teacher(10, "GV A"), Teacher(20, "GV B")],
        need={(1, 101): 3, (2, 101): 3},
        assigned_teacher={(1, 101): 10, (2, 101): 20},
        ban_busy=set(), slots=slots, timeslots=ts,
        config=SchedulingConfig(strict_morning_weekdays=()),
    )


def test_build_result_records_search_telemetry():
    res = cpsat.solve_to_result(cpsat.build_model(_tiny_feasible_input()), time_limit_s=10.0)
    d = res.diagnostics
    assert d["final_status"] in ("OPTIMAL", "FEASIBLE")
    assert d["objective"] >= d["best_bound"] - 1e-6
    assert d["wall_time_s"] >= 0.0


def test_zero_thresholds_never_detect_plateau():
    cb = solver_mod.EarlyStoppingCallback(
        stagnation_s=999.0, plateau_window_s=0.5,
        min_improvement_rate=0.0, min_improvement_abs=0.0, min_search_s=0.2,
    )
    now = time.time()
    cb.start_time = now - 1.0
    cb.history = [(now - 0.6, 1000.0), (now - 0.1, 1000.0)]
    cb.best_obj = 1000.0
    assert cb._check_plateau() is False


def test_deep_mode_disables_early_stop_and_gap(monkeypatch):
    seen = []
    real = solver_mod.EarlyStoppingCallback

    class Spy(real):
        def __init__(self, *a, **kw):
            seen.append(kw)
            super().__init__(*a, **kw)

    monkeypatch.setattr(solver_mod, "EarlyStoppingCallback", Spy)
    res = solver_mod.solve_to_result(cpsat.build_model(_tiny_feasible_input()), time_limit_s=5.0, deep=True)
    assert res is not None and res.diagnostics["deep"] is True
    assert seen[0]["min_improvement_abs"] == 0.0
    assert seen[0]["min_improvement_rate"] == 0.0


def test_default_mode_unchanged(monkeypatch):
    seen = []
    real = solver_mod.EarlyStoppingCallback

    class Spy(real):
        def __init__(self, *a, **kw):
            seen.append(kw)
            super().__init__(*a, **kw)

    monkeypatch.setattr(solver_mod, "EarlyStoppingCallback", Spy)
    res = solver_mod.solve_to_result(cpsat.build_model(_tiny_feasible_input()), time_limit_s=5.0)
    assert res.diagnostics["deep"] is False
    assert "min_improvement_abs" not in seen[0]  # library defaults (600 / 3%) still apply


def test_morning_capacity_rows_explain_ii3_conflict():
    ts = [TimeSlot(1, 2, "S", 1), TimeSlot(2, 2, "S", 2), TimeSlot(3, 2, "S", 3)]
    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1")],
        subjects=[Subject(1, "M1", ROLE_THUONG), Subject(2, "M2", ROLE_THUONG), Subject(99, "HDTN", ROLE_HDTN)],
        teachers=[Teacher(10, "GV A"), Teacher(20, "GV B"), Teacher(99, "GV HDTN")],
        need={(1, 101): 10, (2, 101): 10, (99, 101): 0},
        assigned_teacher={(1, 101): 10, (2, 101): 20, (99, 101): 99},
        ban_busy=set(), slots=[Slot(i + 1, 101, t) for i, t in enumerate(ts)], timeslots=ts,
        config=SchedulingConfig(
            mandatory_morning_weekdays=(2,), min_weekly_periods_for_mandatory_morning=10,
            avoid_teacher_lone_periods=True, allow_lone_period_on_mandatory_mornings=False,
        ),
    )
    built = cpsat.build_model(inp)
    rows = solver_mod._morning_capacity_rows(built)
    monday = next(r for r in rows if r["weekday"] == 2)
    assert monday["teachers"] == 2
    assert monday["need"] == 4
    assert monday["need"] > monday["cap"]
    assert solver_mod._presolve_capacity_screening(built) == {"II.3"}

