import pytest
from core.models import SchedulingConfig, TimeSlot, ClassRoom, Subject, ROLE_NANG, ROLE_THUONG, ROLE_GDTC
from tests.rule_helpers import violations_of


def test_scheduling_config_has_morning_academic_load_defaults():
    config = SchedulingConfig()
    assert hasattr(config, "balance_morning_academic_load")
    assert config.balance_morning_academic_load is True
    assert hasattr(config, "max_academic_per_morning")
    assert config.max_academic_per_morning == 3
    assert hasattr(config, "min_academic_per_morning")
    assert config.min_academic_per_morning == 2


def _make_scheduling_input_for_balance(academic_counts, light_counts, config=None):
    from core.models import SchedulingInput, Slot, Teacher, ROLE_THUONG, ROLE_HDTN

    if config is None:
        config = SchedulingConfig()

    ts = []
    slots = []
    slot_id = 1
    # 3 mornings: Monday (wd=2), Tuesday (wd=3), Wednesday (wd=4), each 4 periods
    for wd in (2, 3, 4):
        for p in (1, 2, 3, 4):
            t = TimeSlot(f"{wd}_S_{p}", wd, "S", p)
            ts.append(t)
            slots.append(Slot(slot_id, 101, t))
            slot_id += 1

    subjects = []
    teachers = []
    need = {}
    assigned_teacher = {}
    tid = 10

    for sid, name, cnt in academic_counts:
        subjects.append(Subject(sid, name, ROLE_THUONG))
        teachers.append(Teacher(tid, f"GV_{name}"))
        need[sid, 101] = cnt
        assigned_teacher[sid, 101] = tid
        tid += 10

    for sid, name, cnt in light_counts:
        subjects.append(Subject(sid, name, ROLE_THUONG))
        teachers.append(Teacher(tid, f"GV_{name}"))
        need[sid, 101] = cnt
        assigned_teacher[sid, 101] = tid
        tid += 10

    # HDTN required
    subjects.append(Subject(99, "HĐTN", ROLE_HDTN))
    teachers.append(Teacher(990, "GV_HDTN"))
    need[99, 101] = 0
    assigned_teacher[99, 101] = 990

    return SchedulingInput(
        classes=[ClassRoom(101, "6A1")],
        subjects=subjects,
        teachers=teachers,
        need=need,
        assigned_teacher=assigned_teacher,
        ban_busy=set(),
        slots=slots,
        timeslots=ts,
        config=config,
    )


def test_cpsat_morning_academic_hard_ceiling():
    import core.scheduler.cpsat_model as cpsat

    # 8 academic (Toán 2, Văn 2, Anh 2, KHTN 2) + 4 light (Tin 1, Nhạc 1, Họa 1, GDCD 1)
    # Total 12 slots across 3 mornings (4 slots/morning)
    academic_counts = [
        (1, "Toán học", 2),
        (2, "Ngữ văn", 2),
        (3, "Ngoại ngữ", 2),
        (4, "Khoa học tự nhiên", 2),
    ]
    light_counts = [
        (5, "Tin học", 1),
        (6, "Âm nhạc", 1),
        (7, "Mỹ thuật", 1),
        (8, "Giáo dục công dân", 1),
    ]
    inp = _make_scheduling_input_for_balance(academic_counts, light_counts)

    built = cpsat.build_model(inp)
    assignment = cpsat.solve(built, time_limit_s=5.0)
    assert assignment is not None, "Phải tìm được lời giải"

    academic_ids = {1, 2, 3, 4}
    overloads = violations_of("ACAD.MAX", inp, assignment)
    assert overloads == [], f"Không được có buổi sáng nào vượt quá 3 tiết học thuật: {overloads}"

    # Counts per morning must all be <= 3 (e.g. 3, 3, 2 in some order)
    counts = {
        wd: sum(1 for s in inp.slots if s.ts.weekday == wd and s.ts.session == "S" and assignment.get(s.slot_id) in academic_ids)
        for wd in (2, 3, 4)
    }
    for wd, cnt in counts.items():
        assert cnt <= 3, f"Sáng thứ {wd} có {cnt} tiết học thuật (> 3)!"


def test_cpsat_morning_academic_soft_floor():
    import core.scheduler.cpsat_model as cpsat

    # 6 academic subjects (1 each: Toán, Văn, Anh, KHTN Lý, KHTN Hóa, KHTN Sinh)
    # 6 light subjects (Tin 2, Nhạc 2, Họa 1, GDCD 1)
    # Total 12 slots across 3 mornings.
    # Without floor penalty, CP-SAT could schedule {2: 0, 3: 4, 4: 2} (Day 2 has 0 academic -> underload!).
    # With floor penalty (min_academic=2), CP-SAT must distribute (2, 2, 2).
    academic_counts = [
        (1, "Toán học", 1),
        (2, "Ngữ văn", 1),
        (3, "Ngoại ngữ", 1),
        (4, "Khoa học tự nhiên (Vật lý)", 1),
        (5, "Khoa học tự nhiên (Hóa học)", 1),
        (6, "Khoa học tự nhiên (Sinh học)", 1),
    ]
    light_counts = [
        (7, "Tin học", 2),
        (8, "Âm nhạc", 2),
        (9, "Mỹ thuật", 1),
        (10, "Giáo dục công dân", 1),
    ]
    inp = _make_scheduling_input_for_balance(academic_counts, light_counts)

    built = cpsat.build_model(inp)
    assignment = cpsat.solve(built, time_limit_s=5.0)
    assert assignment is not None, "Phải tìm được lời giải"

    academic_ids = {1, 2, 3, 4, 5, 6}
    underloads = violations_of("ACAD.MIN", inp, assignment)
    assert underloads == [], f"Mọi buổi sáng (có >= 3 tiết) cần có ít nhất 2 tiết học thuật: {underloads}"

    counts = {
        wd: sum(1 for s in inp.slots if s.ts.weekday == wd and s.ts.session == "S" and assignment.get(s.slot_id) in academic_ids)
        for wd in (2, 3, 4)
    }
    for wd, cnt in counts.items():
        assert cnt == 2, f"Sáng thứ {wd} có {cnt} tiết học thuật (kỳ vọng 2)!"


def test_health_score_includes_morning_academic_metrics():
    from core.validation import compute_tkb_health_score

    # Setup 1 morning with 4 academic subjects (overload)
    academic_counts = [
        (1, "Toán học", 2),
        (2, "Ngữ văn", 2),
    ]
    light_counts = [
        (3, "Tin học", 2),
        (4, "Âm nhạc", 2),
    ]
    inp = _make_scheduling_input_for_balance(academic_counts, light_counts)

    # Force an assignment where Monday morning has all 4 academic periods
    assignment = {
        1: 1, 2: 1, 3: 2, 4: 2,  # Mon morning: 4 academic
        5: 3, 6: 3, 7: 4, 8: 4,  # Tue morning: 0 academic
        9: None, 10: None, 11: None, 12: None,
    }

    health = compute_tkb_health_score(inp, assignment)
    assert "morning_academic_overload" in health["metrics"]
    assert "morning_academic_underload" in health["metrics"]
    assert health["metrics"]["morning_academic_overload"] >= 1
    assert any("quá tải" in rec["message"] for rec in health["recommendations"])


def test_cpsat_morning_academic_hard_floor_prevents_zero_academic():
    """Kiểm tra sàn cứng >= 1: Không bao giờ có buổi sáng >= 3 tiết nào bị 'trắng' môn học thuật (0 tiết)."""
    import core.scheduler.cpsat_model as cpsat

    academic_counts = [
        (1, "Toán học", 3),
        (2, "Ngữ văn", 3),
    ]
    # 6 tiết học thuật cho 3 buổi sáng (Thứ 2, 3, 4) -> Mỗi buổi sáng có 4 tiết
    light_counts = [
        (3, "Tin học", 2),
        (4, "Giáo dục thể chất", 2),
        (5, "Lịch sử và Địa lí", 2),
    ]
    inp = _make_scheduling_input_for_balance(academic_counts, light_counts)

    built = cpsat.build_model(inp)
    assignment = cpsat.solve(built, time_limit_s=5.0)
    assert assignment is not None, "Phải giải thành công"

    academic_ids = {1, 2}
    counts = {
        wd: sum(1 for s in inp.slots if s.ts.weekday == wd and s.ts.session == "S" and assignment.get(s.slot_id) in academic_ids)
        for wd in (2, 3, 4)
    }
    for wd, cnt in counts.items():
        assert cnt >= 1, f"Sáng thứ {wd} có {cnt} tiết học thuật (< 1), vi phạm sàn cứng!"


def test_cpsat_morning_academic_ceiling_when_heavy_morning_only():
    """Kiểm tra: Khi lớp có buổi chiều nhưng bật heavy_subjects_morning_only=True,
    và tổng số tiết học thuật (16 tiết / 5 sáng) vượt quá 5x3=15, trần sáng phải tự động
    nâng lên ceil(16/5) = 4 thay vì gây Infeasible model."""
    import core.scheduler.cpsat_model as cpsat
    from core.models import Subject, ClassRoom, TimeSlot, Slot, SchedulingConfig, SchedulingInput, Teacher, ROLE_NANG, ROLE_THUONG, ROLE_HDTN

    # 1 lớp học 5 sáng (mỗi sáng 4 tiết) + 1 chiều (3 tiết) = 23 slots
    ts_list = []
    slots = []
    slot_id = 1
    # 5 sáng (T2..T6)
    for wd in range(2, 7):
        for p in range(1, 5):
            t = TimeSlot(f"{wd}_S_{p}", wd, "S", p)
            ts_list.append(t)
            slots.append(Slot(slot_id, 101, t))
            slot_id += 1
    # 1 chiều (T3)
    for p in range(1, 4):
        t = TimeSlot(f"3_C_{p}", 3, "C", p)
        ts_list.append(t)
        slots.append(Slot(slot_id, 101, t))
        slot_id += 1

    # 16 tiết học thuật (Toán 4, Văn 4, Anh 4, KHTN 4) + 3 tiết nhẹ (Tin 3)
    subjects = [
        Subject(1, "Toán", ROLE_NANG),
        Subject(2, "Ngữ văn", ROLE_NANG),
        Subject(3, "Tiếng Anh", ROLE_NANG),
        Subject(4, "Khoa học tự nhiên", ROLE_NANG),
        Subject(5, "Tin học", ROLE_THUONG),
        Subject(99, "HĐTN", ROLE_HDTN),
    ]
    teachers = [
        Teacher(10, "GV_Toan"),
        Teacher(20, "GV_Van"),
        Teacher(30, "GV_Anh"),
        Teacher(40, "GV_KHTN"),
        Teacher(50, "GV_Tin"),
        Teacher(990, "GV_HDTN"),
    ]
    need = {(1, 101): 4, (2, 101): 4, (3, 101): 4, (4, 101): 4, (5, 101): 3, (99, 101): 0}
    assigned_teacher = {
        (1, 101): 10, (2, 101): 20, (3, 101): 30, (4, 101): 40, (5, 101): 50, (99, 101): 990
    }

    config = SchedulingConfig(
        heavy_subjects_morning_only=True,  # Cấm môn nặng ở chiều!
        balance_morning_academic_load=True,
        max_academic_per_morning=3,
        avoid_teacher_lone_periods=False,
    )
    inp = SchedulingInput(
        classes=[ClassRoom(101, "9A1")],
        subjects=subjects,
        teachers=teachers,
        slots=slots,
        timeslots=ts_list,
        need=need,
        assigned_teacher=assigned_teacher,
        ban_busy=set(),
        config=config,
    )

    built = cpsat.build_model(inp)
    assignment = cpsat.solve(built, time_limit_s=5.0)
    assert assignment is not None, "CP-SAT phải giải thành công nhờ dynamic ceiling!"

