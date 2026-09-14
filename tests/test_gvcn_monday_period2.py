"""GVCN dạy tiết 2 thứ 2 của lớp chủ nhiệm -- ưu tiên mềm (không phải luật cứng).

GVCN của một lớp được suy ra qua assigned_teacher[(hdtn_id, class_id)] (giáo
viên được phân công dạy môn HĐTN của lớp đó), giống cách hệ thống đã dùng để
ghim chào cờ/SHL. Xem thiết kế đã duyệt: SchedulingConfig.gvcn_monday_period2_enabled
(mặc định True) + gvcn_monday_period2_exempt_class_ids (mặc định rỗng).
"""
import pytest

from core.models import (
    ROLE_HDTN, ROLE_THUONG, ClassRoom, SchedulingConfig, SchedulingInput,
    Slot, Subject, Teacher, TimeSlot,
)
from core.scheduler.cpsat_model import build_model, solve
from core.scheduler.cpsat.types import _HAS_ORTOOLS

pytestmark = pytest.mark.skipif(not _HAS_ORTOOLS, reason="CP-SAT unavailable")


def _minimal_input(config, need_toan=1):
    """1 lớp, 1 ô DUY NHẤT (Thứ 2, tiết 2). hdtn_thematic_week=True để tắt hẳn
    logic ghim chào cờ/SHL (không liên quan tới luật đang kiểm), giữ khung tối
    thiểu để test cấu trúc penalty_terms không lẫn với luật khác."""
    ts = [TimeSlot(1, 2, "S", 2)]
    slots = [Slot(1, 101, ts[0])]
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(99, "HDTN", ROLE_HDTN)]
    teachers = [Teacher(10, "GVCN"), Teacher(20, "GV khac")]
    return SchedulingInput(
        classes=[ClassRoom(101, "6A1")],
        subjects=subjects,
        teachers=teachers,
        need={(1, 101): need_toan, (99, 101): 0},
        assigned_teacher={(1, 101): 10, (99, 101): 10},
        ban_busy=set(), slots=slots, timeslots=ts,
        config=config,
        hdtn_thematic_week=True,
    )


def test_penalty_term_present_when_class_has_determinable_gvcn():
    """GVCN (GV 10) dạy cả HĐTN lẫn Toán cho lớp 101 -> xác định được GVCN,
    ô Thứ 2 tiết 2 của lớp phải sinh ra penalty term theo dõi việc GVCN có
    dạy ô đó hay không."""
    built = build_model(_minimal_input(SchedulingConfig()))
    assert "_gvcn_monday_period2" in built.penalty_terms


def test_no_penalty_term_when_globally_disabled():
    config = SchedulingConfig(gvcn_monday_period2_enabled=False)
    built = build_model(_minimal_input(config))
    assert "_gvcn_monday_period2" not in built.penalty_terms


def test_no_penalty_term_for_exempt_class():
    """2 lớp cùng có GVCN xác định được, nhưng lớp 101 nằm trong danh sách
    miễn trừ -> chỉ lớp 102 (không miễn trừ) sinh ra penalty term."""
    ts = [TimeSlot(1, 2, "S", 2)]
    slots = [Slot(1, 101, ts[0]), Slot(2, 102, ts[0])]
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(2, "Van", ROLE_THUONG),
                Subject(99, "HDTN", ROLE_HDTN)]
    teachers = [Teacher(10, "GVCN 101"), Teacher(30, "GVCN 102")]
    config = SchedulingConfig(gvcn_monday_period2_exempt_class_ids=frozenset({101}))
    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1"), ClassRoom(102, "6A2")],
        subjects=subjects,
        teachers=teachers,
        need={(1, 101): 1, (99, 101): 0, (2, 102): 1, (99, 102): 0},
        assigned_teacher={(1, 101): 10, (99, 101): 10, (2, 102): 30, (99, 102): 30},
        ban_busy=set(), slots=slots, timeslots=ts,
        config=config,
        hdtn_thematic_week=True,
    )
    built = build_model(inp)
    assert len(built.penalty_terms.get("_gvcn_monday_period2", [])) == 1, (
        "chỉ lớp 102 (không miễn trừ) được sinh penalty term, lớp 101 phải bị bỏ qua"
    )


def _full_scenario(config, extra_slot_for_class_102=False):
    """1 lớp (101) đúng khít định mức: chào cờ (Thứ 2 tiết 1, ghim), SHL (Thứ 7,
    ghim) chiếm 2/2 tiết HĐTN; còn lại đúng 2 ô tranh chấp (Thứ 2 tiết 2 và Thứ
    3 tiết 1) cho Toán (dạy bởi GVCN) và Văn (GV khác) -- mỗi môn need=1.
    Không có ràng buộc mới thì có 2 cách xếp hợp lệ ngang nhau; ưu tiên mềm
    phải buộc solver chọn cách đặt Toán (GVCN) vào đúng Thứ 2 tiết 2."""
    ts1 = TimeSlot(1, 2, "S", 1)   # Mon P1 -- chào cờ (ghim)
    ts2 = TimeSlot(2, 2, "S", 2)   # Mon P2 -- tranh chấp (mục tiêu của luật mới)
    ts3 = TimeSlot(3, 3, "S", 1)   # Tue P1 -- tranh chấp (ô còn lại)
    ts4 = TimeSlot(4, 7, "S", 1)   # Sat P1 -- SHL (ghim)
    slots = [Slot(1, 101, ts1), Slot(2, 101, ts2), Slot(3, 101, ts3), Slot(4, 101, ts4)]
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(2, "Van", ROLE_THUONG),
                Subject(99, "HDTN", ROLE_HDTN)]
    teachers = [Teacher(10, "GVCN"), Teacher(20, "GV Van")]
    need = {(1, 101): 1, (2, 101): 1, (99, 101): 2}
    assigned_teacher = {(1, 101): 10, (2, 101): 20, (99, 101): 10}
    all_slots = list(slots)
    if extra_slot_for_class_102:
        # Lớp 102 cần CẢ tiết 1 (Ly, GV khác) lẫn tiết 2 (Sinh, cùng GVCN) Thứ 2
        # -- không thể chỉ có mỗi ô tiết 2 đơn độc: luật "không hở tiết" (rule 5,
        # _add_class_constraints) cấm cứng một lớp có ô tiết P>1 mà không có ô
        # tiết P-1 cùng buổi/ngày trong khung của lớp đó.
        subjects = subjects + [Subject(3, "Sinh", ROLE_THUONG), Subject(4, "Ly", ROLE_THUONG)]
        need[(3, 102)] = 1
        need[(4, 102)] = 1
        assigned_teacher[(3, 102)] = 10
        assigned_teacher[(4, 102)] = 40
        teachers.append(Teacher(40, "GV Ly"))
        all_slots.append(Slot(5, 102, ts1))
        all_slots.append(Slot(6, 102, ts2))
    classes = [ClassRoom(101, "6A1")] if not extra_slot_for_class_102 else \
        [ClassRoom(101, "6A1"), ClassRoom(102, "6A2")]
    return SchedulingInput(
        classes=classes, subjects=subjects, teachers=teachers,
        need=need, assigned_teacher=assigned_teacher,
        ban_busy=set(), slots=all_slots, timeslots=[ts1, ts2, ts3, ts4],
        config=config,
    )


def test_gvcn_preferred_over_other_teacher_for_monday_period2():
    inp = _full_scenario(SchedulingConfig())
    built = build_model(inp)
    assignment = solve(built, time_limit_s=10.0)
    assert assignment is not None
    assert assignment[2] == 1, (
        "Thứ 2 tiết 2 (slot 2) phải được ưu tiên gán cho Toán (dạy bởi GVCN, "
        f"GV 10), không phải Văn (GV 20): {assignment}"
    )


def test_gvcn_penalty_is_soft_not_hard_when_teacher_double_booked_elsewhere():
    """Lớp 102 chỉ có đúng 1 ô, trùng giờ (cùng ts_id) với ô Thứ 2 tiết 2 của
    lớp 101, và bắt buộc dùng đúng GVCN (GV 10) -- theo luật cứng "GV không
    dạy 2 lớp cùng tiết" thì GVCN không thể có mặt ở ô Thứ 2 tiết 2 của lớp
    101 nữa. Ưu tiên MỀM này không được biến bài toán thành vô nghiệm."""
    inp = _full_scenario(SchedulingConfig(), extra_slot_for_class_102=True)
    built = build_model(inp)
    assignment = solve(built, time_limit_s=10.0)
    assert assignment is not None, (
        "GVCN bị lớp 102 giữ chân đúng giờ Thứ 2 tiết 2 -- ưu tiên GVCN dạy "
        "lớp chủ nhiệm phải là RÀNG BUỘC MỀM, không được làm bài toán vô nghiệm"
    )
    assert assignment[2] == 2, "GVCN đang bận dạy lớp 102 nên Văn phải nhận ô Thứ 2 tiết 2 của lớp 101"
    assert assignment[3] == 1, "Toán (không xếp được ô ưu tiên) bị đẩy sang ô còn lại (Thứ 3)"


def test_gvcn_does_not_teach_other_class_at_monday_period2():
    """GV 10 là GVCN lớp 101 (dạy Toán cho cả 101 và 102).
    GV 20 là GVCN lớp 102 (dạy Văn cho cả 101 và 102).
    Vào Thứ 2 tiết 2, solver phải xếp GV 10 dạy đúng lớp 101 (chủ nhiệm),
    và GV 20 dạy đúng lớp 102 (chủ nhiệm), không được tráo đổi lớp của nhau."""
    ts1 = TimeSlot(1, 2, "S", 1)  # Mon P1 - Chào cờ
    ts2 = TimeSlot(2, 2, "S", 2)  # Mon P2 - Tranh chấp
    ts3 = TimeSlot(3, 3, "S", 1)  # Tue P1
    ts4 = TimeSlot(4, 7, "S", 1)  # Sat P1 - SHL
    slots = [
        Slot(1, 101, ts1), Slot(2, 101, ts2), Slot(3, 101, ts3), Slot(4, 101, ts4),
        Slot(5, 102, ts1), Slot(6, 102, ts2), Slot(7, 102, ts3), Slot(8, 102, ts4),
    ]
    subjects = [
        Subject(1, "Toan", ROLE_THUONG),
        Subject(2, "Van", ROLE_THUONG),
        Subject(99, "HDTN", ROLE_HDTN),
    ]
    teachers = [Teacher(10, "GVCN 101"), Teacher(20, "GVCN 102")]
    # 101: Toan(10), Van(20), HDTN(10)
    # 102: Toan(10), Van(20), HDTN(20)
    need = {
        (1, 101): 1, (2, 101): 1, (99, 101): 2,
        (1, 102): 1, (2, 102): 1, (99, 102): 2,
    }
    assigned_teacher = {
        (1, 101): 10, (2, 101): 20, (99, 101): 10,
        (1, 102): 10, (2, 102): 20, (99, 102): 20,
    }
    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1"), ClassRoom(102, "6A2")],
        subjects=subjects,
        teachers=teachers,
        need=need,
        assigned_teacher=assigned_teacher,
        ban_busy=set(),
        slots=slots,
        timeslots=[ts1, ts2, ts3, ts4],
        config=SchedulingConfig(),
    )
    built = build_model(inp)
    assignment = solve(built, time_limit_s=10.0)
    assert assignment is not None
    # Slot 2 là Mon P2 của lớp 101 -> Phải gán Toán (GV 10 là GVCN 101)
    assert assignment[2] == 1, f"Lớp 101 Tiết 2 T2 phải là Toán (GVCN 10): {assignment}"
    # Slot 6 là Mon P2 của lớp 102 -> Phải gán Văn (GV 20 là GVCN 102)
    assert assignment[6] == 2, f"Lớp 102 Tiết 2 T2 phải là Văn (GVCN 20): {assignment}"

