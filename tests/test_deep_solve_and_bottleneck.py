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
