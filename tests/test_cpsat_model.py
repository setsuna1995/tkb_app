import pytest

from core.models import (
    ROLE_GDTC, ROLE_HDTN, ROLE_KEP, ROLE_NANG, ROLE_THUONG, ClassRoom,
    SchedulingConfig, SchedulingInput, Slot, Subject, Teacher, TimeSlot,
)
from core.validation import compute_quota_diff

cpsat = pytest.importorskip("core.scheduler.cpsat_model")


def _tiny_input():
    """1 lớp, 6 ô sáng, MỖI ô một ngày riêng (Thứ 2 -> Thứ 7, tiết 1), 2 môn
    cần 3 tiết mỗi môn. Vừa khít 6 ô = 6 tiết, nên mọi ô đều phải có môn. Dùng
    6 ngày RIÊNG (thay vì 2 ngày x 3 tiết như bản cũ trước Task 4) để tương
    thích với luật khung LỚP mới (task-4-brief.md luật 1: trần 1 tiết/môn/
    ngày/lớp cho môn thường -- xếp 3 tiết Toán trong CÙNG 1 ngày giờ là bất
    hợp lệ).

    Side effect (đáng chú ý cho người đọc sau): với cấu hình mặc định
    (chao_co_weekday=2, chao_co_period=1) và lớp này không có buổi chiều nào
    (SHL rơi Thứ 7 -- ngày cuối cùng trong 6 ngày trên), ô slot1 (Thứ 2, tiết
    1) và slot6 (Thứ 7, tiết 1 -- cũng là tiết CUỐI buổi sáng hôm đó vì mỗi
    ngày chỉ có 1 tiết) bị 2 luật ghim mới của Task 4 (chào cờ + SHL) ép cứng
    thành HĐTN bất cứ khi nào need HĐTN > 0 cho lớp này -- KHÔNG phải do luật
    này (Task 1) chủ động chọn. Vô hại với 2 test dùng need HĐTN=3 (chỉ còn
    lại đúng 1 tiết HĐTN "tự do" cần xếp vào 1 trong 4 ô giữa), và không ảnh
    hưởng `test_leaves_cells_empty_when_there_is_slack` (ghi đè need thành chỉ
    còn Toán, HĐTN need=0 nên không ô nào bị ghim)."""
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
    """1 lớp, 5 ô: 3 ô sáng T2 (tiết 1-3) + 2 ô sáng T3 (tiết 1-2); 1 GV dạy 1
    môn cần đúng 3/5 tiết. Dùng HĐTN tuần chuyên đề (block_size=3, xem
    task-4-brief.md luật 1+4) làm môn thử thay vì môn thường, vì luật khung
    LỚP mới của Task 4 tự nó đã cấm môn thường xếp 3 tiết cùng ngày -- cần một
    môn được PHÉP 3 tiết/ngày ở cấp LỚP để phép thử còn cô lập đúng luật trần
    GV (Task 2), không lẫn với luật trần lớp mới.

    QUAN TRỌNG (fix sau review): với luật "không hở tiết" (5) + "buổi không
    lẻ" (7) đã bật, MỌI cách chia 3 tiết này ra 2 ngày đều để lại đúng 1 ngày
    còn "buổi lẻ" 1 tiết (2+1 hoặc 1+2 đều vi phạm luật 7 vì cả 2 buổi ở đây
    đều có >=2 ô) -- tức {Thứ 2: 3, Thứ 3: 0} (dồn cả 3 tiết vào 1 ngày) là
    cấu hình hợp lệ DUY NHẤT theo các luật KHÁC luật trần GV, không phụ thuộc
    giá trị trần. Bản test trước (dùng T3 chỉ 1 ô, được luật 7 miễn trừ) hoá
    ra có 2 cấu hình hợp lệ ngang nhau ({2,1} lẫn {3,0}) và bộ giải CP-SAT
    luôn tự chọn {2,1} bất kể trần GV là bao nhiêu -- verify bằng
    disable-and-rerun (tạm comment dòng ràng buộc luật 4 trong
    `_add_teacher_constraints`, chạy lại với trần=2): kết quả GIỐNG HỆT nhau
    có/không có ràng buộc, tức test cũ không thật sự kiểm được gì. Bản này
    (Thứ 3 có 2 ô, không được miễn trừ luật 7) không còn đường "lách" đó, nên
    trần GV=2 (< 3) BẮT BUỘC bài toán KHÔNG THỂ GIẢI -- đã verify lại bằng
    disable-and-rerun: tắt ràng buộc luật 4 thì trần=2 giải được (dồn cả 3
    tiết vào T2), bật lại thì trần=2 vô nghiệm như assert dưới đây mong đợi.
    Trần=3 (đủ) thì giải được, đúng cấu hình dồn hết vào T2 và không vi phạm."""
    ts = [TimeSlot(1, 2, "S", 1), TimeSlot(2, 2, "S", 2), TimeSlot(3, 2, "S", 3),
          TimeSlot(4, 3, "S", 1), TimeSlot(5, 3, "S", 2)]
    slots = [Slot(i + 1, 101, t) for i, t in enumerate(ts)]
    subjects = [Subject(1, "HDTN", ROLE_HDTN)]

    def _build(cap):
        config = SchedulingConfig(max_teacher_periods_per_day=cap)
        return SchedulingInput(
            classes=[ClassRoom(101, "6A1")],
            subjects=subjects,
            teachers=[Teacher(10, "GV A")],
            need={(1, 101): 3},
            assigned_teacher={(1, 101): 10},
            ban_busy=set(), slots=slots, timeslots=ts, config=config,
            hdtn_thematic_week=True,
        )

    inp_tight = _build(2)
    blocked = cpsat.solve(cpsat.build_model(inp_tight), time_limit_s=10.0)
    assert blocked is None, (
        "trần GV=2/ngày phải làm bài toán KHÔNG THỂ GIẢI ở đây: cấu hình hợp "
        "lệ DUY NHẤT theo các luật khác là dồn cả 3 tiết vào 1 ngày (Thứ 2)"
    )

    inp_ok = _build(3)
    built = cpsat.build_model(inp_ok)
    assignment = cpsat.solve(built, time_limit_s=10.0)
    assert assignment is not None
    from core.validation import find_teacher_day_cap_violations
    assert find_teacher_day_cap_violations(
        inp_ok.slots, assignment, inp_ok.assigned_teacher, max_per_day=3) == []


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
    """GDTC chỉ được các tiết trong `gdtc_morning_allowed_periods`.

    QUAN TRỌNG (fix sau review): bản trước (5 ô cùng buổi, tiết 1-5, GDTC +
    4 môn thường lấp đầy -- vừa khít) hoá ra KHÔNG hề kiểm được luật này: đã
    verify bằng disable-and-rerun (tạm sửa dòng ràng buộc luật 3 trong
    `_add_subject_constraints` thành `if False and ...`, chạy lại) thì GDTC
    vẫn tự nhiên rơi vào tiết 4 (không bao giờ thử tiết 5) -- tức bộ giải
    CP-SAT với 5 môn khác nhau lấp khít 5 ô có xu hướng nội tại không đụng ô
    cuối cùng cho môn "distinguished" (GDTC), hoàn toàn không liên quan gì
    đến ràng buộc đang kiểm. Gốc rễ: `find_invalid_gdtc_periods` không phát
    hiện được vì có/không luật, GDTC vẫn ở tiết 4 (hợp lệ cả hai trường hợp).

    Bản này dùng khung TỐI THIỂU 2 ô (tiết 1, 2), GDTC + 1 môn thường, vừa
    khít -- luật "không hở tiết" (5) buộc CHỈ CÓ đúng 1 cấu hình hợp lệ mỗi
    lần (GDTC và môn kia hoán đổi vị trí 2 ô đó). Đã verify bằng
    disable-and-rerun: KHÔNG giới hạn (`gdtc_morning_allowed_periods=(1,2)`)
    thì GDTC tự nhiên rơi tiết 2 (`{1: Toan, 2: GDTC}`); ép
    `gdtc_morning_allowed_periods=(1,)` (chỉ tiết 1) buộc bộ giải phải HOÁN
    ĐỔI để GDTC nhận tiết 1 (`{1: GDTC, 2: Toan}`) -- một kết quả THỰC SỰ
    khác nhau tuỳ luật bật/tắt, không phải trùng lặp ngẫu nhiên."""
    ts = [TimeSlot(1, 2, "S", 1), TimeSlot(2, 2, "S", 2)]
    slots = [Slot(i + 1, 101, t) for i, t in enumerate(ts)]
    subjects = [Subject(1, "GDTC", ROLE_GDTC), Subject(2, "HDTN", ROLE_HDTN),
                Subject(3, "Toan", ROLE_THUONG)]
    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1")], subjects=subjects,
        teachers=[Teacher(10, "GV")],
        need={(1, 101): 1, (3, 101): 1},
        assigned_teacher={(1, 101): 10, (3, 101): 10},
        ban_busy=set(), slots=slots, timeslots=ts,
        config=SchedulingConfig(gdtc_morning_allowed_periods=(1,)),
    )
    built = cpsat.build_model(inp)
    assignment = cpsat.solve(built, time_limit_s=10.0)
    assert assignment is not None
    slot_by_id = {s.slot_id: s for s in inp.slots}
    gdtc_slot = next(sid for sid, subj in assignment.items() if subj == 1)
    assert slot_by_id[gdtc_slot].ts.period == 1, (
        "GDTC bị ép chỉ được tiết 1 (gdtc_morning_allowed_periods=(1,)) nhưng "
        f"lại rơi vào tiết {slot_by_id[gdtc_slot].ts.period}"
    )
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
    """Luật 5, cô lập thật sự khỏi luật 6.

    QUAN TRỌNG (fix sau review): bản trước (5 môn Nặng riêng H1..H5 + 2 môn
    thường F1/F2 trải 3 buổi Thứ 3/Thứ 2/Thứ 4, so sánh PHÂN BỐ tiết Nặng
    giữa "luật bật" và "luật tắt/nới trần") hoá ra KHÔNG kiểm được gì: đã
    verify bằng disable-and-rerun + nới `max_heavy_per_session`/
    `max_heavy_consecutive` lên 100 -- CP-SAT dùng 8 worker song song nên
    KHÔNG quyết định (chạy lại nhiều lần ra nhiều phân bố KHÁC NHAU ngay cả
    khi CÙNG một cấu hình, vì có nhiều lời giải hợp lệ ngang nhau và không có
    hàm mục tiêu để phá thế cân bằng) -- so sánh "phân bố A có giống phân bố
    B không" là phép thử không đáng tin với mô hình không có objective.

    Bản này chuyển sang so sánh KHẢ THI/KHÔNG KHẢ THI (nhị phân, đáng tin cậy
    hơn nhiều so với "lời giải nào được chọn"): 1 buổi DUY NHẤT (Thứ 2, 4 ô),
    3 môn Nặng riêng (H1-H3, need=1) + 1 môn thường (F1, need=1) -- vừa khít,
    KHÔNG có buổi/ngày nào khác để 3 tiết Nặng "trốn" đi. max_heavy_consecutive
    =2 (đủ thấp để 2 mẫu xen kẽ hợp lệ theo luật 6 vẫn tồn tại: H-F-H-H hoặc
    H-H-F-H, mỗi mẫu có chuỗi liên tiếp tối đa = 2, không phạm luật 6) NHƯNG
    max_heavy_per_session=2 (< 3 tiết Nặng cần xếp) khiến CẢ 2 mẫu đó (và mọi
    mẫu khác) đều vượt trần TỔNG môn Nặng/buổi -- tức bài toán này chỉ
    KHÔNG THỂ GIẢI được vì luật 5, không phải vì luật 6 (luật 6 đã bị cô lập
    ra khỏi nguyên nhân). Verify bằng disable-and-rerun: tạm comment dòng ràng
    buộc luật 5 trong `_add_subject_constraints` (giữ luật 6 nguyên), bài toán
    NÀY chuyển từ vô nghiệm -> giải được (ra đúng mẫu H-F-H-H hoặc tương tự,
    thoả luật 6 một mình) -- khôi phục lại, xác nhận vô nghiệm trở lại như cũ.
    Đối chứng thêm: trần rộng hơn (max_heavy_per_session=3, đủ cho 3 tiết
    Nặng) làm bài toán giải được và không vi phạm gì."""
    ts = [TimeSlot(i + 1, 2, "S", i + 1) for i in range(4)]
    slots = [Slot(i + 1, 101, t) for i, t in enumerate(ts)]
    heavy_ids = {1, 2, 3}
    subjects = [Subject(1, "H1", ROLE_NANG), Subject(2, "H2", ROLE_NANG),
                Subject(3, "H3", ROLE_NANG), Subject(4, "F1", ROLE_THUONG),
                Subject(5, "HDTN", ROLE_HDTN)]

    def _build(max_per_sess, max_consec=2):
        config = SchedulingConfig(max_heavy_per_session=max_per_sess, max_heavy_consecutive=max_consec)
        return SchedulingInput(
            classes=[ClassRoom(101, "6A1")], subjects=subjects,
            teachers=[Teacher(10, "GV A"), Teacher(20, "GV B")],
            need={(1, 101): 1, (2, 101): 1, (3, 101): 1, (4, 101): 1},
            assigned_teacher={(1, 101): 10, (2, 101): 10, (3, 101): 10, (4, 101): 20},
            ban_busy=set(), slots=slots, timeslots=ts, config=config,
        )

    inp_tight = _build(max_per_sess=2)
    blocked = cpsat.solve(cpsat.build_model(inp_tight), time_limit_s=10.0)
    assert blocked is None, (
        "trần môn Nặng/buổi=2 (< 3 tiết Nặng cần xếp trong 1 buổi duy nhất) "
        "phải làm bài toán KHÔNG THỂ GIẢI -- mọi mẫu xen kẽ hợp lệ theo luật 6 "
        "(vd H-F-H-H) đều vẫn có TỔNG 3 tiết Nặng, vượt trần luật 5"
    )

    inp_ok = _build(max_per_sess=3)
    built = cpsat.build_model(inp_ok)
    assignment = cpsat.solve(built, time_limit_s=10.0)
    assert assignment is not None
    from core.validation import find_max_heavy_violations
    assert find_max_heavy_violations(inp_ok.slots, assignment, heavy_ids, max_consecutive=2) == []


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
    """Luật 7: môn Nặng phải né tiết 3 buổi chiều.

    QUAN TRỌNG (fix sau review): bản trước (Nặng=1 + 3 môn thường riêng trải
    nhiều ngày, môn Nặng "khan hiếm" cạnh tranh ô cuối cùng) hoá ra KHÔNG kiểm
    được gì: đã verify bằng disable-and-rerun (`avoid_heavy_afternoon_period3=
    False`) -- môn Nặng vẫn tự nhiên tránh tiết 3 (rơi vào tiết 2) dù luật đã
    tắt, tức việc nó né tiết 3 không phải nhờ ràng buộc này.

    Bản này khôi phục lại đúng kiểu bất đối xứng "môn khan hiếm (need nhỏ)
    tranh chỗ với môn lấp đầy (need lớn)" đã dùng thành công ở các test Task 3
    khác -- nhưng dùng môn Văn KÉP (ROLE_KEP, need=2, được luật trần lớp mới
    của Task 4 cho phép 2 tiết/ngày vì `block_size[Văn]=2`) làm môn "lấp đầy"
    thay vì Toán (môn thường, giờ chỉ được 1 tiết/ngày). 1 buổi chiều DUY NHẤT
    (3 ô, tiết 1-3), vừa khít (Nặng=1 + Văn=2 = 3 ô). Đã verify bằng
    disable-and-rerun (lặp lại 3 lần, ổn định): `avoid_heavy_afternoon_period3
    =False` -> môn Nặng CHỌN đúng tiết 3 (ô "bẫy"); bật lại (`True`, mặc định)
    -> môn Nặng bị đẩy sang tiết 2 -- một kết quả THỰC SỰ khác nhau tuỳ luật
    bật/tắt, không phải trùng lặp ngẫu nhiên."""
    ts = [TimeSlot(1, 2, "C", 1), TimeSlot(2, 2, "C", 2), TimeSlot(3, 2, "C", 3)]
    slots = [Slot(i + 1, 101, t) for i, t in enumerate(ts)]
    subjects = [Subject(1, "KHTN", ROLE_NANG), Subject(2, "Van", ROLE_KEP),
                Subject(3, "HDTN", ROLE_HDTN)]
    inp = SchedulingInput(
        classes=[ClassRoom(101, "6A1")], subjects=subjects,
        teachers=[Teacher(10, "GV A"), Teacher(20, "GV B")],
        need={(1, 101): 1, (2, 101): 2},
        assigned_teacher={(1, 101): 10, (2, 101): 20},
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


def test_no_gap_defensive_branch_when_predecessor_slot_absent_from_frame():
    """Nhánh phòng thủ của luật 5 (cpsat_model.py, đoạn `else: m.Add(sum(vars_p)
    == 0)`) -- trước fix sau review, nhánh này chưa có test riêng. Ô tiết p-1
    KHÔNG TỒN TẠI trong khung của lớp (khác với "tồn tại nhưng bỏ trống") thì
    ô tiết p phải bị cấm cứng, mirror `feasibility.py`'s `state.occupied.get(...,
    False)` (mặc định False khi tra khoá không có, không phân biệt "chưa xếp"
    với "không có ô").

    Khung: Thứ 3 sáng CHỈ có tiết 3 (không có tiết 1, 2 nào cho lớp này ngày
    đó -- không phải để trống, mà KHÔNG TỒN TẠI trong `inp.slots`) + Thứ 4
    sáng tiết 1 (buổi bình thường). Cả 2 đều là buổi 1-ô-duy-nhất nên không bị
    luật 7 (buổi không lẻ) chi phối, cô lập đúng luật 5. Toán need=1 -> chỉ
    tiết Thứ 4 dùng được, đúng như assert dưới. Toán need=2 -> KHÔNG THỂ GIẢI
    vì chỉ có 1 ô thực sự dùng được trong khi cần 2. Đã verify bằng
    disable-and-rerun (tạm comment dòng `m.Add(sum(vars_p) == 0)`): need=2 lúc
    đó giải được (dùng cả tiết 3 Thứ 3), khôi phục lại thì vô nghiệm như cũ."""
    ts = [TimeSlot(1, 3, "S", 3), TimeSlot(2, 4, "S", 1)]
    slots = [Slot(1, 101, ts[0]), Slot(2, 101, ts[1])]
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]

    inp_ok = SchedulingInput(
        classes=[ClassRoom(101, "6A1")], subjects=subjects,
        teachers=[Teacher(10, "GV A")],
        need={(1, 101): 1},
        assigned_teacher={(1, 101): 10},
        ban_busy=set(), slots=slots, timeslots=ts,
        config=SchedulingConfig(),
    )
    built = cpsat.build_model(inp_ok)
    assignment = cpsat.solve(built, time_limit_s=10.0)
    assert assignment == {2: 1}, (
        "chỉ ô Thứ 4 tiết 1 dùng được -- ô Thứ 3 tiết 3 (không có tiết 1, 2 "
        f"cùng buổi/ngày đó) phải bị cấm cứng: {assignment}"
    )

    inp_tight = SchedulingInput(
        classes=[ClassRoom(101, "6A1")], subjects=subjects,
        teachers=[Teacher(10, "GV A")],
        need={(1, 101): 2},
        assigned_teacher={(1, 101): 10},
        ban_busy=set(), slots=slots, timeslots=ts,
        config=SchedulingConfig(),
    )
    blocked = cpsat.solve(cpsat.build_model(inp_tight), time_limit_s=10.0)
    assert blocked is None, "cần 2 tiết nhưng chỉ có 1 ô thực sự dùng được -- phải KHÔNG THỂ GIẢI"


def test_class_has_no_lone_single_period_session_when_slack_available():
    """1 lớp, 2 buổi RIÊNG (Thứ 2 sáng 3 ô + Thứ 2 chiều 3 ô = 6 ô), 2 môn
    need=1 mỗi môn -> 4 dư địa.

    QUAN TRỌNG (fix sau review): bản trước (không ràng buộc gì thêm ngoài 2
    môn need=1) hoá ra KHÔNG kiểm được luật 7: đã verify bằng disable-and-rerun
    (tạm comment 2 dòng ràng buộc luật 7 trong `_add_class_constraints`, giữ
    nguyên luật 1/2/3/5/6) -- kết quả VẪN dồn cả 2 môn vào CÙNG 1 buổi
    (`{3: Van, 4: Toan}`, cả hai ở buổi chiều), tức các luật KHÁC (rất có thể
    luật 5 -- không hở tiết -- kết hợp xu hướng nội tại của CP-SAT) đã vô
    tình tạo ra đúng kết quả "trông giống" luật 7 đang hoạt động, dù luật 7
    hoàn toàn vắng mặt.

    Bản này ép 2 môn vào 2 buổi RIÊNG BIỆT bằng luật môn-lớp-buổi
    (`subject_class_allowed_cells`, Task 3 luật 8 -- không liên quan gì tới
    luật 7 đang kiểm) -- Toán CHỈ được xếp buổi sáng, Văn CHỈ được xếp buổi
    chiều, mỗi môn need=1. Vì bị tách buộc, MỖI buổi trong 2 buổi (3 ô/buổi,
    >=2) sẽ có ĐÚNG 1 tiết -- vi phạm luật 7 ở CẢ HAI buổi, không cách nào
    tránh được (không có lựa chọn "dồn vào 1 buổi" nữa vì luật 8 đã cấm).
    Do đó bài toán này CHỈ khả thi nếu luật 7 KHÔNG được thực thi -- verify
    bằng disable-and-rerun: bật luật 7 (bình thường) -> KHÔNG THỂ GIẢI; tạm
    tắt luật 7 -> giải được, ra đúng mẫu buổi-lẻ `{Toán@sáng tiết1, Văn@chiều
    tiết1}` -- khôi phục lại, xác nhận vô nghiệm trở lại như cũ."""
    ts = [TimeSlot(1, 2, "S", 1), TimeSlot(2, 2, "S", 2), TimeSlot(3, 2, "S", 3),
          TimeSlot(4, 2, "C", 1), TimeSlot(5, 2, "C", 2), TimeSlot(6, 2, "C", 3)]
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
        subject_class_allowed_cells={
            (1, 101): frozenset({(2, "S")}),
            (2, 101): frozenset({(2, "C")}),
        },
    )
    built = cpsat.build_model(inp)
    assignment = cpsat.solve(built, time_limit_s=10.0)
    assert assignment is None, (
        "Toán bị ép chỉ được buổi sáng, Văn chỉ được buổi chiều (luật môn-lớp-"
        "buổi) -- mỗi buổi 3 ô nhưng chỉ 1 môn cần xếp, nên buộc phải để lại "
        "đúng 1 tiết ở CẢ HAI buổi. Nếu luật 7 (không buổi lẻ) hoạt động đúng, "
        "đây phải là bài toán KHÔNG THỂ GIẢI"
    )


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
