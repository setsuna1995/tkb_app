import os
import pytest
from core.models import SchedulingConfig, SchedulingInput, Subject, Teacher, ClassRoom, TimeSlot, Slot, ROLE_THUONG, ROLE_HDTN
from core.scheduler.cpsat_model import build_model
from core.scheduler.cpsat.types import _HAS_ORTOOLS
from data import db, repository as repo
from io_excel.importer import import_xlsm

FIXTURE = os.path.join(os.path.dirname(__file__), "..", "io_excel", "sample_school.xlsm")


@pytest.mark.skipif(not _HAS_ORTOOLS, reason="CP-SAT unavailable")
def test_domain_pruning_excludes_morning_only_in_afternoon():
    """Biến x không được khởi tạo cho các môn morning_only ở các slot chiều."""
    ts_morning = TimeSlot(1, 2, "S", 2)
    ts_afternoon = TimeSlot(2, 2, "C", 1)
    slots = [Slot(1, 101, ts_morning), Slot(2, 101, ts_afternoon)]

    subjects = [
        Subject(1, "Toan", ROLE_THUONG),
        Subject(99, "HDTN", ROLE_HDTN),
    ]
    teachers = [Teacher(10, "GV Toan"), Teacher(99, "GV HDTN")]

    config = SchedulingConfig(morning_only_subject_ids=(1,))

    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1")],
        subjects=subjects,
        teachers=teachers,
        need={(1, 101): 1, (99, 101): 0},
        assigned_teacher={(1, 101): 10, (99, 101): 99},
        ban_busy=set(),
        slots=slots,
        timeslots=[ts_morning, ts_afternoon],
        config=config,
    )

    built = build_model(inp)
    # Slot 1 (sáng) có môn 1
    assert (1, 1) in built.x
    # Slot 2 (chiều) KHÔNG ĐƯỢC sinh biến x cho môn 1
    assert (2, 1) not in built.x


@pytest.mark.skipif(not _HAS_ORTOOLS, reason="CP-SAT unavailable")
def test_domain_pruning_excludes_teacher_ban_busy():
    """Biến x không được khởi tạo cho ô mà GV bị bận (ban_busy)."""
    ts = TimeSlot(1, 2, "S", 1)
    slots = [Slot(1, 101, ts)]

    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(99, "HDTN", ROLE_HDTN)]
    teachers = [Teacher(10, "GV Toan"), Teacher(99, "GV HDTN")]

    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1")],
        subjects=subjects,
        teachers=teachers,
        need={(1, 101): 1, (99, 101): 0},
        assigned_teacher={(1, 101): 10, (99, 101): 99},
        ban_busy={(10, 1)},  # GV Toan bận tại ts 1
        slots=slots,
        timeslots=[ts],
        config=SchedulingConfig(),
    )

    built = build_model(inp)
    # Vì GV Toan bận tại slot 1, biến (1, 1) không được sinh ra
    assert (1, 1) not in built.x


@pytest.mark.skipif(not _HAS_ORTOOLS, reason="CP-SAT unavailable")
def test_domain_pruning_reduces_sample_school_variables(tmp_path):
    """Trên dữ liệu trường thật, domain pruning cắt giảm đáng kể số biến x."""
    conn = db.get_connection(str(tmp_path / "test.db"))
    db.init_db(conn)
    import_xlsm(conn, FIXTURE)
    inp = repo.build_scheduling_input(conn, parity="C", seed=2026)
    conn.close()

    built = build_model(inp)
    # Kích thước trước đây không tỉa là 3,480 biến
    # Với pruning (bận, chào cờ, sáng, gdtc...), số biến phải giảm ít nhất 15% (dưới 3,100)
    assert len(built.x) < 3100, f"Expected len(built.x) < 3100, got {len(built.x)}"
