"""Tests for weekly curriculum repository and fallback functionality."""
import sqlite3
import pytest
from data import db
from data import repository as repo


@pytest.fixture
def conn():
    c = db.get_connection(":memory:")
    db.init_db(c)
    # create sample classes & subjects
    repo.upsert_class(c, "6A5", 0)
    repo.upsert_class(c, "6A6", 1)
    repo.upsert_subject(c, "Toán", 1, 0)
    repo.upsert_subject(c, "Văn", 1, 1)
    repo.upsert_subject(c, "Lý", 0, 2)
    return c


def test_weekly_curriculum_crud(conn):
    classes = repo.list_classes(conn)
    subjects = repo.list_subjects(conn)
    c1, c2 = classes[0].class_id, classes[1].class_id
    s1, s2 = subjects[0].subject_id, subjects[1].subject_id

    # Test single set
    repo.set_weekly_curriculum(conn, s1, c1, 1, 4)
    repo.set_weekly_curriculum(conn, s2, c1, 1, 4)
    repo.set_weekly_curriculum(conn, s1, c1, 2, 4)

    cur = repo.get_weekly_curriculum(conn)
    assert cur[(s1, c1, 1)] == 4
    assert cur[(s2, c1, 1)] == 4
    assert cur[(s1, c1, 2)] == 4

    # Test bulk set
    entries = [
        (s1, c2, 1, 4),
        (s2, c2, 1, 4),
        (s1, c2, 2, 3),
        (s2, c2, 2, 5),
    ]
    repo.bulk_set_weekly_curriculum(conn, entries)

    weeks = repo.list_configured_weeks(conn)
    assert sorted(weeks) == [1, 2]

    # Filtered get
    cur_c2 = repo.get_weekly_curriculum(conn, class_id=c2)
    assert len(cur_c2) == 4
    assert cur_c2[(s1, c2, 2)] == 3

    cur_w2 = repo.get_weekly_curriculum(conn, week_no=2)
    assert (s1, c1, 2) in cur_w2
    assert (s1, c2, 2) in cur_w2


def test_get_periods_for_week_exact_and_fallback(conn):
    classes = repo.list_classes(conn)
    subjects = repo.list_subjects(conn)
    c1 = classes[0].class_id
    s1, s2 = subjects[0].subject_id, subjects[1].subject_id

    # Setup legacy parity periods_per_week
    repo.set_periods_per_week(conn, s1, c1, "C", 4)
    repo.set_periods_per_week(conn, s1, c1, "L", 4)
    repo.set_periods_per_week(conn, s2, c1, "C", 2)
    repo.set_periods_per_week(conn, s2, c1, "L", 1)

    # Week 1 has no entry in weekly_curriculum -> fallback to Odd (L)
    w1_periods = repo.get_periods_for_week(conn, week_no=1)
    assert w1_periods.get((s1, c1)) == 4
    assert w1_periods.get((s2, c1)) == 1

    # Week 2 has no entry in weekly_curriculum -> fallback to Even (C)
    w2_periods = repo.get_periods_for_week(conn, week_no=2)
    assert w2_periods.get((s1, c1)) == 4
    assert w2_periods.get((s2, c1)) == 2

    # Now set exact custom weekly curriculum for Week 5
    repo.set_weekly_curriculum(conn, s1, c1, 5, 5)
    repo.set_weekly_curriculum(conn, s2, c1, 5, 0)

    w5_periods = repo.get_periods_for_week(conn, week_no=5)
    assert w5_periods.get((s1, c1)) == 5
    assert w5_periods.get((s2, c1)) == 0


def test_teacher_quota_view_with_week_no(conn):
    classes = repo.list_classes(conn)
    subjects = repo.list_subjects(conn)
    c1 = classes[0].class_id
    s1 = subjects[0].subject_id

    repo.upsert_teacher(conn, "Thầy Nam", "GV", 0)
    teachers = repo.list_teachers(conn)
    t1 = teachers[0].teacher_id

    repo.set_assignment(conn, s1, c1, t1)

    # Default parity ppw
    repo.set_periods_per_week(conn, s1, c1, "C", 4)
    repo.set_periods_per_week(conn, s1, c1, "L", 4)

    # Specific week 3 has 6 periods
    repo.set_weekly_curriculum(conn, s1, c1, 3, 6)

    view_c = repo.get_teacher_quota_view(conn, parity="C")
    assert view_c[0]["load"] == 4

    view_w3 = repo.get_teacher_quota_view(conn, week_no=3)
    assert view_w3[0]["load"] == 6
