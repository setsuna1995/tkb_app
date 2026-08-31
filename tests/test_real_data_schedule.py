import os

import pytest

from core import scheduler as sched
from core.models import SchedulingConfig
from core.validation import compute_quota_diff, find_teacher_conflicts
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


@pytest.mark.parametrize("parity", ["C", "L"])
def test_real_data_schedules_successfully(conn, parity):
    inp = repo.build_scheduling_input(conn, parity=parity, seed=2026)
    result = sched.run(inp)

    assert result.success is True, result.failure_reason

    ppw_for_parity = {(s, c, p): n for (s, c, p), n in repo.get_periods_per_week(conn).items()}
    diff = compute_quota_diff(inp.slots, result.assignment, ppw_for_parity, parity)
    bad = {k: v for k, v in diff.items() if v != 0}
    assert bad == {}, f"quota mismatch (actual-quota != 0): {bad}"

    conflicts = find_teacher_conflicts(inp.slots, result.assignment, inp.assigned_teacher)
    assert conflicts == [], f"teacher double-booked: {conflicts}"

    for slot in inp.slots:
        if slot.ts.weekday == 2 and slot.ts.session == "S" and slot.ts.period == 1:
            hdtn_id = next(s.subject_id for s in inp.subjects if s.name.startswith("Hoạt động trải nghiệm"))
            assert result.assignment[slot.slot_id] == hdtn_id

    print(f"\n[{parity}] attempts={result.attempts_tried} successes={result.successes_found} "
          f"cells_changed={result.cells_changed}/{result.cells_total}")


@pytest.mark.parametrize("parity", ["C", "L"])
def test_real_data_schedules_successfully_with_hdtn_thematic_week(conn, parity):
    # R2 at real-data scale: never exercised against the actual sample_school.xlsm
    # fixture before this test (review finding I2) -- hdtn_thematic_week=True skips
    # the chào cờ/SHL pins and routes HDTN's periods through the general
    # block_size-aware greedy/atomic/repair machinery like any other block subject.
    inp = repo.build_scheduling_input(conn, parity=parity, seed=2026, hdtn_thematic_week=True)
    result = sched.run(inp)

    print(f"\n[{parity}, hdtn_thematic_week=True] attempts={result.attempts_tried} "
          f"successes={result.successes_found} cells_changed={result.cells_changed}/{result.cells_total}")

    assert result.success is True, result.failure_reason

    conflicts = find_teacher_conflicts(inp.slots, result.assignment, inp.assigned_teacher)
    assert conflicts == [], f"teacher double-booked: {conflicts}"


@pytest.mark.parametrize("parity", ["L", "C"])
def test_real_data_schedules_successfully_with_heavy_subjects_morning_only(conn, parity):
    # R3 at real-data scale: never exercised against the actual sample_school.xlsm
    # fixture before this test (review finding I2). The design doc's own capacity
    # analysis (design.md §4) found the heavy/morning split is nearly exact-fit
    # with almost no slack, so this is a plausible place for a similar wall to R1's.
    # Parity "L" passes; parity "C" is a known, documented xfail -- see the marks
    # above for the investigation summary.
    repo.set_scheduling_config(conn, SchedulingConfig(heavy_subjects_morning_only=True))
    inp = repo.build_scheduling_input(conn, parity=parity, seed=2026)
    result = sched.run(inp)

    print(f"\n[{parity}, heavy_subjects_morning_only=True] attempts={result.attempts_tried} "
          f"successes={result.successes_found} cells_changed={result.cells_changed}/{result.cells_total}")

    assert result.success is True, result.failure_reason

    conflicts = find_teacher_conflicts(inp.slots, result.assignment, inp.assigned_teacher)
    assert conflicts == [], f"teacher double-booked: {conflicts}"
