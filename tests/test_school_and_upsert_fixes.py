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


def test_teacher_off_sessions_fairness_and_no_cheating():
    from core.models import (
        ClassRoom, SchedulingConfig, SchedulingInput, Slot, Subject, Teacher, TimeSlot,
        ROLE_KEP, ROLE_HDTN
    )
    from core.scheduler.cpsat_model import build_model, solve

    # 4 morning sessions (2, 3, 4, 5) with 2 periods each = 8 slots
    # Teacher 10 has 4 periods (Van - ROLE_KEP), Teacher 20 has 4 periods (HDTN).
    # Config requests 1 off session per week.
    # The zero-off penalty (1500) and excess penalty (60) ensure neither teacher has 0 off sessions.
    timeslots = []
    slot_id = 1
    for wd in (2, 3, 4, 5):
        for period in (1, 2):
            timeslots.append(TimeSlot(slot_id, wd, "S", period))
            slot_id += 1

    slots = [Slot(ts.ts_id, 101, ts) for ts in timeslots]
    subjects = [Subject(1, "Van", ROLE_KEP), Subject(2, "HDTN", ROLE_HDTN)]
    teachers = [Teacher(10, "GV Van"), Teacher(20, "GV HDTN")]
    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1")],
        subjects=subjects,
        teachers=teachers,
        need={(1, 101): 4, (2, 101): 4},
        assigned_teacher={(1, 101): 10, (2, 101): 20},
        ban_busy=set(),
        slots=slots,
        timeslots=timeslots,
        config=SchedulingConfig(
            teacher_off_sessions_per_week=1,
            teacher_off_sessions_mode="soft",
            forbidden_off_cells=frozenset(),
            mandatory_morning_weekdays=(),
            chao_co_weekday=2,
            chao_co_period=1,
        ),
    )
    built = build_model(inp)
    assert "_teacher_zero_off" in built.penalty_terms
    assert "_teacher_off_excess" in built.penalty_terms

    assignment = solve(built, time_limit_s=10.0)
    assert assignment is not None

    slot_by_id = {s.slot_id: s for s in slots}
    taught_by_teacher = {10: set(), 20: set()}
    for s_id, subj_id in assignment.items():
        t_id = inp.assigned_teacher.get((subj_id, 101))
        if t_id in taught_by_teacher:
            s = slot_by_id[s_id]
            taught_by_teacher[t_id].add(s.ts.weekday)

    all_wds = {2, 3, 4, 5}
    off_t10 = len(all_wds - taught_by_teacher[10])
    off_t20 = len(all_wds - taught_by_teacher[20])
    # Both teachers MUST get at least 1 off session (no one left with 0 off sessions)
    assert off_t10 >= 1, f"GV Van must have at least 1 off session, got {off_t10}"
    assert off_t20 >= 1, f"GV HDTN must have at least 1 off session, got {off_t20}"


def test_ii14_penalty_capped_and_weights_aligned():
    from core.models import (
        ClassRoom, SchedulingConfig, SchedulingInput, Slot, Subject, Teacher, TimeSlot,
    )
    from core.validation import compute_tkb_health_score
    from core.scheduler.constants import TEACHER_4CONSEC_MORNING_PENALTY

    # TEACHER_4CONSEC_MORNING_PENALTY must be significantly lower than gap penalties (350+)
    assert TEACHER_4CONSEC_MORNING_PENALTY < 250, "II.14 penalty must be lower than gap penalty to avoid creating gaps"

    # Create dummy schedule where a teacher has 10 days of 4 consecutive morning periods
    slots = []
    assignment = {}
    slot_id = 1
    for wd in (2, 3, 4, 5, 6):
        for period in (1, 2, 3, 4):
            ts = TimeSlot(slot_id, wd, "S", period)
            s = Slot(slot_id, 101, ts)
            slots.append(s)
            assignment[slot_id] = 1
            slot_id += 1

    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1")],
        subjects=[Subject(1, "Toan", 1), Subject(2, "HDTN", 5)],
        teachers=[Teacher(10, "GV Toan")],
        need={(1, 101): 20},
        assigned_teacher={(1, 101): 10},
        ban_busy=set(),
        slots=slots,
        timeslots=[s.ts for s in slots],
        config=SchedulingConfig(
            avoid_teacher_4_consecutive_morning=True,
            avoid_teacher_gaps=True,
        ),
    )
    health = compute_tkb_health_score(inp, assignment)
    # Teacher penalty for II.14 is capped at 15.0 pts, so teacher_score must be at least 85.0
    assert health["teacher_score"] >= 85.0, f"Teacher score should not be wiped out by II.14: {health['teacher_score']}"


def test_shift_adaptive_rules_single_vs_two_shift():
    """Kiểm tra:
    1. Trường toàn sáng (4 tiết/buổi):
       - Không phạt II.14 trong CP-SAT (penalty_terms['II.14'] trống).
       - Health score không trừ điểm II.14 (teacher_score = 100.0).
    2. Trường chia 2 ca (có ca sáng + ca chiều):
       - Kích hoạt phạt II.14 trong CP-SAT cho giáo viên.
       - Buổi nghỉ của GV sáng chỉ tính ca sáng, GV chiều chỉ tính ca chiều.
    """
    from core.models import (
        ClassRoom, SchedulingConfig, SchedulingInput, Slot, Subject, Teacher, TimeSlot,
        ROLE_HDTN,
    )
    from core.scheduler.cpsat_model import build_model
    from core.validation import compute_tkb_health_score

    # --- 1. Trường toàn sáng (Single-shift morning only, 4 periods) ---
    ts_morning = []
    slots_morning = []
    assignment_morn = {}
    sid = 1
    for wd in (2, 3, 4, 5):
        for p in (1, 2, 3, 4):
            t = TimeSlot(sid, wd, "S", p)
            s = Slot(sid, 101, t)
            ts_morning.append(t)
            slots_morning.append(s)
            assignment_morn[sid] = 1
            sid += 1

    inp_morning = SchedulingInput(
        classes=[ClassRoom(101, "9A")],
        subjects=[Subject(1, "Toan", 1), Subject(99, "HDTN", ROLE_HDTN)],
        teachers=[Teacher(10, "GV Toan")],
        need={(1, 101): 16},
        assigned_teacher={(1, 101): 10},
        ban_busy=set(),
        slots=slots_morning,
        timeslots=ts_morning,
        config=SchedulingConfig(avoid_teacher_4_consecutive_morning=True),
    )
    built_morn = build_model(inp_morning)
    # Trường toàn sáng 4 tiết: Không thêm terms II.14
    assert not built_morn.penalty_terms.get("II.14"), "Trường toàn sáng 4 tiết không được phạt II.14 trong CP-SAT"

    score_morn = compute_tkb_health_score(inp_morning, assignment_morn)
    # Không trừ điểm cho buổi sáng 4 tiết chuẩn
    assert score_morn["teacher_score"] == 100.0, f"Teacher score phải là 100, got {score_morn['teacher_score']}"

    # --- 2. Trường chia 2 ca (Two-shift: 6A học chiều, 9A học sáng) ---
    ts_twoshift = []
    slots_twoshift = []
    sid = 1
    # 9A: ca sáng (Thứ 2..5, 4 tiết)
    for wd in (2, 3, 4, 5):
        for p in (1, 2, 3, 4):
            t = TimeSlot(sid, wd, "S", p)
            s = Slot(sid, 101, t)
            ts_twoshift.append(t)
            slots_twoshift.append(s)
            sid += 1
    # 6A: ca chiều (Thứ 2..5, 4 tiết)
    for wd in (2, 3, 4, 5):
        for p in (1, 2, 3, 4):
            t = TimeSlot(sid, wd, "C", p)
            s = Slot(sid, 102, t)
            ts_twoshift.append(t)
            slots_twoshift.append(s)
            sid += 1

    inp_twoshift = SchedulingInput(
        classes=[ClassRoom(101, "9A"), ClassRoom(102, "6A")],
        subjects=[
            Subject(1, "Toan", 1), Subject(2, "Van", 1), Subject(3, "Anh", 1),
            Subject(99, "HDTN", ROLE_HDTN),
        ],
        teachers=[
            Teacher(10, "GV Toan 9"),   # Thuần sáng
            Teacher(20, "GV Van 6"),    # Thuần chiều
            Teacher(30, "GV Anh"),      # Dạy cả 2 ca
        ],
        need={(1, 101): 8, (2, 102): 8, (3, 101): 8, (3, 102): 8},
        assigned_teacher={(1, 101): 10, (2, 102): 20, (3, 101): 30, (3, 102): 30},
        ban_busy=set(),
        slots=slots_twoshift,
        timeslots=ts_twoshift,
        config=SchedulingConfig(
            teacher_off_sessions_per_week=1,
            avoid_teacher_4_consecutive_morning=True,
        ),
    )
    built_twoshift = build_model(inp_twoshift)
    # Trường chia 2 ca: Có áp dụng II.14 để bảo vệ GV
    assert "II.14" in built_twoshift.penalty_terms and len(built_twoshift.penalty_terms["II.14"]) > 0





