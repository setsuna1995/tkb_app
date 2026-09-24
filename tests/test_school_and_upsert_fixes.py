import sqlite3
import pytest
from pathlib import Path
from data import db, repository as repo
import ui_common


@pytest.fixture()
def conn(tmp_path):
    connection = db.get_connection(str(tmp_path / "test.db"))
    db.init_db(connection)
    yield connection
    connection.close()



def test_upsert_class_idempotent_on_duplicate_name(conn):
    id1 = repo.upsert_class(conn, "6A1", sort_order=1)
    id2 = repo.upsert_class(conn, "6A1", sort_order=2)
    assert id1 == id2
    classes = repo.list_classes(conn)
    assert len(classes) == 1
    assert classes[0].name == "6A1"
    assert classes[0].sort_order == 2


def test_upsert_subject_idempotent_on_duplicate_name(conn):
    id1 = repo.upsert_subject(conn, "Toán", role_code=1, sort_order=1)
    id2 = repo.upsert_subject(conn, "Toán", role_code=2, sort_order=2)
    assert id1 == id2
    subjects = repo.list_subjects(conn)
    assert len(subjects) == 1
    assert subjects[0].name == "Toán"
    assert subjects[0].role_code == 2


def test_upsert_teacher_idempotent_on_duplicate_name(conn):
    id1 = repo.upsert_teacher(conn, "Nguyễn Văn A", role="GV")
    id2 = repo.upsert_teacher(conn, "Nguyễn Văn A", role="Tổ trưởng")
    assert id1 == id2
    teachers = repo.list_teachers(conn)
    assert len(teachers) == 1
    assert teachers[0].name == "Nguyễn Văn A"
    assert teachers[0].role == "Tổ trưởng"


def test_list_schools_closes_connections(tmp_path, monkeypatch):
    monkeypatch.setattr(ui_common, "SCHOOLS_DIR", tmp_path)
    monkeypatch.setattr(ui_common, "LEGACY_DB_PATH", str(tmp_path / "legacy.db"))

    # Create two school databases
    s1_path = tmp_path / "truong-a.db"
    conn1 = db.get_connection(str(s1_path))
    db.init_db(conn1)
    repo.set_meta(conn1, "school_name", "Trường A")
    conn1.close()

    s2_path = tmp_path / "truong-b.db"
    conn2 = db.get_connection(str(s2_path))
    db.init_db(conn2)
    repo.set_meta(conn2, "school_name", "Trường B")
    conn2.close()

    schools = ui_common.list_schools()
    assert len(schools) == 2
    assert {s["name"] for s in schools} == {"Trường A", "Trường B"}


def test_teacher_off_sessions_hard_mode():
    from core.models import (
        ClassRoom, SchedulingConfig, SchedulingInput, Slot, Subject, Teacher, TimeSlot,
        ROLE_THUONG, ROLE_HDTN
    )
    from core.scheduler.cpsat_model import build_model, solve

    ts = [TimeSlot(i + 1, wd, "S", 1) for i, wd in enumerate([2, 3, 4, 5, 6, 7])]
    slots = [Slot(i + 1, 101, t) for i, t in enumerate(ts)]
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]
    teachers = [Teacher(10, "GV A"), Teacher(20, "GV B")]
    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1")],
        subjects=subjects,
        teachers=teachers,
        need={(1, 101): 3, (2, 101): 3},
        assigned_teacher={(1, 101): 10, (2, 101): 20},
        ban_busy=set(),
        slots=slots,
        timeslots=ts,
        config=SchedulingConfig(
            teacher_off_sessions_per_week=2,
            teacher_off_sessions_mode="hard",
            forbidden_off_cells=frozenset(),
            mandatory_morning_weekdays=(),
            chao_co_weekday=2,
            chao_co_period=1,
        ),
    )
    built = build_model(inp)
    assignment = solve(built, time_limit_s=10.0)
    assert assignment is not None, "Solver must find a solution with hard off sessions"

    slot_by_id = {s.slot_id: s for s in slots}
    taught_sessions = set()
    for s_id, subj_id in assignment.items():
        t_id = inp.assigned_teacher.get((subj_id, 101))
        if t_id == 10:
            s = slot_by_id[s_id]
            taught_sessions.add((s.ts.weekday, s.ts.session))

    all_sessions = {(t.weekday, t.session) for t in ts}
    off_sessions_count = len(all_sessions - taught_sessions)
    assert off_sessions_count >= 2, f"Expected at least 2 off sessions in hard mode, got {off_sessions_count}"


def test_teacher_off_sessions_hard_mode_overloaded_fallback():
    from core.models import (
        ClassRoom, SchedulingConfig, SchedulingInput, Slot, Subject, Teacher, TimeSlot,
        ROLE_THUONG, ROLE_HDTN
    )
    from core.scheduler.cpsat_model import build_model, solve

    # 6 sessions, teacher 10 teaches 4 periods, but config requests 4 off sessions.
    # 6 - 4 = 2 workable sessions < 4 periods needed. Hard mode would be INFEASIBLE.
    # The capacity fallback detects overload and falls back to soft mode, solving successfully.
    ts = [TimeSlot(i + 1, wd, "S", 1) for i, wd in enumerate([2, 3, 4, 5, 6, 7])]
    slots = [Slot(i + 1, 101, t) for i, t in enumerate(ts)]
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]
    teachers = [Teacher(10, "GV A"), Teacher(20, "GV B")]
    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1")],
        subjects=subjects,
        teachers=teachers,
        need={(1, 101): 4, (2, 101): 2},
        assigned_teacher={(1, 101): 10, (2, 101): 20},
        ban_busy=set(),
        slots=slots,
        timeslots=ts,
        config=SchedulingConfig(
            teacher_off_sessions_per_week=4,
            teacher_off_sessions_mode="hard",
            mandatory_morning_weekdays=(),
            chao_co_weekday=2,
            chao_co_period=1,
        ),
    )
    built = build_model(inp)
    assignment = solve(built, time_limit_s=10.0)
    assert assignment is not None, "Solver should gracefully solve overloaded teacher via soft fallback"


def test_teacher_off_sessions_soft_mode():
    from core.models import (
        ClassRoom, SchedulingConfig, SchedulingInput, Slot, Subject, Teacher, TimeSlot,
        ROLE_THUONG, ROLE_HDTN
    )
    from core.scheduler.cpsat_model import build_model, solve

    ts = [TimeSlot(i + 1, wd, "S", 1) for i, wd in enumerate([2, 3, 4, 5, 6, 7])]
    slots = [Slot(i + 1, 101, t) for i, t in enumerate(ts)]
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]
    teachers = [Teacher(10, "GV A"), Teacher(20, "GV B")]
    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1")],
        subjects=subjects,
        teachers=teachers,
        need={(1, 101): 3, (2, 101): 3},
        assigned_teacher={(1, 101): 10, (2, 101): 20},
        ban_busy=set(),
        slots=slots,
        timeslots=ts,
        config=SchedulingConfig(
            teacher_off_sessions_per_week=2,
            teacher_off_sessions_mode="soft",
            forbidden_off_cells=frozenset(),
            mandatory_morning_weekdays=(),
            chao_co_weekday=2,
            chao_co_period=1,
        ),
    )
    built = build_model(inp)
    assert "_teacher_off" in built.penalty_terms
    assert len(built.penalty_terms["_teacher_off"]) == 2  # 1 shortfall var per teacher

    assignment = solve(built, time_limit_s=10.0)
    assert assignment is not None

    slot_by_id = {s.slot_id: s for s in slots}
    taught_sessions = set()
    for s_id, subj_id in assignment.items():
        t_id = inp.assigned_teacher.get((subj_id, 101))
        if t_id == 10:
            s = slot_by_id[s_id]
            taught_sessions.add((s.ts.weekday, s.ts.session))

    all_sessions = {(t.weekday, t.session) for t in ts}
    off_sessions_count = len(all_sessions - taught_sessions)
    assert off_sessions_count >= 2, f"Expected at least 2 off sessions in soft mode, got {off_sessions_count}"


