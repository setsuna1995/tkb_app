import sqlite3
import pytest

from core.models import SchedulingConfig
from data.repositories import config as config_repo
from data.repositories.builder import build_scheduling_input
from data.db import init_db, get_connection


@pytest.fixture
def mem_conn():
    conn = get_connection(":memory:")
    init_db(conn)
    return conn


def test_scheduling_config_hdtn_defaults():
    cfg = SchedulingConfig()
    assert cfg.hdtn_mode == "separate"
    assert cfg.hdtn_thematic_mode == "auto"
    assert cfg.hdtn_thematic_weekday is None
    assert cfg.hdtn_thematic_session == "S"
    assert cfg.hdtn_thematic_start_period is None


def test_scheduling_config_hdtn_roundtrip(mem_conn):
    custom_cfg = SchedulingConfig(
        hdtn_mode="thematic",
        hdtn_thematic_mode="fixed",
        hdtn_thematic_weekday=3,
        hdtn_thematic_session="C",
        hdtn_thematic_start_period=2,
    )
    config_repo.set_scheduling_config(mem_conn, custom_cfg)
    loaded = config_repo.get_scheduling_config(mem_conn)

    assert loaded.hdtn_mode == "thematic"
    assert loaded.hdtn_thematic_mode == "fixed"
    assert loaded.hdtn_thematic_weekday == 3
    assert loaded.hdtn_thematic_session == "C"
    assert loaded.hdtn_thematic_start_period == 2


def test_build_scheduling_input_hdtn_fallback(mem_conn):
    thematic_cfg = SchedulingConfig(
        hdtn_mode="thematic",
        hdtn_thematic_mode="fixed",
        hdtn_thematic_weekday=4,
        hdtn_thematic_session="S",
        hdtn_thematic_start_period=1,
    )
    config_repo.set_scheduling_config(mem_conn, thematic_cfg)

    # 1. Fallback when not explicitly specified
    inp = build_scheduling_input(mem_conn)
    assert inp.hdtn_thematic_week is True
    assert inp.hdtn_thematic_mode == "fixed"
    assert inp.hdtn_thematic_weekday == 4
    assert inp.hdtn_thematic_session == "S"
    assert inp.hdtn_thematic_start_period == 1

    # 2. Explicit override by caller (e.g. standard week run even if default is thematic)
    inp_override = build_scheduling_input(mem_conn, hdtn_thematic_week=False)
    assert inp_override.hdtn_thematic_week is False


def test_build_scheduling_input_config_override(mem_conn):
    base_cfg = SchedulingConfig()
    config_repo.set_scheduling_config(mem_conn, base_cfg)

    # Custom override for week-specific run
    override_cfg = SchedulingConfig(
        hdtn_p1_weekday=3,
        hdtn_p1_session="S",
        hdtn_p1_period=2,
        hdtn_p2_weekday=4,
        hdtn_p2_session="C",
        hdtn_p2_period=1,
    )
    inp = build_scheduling_input(mem_conn, config_override=override_cfg)
    assert inp.config.hdtn_p1_weekday == 3
    assert inp.config.hdtn_p1_session == "S"
    assert inp.config.hdtn_p1_period == 2
    assert inp.config.hdtn_p2_weekday == 4
    assert inp.config.hdtn_p2_session == "C"
    assert inp.config.hdtn_p2_period == 1

