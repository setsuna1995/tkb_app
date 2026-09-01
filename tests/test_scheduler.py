import os
import random
import threading
from collections import defaultdict

from core import frame
from core import scheduler as sched
from core.models import (
    ROLE_GDTC, ROLE_HDTN, ROLE_KEP, ROLE_NANG, ROLE_NANG_KEP, ROLE_THUONG,
    ClassRoom, SchedulingConfig, SchedulingInput, Slot, Subject, Teacher, TimeSlot,
)
from core.roles import resolve_roles
from core.scheduler import _State, _feasible, _put_at
from data import db, repository as repo
from io_excel.importer import import_xlsm

FIXTURE = os.path.join(os.path.dirname(__file__), "..", "io_excel", "sample_school.xlsm")


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


def test_gdtc_avoid_period_configurable():
    subjects = [Subject(1, "GDTC", ROLE_GDTC), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    state = _State(remaining_need={(1, 1): 10}, busy=set())
    config = SchedulingConfig(gdtc_avoid_period=3)
    ts3 = TimeSlot(1, 2, "S", 3)
    assert _feasible(1, ts3, 1, 100, state, role_index, config=config) is False
    state.occupied[(1, 2, "S", 4)] = True  # satisfy liền mạch so the avoid-period check is what's tested
    ts5 = TimeSlot(2, 2, "S", 5)  # tiết 5 không còn bị né với config này
    assert _feasible(1, ts5, 1, 100, state, role_index, config=config) is True


def test_heavy_subjects_morning_only_off_by_default_allows_afternoon():
    subjects = [Subject(1, "Toan", ROLE_NANG), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    state = _State(remaining_need={(1, 1): 10}, busy=set())
    ts_afternoon = TimeSlot(1, 2, "C", 1)
    assert _feasible(1, ts_afternoon, 1, 100, state, role_index) is True


def test_heavy_subjects_morning_only_rejects_afternoon_when_on():
    subjects = [Subject(1, "Toan", ROLE_NANG), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    state = _State(remaining_need={(1, 1): 10}, busy=set())
    config = SchedulingConfig(heavy_subjects_morning_only=True)
    ts_afternoon = TimeSlot(1, 2, "C", 1)
    assert _feasible(1, ts_afternoon, 1, 100, state, role_index, config=config) is False
    ts_morning = TimeSlot(2, 2, "S", 1)
    assert _feasible(1, ts_morning, 1, 100, state, role_index, config=config) is True


def test_heavy_subjects_morning_only_does_not_restrict_non_heavy_subjects():
    subjects = [Subject(1, "Nhac", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    state = _State(remaining_need={(1, 1): 10}, busy=set())
    config = SchedulingConfig(heavy_subjects_morning_only=True)
    ts_afternoon = TimeSlot(1, 2, "C", 1)
    assert _feasible(1, ts_afternoon, 1, 100, state, role_index, config=config) is True


def test_morning_only_subject_ids_rejects_afternoon():
    subjects = [
        Subject(1, "Toan", ROLE_THUONG),
        Subject(2, "Van", ROLE_THUONG),
        Subject(3, "Nhac", ROLE_THUONG),
        Subject(4, "HDTN", ROLE_HDTN),
    ]
    role_index = resolve_roles(subjects)
    state = _State(remaining_need={(1, 1): 10, (2, 1): 10, (3, 1): 10}, busy=set())
    config = SchedulingConfig(morning_only_subject_ids=frozenset({1, 2}))

    ts_afternoon = TimeSlot(1, 2, "C", 1)
    ts_morning = TimeSlot(2, 2, "S", 1)

    # Subjects in morning_only_subject_ids are rejected in afternoon, allowed in morning
    assert _feasible(1, ts_afternoon, 1, 100, state, role_index, config=config) is False
    assert _feasible(1, ts_morning, 1, 100, state, role_index, config=config) is True
    assert _feasible(1, ts_afternoon, 2, 100, state, role_index, config=config) is False
    assert _feasible(1, ts_morning, 2, 100, state, role_index, config=config) is True

    # Subject not in morning_only_subject_ids is allowed in afternoon
    assert _feasible(1, ts_afternoon, 3, 100, state, role_index, config=config) is True


def test_max_periods_per_session_configurable():
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    ts = TimeSlot(1, 2, "S", 1)
    state = _State(remaining_need={(1, 1): 10}, busy=set())
    config = SchedulingConfig(max_periods_per_session=3)
    state.session_count[(100, 2, "S")] = 3
    assert _feasible(1, ts, 1, 100, state, role_index, config=config) is False
    state.session_count[(100, 2, "S")] = 2
    assert _feasible(1, ts, 1, 100, state, role_index, config=config) is True


def test_feasible_defaults_to_current_behavior_when_config_omitted():
    subjects = [Subject(1, "GDTC", ROLE_GDTC), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    state = _State(remaining_need={(1, 1): 10}, busy=set())
    ts5 = TimeSlot(1, 2, "S", 5)
    assert _feasible(1, ts5, 1, 100, state, role_index) is False  # vẫn né tiết 5 như cũ


def test_feasible_rejects_placement_outside_subject_class_allowed_cells():
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    state = _State(remaining_need={(1, 1): 10}, busy=set())
    allowed = {(1, 1): frozenset({(3, "C")})}
    ts_wrong = TimeSlot(1, 2, "S", 1)
    assert _feasible(1, ts_wrong, 1, 100, state, role_index, subject_class_allowed_cells=allowed) is False
    ts_right = TimeSlot(2, 3, "C", 1)
    assert _feasible(1, ts_right, 1, 100, state, role_index, subject_class_allowed_cells=allowed) is True


def test_feasible_unaffected_when_class_subject_pair_absent_from_allowed_cells():
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    state = _State(remaining_need={(1, 1): 10}, busy=set())
    allowed = {(1, 99): frozenset({(3, "C")})}  # luật chỉ áp dụng cho lớp 99, không phải lớp 1
    ts = TimeSlot(1, 2, "S", 1)
    assert _feasible(1, ts, 1, 100, state, role_index, subject_class_allowed_cells=allowed) is True


def test_feasible_defaults_to_current_behavior_when_subject_class_allowed_cells_omitted():
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    state = _State(remaining_need={(1, 1): 10}, busy=set())
    ts = TimeSlot(1, 2, "S", 1)
    assert _feasible(1, ts, 1, 100, state, role_index) is True


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


def test_block_size_3_allows_extending_either_end_of_the_run():
    subjects = [Subject(1, "HDTN_CD", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects, hdtn_thematic_week=False)
    role_index.block_size[1] = 3
    state = _State(remaining_need={(1, 1): 10}, busy=set())

    ts2 = TimeSlot(1, 2, "S", 2)
    _put_at(state, Slot(1, 1, ts2), 1, 100, role_index)

    # extend forward (period 3) -- still under cap (2 placed, N=3)
    ts3 = TimeSlot(2, 2, "S", 3)
    assert _feasible(1, ts3, 1, 100, state, role_index) is True
    _put_at(state, Slot(2, 1, ts3), 1, 100, role_index)

    # cap reached (2,3 placed, N=3) -- extending backward (period 1) still allowed,
    # it completes the block at exactly 3
    state.occupied[(1, 2, "S", 1)] = True  # satisfy lien-mach for a period-1 placement (always true)
    ts1 = TimeSlot(3, 2, "S", 1)
    assert _feasible(1, ts1, 1, 100, state, role_index) is True
    _put_at(state, Slot(3, 1, ts1), 1, 100, role_index)

    # cap_d=3 reached -- a 4th period the same day is blocked regardless of adjacency
    state.occupied[(1, 2, "S", 4)] = True
    ts4 = TimeSlot(4, 2, "S", 4)
    assert _feasible(1, ts4, 1, 100, state, role_index) is False


def test_block_size_3_rejects_non_adjacent_extension():
    subjects = [Subject(1, "HDTN_CD", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    role_index.block_size[1] = 3
    state = _State(remaining_need={(1, 1): 10}, busy=set())

    ts2 = TimeSlot(1, 2, "S", 2)
    _put_at(state, Slot(1, 1, ts2), 1, 100, role_index)
    ts3 = TimeSlot(2, 2, "S", 3)
    _put_at(state, Slot(2, 1, ts3), 1, 100, role_index)

    # period 5 is not adjacent to the (2,3) run -- must be rejected
    state.occupied[(1, 2, "S", 4)] = True
    ts5 = TimeSlot(3, 2, "S", 5)
    assert _feasible(1, ts5, 1, 100, state, role_index) is False


def test_block_size_defaults_to_one_when_absent():
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    assert role_index.block_size == {}
    state = _State(remaining_need={(1, 1): 10}, busy=set())
    ts1 = TimeSlot(1, 2, "S", 1)
    _put_at(state, Slot(1, 1, ts1), 1, 100, role_index)
    state.occupied[(1, 2, "S", 2)] = True
    ts2 = TimeSlot(2, 2, "S", 2)
    assert _feasible(1, ts2, 1, 100, state, role_index) is False


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


def test_resolve_roles_block_size_for_kep_subjects():
    subjects = [Subject(1, "Van", ROLE_KEP), Subject(2, "Toan", ROLE_NANG_KEP),
                Subject(3, "Su", ROLE_THUONG), Subject(4, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    assert role_index.block_size == {1: 2, 2: 2}


def test_resolve_roles_block_size_includes_extra_kep_ids():
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects, extra_kep_ids=frozenset({1}))
    assert role_index.block_size == {1: 2}


def test_resolve_roles_hdtn_thematic_week_sets_block_size_3():
    subjects = [Subject(1, "Van", ROLE_KEP), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects, hdtn_thematic_week=True)
    assert role_index.block_size == {1: 2, 2: 3}


def test_resolve_roles_hdtn_thematic_week_off_by_default():
    subjects = [Subject(1, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    assert role_index.block_size == {}


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


def test_heavy_subject_consecutive_cap_stricter_than_default():
    # N=2: 1 rồi 2 (heavy) đã đủ; tiết thứ 3 liên tiếp (heavy) phải bị chặn.
    #
    # Lưu ý: dùng 1 môn heavy THỨ 3 riêng biệt (Hoa) cho tiết 3 thay vì lặp lại
    # subject_id đã đặt trước đó -- nếu tái dùng subject_id 1/2, check "positions
    # >= cap_d" (mỗi môn tối đa 1 tiết/ngày, không phải KEP) sẽ return False TRƯỚC
    # khi chạm tới nhánh heavy-window đang muốn kiểm thử, khiến assertion pass vì
    # lý do không liên quan (test giả -- xác nhận bằng cách chạy lại trên code cũ,
    # chưa generalize, vẫn ra False).
    subjects = [
        Subject(1, "Toan", ROLE_NANG), Subject(2, "Ly", ROLE_NANG),
        Subject(3, "Hoa", ROLE_NANG), Subject(4, "HDTN", ROLE_HDTN),
    ]
    role_index = resolve_roles(subjects)
    config = SchedulingConfig(max_heavy_consecutive=2)
    state = _State(remaining_need={(1, 1): 10, (2, 1): 10, (3, 1): 10}, busy=set())

    ts1 = TimeSlot(1, 2, "S", 1)
    assert _feasible(1, ts1, 1, 100, state, role_index, config=config) is True
    _put_at(state, Slot(1, 1, ts1), 1, 100, role_index)

    ts2 = TimeSlot(2, 2, "S", 2)
    assert _feasible(1, ts2, 2, 101, state, role_index, config=config) is True
    _put_at(state, Slot(2, 1, ts2), 2, 101, role_index)

    ts3 = TimeSlot(3, 2, "S", 3)
    assert _feasible(1, ts3, 3, 102, state, role_index, config=config) is False


def test_heavy_subject_consecutive_cap_looser_than_default():
    # N=4: chuỗi 4 tiết heavy liên tiếp phải được phép (mặc định N=3 sẽ chặn ở đây).
    #
    # Lưu ý: dùng 1 môn heavy THỨ 4 riêng biệt (Sinh) cho tiết 4 -- cùng lý do như
    # test_heavy_subject_consecutive_cap_stricter_than_default ở trên (tránh check
    # "positions >= cap_d" che mất nhánh heavy-window đang muốn kiểm thử).
    subjects = [
        Subject(1, "Toan", ROLE_NANG), Subject(2, "Ly", ROLE_NANG),
        Subject(3, "Hoa", ROLE_NANG), Subject(4, "Sinh", ROLE_NANG), Subject(5, "HDTN", ROLE_HDTN),
    ]
    role_index = resolve_roles(subjects)
    config = SchedulingConfig(max_heavy_consecutive=4)
    state = _State(remaining_need={(1, 1): 10, (2, 1): 10, (3, 1): 10, (4, 1): 10}, busy=set())

    ts1 = TimeSlot(1, 2, "S", 1)
    _put_at(state, Slot(1, 1, ts1), 1, 100, role_index)
    ts2 = TimeSlot(2, 2, "S", 2)
    _put_at(state, Slot(2, 1, ts2), 2, 101, role_index)
    ts3 = TimeSlot(3, 2, "S", 3)
    _put_at(state, Slot(3, 1, ts3), 3, 102, role_index)

    ts4 = TimeSlot(4, 2, "S", 4)
    assert _feasible(1, ts4, 4, 103, state, role_index, config=config) is True


def test_heavy_subject_run_of_3_cap_unchanged_with_default_config():
    # Regression: gọi lại y hệt test_heavy_subject_run_of_3_cap nhưng truyền config mặc định
    # tường minh -- phải cho kết quả giống hệt không truyền config.
    subjects = [
        Subject(1, "Toan", ROLE_NANG), Subject(2, "Ly", ROLE_NANG),
        Subject(3, "Hoa", ROLE_NANG), Subject(4, "Sinh", ROLE_NANG), Subject(5, "HDTN", ROLE_HDTN),
    ]
    role_index = resolve_roles(subjects)
    config = SchedulingConfig()
    state = _State(remaining_need={(1, 1): 10, (2, 1): 10, (3, 1): 10, (4, 1): 10}, busy=set())
    _put_at(state, Slot(1, 1, TimeSlot(1, 2, "S", 1)), 1, 100, role_index)
    _put_at(state, Slot(2, 1, TimeSlot(2, 2, "S", 2)), 2, 101, role_index)
    _put_at(state, Slot(3, 1, TimeSlot(3, 2, "S", 3)), 3, 102, role_index)
    ts4 = TimeSlot(4, 2, "S", 4)
    assert _feasible(1, ts4, 4, 103, state, role_index, config=config) is False


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


def test_teacher_pinned_full_day_off():
    rng = random.Random(1)
    teachers_by_id = {1: Teacher(1, "GV The duc", pinned_full_day_off=4)}
    for _ in range(50):
        offs = sched._assign_off_slots({1}, teachers_by_id, rng, off_slot_count=1)
        assert (4, "S") in offs[1]
        assert (4, "C") in offs[1]


def test_teacher_pinned_afternoon_off():
    rng = random.Random(1)
    teachers_by_id = {1: Teacher(1, "GV Thuong", pinned_afternoon_off=3)}
    for _ in range(50):
        offs = sched._assign_off_slots({1}, teachers_by_id, rng, off_slot_count=1)
        assert (3, "C") in offs[1]


def test_teacher_off_sessions_override():
    rng = random.Random(1)
    teachers_by_id = {
        1: Teacher(1, "GV The duc", off_sessions_override=3),
        2: Teacher(2, "GV Thuong"),
    }
    for _ in range(50):
        offs = sched._assign_off_slots({1, 2}, teachers_by_id, rng, off_slot_count=1)
        assert len(offs[1]) == 3
        assert len(offs[2]) == 1


def test_teacher_pinned_full_day_and_extra_afternoon_off():
    # Yêu cầu #3 thật: 1 ngày nghỉ trọn + 1 buổi chiều cố định khác ngày = 3 buổi nghỉ/tuần.
    rng = random.Random(1)
    teachers_by_id = {
        1: Teacher(1, "GV The duc", off_sessions_override=3, pinned_full_day_off=4, pinned_afternoon_off=3),
    }
    for _ in range(50):
        offs = sched._assign_off_slots({1}, teachers_by_id, rng, off_slot_count=1)
        assert len(offs[1]) == 3
        assert (4, "S") in offs[1]
        assert (4, "C") in offs[1]
        assert (3, "C") in offs[1]


def test_pinned_off_conflicts_with_forbidden_are_dropped():
    # Thứ 6 nằm trọn trong FORBIDDEN_OFF_CELLS mặc định (sáng VÀ chiều) -> pin bị bỏ qua,
    # GV vẫn nhận đủ off_slot_count buổi nghỉ ngẫu nhiên như GV thường (không crash, không kẹt).
    rng = random.Random(1)
    teachers_by_id = {1: Teacher(1, "GV", pinned_full_day_off=6)}
    for _ in range(50):
        offs = sched._assign_off_slots({1}, teachers_by_id, rng, off_slot_count=1)
        assert (6, "S") not in offs[1]
        assert (6, "C") not in offs[1]
        assert len(offs[1]) == 1


def test_off_slots_unchanged_when_no_override_or_pins():
    # Regression: GV không có 3 field mới -> hành vi y hệt trước khi có tính năng này.
    rng = random.Random(1)
    teachers_by_id = {1: Teacher(1, "Normal", cap=19)}
    for _ in range(50):
        offs = sched._assign_off_slots({1}, teachers_by_id, rng, off_slot_count=1)
        assert len(offs[1]) == 1


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


def test_assign_off_slots_respects_custom_forbidden_cells_and_count():
    rng = random.Random(1)
    teachers_by_id = {1: Teacher(1, "Normal", role="", must_monday=False, is_gvcn=False, cap=19)}
    custom_forbidden = frozenset({(2, "S"), (2, "C"), (3, "S"), (3, "C"), (4, "S"), (4, "C")})
    off_slots = sched._assign_off_slots(
        {1}, teachers_by_id, rng, off_slot_count=2, forbidden_off_cells=custom_forbidden,
    )
    assert len(off_slots[1]) == 2
    for cell in off_slots[1]:
        assert cell not in custom_forbidden


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
                  seed=12345, ban_busy=None, old_subject=None, extra_kep_ids=frozenset(),
                  hdtn_thematic_week=False, config=None):
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
        extra_kep_ids=extra_kep_ids, hdtn_thematic_week=hdtn_thematic_week,
        config=config or SchedulingConfig(),
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
    inp = _build_input(classes, subjects, teachers, need, assigned_teacher, timeslots, seed=42,
                       config=SchedulingConfig(avoid_gdtc_consecutive_days=False))

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


def test_subject_class_rule_thread_through_run():
    # Luật môn/lớp/buổi phải được tôn trọng xuyên suốt sched.run(), không chỉ ở _feasible.
    # Khung 6 ngày × (2 sáng + 2 chiều) = 24 ô, định mức = đúng 24 tiết để lấp đầy khung
    # (giống mọi test full-run khác trong file này) -- mọi môn cap 1 tiết/ngày nên mỗi ngày
    # cần đúng 4 môn khác nhau. Nhạc/6A bị giới hạn ở (Thứ 3, Thứ 6) buổi chiều.
    classes = [ClassRoom(1, "6A")]
    subjects = [
        Subject(1, "Toan hoc", ROLE_THUONG, 1),
        Subject(2, "Nhac", ROLE_THUONG, 2),
        Subject(3, "HDTN", ROLE_HDTN, 3),
        Subject(4, "Tieng Anh", ROLE_THUONG, 4),
        Subject(5, "Lich su", ROLE_THUONG, 5),
    ]
    teachers = [Teacher(1, "GV1"), Teacher(2, "GV2"), Teacher(3, "GVCN", is_gvcn=True),
                Teacher(4, "GV4"), Teacher(5, "GV5")]
    need = {(1, 1): 6, (2, 1): 2, (3, 1): 6, (4, 1): 5, (5, 1): 5}
    assigned_teacher = {(1, 1): 1, (2, 1): 2, (3, 1): 3, (4, 1): 4, (5, 1): 5}
    timeslots = _make_timeslots(morning=2, afternoon=2)
    inp = _build_input(classes, subjects, teachers, need, assigned_teacher, timeslots, seed=42)
    inp.subject_class_allowed_cells = {(2, 1): frozenset({(3, "C"), (6, "C")})}  # Nhạc/6A chỉ (Thứ 3, Thứ 6) chiều

    result = sched.run(inp, max_attempts=6000, target_successes=3)
    assert result.success is True

    nhac_cells = []
    for slot in inp.slots:
        if slot.class_id != 1:
            continue
        assigned_subject = result.assignment.get(slot.slot_id)
        if assigned_subject == 2:
            nhac_cells.append((slot.ts.weekday, slot.ts.session, slot.ts.period))
            assert (slot.ts.weekday, slot.ts.session) in {(3, "C"), (6, "C")}
    # cả 2 tiết Nhạc đều phải được xếp -- nếu không, assert trên đúng một cách vô nghĩa
    assert len(nhac_cells) == 2, nhac_cells


def test_chao_co_position_configurable_in_full_run():
    classes = [ClassRoom(1, "6A")]
    subjects = [
        Subject(1, "Toan hoc", ROLE_THUONG, 1),
        Subject(2, "Ngu van", ROLE_KEP, 2),
        Subject(3, "GDTC", ROLE_GDTC, 3),
        Subject(4, "HDTN", ROLE_HDTN, 4),
        Subject(5, "Tieng Anh", ROLE_THUONG, 5),
    ]
    teachers = [Teacher(i, f"GV{i}") for i in range(1, 6)]
    need = {(1, 1): 6, (2, 1): 12, (3, 1): 3, (4, 1): 3, (5, 1): 6}
    assigned_teacher = {(1, 1): 1, (2, 1): 2, (3, 1): 3, (4, 1): 4, (5, 1): 5}
    timeslots = _make_timeslots(morning=5, afternoon=0)
    inp = _build_input(classes, subjects, teachers, need, assigned_teacher, timeslots, seed=42)
    # chao_co_period stays 1: the pin block runs before anything else is placed in the
    # attempt, so BAT_LIEN_MACH (no gaps in a session) can never be satisfied for
    # period > 1 at pin time -- same constraint every other period-1-only pin (e.g. the
    # existing Monday chào cờ pin) relies on. Only chao_co_weekday is varied here.
    inp.config = SchedulingConfig(chao_co_weekday=3, chao_co_period=1)

    result = sched.run(inp, max_attempts=6000, target_successes=3)
    assert result.success is True

    hdtn_id = 4
    for slot in inp.slots:
        if slot.ts.weekday == 3 and slot.ts.session == "S" and slot.ts.period == 1:
            assert result.assignment.get(slot.slot_id) == hdtn_id
        if slot.ts.weekday == 2 and slot.ts.session == "S" and slot.ts.period == 1:
            assert result.assignment.get(slot.slot_id) != hdtn_id


# ---------------------------------------------------------------------------
# Mandatory block-pairing: repair pass / validation (_repair_unpaired_blocks /
# _has_unpaired_block / _merge_one_block_period)
# ---------------------------------------------------------------------------

def _slot_by_coord(slots):
    return {(s.class_id, s.ts.weekday, s.ts.session, s.ts.period): s for s in slots}


def test_has_unpaired_block_false_when_fully_paired():
    classes = [ClassRoom(1, "6A")]
    subjects = [Subject(1, "Van", ROLE_KEP), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    timeslots = _make_timeslots(morning=5, afternoon=0)
    inp = _build_input(classes, subjects, [Teacher(1, "GV1"), Teacher(2, "GV2")],
                        {(1, 1): 2, (2, 1): 3}, {(1, 1): 1, (2, 1): 2}, timeslots)
    state = _State(remaining_need={(1, 1): 10}, busy=set())
    ts1 = TimeSlot(1, 2, "S", 1)
    ts2 = TimeSlot(2, 2, "S", 2)
    _put_at(state, Slot(1, 1, ts1), 1, 100, role_index)
    _put_at(state, Slot(2, 1, ts2), 1, 100, role_index)
    assert sched._has_unpaired_block(inp, state, role_index) is False


def test_has_unpaired_block_true_when_two_lone_days_exceed_allowance():
    classes = [ClassRoom(1, "6A")]
    subjects = [Subject(1, "Van", ROLE_KEP), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    timeslots = _make_timeslots(morning=5, afternoon=0)
    inp = _build_input(classes, subjects, [Teacher(1, "GV1"), Teacher(2, "GV2")],
                        {(1, 1): 2, (2, 1): 3}, {(1, 1): 1, (2, 1): 2}, timeslots)
    state = _State(remaining_need={(1, 1): 10}, busy=set())
    # 2 periods needed (block_size=2), but placed as 2 separate lone days -- excess
    ts_mon = TimeSlot(1, 2, "S", 1)
    ts_tue = TimeSlot(2, 3, "S", 1)
    _put_at(state, Slot(1, 1, ts_mon), 1, 100, role_index)
    _put_at(state, Slot(2, 1, ts_tue), 1, 100, role_index)
    assert sched._has_unpaired_block(inp, state, role_index) is True


def test_has_unpaired_block_allows_exactly_one_leftover_single():
    # N=2, total_placed=3 (odd) -- 1 full pair + 1 leftover single is fine.
    classes = [ClassRoom(1, "6A")]
    subjects = [Subject(1, "Anh", ROLE_KEP), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    timeslots = _make_timeslots(morning=5, afternoon=0)
    inp = _build_input(classes, subjects, [Teacher(1, "GV1"), Teacher(2, "GV2")],
                        {(1, 1): 3, (2, 1): 3}, {(1, 1): 1, (2, 1): 2}, timeslots)
    state = _State(remaining_need={(1, 1): 10}, busy=set())
    ts_mon1 = TimeSlot(1, 2, "S", 1)
    ts_mon2 = TimeSlot(2, 2, "S", 2)
    ts_tue = TimeSlot(3, 3, "S", 1)
    _put_at(state, Slot(1, 1, ts_mon1), 1, 100, role_index)
    _put_at(state, Slot(2, 1, ts_mon2), 1, 100, role_index)
    _put_at(state, Slot(3, 1, ts_tue), 1, 100, role_index)
    assert sched._has_unpaired_block(inp, state, role_index) is False


def test_merge_one_block_period_merges_two_lone_days_into_a_pair():
    # IMPORTANT: use real Slot objects looked up via slot_by_coord (built from
    # inp.slots), never hand-fabricated Slot/TimeSlot objects with made-up
    # slot_id/ts_id values -- _merge_one_block_period looks the *same* coordinate
    # up again through slot_by_coord internally (for the target cell) and via
    # _remove_at/_put_at (for the source cell's bookkeeping in state.assigned/
    # state.busy, keyed by slot_id/ts_id). A hand-fabricated Slot's IDs won't
    # match what slot_by_coord returns for that same (weekday, session, period),
    # so state.assigned[<real slot_id>] would KeyError inside _remove_at.
    classes = [ClassRoom(1, "6A")]
    subjects = [Subject(1, "Van", ROLE_KEP), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    teachers = [Teacher(100, "GV1"), Teacher(101, "GV2")]
    timeslots = _make_timeslots(morning=5, afternoon=0)
    inp = _build_input(classes, subjects, teachers,
                        {(1, 1): 2, (2, 1): 3}, {(1, 1): 100, (2, 1): 101}, timeslots)
    slot_by_coord = _slot_by_coord(inp.slots)
    state = _State(remaining_need={(1, 1): 0, (2, 1): 0}, busy=set())
    # rem_need_count/rem_slot_count must be seeded with the class's real totals
    # (mirroring how run() itself seeds them) -- _merge_one_block_period's "safe
    # to mark source as slack" check compares these two counters, so leaving them
    # at their defaultdict(int) default of 0 (then going negative-but-equal after
    # _put_at) makes that comparison spuriously false regardless of whether
    # marking source as slack is actually safe.
    state.rem_need_count[1] = 5   # total need for class 1: (1,1)=2 + (2,1)=3
    state.rem_slot_count[1] = 30  # total slots for class 1: 6 weekdays x 5 periods
    mon_slot = slot_by_coord[(1, 2, "S", 1)]
    tue_slot = slot_by_coord[(1, 3, "S", 3)]
    _put_at(state, mon_slot, 1, 100, role_index)
    _put_at(state, tue_slot, 1, 100, role_index)

    ok = sched._merge_one_block_period(1, 1, 3, 2, state, role_index, subjects,
                                        {(1, 1): 100, (2, 1): 101}, slot_by_coord, None, None, None)
    assert ok is True
    assert state.placed[(1, 1, 3)] == []
    positions = sorted(state.placed[(1, 1, 2)])
    assert positions == [("S", 1), ("S", 2)]


def test_merge_one_block_period_reclaims_adjacent_slack_cell():
    # Day A (Monday) has a lone period; day B (Tuesday) also has a lone period, and
    # the cell immediately after it (Tuesday period 2) is -1 (intentionally-empty
    # slack), not another subject. The merge should reclaim that slack cell for the
    # subject (forming a full pair on Tuesday) rather than skipping it, and leave
    # day A's slot empty.
    classes = [ClassRoom(1, "6A")]
    subjects = [Subject(1, "Van", ROLE_KEP), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    teachers = [Teacher(100, "GV1"), Teacher(101, "GV2")]
    timeslots = _make_timeslots(morning=5, afternoon=0)
    inp = _build_input(classes, subjects, teachers,
                        {(1, 1): 2, (2, 1): 3}, {(1, 1): 100, (2, 1): 101}, timeslots)
    slot_by_coord = _slot_by_coord(inp.slots)
    state = _State(remaining_need={(1, 1): 0, (2, 1): 0}, busy=set())
    # rem_need_count/rem_slot_count must be seeded with the class's real totals --
    # see the comment in test_merge_one_block_period_merges_two_lone_days_into_a_pair
    # above for why.
    state.rem_need_count[1] = 5   # total need for class 1: (1,1)=2 + (2,1)=3
    state.rem_slot_count[1] = 30  # total slots for class 1: 6 weekdays x 5 periods
    mon_slot = slot_by_coord[(1, 2, "S", 1)]
    tue_slot = slot_by_coord[(1, 3, "S", 1)]
    tue_slack_slot = slot_by_coord[(1, 3, "S", 2)]
    _put_at(state, mon_slot, 1, 100, role_index)
    _put_at(state, tue_slot, 1, 100, role_index)
    state.assigned[tue_slack_slot.slot_id] = -1
    state.rem_slot_count[1] -= 1

    ok = sched._merge_one_block_period(1, 1, 2, 3, state, role_index, subjects,
                                        {(1, 1): 100, (2, 1): 101}, slot_by_coord, None, None, None)
    assert ok is True
    # day A's vacated slot is explicitly marked -1 (slack), not left as a bare
    # None -- safe here since it's the trailing edge of Monday's session (nothing
    # placed after period 1 that day) and there's slot budget to spare.
    assert state.assigned.get(mon_slot.slot_id) == -1
    assert state.placed[(1, 1, 2)] == []
    assert state.assigned[tue_slack_slot.slot_id] == 1
    positions = sorted(state.placed[(1, 1, 3)])
    assert positions == [("S", 1), ("S", 2)]


def test_repair_unpaired_blocks_resolves_three_lone_hdtn_days_into_one_block():
    classes = [ClassRoom(1, "6A")]
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects, hdtn_thematic_week=True)
    teachers = [Teacher(1, "GVToan"), Teacher(2, "GVCN")]
    need = {(1, 1): 2, (2, 1): 3}
    assigned_teacher = {(1, 1): 1, (2, 1): 2}
    timeslots = _make_timeslots(morning=5, afternoon=0)
    inp = _build_input(classes, subjects, teachers, need, assigned_teacher, timeslots)
    slot_by_coord = _slot_by_coord(inp.slots)
    state = _State(remaining_need={(1, 1): 0, (2, 1): 0}, busy=set())
    # rem_need_count/rem_slot_count must be seeded with the class's real totals --
    # see the comment in test_merge_one_block_period_merges_two_lone_days_into_a_pair
    # above for why.
    state.rem_need_count[1] = 5   # total need for class 1: (1,1)=2 + (2,1)=3
    state.rem_slot_count[1] = 30  # total slots for class 1: 6 weekdays x 5 periods
    # Real slots from slot_by_coord, not hand-fabricated ones -- see the comment
    # in test_merge_one_block_period_merges_two_lone_days_into_a_pair above for why.
    for wd, period in ((2, 1), (3, 1), (4, 1)):
        _put_at(state, slot_by_coord[(1, wd, "S", period)], 2, assigned_teacher[(2, 1)], role_index)
    assert sched._has_unpaired_block(inp, state, role_index) is True

    sched._repair_unpaired_blocks(inp, state, role_index, assigned_teacher, slot_by_coord, None, None, None)

    assert sched._has_unpaired_block(inp, state, role_index) is False


def test_repair_unpaired_blocks_terminates_on_a_merge_cycle():
    # Reviewer-reproduced infinite loop: N=3 (only reachable via hdtn_thematic_week
    # =True), a 2-period morning, HDTN split as {Mon: p1,p2} + {Tue: p1} with
    # (Tue, p2) = -1. Before the fix, _merge_one_block_period kept successfully
    # "resolving" one day into the other and back through that shared adjacent
    # slack cell, forever -- the while loop in _repair_unpaired_blocks had no
    # iteration bound and no monotonic-progress guarantee. Run in a background
    # thread with a wall-clock timeout so a regression here fails this test
    # instead of hanging the whole suite.
    classes = [ClassRoom(1, "6A")]
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects, hdtn_thematic_week=True)
    assert role_index.block_size[2] == 3
    teachers = [Teacher(1, "GVToan"), Teacher(2, "GVCN")]
    need = {(1, 1): 1, (2, 1): 3}
    assigned_teacher = {(1, 1): 1, (2, 1): 2}
    timeslots = _make_timeslots(morning=2, afternoon=0, weekdays=(2, 3))
    inp = _build_input(classes, subjects, teachers, need, assigned_teacher, timeslots)
    slot_by_coord = _slot_by_coord(inp.slots)
    state = _State(remaining_need={(1, 1): 0, (2, 1): 0}, busy=set())
    mon1 = slot_by_coord[(1, 2, "S", 1)]
    mon2 = slot_by_coord[(1, 2, "S", 2)]
    tue1 = slot_by_coord[(1, 3, "S", 1)]
    tue2 = slot_by_coord[(1, 3, "S", 2)]
    _put_at(state, mon1, 2, assigned_teacher[(2, 1)], role_index)
    _put_at(state, mon2, 2, assigned_teacher[(2, 1)], role_index)
    _put_at(state, tue1, 2, assigned_teacher[(2, 1)], role_index)
    state.assigned[tue2.slot_id] = -1
    state.rem_slot_count[1] -= 1
    assert sched._has_unpaired_block(inp, state, role_index) is True

    finished = threading.Event()

    def run_repair():
        sched._repair_unpaired_blocks(inp, state, role_index, assigned_teacher, slot_by_coord, None, None, None)
        finished.set()

    t = threading.Thread(target=run_repair, daemon=True)
    t.start()
    t.join(timeout=5)
    assert finished.is_set(), "_repair_unpaired_blocks did not return within 5s -- infinite loop regression"
    # genuinely unresolvable with only 2 periods/morning for a 3-period block --
    # repair should give up (bounded), not silently claim success.
    assert sched._has_unpaired_block(inp, state, role_index) is True


def test_merge_one_block_period_never_strands_a_mid_session_gap():
    # Reviewer-reproduced: a merge that vacates `source` when there's nothing to
    # displace at the target must not leave a bare-None/gap hole in the middle of
    # a day's real content. Monday: A at p1, X (kep) at p2, B at p3 -- X's p2 has
    # "later content" (B at p3), so vacating it is only safe if it can be refilled;
    # here nothing can refill it, so the whole merge must roll back rather than
    # leave Monday p1=A, p2=empty, p3=B (a BAT_LIEN_MACH violation).
    classes = [ClassRoom(1, "6A")]
    subjects = [
        Subject(1, "X_kep", ROLE_KEP),
        Subject(2, "A", ROLE_THUONG),
        Subject(3, "B", ROLE_THUONG),
        Subject(4, "HDTN", ROLE_HDTN),
    ]
    role_index = resolve_roles(subjects)
    teachers = [Teacher(1, "GVX"), Teacher(2, "GVA"), Teacher(3, "GVB"), Teacher(4, "GVCN")]
    need = {(1, 1): 2, (2, 1): 1, (3, 1): 1, (4, 1): 1}
    assigned_teacher = {(1, 1): 1, (2, 1): 2, (3, 1): 3, (4, 1): 4}
    # weekday 4 (Wednesday) is intentionally left completely untouched below -- it's
    # real, genuine slack (not merely an inflated fake number), so this test proves
    # source_has_later_content is what blocks the "mark source as slack" fallback,
    # not merely "no slack budget available" (a weaker, less specific claim).
    timeslots = _make_timeslots(morning=3, afternoon=0, weekdays=(2, 3, 4))
    inp = _build_input(classes, subjects, teachers, need, assigned_teacher, timeslots)
    slot_by_coord = _slot_by_coord(inp.slots)
    state = _State(remaining_need={(1, 1): 0, (2, 1): 0, (3, 1): 0, (4, 1): 0}, busy=set())
    state.rem_need_count[1] = 5   # total need for class 1: 2+1+1+1
    state.rem_slot_count[1] = 9   # total slots for class 1: 3 weekdays x 3 periods
    mon1 = slot_by_coord[(1, 2, "S", 1)]  # A
    mon2 = slot_by_coord[(1, 2, "S", 2)]  # X (source -- has later content at p3)
    mon3 = slot_by_coord[(1, 2, "S", 3)]  # B
    tue1 = slot_by_coord[(1, 3, "S", 1)]  # X
    tue2 = slot_by_coord[(1, 3, "S", 2)]  # slack
    tue3 = slot_by_coord[(1, 3, "S", 3)]  # slack
    _put_at(state, mon1, 2, assigned_teacher[(2, 1)], role_index)
    _put_at(state, mon2, 1, assigned_teacher[(1, 1)], role_index)
    _put_at(state, mon3, 3, assigned_teacher[(3, 1)], role_index)
    _put_at(state, tue1, 1, assigned_teacher[(1, 1)], role_index)
    state.assigned[tue2.slot_id] = -1
    state.rem_slot_count[1] -= 1
    state.assigned[tue3.slot_id] = -1
    state.rem_slot_count[1] -= 1

    ok = sched._merge_one_block_period(1, 1, 2, 3, state, role_index, subjects,
                                        assigned_teacher, slot_by_coord, None, None, None)
    assert ok is False
    # state fully restored -- no gap, nothing changed.
    assert state.assigned[mon1.slot_id] == 2
    assert state.assigned[mon2.slot_id] == 1
    assert state.assigned[mon3.slot_id] == 3
    # generic invariant check: for every (class, weekday, session) actually used
    # in this input, the real (non-None, non--1) content must form a contiguous
    # prefix -- no bare None between two real periods.
    for cls in inp.classes:
        by_key = defaultdict(dict)
        for slot in inp.slots:
            if slot.class_id == cls.class_id:
                by_key[(slot.ts.weekday, slot.ts.session)][slot.ts.period] = state.assigned.get(slot.slot_id)
        for (wd, session), periods in by_key.items():
            real_periods = [p for p, v in periods.items() if v not in (None, -1)]
            if not real_periods:
                continue
            for p in range(min(real_periods), max(real_periods) + 1):
                assert periods.get(p) is not None, (
                    f"gap at class={cls.class_id} weekday={wd} session={session} period={p}"
                )


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


def test_full_run_kep_subject_with_odd_weekly_count_pairs_maximally():
    # Mirrors the real school data found during root-cause investigation: Ngoại ngữ
    # is a kép subject with an odd weekly count (3) in every class -- must place as
    # 1 full pair + exactly 1 leftover single, never scattered as 3 separate days.
    #
    # Load = 30 (6 ngày x 5 tiết sáng) to fully fill the class's 1-buổi frame, same
    # convention as test_small_synthetic_schedule_succeeds_and_meets_quotas /
    # test_extra_kep_ids_forces_adjacency_in_full_run -- without it, Saturday's
    # morning periods stay unfilled and the pre-existing SHL pin (which requires
    # period 4 already occupied by a real subject before period 5 can be pinned,
    # per BAT_LIEN_MACH) can never succeed, regardless of this task's changes.
    classes = [ClassRoom(1, "6A")]
    subjects = [
        Subject(1, "Ngoai ngu", ROLE_NANG_KEP, 1),
        Subject(2, "Toan hoc", ROLE_THUONG, 2),
        Subject(3, "Ngu van", ROLE_KEP, 3),
        Subject(4, "GDTC", ROLE_GDTC, 4),
        Subject(5, "Tieng Anh", ROLE_THUONG, 5),
        Subject(6, "HDTN", ROLE_HDTN, 6),
    ]
    teachers = [Teacher(1, "GV1"), Teacher(2, "GV2"), Teacher(3, "GV3"), Teacher(4, "GV4"),
                Teacher(5, "GV5"), Teacher(6, "GVCN", is_gvcn=True)]
    need = {(1, 1): 3, (2, 1): 6, (3, 1): 12, (4, 1): 3, (5, 1): 3, (6, 1): 3}
    assigned_teacher = {(1, 1): 1, (2, 1): 2, (3, 1): 3, (4, 1): 4, (5, 1): 5, (6, 1): 6}
    timeslots = _make_timeslots(morning=5, afternoon=0)
    inp = _build_input(classes, subjects, teachers, need, assigned_teacher, timeslots, seed=1)

    result = sched.run(inp, max_attempts=6000, target_successes=5)
    assert result.success is True

    placed = defaultdict(list)
    for slot in inp.slots:
        if result.assignment.get(slot.slot_id) == 1:
            placed[slot.ts.weekday].append(slot.ts.period)
    day_counts = sorted(len(v) for v in placed.values())
    assert day_counts == [1, 2], day_counts
    paired_day = [wd for wd, periods in placed.items() if len(periods) == 2][0]
    p1, p2 = sorted(placed[paired_day])
    assert p2 - p1 == 1


def test_full_run_all_three_rules_combined():
    # R1 (mandatory kép pairing, odd count) + R2 (HDTN thematic week) + R3 (heavy
    # afternoon ban) together, shaped after the real school data found during
    # root-cause investigation (Ngoại ngữ-like odd kép subject, HDTN 3/week).
    classes = [ClassRoom(1, "6A")]
    subjects = [
        Subject(1, "Ngoai ngu", ROLE_NANG_KEP, 1),   # heavy + kep, odd weekly count
        Subject(2, "Nhac", ROLE_THUONG, 2),           # non-heavy, no session restriction
        Subject(3, "HDTN", ROLE_HDTN, 3),
    ]
    teachers = [Teacher(1, "GVAnh"), Teacher(2, "GVNhac"), Teacher(3, "GVCN", is_gvcn=True)]
    need = {(1, 1): 3, (2, 1): 2, (3, 1): 3}
    assigned_teacher = {(1, 1): 1, (2, 1): 2, (3, 1): 3}
    timeslots = _make_timeslots(morning=4, afternoon=3, weekdays=(2, 3, 4, 5, 6))
    inp = _build_input(classes, subjects, teachers, need, assigned_teacher, timeslots,
                        seed=11, hdtn_thematic_week=True)
    inp.config = SchedulingConfig(heavy_subjects_morning_only=True)

    result = sched.run(inp, max_attempts=6000, target_successes=5)
    assert result.success is True

    # R3: Ngoại ngữ (heavy) never lands in an afternoon slot
    for slot in inp.slots:
        if result.assignment.get(slot.slot_id) == 1:
            assert slot.ts.session == "S", (slot.ts.weekday, slot.ts.session, slot.ts.period)

    # R1: Ngoại ngữ's 3 periods pair maximally (1 pair + 1 single, never 3 singles)
    placed_ngoai_ngu = defaultdict(list)
    for slot in inp.slots:
        if result.assignment.get(slot.slot_id) == 1:
            placed_ngoai_ngu[slot.ts.weekday].append(slot.ts.period)
    assert sorted(len(v) for v in placed_ngoai_ngu.values()) == [1, 2]

    # R2: HDTN's 3 periods form a single contiguous block
    placed_hdtn = defaultdict(list)
    for slot in inp.slots:
        if result.assignment.get(slot.slot_id) == 3:
            placed_hdtn[slot.ts.weekday].append(slot.ts.period)
    assert len(placed_hdtn) == 1, placed_hdtn
    (_wd, periods), = placed_hdtn.items()
    periods = sorted(periods)
    assert periods == [periods[0], periods[0] + 1, periods[0] + 2]


def test_full_run_with_morning_only_subject_ids():
    classes = [ClassRoom(1, "6A")]
    subjects = [
        Subject(1, "Toan", ROLE_THUONG, 1),
        Subject(2, "Van", ROLE_THUONG, 2),
        Subject(3, "Nhac", ROLE_THUONG, 3),
        Subject(4, "HDTN", ROLE_HDTN, 4),
    ]
    teachers = [Teacher(1, "GVToan"), Teacher(2, "GVVan"), Teacher(3, "GVNhac"), Teacher(4, "GVCN", is_gvcn=True)]
    need = {(1, 1): 4, (2, 1): 4, (3, 1): 2, (4, 1): 3}
    assigned_teacher = {(1, 1): 1, (2, 1): 2, (3, 1): 3, (4, 1): 4}
    timeslots = _make_timeslots(morning=4, afternoon=3, weekdays=(2, 3, 4, 5, 6))
    inp = _build_input(classes, subjects, teachers, need, assigned_teacher, timeslots, seed=42)
    # Both Toan (1) and Van (2) are ROLE_THUONG, but morning_only_subject_ids forces them to morning
    inp.config = SchedulingConfig(morning_only_subject_ids=frozenset({1, 2}))

    result = sched.run(inp, max_attempts=1000, target_successes=3)
    assert result.success is True

    for slot in inp.slots:
        assigned = result.assignment.get(slot.slot_id)
        if assigned in (1, 2):
            assert slot.ts.session == "S", f"Subject {assigned} placed in afternoon: {slot.ts}"


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


def test_hdtn_thematic_week_forms_one_block_and_skips_chao_co_shl_pins():
    # Thematic week HDTN: all 3 periods flow through block-aware greedy (no chào cờ/SHL pins).
    # Uses Toan (1 period) + HDTN (3 periods). HDTN forms 3-period contiguous block on a
    # single weekday, proving both pins were skipped: those pins anchor HDTN to Monday
    # period 1 (chào cờ) and Fri/Sat last period (SHL) — different non-adjacent weekdays
    # that would make a single 3-period contiguous block impossible.
    classes = [ClassRoom(1, "6A")]
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]
    teachers = [Teacher(1, "GVToan"), Teacher(2, "GVCN", is_gvcn=True)]
    need = {(1, 1): 1, (2, 1): 3}
    assigned_teacher = {(1, 1): 1, (2, 1): 2}
    timeslots = _make_timeslots(morning=5, afternoon=0, weekdays=(2, 3, 4, 5, 6, 7))
    inp = _build_input(classes, subjects, teachers, need, assigned_teacher, timeslots,
                        seed=3, hdtn_thematic_week=True)

    result = sched.run(inp, max_attempts=6000, target_successes=5)
    assert result.success is True

    placed = defaultdict(list)
    for slot in inp.slots:
        if result.assignment.get(slot.slot_id) == 2:  # HDTN is subject_id 2
            placed[slot.ts.weekday].append(slot.ts.period)
    # All 3 periods land on a single weekday, contiguous -- this alone proves the
    # chào cờ (Monday period 1) and SHL (Friday/Saturday last period) pins were
    # skipped: those two pins anchor HDTN to two *different*, non-adjacent
    # weekdays, which would make a single 3-period contiguous block impossible.
    assert len(placed) == 1, placed
    (_weekday, periods), = placed.items()
    periods = sorted(periods)
    assert periods == [periods[0], periods[0] + 1, periods[0] + 2]


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


def test_busy_teacher_period_and_session_never_scheduled():
    # GV bận (ban_busy) phải là hard-exclusion: không được xếp vào cả tiết lẻ
    # đã khai báo bận (tiết bận) lẫn nguyên 1 buổi đã khai báo bận (buổi bận).
    # Lưu ý: mỗi môn thường (không kép) chỉ được xếp tối đa 1 tiết/ngày/lớp
    # (core/scheduler.py _feasible, cap_d=1), nên nhu cầu Toán (1,1) phải để dư
    # so với 6 ngày trong tuần trừ đi ngày bị chặn nguyên buổi, nếu không lịch
    # sẽ vô nghiệm một cách hợp lệ (không phải do cơ chế bận sai).
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
        (1, 1): 4, (2, 1): 12, (3, 1): 3, (4, 1): 5, (5, 1): 6,
        (1, 2): 6, (2, 2): 12, (3, 2): 3, (4, 2): 3, (5, 2): 6,
    }
    assigned_teacher = {
        (1, 1): 1, (2, 1): 2, (3, 1): 3, (4, 1): 4, (5, 1): 5,
        (1, 2): 6, (2, 2): 7, (3, 2): 8, (4, 2): 9, (5, 2): 10,
    }
    timeslots = _make_timeslots(morning=5, afternoon=0)

    # GV1 (dạy Toán 6A) khai báo bận: 1 tiết lẻ (Thứ 3 Tiết 1) + trọn buổi Sáng Thứ 4
    busy_ts = [ts for ts in timeslots if (ts.weekday, ts.session, ts.period) == (3, "S", 1)]
    busy_ts += [ts for ts in timeslots if ts.weekday == 4 and ts.session == "S"]
    assert len(busy_ts) == 6  # 1 tiết lẻ + 5 tiết của trọn 1 buổi
    ban_busy = {(1, ts.ts_id) for ts in busy_ts}

    inp = _build_input(classes, subjects, teachers, need, assigned_teacher, timeslots,
                        seed=42, ban_busy=ban_busy, config=SchedulingConfig(avoid_gdtc_consecutive_days=False))
    result = sched.run(inp, max_attempts=6000, target_successes=5)
    assert result.success is True

    busy_ts_ids = {ts.ts_id for ts in busy_ts}
    for s in inp.slots:
        if s.ts.ts_id not in busy_ts_ids:
            continue
        subj_id = result.assignment.get(s.slot_id)
        if subj_id is None:
            continue
        teacher_id = assigned_teacher.get((subj_id, s.class_id))
        assert teacher_id != 1, (
            f"GV1 bị xếp vào tiết đã khai báo bận: lớp {s.class_id}, "
            f"Thứ {s.ts.weekday} {s.ts.session}{s.ts.period}"
        )


# ---------------------------------------------------------------------------
# End-to-end: build_scheduling_input() wires the school's saved SchedulingConfig
# ---------------------------------------------------------------------------

def test_build_scheduling_input_respects_saved_scheduling_config(tmp_path):
    # gdtc_avoid_period=4 (default is 5): chosen because it's empirically reliable
    # against this real fixture (verified success in 8/8 independent runs, well
    # under max_attempts). Periods 2 and 3 are genuinely infeasible for GDTC with
    # this school's real subject/teacher data (0/6000 across repeated runs) --
    # a data-driven constraint unrelated to the config-wiring behavior under test.
    conn = db.get_connection(str(tmp_path / "test.db"))
    db.init_db(conn)
    import_xlsm(conn, FIXTURE)
    repo.set_scheduling_config(conn, SchedulingConfig(gdtc_avoid_period=4))

    inp = repo.build_scheduling_input(conn, parity="C")
    assert inp.config.gdtc_avoid_period == 4

    result = sched.run(inp, max_attempts=6000, target_successes=3)
    assert result.success
    gdtc_id = next(s.subject_id for s in inp.subjects if s.role_code == ROLE_GDTC)
    for slot in inp.slots:
        if slot.ts.period == 4:
            assert result.assignment.get(slot.slot_id) != gdtc_id
    conn.close()


# ---------------------------------------------------------------------------
# _pick_best_scored soft-preference bias: heavy subjects toward early morning,
# preferred subjects toward afternoon (2026-08-29 spec)
# ---------------------------------------------------------------------------

def test_heavy_subject_priority_bonus_only_applies_within_configured_window():
    subjects = [Subject(1, "Toan", ROLE_NANG), Subject(2, "Nhac", ROLE_THUONG), Subject(3, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    config = SchedulingConfig(heavy_subject_priority_periods=2)
    assigned_teacher = {(1, 1): 100, (2, 1): 101}

    # Tiết 1 (trong ngưỡng 2 tiết đầu): môn nặng luôn thắng, bất kể seed --
    # bonus (30) > nhiễu rng tối đa (< 1) khi remaining_need bằng nhau.
    for seed in range(10):
        state = _State(remaining_need={(1, 1): 5, (2, 1): 5}, busy=set())
        slot = Slot(1, 1, TimeSlot(1, 2, "S", 1))
        pick = sched._pick_best_scored(1, slot, state, role_index, subjects, assigned_teacher,
                                        0.0, random.Random(seed), config=config)
        assert pick == (1, 100), f"seed={seed}: môn nặng phải thắng tiết 1 (trong ngưỡng ưu tiên 2 tiết đầu)"

    # Tiết 3 (ngoài ngưỡng): không còn bonus -> kết quả phải đổi tuỳ seed, không luôn là môn nặng.
    outcomes = set()
    for seed in range(10):
        state = _State(remaining_need={(1, 1): 5, (2, 1): 5}, busy=set())
        state.occupied[(1, 2, "S", 2)] = True  # BAT_LIEN_MACH trong _feasible: tiết 3 chỉ khả thi khi tiết 2 đã có
        slot = Slot(1, 1, TimeSlot(1, 2, "S", 3))
        pick = sched._pick_best_scored(1, slot, state, role_index, subjects, assigned_teacher,
                                        0.0, random.Random(seed), config=config)
        outcomes.add(pick)
    assert len(outcomes) == 2, "tiết 3 nằm ngoài ngưỡng ưu tiên -> không còn thiên vị, cả 2 môn đều có thể thắng"


def test_afternoon_preferred_subjects_soft_bias():
    subjects = [Subject(1, "Nhac", ROLE_THUONG), Subject(2, "Su", ROLE_THUONG), Subject(3, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    config = SchedulingConfig(afternoon_preferred_subject_ids=frozenset({1}))
    assigned_teacher = {(1, 1): 100, (2, 1): 101}

    # Buổi chiều: Nhạc (trong danh sách ưu tiên) luôn thắng Sử (không trong danh sách).
    for seed in range(10):
        state = _State(remaining_need={(1, 1): 5, (2, 1): 5}, busy=set())
        slot = Slot(1, 1, TimeSlot(1, 2, "C", 1))
        pick = sched._pick_best_scored(1, slot, state, role_index, subjects, assigned_teacher,
                                        0.0, random.Random(seed), config=config)
        assert pick == (1, 100), f"seed={seed}: Nhạc (afternoon_preferred_subject_ids) phải thắng Sử buổi chiều"

    # Buổi sáng: danh sách ưu tiên buổi chiều không áp dụng -> kết quả phải đổi tuỳ seed.
    outcomes = set()
    for seed in range(10):
        state = _State(remaining_need={(1, 1): 5, (2, 1): 5}, busy=set())
        slot = Slot(1, 1, TimeSlot(1, 2, "S", 1))
        pick = sched._pick_best_scored(1, slot, state, role_index, subjects, assigned_teacher,
                                        0.0, random.Random(seed), config=config)
        outcomes.add(pick)
    assert len(outcomes) == 2, "buổi sáng không áp dụng luật ưu tiên buổi chiều -> không còn thiên vị"


def test_pick_best_scored_never_returns_none_for_a_feasible_candidate_under_heavy_penalty_stacking():
    # Regression: best_score sentinel must not silently reject a feasible candidate
    # once soft-rule penalties push its score below the old -1.0 floor.
    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(2, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    config = SchedulingConfig(afternoon_preferred_subject_ids=frozenset({99}))  # 99 doesn't exist -> subject 1 is never "preferred"
    state = _State(remaining_need={(1, 1): 1}, busy=set())
    # Force both ±50 "dàn-môn" (spread) penalties to apply: subject 1 already placed
    # on both the day before and the day after weekday 4.
    state.placed[(1, 1, 3)].append(("C", 1))
    state.placed[(1, 1, 5)].append(("C", 1))
    # Deny the IDLE_DAY_BONUS: this teacher already has a session that day.
    state.session_count[(100, 4, "S")] = 1
    assigned_teacher = {(1, 1): 100}
    slot = Slot(1, 1, TimeSlot(1, 4, "C", 1))

    pick = sched._pick_best_scored(1, slot, state, role_index, subjects, assigned_teacher,
                                    0.0, random.Random(1), config=config)
    assert pick == (1, 100), "a feasible candidate must never be rejected just because its score is very low"


def test_pick_best_scored_unbiased_with_default_config():
    # Regression: config=None (mặc định) -> không thiên vị gì, kể cả tiết 1 buổi sáng.
    subjects = [Subject(1, "Toan", ROLE_NANG), Subject(2, "Nhac", ROLE_THUONG), Subject(3, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    assigned_teacher = {(1, 1): 100, (2, 1): 101}

    outcomes = set()
    for seed in range(10):
        state = _State(remaining_need={(1, 1): 5, (2, 1): 5}, busy=set())
        slot = Slot(1, 1, TimeSlot(1, 2, "S", 1))
        pick = sched._pick_best_scored(1, slot, state, role_index, subjects, assigned_teacher,
                                        0.0, random.Random(seed))
        outcomes.add(pick)
    assert len(outcomes) == 2


def test_full_run_succeeds_with_both_soft_subject_preferences_enabled():
    # Smoke test: sched.run() end-to-end with heavy_subject_priority_periods AND
    # afternoon_preferred_subject_ids both set together must not break a full run --
    # they're soft/best-effort only (Finding 1's fix is what guarantees this).
    classes = [ClassRoom(1, "6A")]
    subjects = [
        Subject(1, "Toan", ROLE_NANG),      # môn "Nặng" -- ưu tiên (mềm) buổi sáng sớm
        Subject(2, "Van", ROLE_KEP),        # môn thường (kép) -- ưu tiên (mềm) buổi chiều
        Subject(3, "HDTN", ROLE_HDTN),
    ]
    teachers = [Teacher(1, "GVToan"), Teacher(2, "GVVan"), Teacher(3, "GVCN", is_gvcn=True)]
    need = {(1, 1): 2, (2, 1): 4, (3, 1): 2}
    assigned_teacher = {(1, 1): 1, (2, 1): 2, (3, 1): 3}
    timeslots = _make_timeslots(morning=2, afternoon=2, weekdays=(2, 6))
    inp = _build_input(classes, subjects, teachers, need, assigned_teacher, timeslots, seed=1)
    inp.config = SchedulingConfig(
        heavy_subject_priority_periods=2,
        afternoon_preferred_subject_ids=frozenset({2}),
    )

    result = sched.run(inp, max_attempts=6000, target_successes=3)
    assert result.success is True


def test_full_run_succeeds_with_teacher_pinned_and_override_off_days():
    # Smoke test: sched.run() end-to-end with a teacher's off_sessions_override/
    # pinned_full_day_off set (Task 3's per-teacher off-day customization, spec
    # 2026-08-29-gv-nghi-rieng) must not break a full run. Small synthetic input
    # with a bit of slack (8 slots, need=6) so the constraint solver has room;
    # GV1 (Toan) is pinned off all of Thứ 4 via off_sessions_override=2 +
    # pinned_full_day_off=4.
    classes = [ClassRoom(1, "6A")]
    subjects = [
        Subject(1, "Toan", ROLE_THUONG, 1),
        Subject(2, "Van", ROLE_KEP, 2),
        Subject(3, "HDTN", ROLE_HDTN, 3),
    ]
    teachers = [
        Teacher(1, "GV1", off_sessions_override=2, pinned_full_day_off=4),
        Teacher(2, "GV2"),
        Teacher(3, "GV3"),
    ]
    need = {(1, 1): 2, (2, 1): 2, (3, 1): 2}
    assigned_teacher = {(1, 1): 1, (2, 1): 2, (3, 1): 3}
    timeslots = _make_timeslots(morning=2, afternoon=0, weekdays=(2, 3, 4, 5))
    inp = _build_input(classes, subjects, teachers, need, assigned_teacher, timeslots, seed=42)

    result = sched.run(inp, max_attempts=6000, target_successes=5)
    assert result.success is True


# ---------------------------------------------------------------------------
# End-to-end regression: the subject/class allowed-cells hard constraint must hold
# on EVERY write, across every placement path threaded through the scheduler
# (greedy fill, swap-repair, lone-period repair, ...), not just at _feasible().
# ---------------------------------------------------------------------------

def test_subject_class_allowed_cells_holds_across_every_placement_in_a_real_run():
    conn = db.get_connection(":memory:")
    db.init_db(conn)
    import_xlsm(conn, FIXTURE)

    # Khoa học tự nhiên (Sinh học) / lớp 7A4 (subject_id=6, class_id=3, role_code
    # ROLE_THUONG): định mức tuần Chẵn thật trong dữ liệu mẫu là đúng 2 tiết -- ràng
    # buộc còn đúng 2 ô cho phép (Thứ 3, Thứ 4 buổi chiều), cả 2 đều là buổi chiều
    # đang hoạt động của lớp 7A4 (không rơi vào buổi chiều Thứ 5/Thứ 6 bị giữ trống
    # toàn trường), nên bài toán vẫn giải được đủ 2 tiết.
    subject_id = 6
    class_id = 3
    repo.upsert_subject_class_rule(conn, subject_id, [class_id], {(2, "C"), (3, "C")})
    inp = repo.build_scheduling_input(conn, parity="C")
    assert inp.need[(subject_id, class_id)] == 2

    original_put_at = sched._put_at
    violations = []

    def wrapped_put_at(state, slot, subj_id, teacher_id, role_index):
        key = (subj_id, slot.class_id)
        allowed = inp.subject_class_allowed_cells.get(key)
        if allowed is not None and (slot.ts.weekday, slot.ts.session) not in allowed:
            violations.append((key, slot.ts.weekday, slot.ts.session))
        return original_put_at(state, slot, subj_id, teacher_id, role_index)

    sched._put_at = wrapped_put_at
    try:
        result = sched.run(inp, max_attempts=6000, target_successes=3)
    finally:
        sched._put_at = original_put_at

    assert result.success is True
    assert violations == []
    conn.close()
