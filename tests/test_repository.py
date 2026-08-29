import pytest

from core.models import SchedulingConfig
from data import db, repository as repo


@pytest.fixture()
def conn(tmp_path):
    connection = db.get_connection(str(tmp_path / "test.db"))
    db.init_db(connection)
    yield connection
    connection.close()


def test_get_scheduling_config_returns_defaults_when_never_saved(conn):
    assert repo.get_scheduling_config(conn) == SchedulingConfig()


def test_set_then_get_scheduling_config_round_trips(conn):
    custom = SchedulingConfig(
        gdtc_avoid_period=3,
        chao_co_weekday=3,
        chao_co_period=2,
        max_heavy_consecutive=2,
        max_periods_per_session=5,
        teacher_off_sessions_per_week=2,
        forbidden_off_cells=frozenset({(2, "S"), (4, "C")}),
        reserved_off_weekdays_chieu=(4, 5),
    )
    repo.set_scheduling_config(conn, custom)
    assert repo.get_scheduling_config(conn) == custom


def test_set_then_get_scheduling_config_round_trips_soft_bias_fields(conn):
    custom = SchedulingConfig(
        heavy_subject_priority_periods=2,
        afternoon_preferred_subject_ids=frozenset({3, 7}),
    )
    repo.set_scheduling_config(conn, custom)
    assert repo.get_scheduling_config(conn) == custom


def test_upsert_and_list_teacher_round_trips_off_override_and_pins(conn):
    tid = repo.upsert_teacher(
        conn, "GV The duc", role="", must_monday=False, is_gvcn=False,
        off_sessions_override=3, pinned_full_day_off=5, pinned_afternoon_off=3,
    )
    teachers = {t.teacher_id: t for t in repo.list_teachers(conn)}
    t = teachers[tid]
    assert t.off_sessions_override == 3
    assert t.pinned_full_day_off == 5
    assert t.pinned_afternoon_off == 3


def test_teacher_off_override_and_pins_default_to_none(conn):
    tid = repo.upsert_teacher(conn, "GV Thuong")
    teachers = {t.teacher_id: t for t in repo.list_teachers(conn)}
    t = teachers[tid]
    assert t.off_sessions_override is None
    assert t.pinned_full_day_off is None
    assert t.pinned_afternoon_off is None


def test_upsert_teacher_without_new_kwargs_preserves_existing_pins_and_override(conn):
    # Regression for the Excel re-import bug: io_excel/importer.py's DinhMuc_GV
    # loop calls upsert_teacher(conn, name, role=..., must_monday=..., is_gvcn=...,
    # teacher_id=tid) on an UPDATE, never mentioning the 3 new columns -- that must
    # NOT wipe a previously-saved off_sessions_override/pinned_full_day_off/
    # pinned_afternoon_off back to NULL.
    tid = repo.upsert_teacher(conn, "GV The duc", role="", must_monday=False, is_gvcn=False,
                               off_sessions_override=3, pinned_full_day_off=4, pinned_afternoon_off=3)
    # Simulate an Excel re-import call: same shape as io_excel/importer.py's call, no new kwargs at all.
    repo.upsert_teacher(conn, "GV The duc", role="", must_monday=False, is_gvcn=False, teacher_id=tid)
    teachers = {t.teacher_id: t for t in repo.list_teachers(conn)}
    t = teachers[tid]
    assert t.off_sessions_override == 3
    assert t.pinned_full_day_off == 4
    assert t.pinned_afternoon_off == 3


def test_upsert_teacher_can_still_explicitly_clear_pins_and_override(conn):
    tid = repo.upsert_teacher(conn, "GV The duc", off_sessions_override=3, pinned_full_day_off=4,
                               pinned_afternoon_off=3)
    repo.upsert_teacher(conn, "GV The duc", teacher_id=tid,
                        off_sessions_override=None, pinned_full_day_off=None, pinned_afternoon_off=None)
    teachers = {t.teacher_id: t for t in repo.list_teachers(conn)}
    t = teachers[tid]
    assert t.off_sessions_override is None
    assert t.pinned_full_day_off is None
    assert t.pinned_afternoon_off is None
