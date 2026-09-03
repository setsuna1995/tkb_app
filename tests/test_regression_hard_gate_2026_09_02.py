"""Regression coverage for the two bugs the user (Kien) reported on
2026-09-02: teacher off-slot shortfall was silently swallowed (root cause of
"vẫn có người được nghỉ sáng T2"), and teacher lone-session repair was never
verified (root cause of "vẫn nhiều buổi lẻ 1 tiết"). See
.superpowers/sdd/2026-09-02-hard-gate-hdsp-rules/progress.md.
"""
import os
import random

from core.models import SchedulingConfig, Teacher
from core.scheduler import run
from core.scheduler.teacher_off import _assign_off_slots
from core.validation import find_teacher_lone_day_violations, find_teacher_lone_session_violations
from data import db, repository as repo
from io_excel.importer import import_xlsm


def test_off_slot_shortfall_is_reported_not_silently_dropped():
    """Root cause #1: a heavily-excluded teacher (Hiệu trưởng/TPT/BGH role forbids
    all mornings) asked for more off-sessions than eligible cells remain must be
    REPORTED as shortfall, never silently given fewer with no trace."""
    teachers_by_id = {1: Teacher(teacher_id=1, name="Hieu Truong", role="Hiệu trưởng")}
    rng = random.Random(2026)
    gv_off_slots, shortfall = _assign_off_slots({1}, teachers_by_id, rng, off_slot_count=5)
    assert 1 in shortfall, "Regression: shortfall must be reported, not silently absorbed"
    assigned_count, required_count = shortfall[1]
    assert assigned_count == len(gv_off_slots[1])
    assert assigned_count < required_count


def test_full_schedule_never_silently_drops_lone_session_violations(tmp_path):
    """Root cause #2: after _repair_teacher_lone_sessions runs, any teacher lone
    session/day that survives repair must show up in result.relaxed_rules under
    'II.4' -- never silently accepted as if it were fully compliant."""
    fixture_path = os.path.join(os.path.dirname(__file__), "..", "io_excel", "sample_school.xlsm")
    connection = db.get_connection(str(tmp_path / "test_regression.db"))
    db.init_db(connection)
    import_xlsm(connection, fixture_path)

    config = SchedulingConfig(avoid_teacher_lone_periods=True, min_weekly_periods_for_lone_penalty=15)
    repo.set_scheduling_config(connection, config)
    inp = repo.build_scheduling_input(connection, parity="L", seed=2026)
    result = run(inp)

    assert result.success is True, f"Schedule generation failed: {result.failure_reason}"

    min_lone_load = config.min_weekly_periods_for_lone_penalty
    lone_sessions = find_teacher_lone_session_violations(inp.slots, result.assignment, inp.assigned_teacher, min_lone_load)
    lone_days = find_teacher_lone_day_violations(inp.slots, result.assignment, inp.assigned_teacher, min_lone_load)

    if lone_sessions or lone_days:
        relaxed_ids = {item.get("rule_id") for item in result.relaxed_rules}
        assert "II.4" in relaxed_ids, (
            f"Regression: found unreported lone-session/day violations "
            f"{lone_sessions + lone_days} with empty/non-matching relaxed_rules {result.relaxed_rules}"
        )

    connection.close()
