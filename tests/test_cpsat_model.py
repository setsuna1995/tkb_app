import pytest

from core.models import (
    ROLE_GDTC, ROLE_HDTN, ROLE_NANG, ROLE_THUONG, ClassRoom, SchedulingConfig,
    SchedulingInput, Slot, Subject, Teacher, TimeSlot,
)
from core.validation import compute_quota_diff

cpsat = pytest.importorskip("core.scheduler.cpsat_model")


def _tiny_input():
    """1 lớp, 6 ô sáng, MỖI ô một ngày riêng (Thứ 2..Chủ nhật=8, tiết 1), 2 môn
    cần 3 tiết mỗi môn. Vừa khít 6 ô = 6 tiết, nên mọi ô đều phải có môn. Dùng
    6 ngày RIÊNG (thay vì 2 ngày x 3 tiết như bản cũ trước Task 4) để tương
    thích với luật khung LỚP mới (task-4-brief.md luật 1: trần 1 tiết/môn/
    ngày/lớp cho môn thường -- xếp 3 tiết Toán trong CÙNG 1 ngày giờ là bất
    hợp lệ)."""
    ts = [TimeSlot(i + 1, wd, "S", 1) for i, wd in enumerate([2, 3, 4, 5, 6, 7])]
    slots = [Slot(i + 1, 101, t) for i, t in enumerate(ts)]
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]
    return SchedulingInput(
        classes=[ClassRoom(101, "6A1")],
        subjects=subjects,
        teachers=[Teacher(10, "GV A"), Teacher(20, "GV B")],
        need={(1, 101): 3, (2, 101): 3},
        assigned_teacher={(1, 101): 10, (2, 101): 20},
        ban_busy=set(), slots=slots, timeslots=ts,
        config=SchedulingConfig(),
    )


def test_solution_meets_every_subject_class_quota():
    inp = _tiny_input()
    built = cpsat.build_model(inp)
    assignment = cpsat.solve(built, time_limit_s=10.0)
    assert assignment is not None, "phải giải được bài toán vừa khít này"

    diff = compute_quota_diff(inp.slots, assignment, inp.need)
    bad = {k: v for k, v in diff.items() if v != 0}
    assert bad == {}, f"sai định mức: {bad}"


def test_each_cell_holds_at_most_one_subject():
    inp = _tiny_input()
    built = cpsat.build_model(inp)
    assignment = cpsat.solve(built, time_limit_s=10.0)
    # assignment là dict slot_id -> subject_id nên "tối đa 1" là bất biến của
    # kiểu dữ liệu; điều cần khẳng định là không ô nào bị bỏ sót ở bài vừa khít.
    assert len(assignment) == len(inp.slots)


def test_leaves_cells_empty_when_there_is_slack():
    """Dư địa > 0: chỉ cần 2 tiết cho 6 ô -> 4 ô phải để trống, không được
    nhồi cho đủ. Engine cũ để trống bằng sentinel -1; ở đây ô trống đơn giản
    là không có mặt trong dict kết quả."""
    inp = _tiny_input()
    inp.need = {(1, 101): 2}
    built = cpsat.build_model(inp)
    assignment = cpsat.solve(built, time_limit_s=10.0)
    assert assignment is not None
    assert len(assignment) == 2
    assert all(sid == 1 for sid in assignment.values())


def test_teacher_never_double_booked():
    """2 lớp, cùng 4 ô sáng (4 NGÀY riêng, tiết 1 mỗi ngày -- tương thích luật
    trần 1 tiết/môn/ngày/lớp của Task 4); 1 GV dạy cả 2 lớp mỗi lớp 2 tiết.
    Nếu thiếu ràng buộc trùng giờ, bộ giải có thể xếp GV đó vào cùng ts_id ở
    2 lớp."""
    ts = [TimeSlot(i + 1, wd, "S", 1) for i, wd in enumerate([2, 3, 4, 5])]
    slots = [Slot(i + 1, 101, t) for i, t in enumerate(ts)] + \
            [Slot(i + 5, 102, t) for i, t in enumerate(ts)]
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]
    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1"), ClassRoom(102, "6A2")],
        subjects=subjects,
        teachers=[Teacher(10, "GV A")],
        need={(1, 101): 2, (1, 102): 2},
        assigned_teacher={(1, 101): 10, (1, 102): 10},
        ban_busy=set(), slots=slots, timeslots=ts, config=SchedulingConfig(),
    )
    built = cpsat.build_model(inp)
    assignment = cpsat.solve(built, time_limit_s=10.0)
    assert assignment is not None
    from core.validation import find_teacher_conflicts
    assert find_teacher_conflicts(inp.slots, assignment, inp.assigned_teacher) == []


def test_teacher_respects_busy_slots():
    """1 lớp, 4 ô sáng (4 NGÀY riêng, tiết 1 mỗi ngày -- tương thích luật trần
    1 tiết/môn/ngày/lớp của Task 4); 1 GV dạy 1 môn cần 3/4 tiết (dư 1 ô), GV
    bị khai GV_Bận đúng ô đầu tiên (ts thứ 1). Nếu thiếu ràng buộc GV_Bận, bộ
    giải có thể xếp đúng vào ô bận đó vì không có gì ngăn cản."""
    ts = [TimeSlot(i + 1, wd, "S", 1) for i, wd in enumerate([2, 3, 4, 5])]
    slots = [Slot(i + 1, 101, t) for i, t in enumerate(ts)]
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]
    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1")],
        subjects=subjects,
        teachers=[Teacher(10, "GV A")],
        need={(1, 101): 3},
        assigned_teacher={(1, 101): 10},
        ban_busy={(10, ts[0].ts_id)}, slots=slots, timeslots=ts,
        config=SchedulingConfig(),
    )
    built = cpsat.build_model(inp)
    assignment = cpsat.solve(built, time_limit_s=10.0)
    assert assignment is not None
    from core.validation import find_teacher_unavailability_violations
    assert find_teacher_unavailability_violations(
        inp.slots, assignment, inp.assigned_teacher, inp.ban_busy) == []


def test_teacher_respects_daily_cap():
    """1 lớp, 4 ô: 3 ô sáng T2 (tiết 1-3) + 1 ô sáng T3 (tiết 1); 1 GV dạy 1
    môn cần đúng 3/4 tiết, max_teacher_periods_per_day=2. Nếu thiếu ràng buộc
    trần tiết/ngày CỦA GV, bộ giải có thể dồn cả 3 tiết vào T2, vượt trần 2
    tiết/ngày -- trong khi vẫn còn ô T3 để dùng thay. Dùng HĐTN tuần chuyên đề
    (block_size=3, xem task-4-brief.md luật 1+4) làm môn thử thay vì môn
    thường, vì luật khung LỚP mới của Task 4 tự nó đã cấm môn thường xếp 3
    tiết cùng ngày -- cần một môn được PHÉP 3 tiết/ngày ở cấp LỚP để phép thử
    còn cô lập đúng luật trần GV (Task 2), không lẫn với luật trần lớp mới."""
    ts = [TimeSlot(1, 2, "S", 1), TimeSlot(2, 2, "S", 2), TimeSlot(3, 2, "S", 3),
          TimeSlot(4, 3, "S", 1)]
    slots = [Slot(i + 1, 101, t) for i, t in enumerate(ts)]
    subjects = [Subject(1, "HDTN", ROLE_HDTN)]
    config = SchedulingConfig(max_teacher_periods_per_day=2)
    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1")],
        subjects=subjects,
        teachers=[Teacher(10, "GV A")],
        need={(1, 101): 3},
        assigned_teacher={(1, 101): 10},
        ban_busy=set(), slots=slots, timeslots=ts, config=config,
        hdtn_thematic_week=True,
    )
    built = cpsat.build_model(inp)
    assignment = cpsat.solve(built, time_limit_s=10.0)
    assert assignment is not None
    from core.validation import find_teacher_day_cap_violations
    assert find_teacher_day_cap_violations(
        inp.slots, assignment, inp.assigned_teacher, max_per_day=2) == []


# ---------------------------------------------------------------------------
# Task 3: ràng buộc MÔN HỌC (task-3-brief.md). Mỗi test ép đúng 1 luật cắn bằng
# cách cho môn "khan hiếm" (need nhỏ) và môn "lấp chỗ" (need lớn) cùng tranh
# một tập ô vừa khít -- không có ràng buộc thì bộ giải tự nhiên dồn môn khan
# hiếm vào ô cuối cùng được tạo, đúng ô mà luật đang kiểm cấm. Xác nhận bằng
# hàm thẩm định của core/validation.py theo đúng bảng trong brief.
# ---------------------------------------------------------------------------


def test_morning_only_subject_never_scheduled_afternoon():
    """Luật 1: môn bắt buộc buổi sáng. 4 ô sáng (4 NGÀY riêng, tiết 1 mỗi ngày
    -- tương thích luật trần 1 tiết/môn/ngày/lớp của Task 4) + 1 ô chiều (ngày
    thứ 5, tiết 1, tạo SAU CÙNG). Môn Văn (morning-only) cần 1 tiết, môn Toán
    cần 4 -- vừa khít 5 ô. Không ràng buộc thì bộ giải dồn Văn (need nhỏ) vào
    ô cuối (ô chiều)."""
    ts = [TimeSlot(i + 1, wd, "S", 1) for i, wd in enumerate([2, 3, 4, 5])] + [TimeSlot(5, 6, "C", 1)]
    slots = [Slot(i + 1, 101, t) for i, t in enumerate(ts)]
    subjects = [Subject(1, "Van", ROLE_THUONG), Subject(2, "Toan", ROLE_THUONG),
                Subject(3, "HDTN", ROLE_HDTN)]
    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1")], subjects=subjects,
        teachers=[Teacher(10, "GV A"), Teacher(20, "GV B")],
        need={(1, 101): 1, (2, 101): 4},
        assigned_teacher={(1, 101): 10, (2, 101): 20},
        ban_busy=set(), slots=slots, timeslots=ts,
        config=SchedulingConfig(morning_only_subject_ids=frozenset({1})),
    )
    built = cpsat.build_model(inp)
    assignment = cpsat.solve(built, time_limit_s=10.0)
    assert assignment is not None
    from core.validation import find_morning_only_violations
    assert find_morning_only_violations(inp.slots, assignment, {1}) == []


def test_heavy_subject_morning_only_when_enabled():
    """Luật 2 (không có hàm thẩm định riêng -> assert thủ công). Cùng khung ô
    như test luật 1, nhưng môn khan hiếm là môn Nặng và bật
    heavy_subjects_morning_only -- môn Nặng cấm cứng buổi chiều."""
    ts = [TimeSlot(i + 1, wd, "S", 1) for i, wd in enumerate([2, 3, 4, 5])] + [TimeSlot(5, 6, "C", 1)]
    slots = [Slot(i + 1, 101, t) for i, t in enumerate(ts)]
    subjects = [Subject(1, "KHTN", ROLE_NANG), Subject(2, "Toan", ROLE_THUONG),
                Subject(3, "HDTN", ROLE_HDTN)]
    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1")], subjects=subjects,
        teachers=[Teacher(10, "GV A"), Teacher(20, "GV B")],
        need={(1, 101): 1, (2, 101): 4},
        assigned_teacher={(1, 101): 10, (2, 101): 20},
        ban_busy=set(), slots=slots, timeslots=ts,
        config=SchedulingConfig(heavy_subjects_morning_only=True),
    )
    built = cpsat.build_model(inp)
    assignment = cpsat.solve(built, time_limit_s=10.0)
    assert assignment is not None
    slot_by_id = {s.slot_id: s for s in inp.slots}
    bad = [(sid, slot_by_id[sid].ts) for sid, subj in assignment.items()
           if subj == 1 and slot_by_id[sid].ts.session == "C"]
    assert bad == [], f"môn Nặng bị xếp buổi chiều dù heavy_subjects_morning_only=True: {bad}"


def test_gdtc_respects_allowed_periods():
    """GDTC chỉ được tiết 1-4 sáng. Cho lớp 5 ô sáng CÙNG 1 buổi (tiết 1-5) và
    cần đúng 1 tiết GDTC -> bộ giải không được chọn tiết 5. 4 ô còn lại của
    buổi này được lấp bằng 4 MÔN THƯỜNG khác nhau (thay vì 1 môn Toán x4 như
    bản trước Task 4) vì luật trần 1 tiết/môn/ngày/lớp của Task 4 cấm 1 môn
    thường xuất hiện 4 lần cùng ngày; dùng 4 môn riêng vẫn giữ nguyên bản chất
    phép thử (buổi đủ 5 ô, GDTC phải né tiết 5)."""
    ts = [TimeSlot(i + 1, 2, "S", i + 1) for i in range(5)]
    slots = [Slot(i + 1, 101, t) for i, t in enumerate(ts)]
    subjects = [Subject(1, "GDTC", ROLE_GDTC), Subject(2, "HDTN", ROLE_HDTN),
                Subject(3, "Toan", ROLE_THUONG), Subject(4, "Van", ROLE_THUONG),
                Subject(5, "Anh", ROLE_THUONG), Subject(6, "Su", ROLE_THUONG)]
    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1")], subjects=subjects,
        teachers=[Teacher(10, "GV")],
        need={(1, 101): 1, (3, 101): 1, (4, 101): 1, (5, 101): 1, (6, 101): 1},
        assigned_teacher={(1, 101): 10, (3, 101): 10, (4, 101): 10,
                           (5, 101): 10, (6, 101): 10},
        ban_busy=set(), slots=slots, timeslots=ts,
        config=SchedulingConfig(gdtc_morning_allowed_periods=(1, 2, 3, 4),
                                 max_periods_per_session=5),
    )
    built = cpsat.build_model(inp)
    assignment = cpsat.solve(built, time_limit_s=10.0)
    assert assignment is not None
    from core.validation import find_invalid_gdtc_periods
    assert find_invalid_gdtc_periods(inp.slots, assignment, 1,
                                      inp.config.gdtc_morning_allowed_periods,
                                      inp.config.gdtc_afternoon_allowed_periods) == []


def test_subject_not_scheduled_on_consecutive_days():
    """Luật 4: 3 ngày (Thứ 2,3,4), mỗi ngày 1 ô. Văn (non_consecutive) cần 2
    tiết, Toán cần 1 -- vừa khít 3 ô. Không ràng buộc thì bộ giải dồn Toán
    (need nhỏ) vào ngày cuối (Thứ 4), ép Văn vào Thứ 2+Thứ 3 liền kề (vi
    phạm). Với luật 4 bật, cấu hình khả thi duy nhất là Toán->Thứ 3, Văn->Thứ
    2 + Thứ 4 -- hai ngày này CÁCH nhau 1 ngày nên không "liền kề"."""
    ts = [TimeSlot(1, 2, "S", 1), TimeSlot(2, 3, "S", 1), TimeSlot(3, 4, "S", 1)]
    slots = [Slot(i + 1, 101, t) for i, t in enumerate(ts)]
    subjects = [Subject(1, "Van", ROLE_THUONG), Subject(2, "Toan", ROLE_THUONG),
                Subject(3, "HDTN", ROLE_HDTN)]
    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1")], subjects=subjects,
        teachers=[Teacher(10, "GV A"), Teacher(20, "GV B")],
        need={(1, 101): 2, (2, 101): 1},
        assigned_teacher={(1, 101): 10, (2, 101): 20},
        ban_busy=set(), slots=slots, timeslots=ts,
        config=SchedulingConfig(non_consecutive_subject_ids=frozenset({1})),
    )
    built = cpsat.build_model(inp)
    assignment = cpsat.solve(built, time_limit_s=10.0)
    assert assignment is not None
    from core.validation import find_consecutive_subject_days
    assert find_consecutive_subject_days(inp.slots, assignment, {1}) == []


def test_max_heavy_per_session():
    """Luật 5, cô lập thật sự khỏi luật 6 (review round: bản trước dùng cấu
    hình mặc định max_heavy_per_session=3 == max_heavy_consecutive=3 trên 1
    buổi đúng 4 ô -- cửa sổ trượt của luật 6 (kích thước 4) khi đó trùng khít
    CẢ buổi, nên tự luật 6 đã ép "tổng buổi <= 3" giống hệt luật 5; xoá luật 5
    đi test đó vẫn PASS, không chứng minh được gì).

    Bản này dùng max_heavy_consecutive=2 (< max_heavy_per_session=2, để công
    thức max(...) không đội trần buổi lên theo luật 6) và 3 buổi RIÊNG cho
    lớp: Thứ 3 (2 ô), Thứ 2 (4 ô), Thứ 4 (1 ô) -- tổng trần-theo-luật-5 vừa
    đúng bằng nhu cầu (2+2+1=5), buộc lời giải hợp lệ gần như duy nhất.

    Dùng 5 MÔN NẶNG RIÊNG (H1..H5, mỗi môn need=1) thay vì 1 môn Nặng duy
    nhất cần 5 tiết như bản trước Task 4: luật trần 1 tiết/môn/ngày/lớp mới
    (task-4-brief.md luật 1) cấm 1 môn xuất hiện 2 lần cùng ngày (ở đây Thứ 3
    và Thứ 2 đều cần 2 tiết Nặng/ngày), trong khi luật 5 (max_heavy_per_
    session) vốn kiểm TỔNG số tiết Nặng trong 1 buổi CỘNG DỒN từ nhiều môn
    Nặng khác nhau -- đúng cách môn Nặng vận hành trong dữ liệu trường thật
    (nhiều môn Nặng khác nhau cùng chia sẻ 1 buổi), không phải 1 môn lặp lại.
    Tương tự, 2 tiết Toán tách thành F1/F2 (mỗi môn need=1) vì cả 2 đều rơi
    cùng buổi Thứ 2."""
    ts = [TimeSlot(1, 3, "S", 1), TimeSlot(2, 3, "S", 2),
          TimeSlot(3, 2, "S", 1), TimeSlot(4, 2, "S", 2), TimeSlot(5, 2, "S", 3), TimeSlot(6, 2, "S", 4),
          TimeSlot(7, 4, "S", 1)]
    slots = [Slot(i + 1, 101, t) for i, t in enumerate(ts)]
    heavy_ids = {1, 2, 3, 4, 5}
    subjects = [Subject(1, "H1", ROLE_NANG), Subject(2, "H2", ROLE_NANG),
                Subject(3, "H3", ROLE_NANG), Subject(4, "H4", ROLE_NANG),
                Subject(5, "H5", ROLE_NANG), Subject(6, "F1", ROLE_THUONG),
                Subject(7, "F2", ROLE_THUONG), Subject(8, "HDTN", ROLE_HDTN)]
    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1")], subjects=subjects,
        teachers=[Teacher(10, "GV A"), Teacher(20, "GV B")],
        need={(sid, 101): 1 for sid in (1, 2, 3, 4, 5, 6, 7)},
        assigned_teacher={(sid, 101): (10 if sid in heavy_ids else 20) for sid in (1, 2, 3, 4, 5, 6, 7)},
        ban_busy=set(), slots=slots, timeslots=ts,
        config=SchedulingConfig(max_heavy_per_session=2, max_heavy_consecutive=2),
    )
    built = cpsat.build_model(inp)
    assignment = cpsat.solve(built, time_limit_s=10.0)
    assert assignment is not None
    # Kiểm trực tiếp tổng số tiết Nặng/buổi (điều luật 5 THỰC SỰ khống chế) --
    # find_max_heavy_violations chỉ đếm chuỗi liên tiếp nên mù trước mẫu rời
    # rạc như {1,3,4}; giữ lại nó như một kiểm tra bổ sung, không thay thế.
    slot_by_id = {s.slot_id: s for s in inp.slots}
    per_session = {}
    for sid, subj in assignment.items():
        if subj in heavy_ids:
            key = (slot_by_id[sid].ts.weekday, slot_by_id[sid].ts.session)
            per_session[key] = per_session.get(key, 0) + 1
    over_cap = {k: v for k, v in per_session.items() if v > inp.config.max_heavy_per_session}
    assert over_cap == {}, f"buổi vượt trần môn Nặng ({inp.config.max_heavy_per_session}/buổi): {over_cap}"
    from core.validation import find_max_heavy_violations
    assert find_max_heavy_violations(inp.slots, assignment, heavy_ids) == []


def test_max_heavy_consecutive_sliding_window():
    """Luật 6 (không có hàm thẩm định riêng -> assert thủ công). 5 ô sáng Thứ
    2 (tiết 1-5), max_heavy_per_session=5 (không chặn ở luật 5) và
    max_heavy_consecutive=2 để luật 6 là luật thực sự bó buộc. 4 MÔN NẶNG
    RIÊNG (H1..H4, mỗi môn need=1 -- thay vì 1 môn Nặng cần 4 tiết như bản
    trước Task 4, vì luật trần 1 tiết/môn/ngày/lớp mới cấm 1 môn lặp 4 lần
    cùng ngày; luật 6 vốn kiểm TỔNG số tiết Nặng liên tiếp CỘNG DỒN từ nhiều
    môn Nặng khác nhau, không phải 1 môn lặp lại -- xem ghi chú tương tự ở
    test_max_heavy_per_session) và Toán cần 1. Với luật 6 bật, không được có
    cửa sổ 3 tiết liên tiếp nào toàn môn Nặng (H1..H4)."""
    ts = [TimeSlot(i + 1, 2, "S", i + 1) for i in range(5)]
    slots = [Slot(i + 1, 101, t) for i, t in enumerate(ts)]
    heavy_ids = {1, 2, 3, 4}
    subjects = [Subject(1, "H1", ROLE_NANG), Subject(2, "H2", ROLE_NANG),
                Subject(3, "H3", ROLE_NANG), Subject(4, "H4", ROLE_NANG),
                Subject(5, "Toan", ROLE_THUONG), Subject(6, "HDTN", ROLE_HDTN)]
    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1")], subjects=subjects,
        teachers=[Teacher(10, "GV A"), Teacher(20, "GV B")],
        need={(1, 101): 1, (2, 101): 1, (3, 101): 1, (4, 101): 1, (5, 101): 1},
        assigned_teacher={(1, 101): 10, (2, 101): 10, (3, 101): 10, (4, 101): 10,
                           (5, 101): 20},
        ban_busy=set(), slots=slots, timeslots=ts,
        config=SchedulingConfig(max_heavy_per_session=5, max_heavy_consecutive=2),
    )
    built = cpsat.build_model(inp)
    assignment = cpsat.solve(built, time_limit_s=10.0)
    assert assignment is not None
    slot_by_id = {s.slot_id: s for s in inp.slots}
    heavy_periods = sorted(slot_by_id[sid].ts.period for sid, subj in assignment.items() if subj in heavy_ids)
    window = inp.config.max_heavy_consecutive + 1
    last_start = 5 - inp.config.max_heavy_consecutive
    violations = [w for w in range(1, last_start + 1)
                  if all(p in heavy_periods for p in range(w, w + window))]
    assert violations == [], f"có cửa sổ {window} tiết liên tiếp toàn môn Nặng: {violations}"


def test_heavy_subject_avoids_afternoon_period3():
    """Luật 7: môn Nặng cần 1 tiết, phải né tiết 3 buổi chiều. Toán cần 3 tiết
    trải trên 3 NGÀY riêng (tiết 1 sáng mỗi ngày -- tương thích luật trần 1
    tiết/môn/ngày/lớp của Task 4). Ô "bẫy" (chiều tiết 3) nằm ở 1 ngày RIÊNG,
    cùng buổi chiều đó còn có tiết 1 (Văn) và tiết 2 (Sử) để luật "không hở
    tiết" (luật 5) có đủ tiết 1, 2 hợp lệ đứng trước tiết 3 -- nếu không, một
    buổi chiều chỉ có mỗi tiết 3 (không có tiết 1, 2) sẽ bị luật 5 cấm cứng
    (ô không có "tiết liền trước" thì luôn phải để trống), che mất hoàn toàn
    ý định phép thử này (né luật 7, không phải bị luật 5 chặn hộ). Vừa khít 6
    ô = 6 tiết (Nặng=1, Toán=3, Văn=1, Sử=1)."""
    ts = [TimeSlot(1, 2, "S", 1), TimeSlot(2, 3, "S", 1), TimeSlot(3, 4, "S", 1),
          TimeSlot(4, 5, "C", 1), TimeSlot(5, 5, "C", 2), TimeSlot(6, 5, "C", 3)]
    slots = [Slot(i + 1, 101, t) for i, t in enumerate(ts)]
    subjects = [Subject(1, "KHTN", ROLE_NANG), Subject(2, "Toan", ROLE_THUONG),
                Subject(3, "Van", ROLE_THUONG), Subject(4, "Su", ROLE_THUONG),
                Subject(5, "HDTN", ROLE_HDTN)]
    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1")], subjects=subjects,
        teachers=[Teacher(10, "GV A"), Teacher(20, "GV B"), Teacher(30, "GV C"), Teacher(40, "GV D")],
        need={(1, 101): 1, (2, 101): 3, (3, 101): 1, (4, 101): 1},
        assigned_teacher={(1, 101): 10, (2, 101): 20, (3, 101): 30, (4, 101): 40},
        ban_busy=set(), slots=slots, timeslots=ts,
        config=SchedulingConfig(),
    )
    built = cpsat.build_model(inp)
    assignment = cpsat.solve(built, time_limit_s=10.0)
    assert assignment is not None
    from core.validation import find_heavy_afternoon_period3_violations
    assert find_heavy_afternoon_period3_violations(inp.slots, assignment, {1}) == []


# ---------------------------------------------------------------------------
# Task 4: ràng buộc KHUNG LỚP (task-4-brief.md) -- chào cờ/SHL ghim, trần HĐTN
# 2 tiết/ngày (thay vì 1) với tiết thứ ba tự do không cần liền kề, không hở
# tiết trong buổi, và không để buổi nào của lớp chỉ có đúng 1 tiết.
# ---------------------------------------------------------------------------


def test_opening_ceremony_and_shl_pinned_for_every_class():
    """2 lớp dùng chung khung giờ (Thứ 2 sáng tiết 1-2) nhưng khác hình dạng
    tuần: lớp 101 có buổi chiều (Thứ 3 chiều) -> SHL phải rơi Thứ 6 sáng, tiết
    CUỐI của buổi sáng đó (tiết 3, vì Thứ 6 sáng có 3 tiết); lớp 102 chỉ học
    sáng -> SHL phải rơi Thứ 7 sáng, tiết CUỐI (tiết 2, vì Thứ 7 sáng có 2
    tiết). Định mức khít tuyệt đối (0 dư địa) để lời giải gần như duy nhất,
    cô lập đúng luật ghim mà không lẫn với các luật khác (hở tiết/buổi lẻ)."""
    ts1 = TimeSlot(1, 2, "S", 1)   # Thứ 2 sáng tiết 1 -- ghim chào cờ (mặc định config)
    ts2 = TimeSlot(2, 2, "S", 2)   # Thứ 2 sáng tiết 2
    ts3 = TimeSlot(3, 3, "C", 1)   # Thứ 3 chiều tiết 1 -- chỉ lớp 101 dùng (đánh dấu có buổi chiều)
    ts4 = TimeSlot(4, 6, "S", 1)   # Thứ 6 sáng tiết 1
    ts5 = TimeSlot(5, 6, "S", 2)   # Thứ 6 sáng tiết 2
    ts6 = TimeSlot(6, 6, "S", 3)   # Thứ 6 sáng tiết 3 -- ghim SHL lớp 101 (tiết cuối)
    ts7 = TimeSlot(7, 7, "S", 1)   # Thứ 7 sáng tiết 1
    ts8 = TimeSlot(8, 7, "S", 2)   # Thứ 7 sáng tiết 2 -- ghim SHL lớp 102 (tiết cuối)
    all_ts = [ts1, ts2, ts3, ts4, ts5, ts6, ts7, ts8]

    slots_101 = [Slot(1, 101, ts1), Slot(2, 101, ts2), Slot(3, 101, ts3),
                 Slot(4, 101, ts4), Slot(5, 101, ts5), Slot(6, 101, ts6)]
    slots_102 = [Slot(7, 102, ts1), Slot(8, 102, ts2),
                 Slot(9, 102, ts7), Slot(10, 102, ts8)]

    subjects = [Subject(1, "HDTN", ROLE_HDTN), Subject(2, "Toan", ROLE_THUONG),
                Subject(3, "Van", ROLE_THUONG)]
    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1"), ClassRoom(102, "6A2")], subjects=subjects,
        teachers=[Teacher(10, "GVCN 101"), Teacher(20, "GV Toan 101"), Teacher(30, "GV Van 101"),
                  Teacher(40, "GVCN 102"), Teacher(50, "GV Toan 102")],
        need={(1, 101): 2, (2, 101): 2, (3, 101): 2, (1, 102): 2, (2, 102): 2},
        assigned_teacher={(1, 101): 10, (2, 101): 20, (3, 101): 30,
                           (1, 102): 40, (2, 102): 50},
        ban_busy=set(), slots=slots_101 + slots_102, timeslots=all_ts,
        config=SchedulingConfig(),
    )
    built = cpsat.build_model(inp)
    assignment = cpsat.solve(built, time_limit_s=10.0)
    assert assignment is not None, "phải giải được bài toán khít định mức này"

    hdtn_id = 1
    assert assignment[1] == hdtn_id, "lớp 101: chào cờ (Thứ 2 sáng tiết 1) phải là HĐTN"
    assert assignment[6] == hdtn_id, "lớp 101 có buổi chiều -> SHL Thứ 6 sáng tiết cuối (3) phải là HĐTN"
    assert assignment[7] == hdtn_id, "lớp 102: chào cờ (Thứ 2 sáng tiết 1) phải là HĐTN"
    assert assignment[10] == hdtn_id, "lớp 102 chỉ học sáng -> SHL Thứ 7 sáng tiết cuối (2) phải là HĐTN"


def test_hdtn_third_period_allowed_same_day_as_pin_without_adjacency():
    """Trước bản sửa 2026-09-04, luật chung "1 tiết/môn/ngày" (không có ngoại lệ
    HĐTN) sẽ đẩy tiết HĐTN thứ ba sang một ngày thứ ba -- ở đây khung CHỈ có 2
    ngày (Thứ 2 = chào cờ, Thứ 7 = SHL, lớp chỉ học sáng nên không có buổi
    chiều), không có ngày thứ ba nào để "trốn" đi, nên hành vi CŨ sẽ làm bài
    toán KHÔNG THỂ GIẢI. Bản ĐÚNG (trần HĐTN = 2/ngày) phải giải được bằng
    cách xếp tiết thứ ba vào tiết 3 sáng Thứ 2 -- CÙNG NGÀY với chào cờ (tiết
    1) nhưng CÁCH nó bởi tiết Toán ở giữa (tiết 2) -- tức không hề liền kề
    tiết ghim, đúng như "Ghi chú quan trọng" của brief mô tả."""
    ts = [TimeSlot(1, 2, "S", 1),   # chào cờ (ghim)
          TimeSlot(2, 2, "S", 2),   # Toan (chen giữa, phá liền kề)
          TimeSlot(3, 2, "S", 3),   # tiết HĐTN thứ ba (tự do), không liền chào cờ
          TimeSlot(4, 7, "S", 1)]   # SHL (ghim, tiết duy nhất/cuối buổi Thứ 7)
    slots = [Slot(i + 1, 101, t) for i, t in enumerate(ts)]
    subjects = [Subject(1, "HDTN", ROLE_HDTN), Subject(2, "Toan", ROLE_THUONG)]
    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1")], subjects=subjects,
        teachers=[Teacher(10, "GVCN"), Teacher(20, "GV Toan")],
        need={(1, 101): 3, (2, 101): 1},
        assigned_teacher={(1, 101): 10, (2, 101): 20},
        ban_busy=set(), slots=slots, timeslots=ts,
        config=SchedulingConfig(),
    )
    built = cpsat.build_model(inp)
    assignment = cpsat.solve(built, time_limit_s=10.0)
    assert assignment is not None, (
        "HĐTN phải được phép có 2 tiết/ngày (chào cờ + tiết tự do), kể cả khi "
        "tiết tự do không liền kề tiết ghim -- bộ giải không được coi đây là bế tắc"
    )
    assert assignment[1] == 1 and assignment[4] == 1, "hai tiết ghim vẫn phải là HĐTN"
    diff = compute_quota_diff(inp.slots, assignment, inp.need)
    assert all(v == 0 for v in diff.values()), f"sai định mức: {diff}"


def test_no_gap_within_session_when_slack_available():
    """1 buổi 4 ô (Thứ 2 sáng tiết 1-4), 2 môn need=1 mỗi môn -> 2 dư địa.
    Không ràng buộc "không hở tiết" thì bộ giải CP-SAT (đã xác nhận thực
    nghiệm) tự nhiên chọn tiết 1 và tiết 4, để hở tiết 2-3 ở giữa. Với luật
    bật, tổ hợp 2-ô hợp lệ DUY NHẤT tôn trọng "tiết p có môn => tiết p-1 cùng
    buổi cũng có môn" là {tiết 1, tiết 2} (mọi tổ hợp khác đều để hở hoặc
    thiếu tiết 1)."""
    ts = [TimeSlot(i + 1, 2, "S", i + 1) for i in range(4)]
    slots = [Slot(i + 1, 101, t) for i, t in enumerate(ts)]
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(2, "Van", ROLE_THUONG),
                Subject(3, "HDTN", ROLE_HDTN)]
    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1")], subjects=subjects,
        teachers=[Teacher(10, "GV A"), Teacher(20, "GV B")],
        need={(1, 101): 1, (2, 101): 1},
        assigned_teacher={(1, 101): 10, (2, 101): 20},
        ban_busy=set(), slots=slots, timeslots=ts,
        config=SchedulingConfig(),
    )
    built = cpsat.build_model(inp)
    assignment = cpsat.solve(built, time_limit_s=10.0)
    assert assignment is not None

    slot_by_id = {s.slot_id: s for s in inp.slots}
    filled_by_group = {}
    for sid, subj in assignment.items():
        ts_ = slot_by_id[sid].ts
        filled_by_group.setdefault((slot_by_id[sid].class_id, ts_.weekday, ts_.session), set()).add(ts_.period)
    for key, periods in filled_by_group.items():
        for p in periods:
            if p > 1:
                assert (p - 1) in periods, f"hở tiết {p - 1} trong buổi {key} (tiết {p} có môn nhưng {p - 1} thì không)"


def test_class_has_no_lone_single_period_session_when_slack_available():
    """1 lớp, 2 buổi RIÊNG (Thứ 2 sáng 2 ô + Thứ 2 chiều 2 ô = 4 ô), 2 môn
    need=1 mỗi môn -> 2 dư địa. Không ràng buộc thì bộ giải (đã xác nhận thực
    nghiệm) tự nhiên tách 2 môn ra 2 buổi khác nhau, mỗi buổi chỉ 1 tiết --
    đúng "buổi lẻ" luật 7 cấm. Với luật bật, 2 môn buộc phải dồn vào CÙNG 1
    buổi (buổi kia để trống hẳn), vì buổi nào ĐƯỢC DÙNG cũng phải có >= 2
    tiết."""
    ts = [TimeSlot(1, 2, "S", 1), TimeSlot(2, 2, "S", 2),
          TimeSlot(3, 2, "C", 1), TimeSlot(4, 2, "C", 2)]
    slots = [Slot(i + 1, 101, t) for i, t in enumerate(ts)]
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(2, "Van", ROLE_THUONG),
                Subject(3, "HDTN", ROLE_HDTN)]
    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1")], subjects=subjects,
        teachers=[Teacher(10, "GV A"), Teacher(20, "GV B")],
        need={(1, 101): 1, (2, 101): 1},
        assigned_teacher={(1, 101): 10, (2, 101): 20},
        ban_busy=set(), slots=slots, timeslots=ts,
        config=SchedulingConfig(),
    )
    built = cpsat.build_model(inp)
    assignment = cpsat.solve(built, time_limit_s=10.0)
    assert assignment is not None

    slot_by_id = {s.slot_id: s for s in inp.slots}
    filled_count = {}
    for sid in assignment:
        ts_ = slot_by_id[sid].ts
        key = (slot_by_id[sid].class_id, ts_.weekday, ts_.session)
        filled_count[key] = filled_count.get(key, 0) + 1
    bad = {k: v for k, v in filled_count.items() if v == 1}
    assert bad == {}, f"buổi lẻ 1 tiết (trong khi buổi đó có >=2 ô): {bad}"


def test_subject_class_allowed_cells_rule():
    """Luật 8: lớp chỉ được xếp môn Văn vào Thứ 3 sáng (không được Thứ 2
    sáng). Ô Thứ 3 (cho phép) tạo TRƯỚC, ô Thứ 2 (cấm) tạo SAU -- không ràng
    buộc thì bộ giải dồn tiết Văn duy nhất vào ô cuối (Thứ 2, ô bị cấm)."""
    ts = [TimeSlot(1, 3, "S", 1), TimeSlot(2, 2, "S", 1)]
    slots = [Slot(i + 1, 101, t) for i, t in enumerate(ts)]
    subjects = [Subject(1, "Van", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]
    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1")], subjects=subjects,
        teachers=[Teacher(10, "GV A")],
        need={(1, 101): 1},
        assigned_teacher={(1, 101): 10},
        ban_busy=set(), slots=slots, timeslots=ts,
        config=SchedulingConfig(),
        subject_class_allowed_cells={(1, 101): frozenset({(3, "S")})},
    )
    built = cpsat.build_model(inp)
    assignment = cpsat.solve(built, time_limit_s=10.0)
    assert assignment is not None
    from core.validation import find_subject_class_rule_violations
    rules = [{"subject_id": 1, "class_ids": [101], "cells": [(3, "S")]}]
    assert find_subject_class_rule_violations(inp.slots, assignment, rules) == []
