import pytest
from collections import Counter
from core.models import (
    ClassRoom, SchedulingConfig, SchedulingInput, Slot, Subject, Teacher, TimeSlot, ROLE_HDTN
)
import core.scheduler.cpsat_model as cpsat


def test_inter_school_teachers_hoa_and_trang():
    """Kiểm thử hai giáo viên liên trường:
    - Cô Hoà (7 tiết, off_sessions_override=3):
      + Phải có ít nhất 3 buổi nghỉ trọn vẹn trong các buổi trường học.
      + 7 tiết phải được gom gọn (mỗi buổi dạy >= 2 tiết), KHÔNG CÓ buổi lẻ 1 tiết nào.
    - Cô Trang (16 tiết, off_sessions_override=2):
      + Phải có ít nhất 2 buổi nghỉ trọn vẹn trong các buổi trường học.
    """
    slots = []
    ts_list = []
    slot_id = 1
    # 5 sáng (T2..T6, 4 tiết/buổi) + 3 chiều (T2..T4, 3 tiết/buổi) = 29 slots/lớp
    # 2 lớp: 6A (1) và 6B (2) -> 58 slots
    for wd in range(2, 7):
        for p in range(1, 5):
            ts = TimeSlot(ts_id=slot_id, weekday=wd, session="S", period=p)
            ts_list.append(ts)
            for c_id in (1, 2):
                slots.append(Slot(slot_id=slot_id, class_id=c_id, ts=ts))
                slot_id += 1
    for wd in (2, 3, 4):
        for p in range(1, 4):
            ts = TimeSlot(ts_id=slot_id, weekday=wd, session="C", period=p)
            ts_list.append(ts)
            for c_id in (1, 2):
                slots.append(Slot(slot_id=slot_id, class_id=c_id, ts=ts))
                slot_id += 1

    # Phân phối môn học thực tế:
    # Lớp 1 (29 tiết): Toán (4), Văn (4), Anh (3), Hóa (4), Sinh (2), GDCD (4), Địa (4), Sử (2), Công nghệ (1), Tin (1)
    # Lớp 2 (29 tiết): Toán (4), Văn (4), Anh (3), Hóa (4), Sinh (2), GDCD (4), Địa (4), Sử (2), Công nghệ (1), Tin (1)
    # Cô Hoà (GV 14): Sinh (2+2=4), Công nghệ (1+1=2), Tin lớp 2 (1) = 7 tiết
    # Cô Trang (GV 15): GDCD (4+4=8), Địa (4+4=8) = 16 tiết
    subjects = [
        Subject(1, "Toán"),
        Subject(2, "Ngữ văn"),
        Subject(3, "Tiếng Anh"),
        Subject(4, "KHTN: Hóa"),
        Subject(5, "KHTN: Sinh"),
        Subject(6, "GDCD"),
        Subject(7, "Địa lý"),
        Subject(8, "Lịch sử"),
        Subject(9, "Công nghệ"),
        Subject(10, "Tin học"),
        Subject(99, "HĐTN", role_code=ROLE_HDTN),
    ]
    need = {
        (1, 1): 4, (1, 2): 4,
        (2, 1): 4, (2, 2): 4,
        (3, 1): 3, (3, 2): 3,
        (4, 1): 4, (4, 2): 4,
        (5, 1): 2, (5, 2): 2,  # Hoà: 4 tiết Sinh
        (6, 1): 4, (6, 2): 4,  # Trang: 8 tiết GDCD
        (7, 1): 4, (7, 2): 4,  # Trang: 8 tiết Địa (tổng Trang = 16 tiết)
        (8, 1): 2, (8, 2): 2,  # GV 5: 4 tiết Sử
        (9, 1): 1, (9, 2): 1,  # Hoà: 2 tiết Công nghệ
        (10, 1): 1, (10, 2): 1, # Hoà: 1 tiết Tin (Lớp 2), GV 1: 1 tiết Tin (Lớp 1) -> Hoà = 7 tiết
        (99, 1): 0, (99, 2): 0,
    }
    assigned_teacher = {
        (1, 1): 1, (1, 2): 1,
        (2, 1): 2, (2, 2): 2,
        (3, 1): 3, (3, 2): 3,
        (4, 1): 4, (4, 2): 4,
        (5, 1): 14, (5, 2): 14,  # Cô Hoà
        (6, 1): 15, (6, 2): 15,  # Cô Trang
        (7, 1): 15, (7, 2): 15,  # Cô Trang
        (8, 1): 5, (8, 2): 5,
        (9, 1): 14, (9, 2): 14,  # Cô Hoà
        (10, 1): 1, (10, 2): 14, # Cô Hoà
        (99, 1): 1, (99, 2): 1,
    }
    teachers = [
        Teacher(teacher_id=1, name="GV 1"),
        Teacher(teacher_id=2, name="GV 2"),
        Teacher(teacher_id=3, name="GV 3"),
        Teacher(teacher_id=4, name="GV 4"),
        Teacher(teacher_id=5, name="GV 5"),
        Teacher(teacher_id=14, name="Cô Hoà", off_sessions_override=3),
        Teacher(teacher_id=15, name="Cô Trang", off_sessions_override=2),
    ]
    config = SchedulingConfig(
        teacher_off_sessions_per_week=1,
        teacher_off_sessions_mode="hard",
        reserved_off_weekdays_chieu=(5, 6),
        strict_morning_weekdays=(2,),
    )
    inp = SchedulingInput(
        classes=[ClassRoom(1, "6A"), ClassRoom(2, "6B")],
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
    res = cpsat.solve_to_result(built, time_limit_s=15.0)
    assert res is not None and res.success is True

    all_sessions = sorted({(ts.weekday, ts.session) for ts in ts_list})

    # 1. Kiểm tra Cô Hoà (GV 14, 7 tiết):
    hoa_slots = [s for s in slots if assigned_teacher.get((res.assignment.get(s.slot_id), s.class_id)) == 14]
    hoa_sessions = {(s.ts.weekday, s.ts.session) for s in hoa_slots}
    hoa_off_sessions = set(all_sessions) - hoa_sessions
    assert len(hoa_off_sessions) >= 3, (
        f"Cô Hoà phải có ít nhất 3 buổi nghỉ! Thực tế nghỉ {len(hoa_off_sessions)} buổi: {sorted(hoa_off_sessions)}"
    )

    # Đếm số tiết mỗi buổi của cô Hoà: KHÔNG ĐƯỢC có buổi nào chỉ có 1 tiết!
    hoa_sess_counts = Counter((s.ts.weekday, s.ts.session) for s in hoa_slots)
    for sess, count in hoa_sess_counts.items():
        assert count >= 2, f"Cô Hoà bị dính buổi lẻ 1 tiết tại {sess} ({count} tiết)!"

    # 2. Kiểm tra Cô Trang (GV 15, 16 tiết):
    trang_slots = [s for s in slots if assigned_teacher.get((res.assignment.get(s.slot_id), s.class_id)) == 15]
    trang_sessions = {(s.ts.weekday, s.ts.session) for s in trang_slots}
    trang_off_sessions = set(all_sessions) - trang_sessions
    assert len(trang_off_sessions) >= 2, (
        f"Cô Trang phải có ít nhất 2 buổi nghỉ! Thực tế nghỉ {len(trang_off_sessions)} buổi: {sorted(trang_off_sessions)}"
    )
