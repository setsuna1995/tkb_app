import pytest
from core.models import (
    ROLE_HDTN, ROLE_NANG, ROLE_THUONG, ClassRoom, SchedulingConfig,
    SchedulingInput, Slot, Subject, Teacher, TimeSlot,
)
from core.validation import compute_tkb_health_score


def test_perfect_tkb_health_score():
    """TKB hoàn hảo không vi phạm bất kỳ tiêu chí nào phải đạt 100 điểm."""
    ts = [
        TimeSlot(1, 2, "S", 1), TimeSlot(2, 2, "S", 2),
        TimeSlot(3, 4, "S", 1), TimeSlot(4, 4, "S", 2),
    ]
    slots = [Slot(i + 1, 101, t) for i, t in enumerate(ts)]
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(2, "Van", ROLE_THUONG)]
    teachers = [Teacher(10, "GV Toan"), Teacher(20, "GV Van")]
    assigned_teacher = {(1, 101): 10, (2, 101): 20}
    assignment = {1: 1, 2: 1, 3: 2, 4: 2}

    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1")],
        subjects=subjects,
        teachers=teachers,
        need={(1, 101): 2, (2, 101): 2},
        assigned_teacher=assigned_teacher,
        ban_busy=set(),
        slots=slots,
        timeslots=ts,
        config=SchedulingConfig(
            mandatory_morning_weekdays=(2, 4),
            min_weekly_periods_for_mandatory_morning=10,
            min_weekly_periods_for_lone_penalty=5,
        ),
    )

    health = compute_tkb_health_score(inp, assignment)
    assert health["overall_score"] == 100.0
    assert health["pedagogical_score"] == 100.0
    assert health["teacher_score"] == 100.0
    assert health["compliance_score"] == 100.0
    assert health["rating"] == "Xuất sắc"
    assert len(health["recommendations"]) == 0 or all(r["type"] == "success" for r in health["recommendations"])


def test_penalized_tkb_health_score():
    """TKB có vi phạm sư phạm và tiện nghi GV phải bị trừ điểm và có khuyến nghị."""
    # GV 10 có ca chiều T2 tiết 4 và sáng T3 tiết 1 (nhảy ca gắt)
    # Lớp 101 môn 1 học T2 và T3 (liền kề 2 ngày)
    ts = [
        TimeSlot(1, 2, "C", 4),
        TimeSlot(2, 3, "S", 1),
    ]
    slots = [Slot(1, 101, ts[0]), Slot(2, 101, ts[1])]
    subjects = [Subject(1, "Anh", ROLE_THUONG)]
    teachers = [Teacher(10, "GV Anh")]
    assigned_teacher = {(1, 101): 10}
    assignment = {1: 1, 2: 1}

    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1")],
        subjects=subjects,
        teachers=teachers,
        need={(1, 101): 2},
        assigned_teacher=assigned_teacher,
        ban_busy=set(),
        slots=slots,
        timeslots=ts,
        config=SchedulingConfig(teacher_off_sessions_per_week=0),
    )

    health = compute_tkb_health_score(inp, assignment)
    assert health["pedagogical_score"] < 100.0
    assert health["teacher_score"] < 100.0
    assert len(health["recommendations"]) > 0


def test_sample_school_health_score_integration(tmp_path):
    """Giải sample_school.xlsm và tính điểm sức khỏe TKB thực tế."""
    import os
    from data import db, repository as repo
    from io_excel.importer import import_xlsm
    from core.scheduler import run

    fixture = os.path.join(os.path.dirname(__file__), "..", "io_excel", "sample_school.xlsm")
    conn = db.get_connection(str(tmp_path / "test.db"))
    db.init_db(conn)
    import_xlsm(conn, fixture)
    inp = repo.build_scheduling_input(conn, parity="C", seed=2026)
    conn.close()

    inp.config.cpsat_time_limit_seconds = 15
    result = run(inp)
    assert result.success is True

    health = compute_tkb_health_score(inp, result.assignment)
    assert 0.0 <= health["overall_score"] <= 100.0
    assert 0.0 <= health["pedagogical_score"] <= 100.0
    assert 0.0 <= health["teacher_score"] <= 100.0
    assert 0.0 <= health["compliance_score"] <= 100.0
    assert health["rating"] in ("Xuất sắc", "Tốt", "Khá", "Cần cải thiện")
    assert isinstance(health["recommendations"], list)
    assert len(health["recommendations"]) > 0

