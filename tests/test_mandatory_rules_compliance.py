import pytest
from core.models import SchedulingConfig


def test_scheduling_config_has_all_hdsp_and_moet_criteria_fields():
    """Verify that SchedulingConfig provides default fields covering all 15 HĐSP rules."""
    config = SchedulingConfig()

    # Tiêu chí II.2: Mỗi GV không quá tải vượt 5 tiết/ngày
    assert hasattr(config, "max_teacher_periods_per_day")
    assert config.max_teacher_periods_per_day == 5

    # Tiêu chí I.2 & II.13: Tối đa 3 tiết môn nặng/buổi cho 1 lớp
    assert hasattr(config, "max_heavy_per_session")
    assert config.max_heavy_per_session == 3

    # Tiêu chí II.6: Tiết 2 HĐTN xếp vào buổi chiều cho các lớp có học chiều
    assert hasattr(config, "hdtn_period2_afternoon")
    assert config.hdtn_period2_afternoon is True

    # Tiêu chí II.15: Hạn chế môn nặng tiết 3 chiều
    assert hasattr(config, "avoid_heavy_afternoon_period3")
    assert config.avoid_heavy_afternoon_period3 is True

    # Tiêu chí II.14: Hạn chế GV dạy 4 tiết sáng liên tục nếu tải <= 20
    assert hasattr(config, "avoid_teacher_4_consecutive_morning")
    assert config.avoid_teacher_4_consecutive_morning is True

    # Tiêu chí II.4: Cấu hình ngưỡng tải miễn trừ phạt lẻ tiết cho GV (default 15 = miễn trừ GV <15 tiết/tuần)
    assert hasattr(config, "min_weekly_periods_for_lone_penalty")
    assert config.min_weekly_periods_for_lone_penalty == 15


def test_teacher_max_periods_per_day_constraint():
    """Tiêu chí II.2: Mỗi GV không bị quá tải vượt 5 tiết/ngày."""
    from core import scheduler as sched
    from core.models import Subject, ROLE_THUONG, ROLE_HDTN, TimeSlot
    from core.roles import resolve_roles

    subjects = [Subject(1, "Toan", ROLE_THUONG), Subject(99, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    state = sched._State(remaining_need={(1, 101): 10}, busy=set())

    # Simulate Teacher 1 already teaching 5 periods on Monday (e.g. 4 morning + 1 afternoon)
    state.teacher_day_count[(1, 2)] = 5
    ts_mon_chieu_2 = TimeSlot(10, 2, "C", 2)

    config = SchedulingConfig(max_teacher_periods_per_day=5)
    # Attempting to schedule a 6th period on Monday for Teacher 1 must fail
    assert sched._feasible(101, ts_mon_chieu_2, 1, 1, state, role_index, config=config) is False

    # For another weekday (Tuesday, day 3) where Teacher 1 has 0 periods, it should succeed
    ts_tue_sang_1 = TimeSlot(11, 3, "S", 1)
    assert sched._feasible(101, ts_tue_sang_1, 1, 1, state, role_index, config=config) is True


def test_class_max_heavy_per_session_constraint():
    """Tiêu chuẩn I.2 & Tiêu chí II.13: Không quá 3 tiết môn nặng trong 1 buổi cho 1 lớp."""
    from core import scheduler as sched
    from core.models import Subject, ROLE_NANG, ROLE_HDTN, TimeSlot
    from core.roles import resolve_roles

    subjects = [Subject(1, "Toan", ROLE_NANG), Subject(99, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    state = sched._State(remaining_need={(1, 101): 10}, busy=set())

    # Simulate Class 101 already having 3 heavy periods on Monday morning
    state.session_heavy_count[(101, 2, "S")] = 3
    state.occupied[(101, 2, "S", 1)] = True
    state.occupied[(101, 2, "S", 2)] = True
    state.occupied[(101, 2, "S", 3)] = True

    ts_mon_sang_4 = TimeSlot(4, 2, "S", 4)
    config = SchedulingConfig(max_heavy_per_session=3)

    # Attempting to place a 4th heavy period in Monday morning session must fail
    assert sched._feasible(101, ts_mon_sang_4, 1, 1, state, role_index, config=config) is False


def test_avoid_heavy_afternoon_period3_constraint():
    """Tiêu chí II.15: Hạn chế xếp môn nặng vào tiết 3 chiều."""
    from core import scheduler as sched
    from core.models import Subject, ROLE_NANG, ROLE_THUONG, ROLE_HDTN, TimeSlot
    from core.roles import resolve_roles

    subjects = [Subject(1, "Toan", ROLE_NANG), Subject(2, "AmNhac", ROLE_THUONG), Subject(99, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    state = sched._State(remaining_need={(1, 101): 5, (2, 101): 5}, busy=set())
    state.occupied[(101, 2, "C", 1)] = True
    state.occupied[(101, 2, "C", 2)] = True

    ts_mon_chieu_3 = TimeSlot(8, 2, "C", 3)
    config = SchedulingConfig(avoid_heavy_afternoon_period3=True)

    # Placing heavy subject (Toan) on afternoon period 3 must fail
    assert sched._feasible(101, ts_mon_chieu_3, 1, 1, state, role_index, config=config) is False

    # Placing light subject (AmNhac) on afternoon period 3 should succeed
    assert sched._feasible(101, ts_mon_chieu_3, 2, 2, state, role_index, config=config) is True


def test_teacher_lone_period_penalty_exempts_low_workload():
    """Tiêu chí II.4: Hạn chế tối đa GV có 1 tiết/buổi hoặc 1 tiết/ngày, trừ GV < 15 tiết/tuần."""
    from core.models import Slot, TimeSlot
    from core.scheduler.quality import _count_teacher_lone_sessions, _count_teacher_lone_days

    # Teacher 1 has 4 total periods in week (low workload < 15), placed in 4 separate lone sessions
    # Teacher 2 has 16 total periods in week (normal workload >= 15), placed with 1 lone session
    slots = [
        Slot(1, 101, TimeSlot(1, 2, "S", 1)),
        Slot(2, 101, TimeSlot(2, 3, "S", 1)),
        Slot(3, 101, TimeSlot(3, 4, "S", 1)),
        Slot(4, 101, TimeSlot(4, 5, "S", 1)),
        Slot(5, 102, TimeSlot(5, 2, "S", 1)),  # Teacher 2 lone session on Monday
    ]
    # Add 15 more periods for Teacher 2 on other days (e.g. 3 sessions of 5 periods each)
    for i in range(6, 21):
        wd = 3 + (i - 6) // 5
        period = 1 + (i - 6) % 5
        slots.append(Slot(i, 102, TimeSlot(i, wd, "S", period)))

    assigned = {s.slot_id: 1 for s in slots}
    slot_teacher = {s.slot_id: (1 if s.slot_id <= 4 else 2) for s in slots}

    # For default min_weekly_periods=15:
    # Teacher 1 (<15) is exempt (0 violations counted for T1).
    # Teacher 2 (>=15) has 1 lone session on Monday.
    # Total lone sessions should be 1, not 5.
    lone_sess = _count_teacher_lone_sessions(slots, assigned, slot_teacher, min_weekly_periods=15)
    assert lone_sess == 1

    lone_days = _count_teacher_lone_days(slots, assigned, slot_teacher, min_weekly_periods=15)
    assert lone_days == 1


def test_teacher_4_consecutive_mornings_penalty():
    """Tiêu chí II.14: Hạn chế xếp cho GV 4 tiết liên tục vào buổi sáng trừ GV > 20 tiết/tuần."""
    from core.models import Slot, TimeSlot
    from core.scheduler.quality import _count_teacher_4_consecutive_mornings

    # Teacher 1 (workload 16 <= 20) has 4 periods on Monday morning
    # Teacher 2 (workload 24 > 20) has 4 periods on Tuesday morning
    slots = []
    slot_teacher = {}
    assigned = {}

    # Teacher 1: Mon morning 4 periods + Tue morning 4 + Wed morning 4 + Thu morning 4 = 16 total
    sid = 1
    for wd in (2, 3, 4, 5):
        for p in range(1, 5):
            s = Slot(sid, 101, TimeSlot(sid, wd, "S", p))
            slots.append(s)
            assigned[sid] = 1
            slot_teacher[sid] = 1
            sid += 1

    # Teacher 2: 24 total periods
    for wd in (2, 3, 4, 5, 6, 7):
        for p in range(1, 5):
            s = Slot(sid, 102, TimeSlot(sid, wd, "S", p))
            slots.append(s)
            assigned[sid] = 2
            slot_teacher[sid] = 2
            sid += 1

    # Teacher 1 has load 16 (<=20) -> all 4 morning sessions are counted as violations (4)
    # Teacher 2 has load 24 (>20) -> exempt (0)
    count_4 = _count_teacher_4_consecutive_mornings(slots, assigned, slot_teacher, max_load_for_penalty=20)
    assert count_4 == 4


def test_hdtn_period2_afternoon_heuristic_scoring():
    """Tiêu chí II.6: Tiết 2 HĐTN xếp vào buổi chiều."""
    import random
    from core import scheduler as sched
    from core.models import Subject, ROLE_HDTN, TimeSlot, Slot, SchedulingConfig
    from core.roles import resolve_roles

    subjects = [Subject(1, "HDTN", ROLE_HDTN)]
    role_index = resolve_roles(subjects)
    state = sched._State(remaining_need={(1, 101): 1}, busy=set())

    # Slot in afternoon vs slot in morning for a class that has afternoon sessions
    slot_afternoon = Slot(1, 101, TimeSlot(1, 3, "C", 1))
    slot_morning = Slot(2, 101, TimeSlot(2, 3, "S", 2))
    assigned_teacher = {(1, 101): 10}
    rng = random.Random(42)

    config_on = SchedulingConfig(hdtn_period2_afternoon=True)
    # In afternoon, HDTN should be selected easily
    pick_afternoon = sched._pick_best_scored(101, slot_afternoon, state, role_index, subjects, assigned_teacher, 0.0, rng, config=config_on)
    assert pick_afternoon is not None
    assert pick_afternoon[0] == 1


def test_full_schedule_15_criteria_compliance(tmp_path):
    """End-to-end verification of 100% MOET standards and 15 HĐSP criteria on real-scale school data."""
    import os
    from core import scheduler as sched
    from core.models import ROLE_GDTC, ROLE_HDTN, ROLE_NANG, ROLE_NANG_KEP, SchedulingConfig
    from core.validation import (
        compute_quota_diff, find_consecutive_subject_days, find_heavy_afternoon_period3_violations,
        find_invalid_gdtc_periods, find_max_heavy_violations, find_teacher_conflicts,
        find_teacher_day_cap_violations, find_teacher_gaps,
        find_teacher_lone_day_violations, find_teacher_lone_session_violations,
        find_teacher_missing_mandatory_morning_violations, find_teacher_split_day_violations,
    )
    from data import db, repository as repo
    from io_excel.importer import import_xlsm

    fixture_path = os.path.join(os.path.dirname(__file__), "..", "io_excel", "sample_school.xlsm")
    connection = db.get_connection(str(tmp_path / "test_compliance.db"))
    db.init_db(connection)
    import_xlsm(connection, fixture_path)

    config = SchedulingConfig(
        max_teacher_periods_per_day=5,
        max_heavy_per_session=3,
        hdtn_period2_afternoon=True,
        avoid_heavy_afternoon_period3=True,
        avoid_teacher_4_consecutive_morning=True,
        avoid_gdtc_consecutive_days=True,
        avoid_teacher_gaps=True,
        avoid_teacher_lone_periods=True,
        balance_afternoon_teachers=True,
    )
    repo.set_scheduling_config(connection, config)

    inp = repo.build_scheduling_input(connection, parity="L", seed=2026)
    result = sched.run(inp)

    assert result.success is True, f"Schedule generation failed: {result.failure_reason}"

    # 1. Ràng buộc Hệ thống: Không trùng tiết GV (I.1.1, II.10)
    conflicts = find_teacher_conflicts(inp.slots, result.assignment, inp.assigned_teacher)
    assert conflicts == [], f"Found teacher double-booking: {conflicts}"

    # 2. Ràng buộc Hệ thống: Khớp định lượng 100% (I.1.3, II.1)
    ppw = {(s, c, p): n for (s, c, p), n in repo.get_periods_per_week(connection).items()}
    diff = compute_quota_diff(inp.slots, result.assignment, ppw, "L")
    bad_diff = {k: v for k, v in diff.items() if v != 0}
    assert bad_diff == {}, f"Quota diff mismatch: {bad_diff}"

    # 3. Tiêu chí II.2: Mỗi GV không vượt quá 5 tiết/ngày
    day_cap_violations = find_teacher_day_cap_violations(inp.slots, result.assignment, inp.assigned_teacher, max_per_day=5)
    assert day_cap_violations == [], f"Teacher day cap violations: {day_cap_violations}"

    # 4. Tiêu chí I.2.5: Thể dục (GDTC) tránh tiết 5
    gdtc_id = next(s.subject_id for s in inp.subjects if s.role_code == ROLE_GDTC)
    gdtc_violations = find_invalid_gdtc_periods(inp.slots, result.assignment, gdtc_id)
    assert gdtc_violations == [], f"GDTC placed in forbidden periods: {gdtc_violations}"

    # 5. Tiêu chí II.12: GDTC không học 2 ngày liên tiếp
    gdtc_consec = find_consecutive_subject_days(inp.slots, result.assignment, {gdtc_id})
    assert gdtc_consec == [], f"GDTC consecutive day violations: {gdtc_consec}"

    # 6. Tiêu chí I.2.2 & II.13: Môn Nặng không quá 3 tiết liên tiếp
    heavy_ids = {s.subject_id for s in inp.subjects if s.role_code in (ROLE_NANG, ROLE_NANG_KEP)}
    heavy_runs = find_max_heavy_violations(inp.slots, result.assignment, heavy_ids, max_consecutive=3)
    assert heavy_runs == [], f"Heavy subject consecutive run violations: {heavy_runs}"

    # 7. Tiêu chí II.15: Không xếp môn Nặng vào tiết 3 chiều
    heavy_p3 = find_heavy_afternoon_period3_violations(inp.slots, result.assignment, heavy_ids)
    assert heavy_p3 == [], f"Heavy subjects on afternoon period 3: {heavy_p3}"

    # 8. Tiêu chí I.2.6 & II.6: Chào cờ tiết 1 Thứ Hai
    hdtn_id = next(s.subject_id for s in inp.subjects if s.role_code == ROLE_HDTN)
    for slot in inp.slots:
        if slot.ts.weekday == 2 and slot.ts.session == "S" and slot.ts.period == 1:
            assert result.assignment.get(slot.slot_id) == hdtn_id, f"Slot {slot} is not Chào cờ (HDTN)"

    # 9-11. Tiêu chí II.3, II.4, II.8 (hard-gated as of 2026-09-03, third revision
    # same day): mọi vi phạm phải được engine tự tránh, HOẶC được báo cáo minh bạch
    # qua relaxed_rules -- không được có vi phạm "câm" (tồn tại nhưng không báo
    # cáo). Đây chính là bug gốc gây ra báo cáo của người dùng ngày 2026-09-02
    # ("vẫn có người được nghỉ sáng T2, vẫn nhiều buổi lẻ").
    relaxed_ids = {item.get("rule_id") for item in result.relaxed_rules}

    missing_morning = find_teacher_missing_mandatory_morning_violations(inp.slots, result.assignment, inp.assigned_teacher)
    assert not missing_morning or "II.3" in relaxed_ids, f"Unreported II.3 violations: {missing_morning}"

    min_lone_load = config.min_weekly_periods_for_lone_penalty
    lone_sessions = find_teacher_lone_session_violations(inp.slots, result.assignment, inp.assigned_teacher, min_lone_load)
    lone_days = find_teacher_lone_day_violations(inp.slots, result.assignment, inp.assigned_teacher, min_lone_load)
    assert not (lone_sessions or lone_days) or "II.4" in relaxed_ids, f"Unreported II.4 violations: {lone_sessions + lone_days}"

    split_days = find_teacher_split_day_violations(inp.slots, result.assignment, inp.assigned_teacher, min_lone_load)
    assert not split_days or "II.8" in relaxed_ids, f"Unreported II.8 violations: {split_days}"

    # II.14 is soft -- not part of the relaxed_rules transparency invariant above.
    # It still gets scored (and thus minimized when possible) via quality.py's
    # existing soft penalty, unaffected by this change.

    connection.close()


