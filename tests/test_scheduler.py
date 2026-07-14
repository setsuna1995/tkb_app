import random
from collections import defaultdict

from core import frame
from core import scheduler as sched
from core.models import (
    ROLE_GDTC, ROLE_HDTN, ROLE_KEP, ROLE_NANG, ROLE_THUONG,
    ClassRoom, SchedulingInput, Slot, Subject, Teacher, TimeSlot,
)
from core.roles import resolve_roles
from core.scheduler import _State, _feasible, _put_at


# ---------------------------------------------------------------------------
# Isolated invariant tests against _feasible / _put_at (white-box, no randomness)
# ---------------------------------------------------------------------------

def test_max_gv_buoi_session_cap():
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    ts = TimeSlot(1, 2, "S", 1)
    state = _State(remaining_need={(1, 1): 10}, busy=set())
    state.session_count[(100, 2, "S")] = 4
    assert _feasible(1, ts, 1, 100, state, role_index) is False
    state.session_count[(100, 2, "S")] = 3
    assert _feasible(1, ts, 1, 100, state, role_index) is True


def test_teacher_off_slot():
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    ts = TimeSlot(1, 3, "S", 1)
    state = _State(remaining_need={(1, 1): 10}, busy=set())
    state.gv_off_slots[100] = {(3, "S")}
    assert _feasible(1, ts, 1, 100, state, role_index) is False
    state.gv_off_slots[100] = {(4, "S")}
    assert _feasible(1, ts, 1, 100, state, role_index) is True
    # a slot on the same weekday but the other session is unaffected
    state.gv_off_slots[100] = {(3, "C")}
    assert _feasible(1, ts, 1, 100, state, role_index) is True


def test_gdtc_never_period5():
    subjects = [Subject(1, "GDTC", ROLE_GDTC), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    state = _State(remaining_need={(1, 1): 10}, busy=set())
    ts5 = TimeSlot(1, 2, "S", 5)
    assert _feasible(1, ts5, 1, 100, state, role_index) is False
    ts1 = TimeSlot(2, 2, "S", 1)
    assert _feasible(1, ts1, 1, 100, state, role_index) is True


def test_day_cap_5_per_day():
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    ts = TimeSlot(1, 2, "S", 1)
    state = _State(remaining_need={(1, 1): 10}, busy=set())
    state.day_count[(1, 2)] = 5
    assert _feasible(1, ts, 1, 100, state, role_index) is False
    state.day_count[(1, 2)] = 4
    assert _feasible(1, ts, 1, 100, state, role_index) is True


def test_day_cap_follows_frame_total_when_day_capacity_given():
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    ts = TimeSlot(1, 2, "S", 1)
    state = _State(remaining_need={(1, 1): 10}, busy=set())
    day_capacity = {(1, 2): 7}  # e.g. a 4 sáng + 3 chiều frame that day

    state.day_count[(1, 2)] = 5  # would already be blocked under the hardcoded fallback of 5
    assert _feasible(1, ts, 1, 100, state, role_index, day_capacity) is True
    state.day_count[(1, 2)] = 7
    assert _feasible(1, ts, 1, 100, state, role_index, day_capacity) is False

    # a (class, weekday) missing from day_capacity still falls back to CAP_TIET_NGAY
    state.day_count[(1, 3)] = 5
    assert _feasible(1, TimeSlot(2, 3, "S", 1), 1, 100, state, role_index, day_capacity) is False


def test_lien_mach_no_gaps_in_session():
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    ts3 = TimeSlot(1, 2, "S", 3)
    state = _State(remaining_need={(1, 1): 10}, busy=set())
    assert _feasible(1, ts3, 1, 100, state, role_index) is False
    state.occupied[(1, 2, "S", 2)] = True
    assert _feasible(1, ts3, 1, 100, state, role_index) is True


def test_kep_double_period_adjacency_and_cap():
    subjects = [Subject(1, "Van", ROLE_KEP), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    state = _State(remaining_need={(1, 1): 10}, busy=set())

    ts1 = TimeSlot(1, 2, "S", 1)
    assert _feasible(1, ts1, 1, 100, state, role_index) is True
    _put_at(state, Slot(1, 1, ts1), 1, 100, role_index)

    # second period of the double must be adjacent, same session -> period 2 OK
    ts2 = TimeSlot(2, 2, "S", 2)
    assert _feasible(1, ts2, 1, 100, state, role_index) is True
    _put_at(state, Slot(2, 1, ts2), 1, 100, role_index)

    # cap_d=2 reached -> a third period the same day is blocked regardless of adjacency
    state.occupied[(1, 2, "S", 3)] = True  # satisfy lien-mach so the cap check is what's tested
    ts4 = TimeSlot(3, 2, "S", 4)
    assert _feasible(1, ts4, 1, 100, state, role_index) is False


def test_kep_second_period_must_be_adjacent():
    subjects = [Subject(1, "Van", ROLE_KEP), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    state = _State(remaining_need={(1, 1): 10}, busy=set())
    ts1 = TimeSlot(1, 2, "S", 1)
    _put_at(state, Slot(1, 1, ts1), 1, 100, role_index)
    state.occupied[(1, 2, "S", 2)] = True
    state.occupied[(1, 2, "S", 3)] = True
    ts4 = TimeSlot(2, 2, "S", 4)  # not adjacent to period 1
    assert _feasible(1, ts4, 1, 100, state, role_index) is False


def test_extra_kep_ids_makes_normal_subject_require_adjacency_this_run_only():
    # Toan (ROLE_THUONG, không phải KEP cố định) nhưng được đánh dấu extra_kep_ids={1} cho lần
    # chạy này -- phải xử sự y hệt 1 môn KEP thật (cap_d=2, tiết thứ 2 phải liền kề cùng buổi).
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects, extra_kep_ids=frozenset({1}))
    assert 1 in role_index.kep_ids
    state = _State(remaining_need={(1, 1): 10}, busy=set())

    ts1 = TimeSlot(1, 2, "S", 1)
    _put_at(state, Slot(1, 1, ts1), 1, 100, role_index)
    state.occupied[(1, 2, "S", 2)] = True
    state.occupied[(1, 2, "S", 3)] = True
    ts4 = TimeSlot(2, 2, "S", 4)  # not adjacent to period 1 -- phải bị chặn như môn KEP thật
    assert _feasible(1, ts4, 1, 100, state, role_index) is False

    ts2 = TimeSlot(3, 2, "S", 2)  # liền kề period 1, cùng buổi -- hợp lệ
    assert _feasible(1, ts2, 1, 100, state, role_index) is True


def test_resolve_roles_without_extra_kep_ids_is_unchanged():
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]
    assert resolve_roles(subjects).kep_ids == resolve_roles(subjects, extra_kep_ids=frozenset()).kep_ids == set()


def test_heavy_subject_run_of_3_cap():
    subjects = [
        Subject(1, "Toan", ROLE_NANG), Subject(2, "Ly", ROLE_NANG),
        Subject(3, "Hoa", ROLE_NANG), Subject(4, "Sinh", ROLE_NANG),
        Subject(5, "HDTN", ROLE_HDTN),
    ]
    role_index = resolve_roles(subjects)
    state = _State(remaining_need={(1, 1): 10, (2, 1): 10, (3, 1): 10, (4, 1): 10}, busy=set())

    ts1 = TimeSlot(1, 2, "S", 1)
    assert _feasible(1, ts1, 1, 100, state, role_index) is True
    _put_at(state, Slot(1, 1, ts1), 1, 100, role_index)

    ts2 = TimeSlot(2, 2, "S", 2)
    assert _feasible(1, ts2, 2, 101, state, role_index) is True
    _put_at(state, Slot(2, 1, ts2), 2, 101, role_index)

    ts3 = TimeSlot(3, 2, "S", 3)
    assert _feasible(1, ts3, 3, 102, state, role_index) is True
    _put_at(state, Slot(3, 1, ts3), 3, 102, role_index)

    # periods 1,2,3 are now all heavy -> a 4th heavy subject at period 4 would make a run of 4
    ts4 = TimeSlot(4, 2, "S", 4)
    assert _feasible(1, ts4, 4, 103, state, role_index) is False


def test_off_slots_respect_forbidden_cells_gvcn_and_must_monday():
    rng = random.Random(1)
    teachers_by_id = {
        1: Teacher(1, "GVCN_Teacher", role="GVCN", must_monday=True, is_gvcn=True, cap=15),
        2: Teacher(2, "ToTruong", role="Tổ trưởng", must_monday=True, is_gvcn=False, cap=16),
        3: Teacher(3, "Normal", role="", must_monday=False, is_gvcn=False, cap=19),
    }
    # teacher 1's homeroom class holds sinh hoạt lớp ở tiết cuối sáng Thứ 7 (trường 1 buổi)
    gvcn_shl_cell = {1: (7, "S")}

    for _ in range(200):
        offs = sched._assign_off_slots({1, 2, 3}, teachers_by_id, rng, gvcn_shl_cell, off_slot_count=2)

        for tid, slots in offs.items():
            assert len(slots) == 2
            assert len({wd for wd, _ in slots}) == 2, "2 buổi nghỉ phải rơi vào 2 ngày khác nhau"
            for cell in slots:
                assert cell not in sched.FORBIDDEN_OFF_CELLS

        # GVCN: chỉ ô SHL (sáng Thứ 7, theo gvcn_shl_cell) bị cấm -> chiều Thứ 7 vẫn chọn được
        assert (7, "S") not in offs[1]
        assert {wd for wd, _ in offs[1]} <= {3, 4, 7}

        # Tổ trưởng, must_monday: Thứ 2 bị cấm cả 2 buổi -> chọn 2 trong {3, 4, 7}
        assert {wd for wd, _ in offs[2]} <= {3, 4, 7}

        # GV thường: chỉ áp dụng FORBIDDEN_OFF_CELLS chung (sáng T2 vẫn cấm, chiều T2 thì không)
        assert (2, "S") not in offs[3]


def test_gvcn_off_slot_defaults_to_chieu_thu7_when_saturday_session_unknown():
    rng = random.Random(2)
    teachers_by_id = {1: Teacher(1, "GVCN_Teacher", role="GVCN", is_gvcn=True, cap=15)}
    for _ in range(50):
        offs = sched._assign_off_slots({1}, teachers_by_id, rng)  # no gvcn_shl_cell passed -> default (7,"C")
        assert (7, "C") not in offs[1]


def test_off_slot_count_defaults_to_1_buoi_per_week():
    rng = random.Random(3)
    teachers_by_id = {1: Teacher(1, "Normal", cap=19)}
    for _ in range(50):
        offs = sched._assign_off_slots({1}, teachers_by_id, rng)  # off_slot_count not passed -> default 1
        assert len(offs[1]) == 1


def test_active_cells_never_includes_chieu_thu5_thu6():
    for morning, afternoon in ((5, 0), (4, 3), (5, 2), (4, 4)):
        cells = frame.active_cells(morning, afternoon)
        assert not any(wd in (5, 6) and session == "C" for wd, session, _ in cells)


def test_active_cells_skips_saturday_when_2_buoi_by_default():
    cells = frame.active_cells(4, 3)  # afternoon > 0 -- học 2 buổi/ngày
    assert not any(wd == 7 for wd, _session, _period in cells)


def test_active_cells_allows_saturday_as_exception_when_flagged():
    cells = frame.active_cells(4, 3, allow_saturday=True)
    assert any(wd == 7 and session == "S" for wd, session, _period in cells)
    assert any(wd == 7 and session == "C" for wd, session, _period in cells)


def test_active_cells_always_includes_saturday_when_1_buoi():
    cells = frame.active_cells(5, 0)  # afternoon == 0 -- chỉ học 1 buổi/ngày
    assert any(wd == 7 and session == "S" for wd, session, _period in cells)


def test_validate_periods_rejects_exactly_one_period():
    frame.validate_periods(0, 0)
    frame.validate_periods(2, 5)
    frame.validate_periods(5, 0)
    for morning, afternoon in ((1, 0), (0, 1), (1, 3), (4, 1)):
        try:
            frame.validate_periods(morning, afternoon)
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected ValueError for ({morning}, {afternoon})")


# ---------------------------------------------------------------------------
# Full synthetic run() integration tests
# ---------------------------------------------------------------------------

def _make_timeslots(morning=5, afternoon=0, weekdays=(2, 3, 4, 5, 6, 7)):
    slots = []
    ts_id = 0
    for wd in weekdays:
        for p in range(1, morning + 1):
            ts_id += 1
            slots.append(TimeSlot(ts_id, wd, "S", p))
        for p in range(1, afternoon + 1):
            ts_id += 1
            slots.append(TimeSlot(ts_id, wd, "C", p))
    return slots


def _build_input(classes, subjects, teachers, need, assigned_teacher, timeslots,
                  seed=12345, ban_busy=None, old_subject=None, extra_kep_ids=frozenset()):
    slots = []
    slot_id = 0
    for c in classes:
        for ts in timeslots:
            slot_id += 1
            old = None
            if old_subject:
                old = old_subject.get((c.class_id, ts.weekday, ts.session, ts.period))
            slots.append(Slot(slot_id, c.class_id, ts, old_subject_id=old))
    return SchedulingInput(
        classes=classes, subjects=subjects, teachers=teachers, need=need,
        assigned_teacher=assigned_teacher, ban_busy=ban_busy or set(),
        slots=slots, timeslots=timeslots, seed=seed,
        extra_kep_ids=extra_kep_ids,
    )


def test_small_synthetic_schedule_succeeds_and_meets_quotas():
    classes = [ClassRoom(1, "6A"), ClassRoom(2, "6B")]
    subjects = [
        Subject(1, "Toan hoc", ROLE_THUONG, 1),
        Subject(2, "Ngu van", ROLE_KEP, 2),
        Subject(3, "GDTC", ROLE_GDTC, 3),
        Subject(4, "HDTN", ROLE_HDTN, 4),
        Subject(5, "Tieng Anh", ROLE_THUONG, 5),
    ]
    teachers = [Teacher(i, f"GV{i}") for i in range(1, 11)]
    # 1 buổi/ngày: 6 ngày × 5 tiết sáng = 30 ô/lớp. Tải = 30 để lấp đầy khung, đảm
    # bảo sáng Thứ 7 đầy -> ô SHL (tiết cuối sáng Thứ 7) ghim được.
    need = {
        (1, 1): 6, (2, 1): 12, (3, 1): 3, (4, 1): 3, (5, 1): 6,
        (1, 2): 6, (2, 2): 12, (3, 2): 3, (4, 2): 3, (5, 2): 6,
    }
    assigned_teacher = {
        (1, 1): 1, (2, 1): 2, (3, 1): 3, (4, 1): 4, (5, 1): 5,
        (1, 2): 6, (2, 2): 7, (3, 2): 8, (4, 2): 9, (5, 2): 10,
    }
    timeslots = _make_timeslots(morning=5, afternoon=0)
    inp = _build_input(classes, subjects, teachers, need, assigned_teacher, timeslots, seed=42)

    result = sched.run(inp, max_attempts=6000, target_successes=5)

    assert result.success is True

    from core.validation import compute_quota_diff, find_teacher_conflicts
    diff = compute_quota_diff(inp.slots, result.assignment,
                               {(s, c, "C"): n for (s, c), n in need.items()}, "C")
    assert all(v == 0 for v in diff.values()), diff

    conflicts = find_teacher_conflicts(inp.slots, result.assignment, assigned_teacher)
    assert conflicts == []

    # HDTN must occupy every class's Monday-session-S-period-1 (chào cờ)
    for slot in inp.slots:
        if slot.ts.weekday == 2 and slot.ts.session == "S" and slot.ts.period == 1:
            assert result.assignment[slot.slot_id] == 4

    # SHL (HDTN) must occupy every class's LAST morning period of Thứ 7 (1 buổi/ngày)
    for slot in inp.slots:
        if slot.ts.weekday == 7 and slot.ts.session == "S" and slot.ts.period == 5:
            assert result.assignment[slot.slot_id] == 4

    # no (class, weekday, session) may end up with exactly 1 period filled
    filled_count = defaultdict(int)
    for slot in inp.slots:
        if result.assignment.get(slot.slot_id) is not None:
            filled_count[(slot.class_id, slot.ts.weekday, slot.ts.session)] += 1
    assert all(v != 1 for v in filled_count.values()), filled_count


def test_extra_kep_ids_forces_adjacency_in_full_run():
    # Toán học (subject 1, ROLE_THUONG) không phải KEP cố định, nhưng được đánh dấu
    # extra_kep_ids={1} cho lần chạy này -- mọi lần môn 1 xuất hiện 2 tiết cùng ngày ở 1 lớp
    # phải liền kề cùng buổi, giống hệt Ngữ văn (KEP cố định).
    classes = [ClassRoom(1, "6A"), ClassRoom(2, "6B")]
    subjects = [
        Subject(1, "Toan hoc", ROLE_THUONG, 1),
        Subject(2, "Ngu van", ROLE_KEP, 2),
        Subject(3, "GDTC", ROLE_GDTC, 3),
        Subject(4, "HDTN", ROLE_HDTN, 4),
        Subject(5, "Tieng Anh", ROLE_THUONG, 5),
    ]
    teachers = [Teacher(i, f"GV{i}") for i in range(1, 11)]
    need = {
        (1, 1): 6, (2, 1): 12, (3, 1): 3, (4, 1): 3, (5, 1): 6,
        (1, 2): 6, (2, 2): 12, (3, 2): 3, (4, 2): 3, (5, 2): 6,
    }
    assigned_teacher = {
        (1, 1): 1, (2, 1): 2, (3, 1): 3, (4, 1): 4, (5, 1): 5,
        (1, 2): 6, (2, 2): 7, (3, 2): 8, (4, 2): 9, (5, 2): 10,
    }
    timeslots = _make_timeslots(morning=5, afternoon=0)
    inp = _build_input(classes, subjects, teachers, need, assigned_teacher, timeslots, seed=42,
                        extra_kep_ids=frozenset({1}))

    result = sched.run(inp, max_attempts=6000, target_successes=5)
    assert result.success is True

    placed = defaultdict(list)
    for slot in inp.slots:
        subj_id = result.assignment.get(slot.slot_id)
        if subj_id == 1:
            placed[(slot.class_id, slot.ts.weekday)].append((slot.ts.session, slot.ts.period))
    for (_class_id, _wd), positions in placed.items():
        if len(positions) == 2:
            (s1, p1), (s2, p2) = sorted(positions)
            assert s1 == s2 and abs(p1 - p2) == 1, positions


def _subject_at(inp, result, class_id, wd, session, period):
    for s in inp.slots:
        if (s.class_id == class_id and s.ts.weekday == wd
                and s.ts.session == session and s.ts.period == period):
            return result.assignment.get(s.slot_id)
    return None


def test_shl_pinned_last_morning_period_2buoi():
    # lớp học 2 buổi/ngày (có tiết chiều) -> SHL = tiết cuối sáng Thứ 6
    classes = [ClassRoom(1, "6A")]
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(2, "Van", ROLE_KEP),
                Subject(3, "HDTN", ROLE_HDTN)]
    teachers = [Teacher(1, "GVToan"), Teacher(2, "GVVan"), Teacher(3, "GVCN", is_gvcn=True)]
    need = {(1, 1): 2, (2, 1): 4, (3, 1): 2}
    assigned_teacher = {(1, 1): 1, (2, 1): 2, (3, 1): 3}
    timeslots = _make_timeslots(morning=2, afternoon=2, weekdays=(2, 6))
    inp = _build_input(classes, subjects, teachers, need, assigned_teacher, timeslots, seed=1)
    result = sched.run(inp, max_attempts=6000, target_successes=3)
    assert result.success is True
    assert _subject_at(inp, result, 1, 6, "S", 2) == 3   # SHL: tiết cuối sáng Thứ 6
    assert _subject_at(inp, result, 1, 2, "S", 1) == 3   # chào cờ: Thứ 2 sáng tiết 1


def test_shl_pinned_last_morning_period_1buoi():
    # lớp học 1 buổi/ngày (không có tiết chiều) -> SHL = tiết cuối sáng Thứ 7
    classes = [ClassRoom(1, "6A")]
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]
    teachers = [Teacher(1, "GVToan"), Teacher(2, "GVCN", is_gvcn=True)]
    need = {(1, 1): 2, (2, 1): 2}
    assigned_teacher = {(1, 1): 1, (2, 1): 2}
    timeslots = _make_timeslots(morning=2, afternoon=0, weekdays=(2, 7))
    inp = _build_input(classes, subjects, teachers, need, assigned_teacher, timeslots, seed=1)
    result = sched.run(inp, max_attempts=2000, target_successes=3)
    assert result.success is True
    assert _subject_at(inp, result, 1, 7, "S", 2) == 2   # SHL: tiết cuối sáng Thứ 7
    assert _subject_at(inp, result, 1, 2, "S", 1) == 2   # chào cờ


def test_shl_derives_last_period_not_hardcoded():
    # khung sáng 4 tiết -> SHL ở tiết 4 (tiết cuối), KHÔNG cố định là 5
    classes = [ClassRoom(1, "6A")]
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(2, "Anh", ROLE_THUONG),
                Subject(3, "Su", ROLE_THUONG), Subject(4, "HDTN", ROLE_HDTN)]
    teachers = [Teacher(1, "GVToan"), Teacher(2, "GVAnh"), Teacher(3, "GVSu"),
                Teacher(4, "GVCN", is_gvcn=True)]
    need = {(1, 1): 2, (2, 1): 2, (3, 1): 2, (4, 1): 2}
    assigned_teacher = {(1, 1): 1, (2, 1): 2, (3, 1): 3, (4, 1): 4}
    timeslots = _make_timeslots(morning=4, afternoon=0, weekdays=(2, 7))
    inp = _build_input(classes, subjects, teachers, need, assigned_teacher, timeslots, seed=1)
    result = sched.run(inp, max_attempts=6000, target_successes=3)
    assert result.success is True
    assert _subject_at(inp, result, 1, 7, "S", 4) == 4   # SHL ở tiết 4 (tiết cuối sáng), không phải 5
    assert _subject_at(inp, result, 1, 2, "S", 1) == 4   # chào cờ


def test_shl_supports_hdtn_quota_3_with_third_free():
    # HĐTN = 3 tiết: chào cờ + SHL (ghim) + 1 tiết chủ đề (greedy xếp ở ngày khác)
    classes = [ClassRoom(1, "6A")]
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]
    teachers = [Teacher(1, "GVToan"), Teacher(2, "GVCN", is_gvcn=True)]
    need = {(1, 1): 3, (2, 1): 3}
    assigned_teacher = {(1, 1): 1, (2, 1): 2}
    timeslots = _make_timeslots(morning=2, afternoon=0, weekdays=(2, 3, 7))
    inp = _build_input(classes, subjects, teachers, need, assigned_teacher, timeslots, seed=1)
    result = sched.run(inp, max_attempts=4000, target_successes=3)
    assert result.success is True
    assert _subject_at(inp, result, 1, 2, "S", 1) == 2   # chào cờ
    assert _subject_at(inp, result, 1, 7, "S", 2) == 2   # SHL
    # tiết HĐTN thứ 3 (chủ đề) xếp linh hoạt -> nằm ở Thứ 3
    assert _subject_at(inp, result, 1, 3, "S", 1) == 2 or _subject_at(inp, result, 1, 3, "S", 2) == 2
    # trên NGÀY SHL (Thứ 7) HĐTN chỉ ở đúng ô ghim, không nơi khác
    assert _subject_at(inp, result, 1, 7, "S", 1) != 2
    hdtn_cells = sum(1 for s in inp.slots if result.assignment.get(s.slot_id) == 2)
    assert hdtn_cells == 3


def test_shl_skipped_when_hdtn_quota_one():
    # HĐTN chỉ 1 tiết -> chào cờ chiếm hết, SHL bị bỏ (tiết cuối sáng Thứ 7 không phải HĐTN)
    classes = [ClassRoom(1, "6A")]
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(2, "Anh", ROLE_THUONG),
                Subject(3, "HDTN", ROLE_HDTN)]
    teachers = [Teacher(1, "GVToan"), Teacher(2, "GVAnh"), Teacher(3, "GVCN", is_gvcn=True)]
    need = {(1, 1): 2, (2, 1): 1, (3, 1): 1}
    assigned_teacher = {(1, 1): 1, (2, 1): 2, (3, 1): 3}
    timeslots = _make_timeslots(morning=2, afternoon=0, weekdays=(2, 7))
    inp = _build_input(classes, subjects, teachers, need, assigned_teacher, timeslots, seed=1)
    result = sched.run(inp, max_attempts=2000, target_successes=3)
    assert result.success is True
    assert _subject_at(inp, result, 1, 2, "S", 1) == 3   # chào cờ vẫn ghim
    assert _subject_at(inp, result, 1, 7, "S", 2) != 3   # SHL không ghim
    hdtn_cells = sum(1 for s in inp.slots if result.assignment.get(s.slot_id) == 3)
    assert hdtn_cells == 1


def test_shl_cell_pinned_not_moved_by_swap():
    # white-box: ô SHL đã ghim (pinned) không bị _try_swap_repair dời đi
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    assigned_teacher = {(1, 1): 10, (2, 1): 20}
    slot_pinned = Slot(1, 1, TimeSlot(1, 7, "S", 2))   # ô SHL
    slot_empty = Slot(2, 1, TimeSlot(2, 3, "S", 1))    # ô trống cần lấp
    state = _State(remaining_need={(1, 1): 1, (2, 1): 1}, busy=set())
    _put_at(state, slot_pinned, 2, 20, role_index)
    state.pinned[slot_pinned.slot_id] = True
    slots_by_class = {1: [slot_pinned, slot_empty]}
    sched._try_swap_repair(1, slot_empty, state, role_index, subjects,
                            assigned_teacher, slots_by_class, None)
    assert state.assigned[slot_pinned.slot_id] == 2    # vẫn là HĐTN, không bị dời
    assert state.pinned[slot_pinned.slot_id] is True


def test_idle_day_bonus_prefers_absent_teacher_day():
    # white-box: giữa 2 môn cân bằng, ưu tiên môn có GV đang TRỐNG cả ngày đó
    subjects = [Subject(1, "A", ROLE_THUONG), Subject(2, "B", ROLE_THUONG),
                Subject(3, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    slot = Slot(1, 1, TimeSlot(1, 3, "S", 1))
    state = _State(remaining_need={(1, 1): 3, (2, 1): 3}, busy=set())
    assigned_teacher = {(1, 1): 100, (2, 1): 200}
    state.session_count[(100, 3, "S")] = 1   # GV 100 đã có tiết Thứ 3; GV 200 chưa
    rng = random.Random(0)
    pick = sched._pick_best_scored(1, slot, state, role_index, subjects,
                                    assigned_teacher, 0.0, rng)
    assert pick == (2, 200)   # môn B (GV 200 trống ngày đó) nhận điểm thưởng idle-day


def test_change_minimization_keeps_old_baseline_when_feasible():
    classes = [ClassRoom(1, "6A")]
    subjects = [
        Subject(1, "Toan hoc", ROLE_THUONG, 1),
        Subject(2, "HDTN", ROLE_HDTN, 2),
    ]
    teachers = [Teacher(1, "GV1"), Teacher(2, "GV2")]
    need = {(1, 1): 1, (2, 1): 1}
    assigned_teacher = {(1, 1): 1, (2, 1): 2}
    timeslots = _make_timeslots(morning=1, afternoon=0, weekdays=(3,))  # single Tuesday period-1 slot
    old_subject = {(1, 3, "S", 1): 1}  # baseline already has Toan in that slot
    inp = _build_input(classes, subjects, teachers, need, assigned_teacher, timeslots,
                        seed=7, old_subject=old_subject)

    result = sched.run(inp, max_attempts=100, target_successes=3)
    assert result.success is True
    slot_id = inp.slots[0].slot_id
    assert result.assignment[slot_id] == 1
    assert result.cells_changed == 0
