"""Tests for 35-week teacher workload profile and quota calculations."""
import os
import sqlite3
import pytest

from data import db
from data import repository as repo
from io_excel.weekly_importer import import_weekly_curriculum_from_excel


@pytest.fixture
def populated_school_conn():
    conn = db.get_connection(":memory:")
    db.init_db(conn)

    # Add sample classes
    c6 = repo.upsert_class(conn, "6A5", 0)
    c8 = repo.upsert_class(conn, "8A5", 1)

    # Add subjects
    s_toan = repo.upsert_subject(conn, "Toán học", 3, 0)
    s_van = repo.upsert_subject(conn, "Ngữ văn", 3, 1)
    s_cn = repo.upsert_subject(conn, "Công nghệ", 0, 2)
    s_ly = repo.upsert_subject(conn, "Khoa học tự nhiên (Vật lý)", 0, 3)

    # Add teachers
    # Teacher 1: Toan (6A5 + 8A5) = 4 + 4 = 8 periods/week
    t_toan = repo.upsert_teacher(conn, "Thầy Toán", role="Tổ trưởng", reduction_override=3)
    # Teacher 2: Cong nghe (6A5 + 8A5) -> 6A5: 1 period all year. 8A5: 2 periods (w1..9, 28..35) & 1 period (w10..27)
    t_cn = repo.upsert_teacher(conn, "Cô Công Nghệ", role="GV", reduction_override=0)

    # Assign teachers
    repo.set_assignment(conn, s_toan, c6, t_toan)
    repo.set_assignment(conn, s_toan, c8, t_toan)
    repo.set_assignment(conn, s_cn, c6, t_cn)
    repo.set_assignment(conn, s_cn, c8, t_cn)

    # Set weekly curriculum for 35 weeks
    entries = []
    for w in range(1, 36):
        entries.append((s_toan, c6, w, 4))
        entries.append((s_toan, c8, w, 4))
        entries.append((s_cn, c6, w, 1))
        # 8A5 Cong nghe: 2 in w1..9 & w28..35, 1 in w10..27
        p_cn8 = 2 if (w <= 9 or w >= 28) else 1
        entries.append((s_cn, c8, w, p_cn8))

    repo.bulk_set_weekly_curriculum(conn, entries)
    return conn


def test_teacher_quota_view_35_week_profile(populated_school_conn):
    conn = populated_school_conn
    repo.set_base_cap(conn, 19)
    repo.set_min_floor(conn, 16)

    # Check for Week 1 (Tuần 1 - HKI)
    view_w1 = repo.get_teacher_quota_view(conn, week_no=1)
    
    t_toan_view = next(v for v in view_w1 if v["name"] == "Thầy Toán")
    t_cn_view = next(v for v in view_w1 if v["name"] == "Cô Công Nghệ")

    # Thầy Toán: 8 periods every week. Cap = 19 - 3 = 16.
    assert t_toan_view["cap"] == 16
    assert t_toan_view["load"] == 8
    assert t_toan_view["load_full_year_avg"] == 8.0
    assert t_toan_view["load_hk1_avg"] == 8.0
    assert t_toan_view["load_hk2_avg"] == 8.0
    assert t_toan_view["weekly_loads"][1] == 8
    assert t_toan_view["weekly_loads"][35] == 8
    assert t_toan_view["max_load"] == 8
    assert t_toan_view["min_load"] == 8

    # Cô Công Nghệ: Cap = 19 - 0 = 19.
    # Week 1: 6A5 (1) + 8A5 (2) = 3 periods
    assert t_cn_view["cap"] == 19
    assert t_cn_view["load"] == 3
    assert t_cn_view["weekly_loads"][1] == 3
    assert t_cn_view["weekly_loads"][10] == 2 # 6A5 (1) + 8A5 (1) = 2 periods
    assert t_cn_view["weekly_loads"][30] == 3 # 6A5 (1) + 8A5 (2) = 3 periods

    # Check averages:
    # HK1 (18 weeks): 9 weeks x 3 + 9 weeks x 2 = 27 + 18 = 45 -> 45 / 18 = 2.5
    assert abs(t_cn_view["load_hk1_avg"] - 2.5) < 1e-4
    # HK2 (17 weeks): 9 weeks (19..27) x 2 + 8 weeks (28..35) x 3 = 18 + 24 = 42 -> 42 / 17 ≈ 2.47
    assert abs(t_cn_view["load_hk2_avg"] - (42 / 17)) < 1e-4
    # Full year (35 weeks): (45 + 42) / 35 = 87 / 35 ≈ 2.4857
    assert abs(t_cn_view["load_full_year_avg"] - (87 / 35)) < 1e-4

    assert t_cn_view["max_load"] == 3
    assert t_cn_view["min_load"] == 2
    assert t_cn_view["over_current"] == 3 - 19  # -16


def test_bgh_quota_tt28_2009():
    conn = db.get_connection(":memory:")
    db.init_db(conn)

    t_ht = repo.upsert_teacher(conn, "Thầy Hiệu Trưởng", role="Hiệu trưởng")
    t_hp = repo.upsert_teacher(conn, "Cô Hiệu Phó", role="Phó hiệu trưởng")
    t_gvcn = repo.upsert_teacher(conn, "Thầy Chủ Nhiệm", role="GVCN")

    caps = repo.get_teacher_caps(conn)
    floors = repo.get_teacher_floors(conn)
    # Hiệu trưởng THCS: 2 periods/week (TT 28/2009)
    assert caps[t_ht] == 2
    assert floors[t_ht] == 2
    # Phó hiệu trưởng THCS: 4 periods/week (TT 28/2009)
    assert caps[t_hp] == 4
    assert floors[t_hp] == 4
    # GVCN: Trần 19 - 4 = 15, Sàn 16 - 4 = 12 (khoảng định mức 12-15)
    assert caps[t_gvcn] == 15
    assert floors[t_gvcn] == 12

    view = repo.get_teacher_quota_view(conn, week_no=1)
    ht_view = next(v for v in view if v["teacher_id"] == t_ht)
    hp_view = next(v for v in view if v["teacher_id"] == t_hp)
    gvcn_view = next(v for v in view if v["teacher_id"] == t_gvcn)
    assert ht_view["cap"] == 2
    assert ht_view["floor"] == 2
    assert hp_view["cap"] == 4
    assert hp_view["floor"] == 4
    assert gvcn_view["cap"] == 15
    assert gvcn_view["floor"] == 12
