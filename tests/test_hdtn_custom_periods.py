import sqlite3
import pytest

from core.models import (
    ClassRoom,
    SchedulingConfig,
    SchedulingInput,
    Slot,
    Subject,
    Teacher,
    TimeSlot,
    ROLE_THUONG,
    ROLE_HDTN,
)
from core.scheduler import cpsat_model
from core.scheduler.hdtn import get_hdtn_pinned_slots_for_class
from data.repositories import config as config_repo


def test_hdtn_default_slots_resolution():
    slots = [
        Slot(1, 1, TimeSlot(1, 2, "S", 1)),
        Slot(2, 1, TimeSlot(2, 2, "S", 2)),
        Slot(3, 1, TimeSlot(3, 6, "S", 4)),
        Slot(4, 1, TimeSlot(4, 6, "S", 5)),
        Slot(5, 1, TimeSlot(5, 4, "C", 1)),
    ]
    cfg = SchedulingConfig()
    # Need 3 periods of HDTN
    pinned = get_hdtn_pinned_slots_for_class(1, slots, cfg, need_hdtn=3)
    # Default: Period 1 at Monday Sáng Tiết 1 (slot 1)
    # Period 2: None (free)
    # Period 3: Friday Sáng last period (slot 4, since class has afternoon on Wed)
    pinned_ids = {s.slot_id for s in pinned}
    assert 1 in pinned_ids
    assert 4 in pinned_ids
    assert len(pinned) == 2  # Period 2 is floating by default


def test_hdtn_custom_all_three_periods_resolution():
    slots = [
        Slot(1, 1, TimeSlot(1, 2, "S", 1)),
        Slot(2, 1, TimeSlot(2, 3, "S", 2)),
        Slot(3, 1, TimeSlot(3, 4, "S", 3)),
        Slot(4, 1, TimeSlot(4, 5, "S", 4)),
        Slot(5, 1, TimeSlot(5, 6, "S", 5)),
    ]
    cfg = SchedulingConfig(
        hdtn_p1_weekday=3,
        hdtn_p1_session="S",
        hdtn_p1_period=2,
        hdtn_p2_weekday=4,
        hdtn_p2_session="S",
        hdtn_p2_period=3,
        hdtn_p3_weekday=6,
        hdtn_p3_session="S",
        hdtn_p3_period=5,
    )
    pinned = get_hdtn_pinned_slots_for_class(1, slots, cfg, need_hdtn=3)
    pinned_ids = {s.slot_id for s in pinned}
    assert pinned_ids == {2, 3, 5}
    assert len(pinned) == 3


def test_hdtn_config_persistence_roundtrip():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE app_meta (key TEXT PRIMARY KEY, value TEXT)")

    cfg = SchedulingConfig(
        hdtn_p1_weekday=3,
        hdtn_p1_session="S",
        hdtn_p1_period=2,
        hdtn_p2_weekday=4,
        hdtn_p2_session="S",
        hdtn_p2_period=3,
        hdtn_p3_weekday=5,
        hdtn_p3_session="C",
        hdtn_p3_period=1,
    )
    config_repo.set_scheduling_config(conn, cfg)
    loaded = config_repo.get_scheduling_config(conn)

    assert loaded.hdtn_p1_weekday == 3
    assert loaded.hdtn_p1_session == "S"
    assert loaded.hdtn_p1_period == 2
    assert loaded.chao_co_weekday == 3
    assert loaded.chao_co_period == 2
    assert loaded.hdtn_p2_weekday == 4
    assert loaded.hdtn_p2_session == "S"
    assert loaded.hdtn_p2_period == 3
    assert loaded.hdtn_p3_weekday == 5
    assert loaded.hdtn_p3_session == "C"
    assert loaded.hdtn_p3_period == 1


def test_cpsat_solver_respects_custom_hdtn_periods():
    classes = [ClassRoom(1, "6A")]
    subjects = [
        Subject(1, "Toán", ROLE_THUONG),
        Subject(2, "HĐTN", ROLE_HDTN),
    ]
    teachers = [
        Teacher(1, "GV Toán"),
        Teacher(2, "GVCN 6A"),
    ]
    assigned_teacher = {
        (1, 1): 1,
        (2, 1): 2,
    }
    need = {
        (1, 1): 5,
        (2, 1): 3,
    }

    # Build 6 slots: 1 per weekday (Thứ 2 đến Thứ 7, tiết 1)
    ts = [TimeSlot(i + 1, wd, "S", 1) for i, wd in enumerate([2, 3, 4, 5, 6, 7])]
    slots = [Slot(i + 1, 1, t) for i, t in enumerate(ts)]
    need = {
        (1, 1): 3,
        (2, 1): 3,
    }

    cfg = SchedulingConfig(
        hdtn_p1_weekday=2,
        hdtn_p1_period=1,
        hdtn_p2_weekday=4,
        hdtn_p2_period=1,
        hdtn_p3_weekday=6,
        hdtn_p3_period=1,
        balance_morning_academic_load=False,
    )
    inp = SchedulingInput(
        classes=classes,
        subjects=subjects,
        teachers=teachers,
        need=need,
        assigned_teacher=assigned_teacher,
        ban_busy=set(),
        slots=slots,
        timeslots=ts,
        config=cfg,
    )

    model = cpsat_model.build_model(inp)
    res = cpsat_model.solve_to_result(model, time_limit_s=15)
    assert res is not None
    assert res.success is True

    # Verify HDTN is placed at the 3 configured slots:
    # 1: (wd=2, p=1)
    # 2: (wd=4, p=1)
    # 3: (wd=6, p=1)
    slot_map = {s.slot_id: s for s in slots}
    hdtn_slots = [
        slot_map[sid] for sid, subj_id in res.assignment.items() if subj_id == 2
    ]
    assert len(hdtn_slots) == 3
    coords = {(s.ts.weekday, s.ts.session, s.ts.period) for s in hdtn_slots}
    assert (2, "S", 1) in coords
    assert (4, "S", 1) in coords
    assert (6, "S", 1) in coords

