from core.models import ClassRoom, SchedulingConfig, SchedulingInput, Slot, Subject, Teacher, TimeSlot, ROLE_HDTN
import core.scheduler.cpsat_model as cpsat


def test_teacher_busy_morning_with_less_than_2_free_slots():
    """Kiểm tra: Khi GV bị bận 3/4 tiết sáng Thứ 2 (chỉ còn rảnh 1 tiết),
    GV phải được tự động coi là bận buổi sáng đó để không bị kẹt xung đột giữa
    II.3 (ép có mặt) và II.4 (cấm buổi 1 tiết)."""
    slots = []
    ts_list = []
    slot_id = 1
    # 2 sáng: Thứ 2 và Thứ 3 (mỗi sáng 4 tiết) = 8 slots
    for wd in (2, 3):
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
        Subject(subject_id=99, name="HĐTN", role_code=ROLE_HDTN),
    ]
    need = {(1, 1): 2, (2, 1): 2, (3, 1): 2, (4, 1): 2, (99, 1): 0}
    assigned_teacher = {(1, 1): 10, (2, 1): 20, (3, 1): 30, (4, 1): 40, (99, 1): 990}
    teachers = [
        Teacher(teacher_id=10, name="GV Toán"),
        Teacher(teacher_id=20, name="GV Văn"),
        Teacher(teacher_id=30, name="GV Anh"),
        Teacher(teacher_id=40, name="GV KHTN"),
        Teacher(teacher_id=990, name="GV HDTN"),
    ]
    # GV 10 bận tiết 1, 2, 3 của Thứ 2 -> chỉ rảnh tiết 4 (1 tiết duy nhất vào sáng Thứ 2)
    ban_busy = {(10, 1), (10, 2), (10, 3)}

    config = SchedulingConfig(
        strict_morning_weekdays=(2,),  # Sáng Thứ 2 bắt buộc toàn thể GV
        avoid_teacher_lone_periods=True,
    )
    inp = SchedulingInput(
        classes=[ClassRoom(class_id=1, name="6A1", sort_order=0)],
        subjects=subjects,
        teachers=teachers,
        slots=slots,
        timeslots=ts_list,
        need=need,
        assigned_teacher=assigned_teacher,
        ban_busy=ban_busy,
        config=config,
    )

    built = cpsat.build_model(inp)
    res = cpsat.solve_to_result(built, time_limit_s=5.0)
    assert res is not None and res.success is True
    # GV 10 không bị ép xếp vào tiết 4 sáng Thứ 2 (để tránh buổi lẻ II.4) và không bị phạt II.3
    relaxed_ids = [r["rule_id"] for r in res.relaxed_rules]
    assert "II.3" not in relaxed_ids
