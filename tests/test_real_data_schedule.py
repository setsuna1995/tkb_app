import os

import pytest

from core import scheduler as sched
from core.validation import compute_quota_diff, find_teacher_conflicts
from data import db, repository as repo
from io_excel.importer import import_xlsm

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "TKB_9lop_moi.xlsm")


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
