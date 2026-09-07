from core.models import ClassRoom, SchedulingConfig, SchedulingInput, Slot, Subject, Teacher, TimeSlot, ROLE_HDTN
import core.scheduler.cpsat_model as cpsat


def test_pinned_full_day_off_on_friday_is_honored():
    """Kiểm tra: Khi BGH ghim nghỉ trọn ngày Thứ 6 cho GV (pinned_full_day_off=6),
    lệnh ghim này phải được tôn trọng và GV không có bất kỳ tiết nào vào Thứ 6,
    không bị FORBIDDEN_OFF_CELLS nuốt mất và không bị phạt II.3."""
    slots = []
    ts_list = []
    slot_id = 1
    for wd in range(2, 7):
        for p in range(1, 5):
            ts = TimeSlot(ts_id=slot_id, weekday=wd, session="S", period=p)
            ts_list.append(ts)
            slots.append(Slot(slot_id=slot_id, class_id=1, ts=ts))
            slot_id += 1

    subjects = [
        Subject(subject_id=1, name="Toán", role_code=0),
        Subject(subject_id=2, name="Ngữ văn", role_code=0),
        Subject(subject_id=3, name="Tiếng Anh", role_code=0),
        Subject(subject_id=4, name="Khoa học tự nhiên", role_code=0),
        Subject(subject_id=5, name="Giáo dục công dân", role_code=0),
        Subject(subject_id=99, name="HĐTN", role_code=ROLE_HDTN),
    ]
    need = {(1, 1): 4, (2, 1): 4, (3, 1): 4, (4, 1): 4, (5, 1): 4, (99, 1): 0}
    assigned_teacher = {(1, 1): 10, (2, 1): 20, (3, 1): 30, (4, 1): 40, (5, 1): 50, (99, 1): 990}
    teachers = [
        Teacher(teacher_id=10, name="GV Toán", pinned_full_day_off=6),
        Teacher(teacher_id=20, name="GV Văn"),
        Teacher(teacher_id=30, name="GV Anh"),
        Teacher(teacher_id=40, name="GV KHTN"),
        Teacher(teacher_id=50, name="GV GDCD"),
        Teacher(teacher_id=990, name="GV HDTN"),
    ]

    config = SchedulingConfig(
        strict_morning_weekdays=(),
        mandatory_morning_weekdays=(2, 5, 6),
    )
    inp = SchedulingInput(
        classes=[ClassRoom(class_id=1, name="6A", sort_order=0)],
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
    res = cpsat.solve_to_result(built, time_limit_s=5.0)
    assert res is not None and res.success is True
    # Kiểm tra GV 10 không có tiết nào vào Thứ 6
    eff_slots_t6 = [
        s.slot_id for s in slots if s.ts.weekday == 6 and res.assignment.get(s.slot_id) == 1
    ]
    assert len(eff_slots_t6) == 0, "GV đã được ghim nghỉ trọn ngày Thứ 6 thì không được có tiết Thứ 6"
    relaxed_ids = [r["rule_id"] for r in res.relaxed_rules]
    assert "II.3" not in relaxed_ids


def test_pinned_full_day_off_on_monday_is_honored():
    """Kiểm tra: BGH đã duyệt ghim nghỉ Thứ 2 cho GV (pinned_full_day_off=2),
    GV không có bất kỳ tiết nào vào Thứ 2 (kể cả sáng Thứ 2) và không bị phạt II.3."""
    slots = []
    ts_list = []
    slot_id = 1
    for wd in range(2, 7):
        for p in range(1, 5):
            ts = TimeSlot(ts_id=slot_id, weekday=wd, session="S", period=p)
            ts_list.append(ts)
            slots.append(Slot(slot_id=slot_id, class_id=1, ts=ts))
            slot_id += 1

    subjects = [
        Subject(subject_id=1, name="Toán", role_code=0),
        Subject(subject_id=2, name="Ngữ văn", role_code=0),
        Subject(subject_id=3, name="Tiếng Anh", role_code=0),
        Subject(subject_id=4, name="Khoa học tự nhiên", role_code=0),
        Subject(subject_id=5, name="Giáo dục công dân", role_code=0),
        Subject(subject_id=99, name="HĐTN", role_code=ROLE_HDTN),
    ]
    need = {(1, 1): 4, (2, 1): 4, (3, 1): 4, (4, 1): 4, (5, 1): 4, (99, 1): 0}
    assigned_teacher = {(1, 1): 10, (2, 1): 20, (3, 1): 30, (4, 1): 40, (5, 1): 50, (99, 1): 990}
    teachers = [
        Teacher(teacher_id=10, name="GV Toán", pinned_full_day_off=2),
        Teacher(teacher_id=20, name="GV Văn"),
        Teacher(teacher_id=30, name="GV Anh"),
        Teacher(teacher_id=40, name="GV KHTN"),
        Teacher(teacher_id=50, name="GV GDCD"),
        Teacher(teacher_id=990, name="GV HDTN"),
    ]

    config = SchedulingConfig(
        strict_morning_weekdays=(2,),
        mandatory_morning_weekdays=(2, 5, 6),
    )
    inp = SchedulingInput(
        classes=[ClassRoom(class_id=1, name="6A", sort_order=0)],
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
    res = cpsat.solve_to_result(built, time_limit_s=5.0)
    assert res is not None and res.success is True
    eff_slots_t2 = [
        s.slot_id for s in slots if s.ts.weekday == 2 and res.assignment.get(s.slot_id) == 1
    ]
    assert len(eff_slots_t2) == 0, "GV đã được BGH duyệt ghim nghỉ Thứ 2 thì không được có tiết Thứ 2"
    relaxed_ids = [r["rule_id"] for r in res.relaxed_rules]
    assert "II.3" not in relaxed_ids
