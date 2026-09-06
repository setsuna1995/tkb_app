import pytest
from core.models import SchedulingConfig, TimeSlot, ClassRoom, Subject, ROLE_NANG, ROLE_THUONG, ROLE_GDTC
from core.validation import (
    find_morning_academic_overload_violations,
    find_morning_academic_underload_violations,
)


def _make_slot(slot_id, class_id, weekday, session, period):
    class DummySlot:
        def __init__(self, sid, cid, wd, sess, per):
            self.slot_id = sid
            self.class_id = cid
            self.ts = TimeSlot(f"{wd}_{sess}_{per}", weekday, session, per)
    return DummySlot(slot_id, class_id, weekday, session, period)


def test_scheduling_config_has_morning_academic_load_defaults():
    config = SchedulingConfig()
    assert hasattr(config, "balance_morning_academic_load")
    assert config.balance_morning_academic_load is True
    assert hasattr(config, "max_academic_per_morning")
    assert config.max_academic_per_morning == 3
    assert hasattr(config, "min_academic_per_morning")
    assert config.min_academic_per_morning == 2


def test_find_morning_academic_overload_violations():
    # 4 periods in morning, all 4 are academic (Toan=1, Van=2, Anh=3, Ly=4)
    academic_ids = {1, 2, 3, 4}
    slots = [
        _make_slot(1, 1, 2, "S", 1),
        _make_slot(2, 1, 2, "S", 2),
        _make_slot(3, 1, 2, "S", 3),
        _make_slot(4, 1, 2, "S", 4),
        # Tuesday morning: 3 academic + 1 light (gdtc=5) -> no violation
        _make_slot(5, 1, 3, "S", 1),
        _make_slot(6, 1, 3, "S", 2),
        _make_slot(7, 1, 3, "S", 3),
        _make_slot(8, 1, 3, "S", 4),
    ]
    assignment = {
        1: 1, 2: 2, 3: 3, 4: 4,  # Mon: 4 academic
        5: 1, 6: 2, 7: 3, 8: 5,  # Tue: 3 academic + 1 light
    }

    overloads = find_morning_academic_overload_violations(slots, assignment, academic_ids, max_academic=3)
    assert len(overloads) == 1
    assert overloads[0] == (1, 2, 4)  # class 1, Monday (wd 2), count 4


def test_find_morning_academic_underload_violations():
    academic_ids = {1, 2, 3, 4}
    slots = [
        # Monday morning: only 1 academic (Toan=1) + 3 light subjects (5, 6, 7) -> underload (<2)
        _make_slot(1, 1, 2, "S", 1),
        _make_slot(2, 1, 2, "S", 2),
        _make_slot(3, 1, 2, "S", 3),
        _make_slot(4, 1, 2, "S", 4),
        # Tuesday morning: 2 academic + 2 light -> normal (>=2)
        _make_slot(5, 1, 3, "S", 1),
        _make_slot(6, 1, 3, "S", 2),
        _make_slot(7, 1, 3, "S", 3),
        _make_slot(8, 1, 3, "S", 4),
        # Afternoon slots -> should be completely ignored
        _make_slot(9, 1, 2, "C", 1),
        _make_slot(10, 1, 2, "C", 2),
        _make_slot(11, 1, 2, "C", 3),
    ]
    assignment = {
        1: 1, 2: 5, 3: 6, 4: 7,  # Mon morning: 1 academic
        5: 1, 6: 2, 7: 5, 8: 6,  # Tue morning: 2 academic
        9: 5, 10: 6, 11: 7,      # Mon afternoon: 0 academic (ignored)
    }

    underloads = find_morning_academic_underload_violations(slots, assignment, academic_ids, min_academic=2)
    assert len(underloads) == 1
    assert underloads[0] == (1, 2, 1)  # class 1, Monday (wd 2), count 1


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
    overloads = find_morning_academic_overload_violations(inp.slots, assignment, academic_ids, max_academic=3)
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
    underloads = find_morning_academic_underload_violations(inp.slots, assignment, academic_ids, min_academic=2)
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




