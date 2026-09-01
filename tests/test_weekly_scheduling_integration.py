"""Integration tests for week-specific scheduling input and solver execution."""
import os
import sqlite3
import pytest
from core import scheduler as sched
from core.validation import compute_quota_diff
from data import db
from data import repository as repo
from io_excel.weekly_importer import import_weekly_curriculum_from_excel


@pytest.fixture
def real_school_conn():
    # Copy from truong-thcs.db or build in-memory
    excel_path = "Định lượng số tiết theo tuần năm học 2026_2027.xlsx"
    if not os.path.exists(excel_path):
        pytest.skip(f"{excel_path} not found")
        
    db_path = "schools/truong-thcs.db"
    if not os.path.exists(db_path):
        pytest.skip(f"{db_path} not found")
        
    conn = db.get_connection(db_path)
    db.init_db(conn)
    import_weekly_curriculum_from_excel(conn, excel_path)
    return conn


def test_build_scheduling_input_week_no(real_school_conn):
    conn = real_school_conn

    # Build input for Week 1 (Khối 8, 9 have 30 periods)
    inp_w1 = repo.build_scheduling_input(conn, parity="L", seed=42, week_no=1)
    c_8a5_id = repo.get_class_by_name(conn, "8A5")
    c_6a5_id = repo.get_class_by_name(conn, "6A5")
    
    need_8a5_w1 = sum(v for (s, c), v in inp_w1.need.items() if c == c_8a5_id)
    need_6a5_w1 = sum(v for (s, c), v in inp_w1.need.items() if c == c_6a5_id)
    assert need_8a5_w1 == 30
    assert need_6a5_w1 == 29

    # Build input for Week 10 (Khối 8, 9 have 29 periods)
    inp_w10 = repo.build_scheduling_input(conn, parity="C", seed=42, week_no=10)
    need_8a5_w10 = sum(v for (s, c), v in inp_w10.need.items() if c == c_8a5_id)
    need_6a5_w10 = sum(v for (s, c), v in inp_w10.need.items() if c == c_6a5_id)
    assert need_8a5_w10 == 29
    assert need_6a5_w10 == 29


def test_compute_quota_diff_with_week_dict():
    from core.models import Slot, TimeSlot
    ts1 = TimeSlot(1, 2, "S", 1)
    ts2 = TimeSlot(2, 2, "S", 2)
    slots = [Slot(1, 10, ts1), Slot(2, 10, ts2)]
    assignment = {1: 1, 2: 2}

    # 2-tuple dict {(subject_id, class_id): periods}
    week_quota = {(1, 10): 1, (2, 10): 1}
    diff = compute_quota_diff(slots, assignment, week_quota)
    assert diff[(1, 10)] == 0
    assert diff[(2, 10)] == 0
