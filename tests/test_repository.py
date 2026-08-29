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
