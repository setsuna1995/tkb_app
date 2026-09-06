"""Port of the KiemTra sheet's checks: per (subject,class) quota diff (expect
0), and teacher double-booking detection (mirrors TKB_GV's hidden COUNTIFS
helper columns).
"""
from __future__ import annotations

from collections import defaultdict
from typing import Optional

from core.models import (
    ROLE_GDTC, ROLE_HDTN, ROLE_NANG, ROLE_NANG_KEP, WEEKDAY_NAMES, SchedulingInput, is_bgh,
)
from core.scheduler.placement import _build_effective_assigned_teacher
from core.scheduler.quality import (
    _count_subject_consecutive_days,
    _count_teacher_back_to_back_shifts,
    _count_teacher_excess_gaps,
)


def compute_actual_counts(slots: list, assignment: dict) -> dict:
    counts = defaultdict(int)
    for slot in slots:
        subject_id = assignment.get(slot.slot_id)
        if subject_id is not None:
            counts[(subject_id, slot.class_id)] += 1
    return counts


def compute_quota_diff(slots: list, assignment: dict, periods_per_week: dict, parity: Optional[str] = None) -> dict:
    """Returns (subject_id, class_id) -> actual - quota. Expect all zeros.
    Supports either:
    - 2-tuple dict: (subject_id, class_id) -> periods
    - 3-tuple dict: (subject_id, class_id, parity) -> periods (requires parity or defaults to 'C')
    """
    actual = compute_actual_counts(slots, assignment)
    sample_key = next(iter(periods_per_week.keys()), None)
    if sample_key and len(sample_key) == 2:
        keys = set(actual.keys()) | set(periods_per_week.keys())
        diff = {}
        for key in keys:
            quota = periods_per_week.get(key, 0)
            diff[key] = actual.get(key, 0) - quota
        return diff
    else:
        effective_parity = parity or "C"
        keys = set(actual.keys()) | {(s_id, c_id) for (s_id, c_id, p) in periods_per_week if p == effective_parity}
        diff = {}
        for key in keys:
            quota = periods_per_week.get((key[0], key[1], effective_parity), 0)
            diff[key] = actual.get(key, 0) - quota
        return diff


def find_teacher_conflicts(slots: list, assignment: dict, assigned_teacher: dict) -> list:
    """Returns [(teacher_id, weekday, session, period, [class_id, ...]), ...] for any
    teacher booked into more than one class at the same timeslot. Synthetic
    (unassigned-PhanCong) placeholder teacher ids are negative and always skipped.
    """
    by_slot_teacher = defaultdict(list)
    for slot in slots:
        subject_id = assignment.get(slot.slot_id)
        if subject_id is None:
            continue
        teacher_id = assigned_teacher.get((subject_id, slot.class_id))
        if teacher_id is None or teacher_id < 0:
            continue
        key = (teacher_id, slot.ts.weekday, slot.ts.session, slot.ts.period)
        by_slot_teacher[key].append(slot.class_id)
    return [key + (classes,) for key, classes in by_slot_teacher.items() if len(classes) > 1]


def find_teacher_gaps(slots: list, assignment: dict, assigned_teacher: dict) -> list:
    """Returns [(teacher_id, weekday, session, [period, ...]), ...] for any teacher
    who has idle gaps between teaching periods in the same session."""
    teacher_sessions = defaultdict(list)
    for slot in slots:
        subject_id = assignment.get(slot.slot_id)
        if subject_id is None:
            continue
        teacher_id = assigned_teacher.get((subject_id, slot.class_id))
        if teacher_id is None or teacher_id < 0:
            continue
        teacher_sessions[(teacher_id, slot.ts.weekday, slot.ts.session)].append(slot.ts.period)

    gaps = []
    for (tid, wd, sess), periods in teacher_sessions.items():
        if len(periods) >= 2:
            span = max(periods) - min(periods) + 1
            if span > len(periods):
                gaps.append((tid, wd, sess, sorted(periods)))
    return gaps


def find_consecutive_subject_days(slots: list, assignment: dict, target_subject_ids: set) -> list:
    """Returns [(class_id, subject_id, weekday1, weekday2), ...] for any class having
    a target subject (e.g. GDTC) scheduled on consecutive weekdays."""
    class_subject_days = defaultdict(set)
    for slot in slots:
        subject_id = assignment.get(slot.slot_id)
        if subject_id in target_subject_ids:
            class_subject_days[(slot.class_id, subject_id)].add(slot.ts.weekday)

    violations = []
    for (class_id, subject_id), days in class_subject_days.items():
        sorted_days = sorted(days)
        for i in range(len(sorted_days) - 1):
            if sorted_days[i + 1] == sorted_days[i] + 1:
                violations.append((class_id, subject_id, sorted_days[i], sorted_days[i + 1]))
    return violations


def find_teacher_unavailability_violations(slots: list, assignment: dict, assigned_teacher: dict, ban_busy: set) -> list:
    """Returns [(teacher_id, class_id, weekday, session, period), ...] for any slot where
    a teacher is scheduled in a banned/busy timeslot."""
    violations = []
    for slot in slots:
        subject_id = assignment.get(slot.slot_id)
        if subject_id is None:
            continue
        teacher_id = assigned_teacher.get((subject_id, slot.class_id))
        if teacher_id is None or teacher_id < 0:
            continue
        if (teacher_id, slot.ts.ts_id) in ban_busy:
            violations.append((teacher_id, slot.class_id, slot.ts.weekday, slot.ts.session, slot.ts.period))
    return violations


def find_invalid_gdtc_periods(slots: list, assignment: dict, gdtc_id: int,
                              morning_allowed: tuple = (1, 2, 3, 4),
                              afternoon_allowed: tuple = (2, 3)) -> list:
    """Returns [(class_id, weekday, session, period), ...] for any GDTC slot placed
    outside allowed morning or afternoon periods."""
    violations = []
    for slot in slots:
        subject_id = assignment.get(slot.slot_id)
        if subject_id == gdtc_id:
            if slot.ts.session == "S" and morning_allowed and slot.ts.period not in morning_allowed:
                violations.append((slot.class_id, slot.ts.weekday, slot.ts.session, slot.ts.period))
            elif slot.ts.session == "C" and afternoon_allowed and slot.ts.period not in afternoon_allowed:
                violations.append((slot.class_id, slot.ts.weekday, slot.ts.session, slot.ts.period))
    return violations


def find_morning_only_violations(slots: list, assignment: dict, morning_only_ids: set) -> list:
    """Returns [(class_id, subject_id, weekday, session, period), ...] for any morning-only
    subject placed in the afternoon."""
    violations = []
    for slot in slots:
        subject_id = assignment.get(slot.slot_id)
        if subject_id is not None and subject_id in morning_only_ids and slot.ts.session == "C":
            violations.append((slot.class_id, subject_id, slot.ts.weekday, slot.ts.session, slot.ts.period))
    return violations


def find_max_heavy_violations(slots: list, assignment: dict, heavy_ids: set, max_consecutive: int = 3) -> list:
    """Returns [(class_id, weekday, session, start_period, length), ...] for any continuous run of
    heavy subjects in a session exceeding max_consecutive."""
    # Group heavy periods by (class_id, weekday, session)
    class_session_heavy = defaultdict(set)
    for slot in slots:
        subject_id = assignment.get(slot.slot_id)
        if subject_id is not None and subject_id in heavy_ids:
            class_session_heavy[(slot.class_id, slot.ts.weekday, slot.ts.session)].add(slot.ts.period)

    violations = []
    for (class_id, weekday, session), periods in class_session_heavy.items():
        sorted_p = sorted(periods)
        current_run = []
        for p in sorted_p:
            if not current_run or p == current_run[-1] + 1:
                current_run.append(p)
            else:
                if len(current_run) > max_consecutive:
                    violations.append((class_id, weekday, session, current_run[0], len(current_run)))
                current_run = [p]
        if len(current_run) > max_consecutive:
            violations.append((class_id, weekday, session, current_run[0], len(current_run)))
    return violations


def find_subject_class_rule_violations(slots: list, assignment: dict, subject_class_rules: list) -> list:
    """Returns [(class_id, subject_id, weekday, session, period), ...] for any placement
    violating subject_class_rules (allowed (weekday, session) cells)."""
    violations = []
    # Build lookup: (subject_id, class_id) -> set of allowed (weekday, session)
    allowed_map = {}
    for rule in subject_class_rules:
        sid = rule["subject_id"]
        for cid in rule.get("class_ids", []):
            allowed_map[(sid, cid)] = set(rule.get("cells", []))

    for slot in slots:
        subject_id = assignment.get(slot.slot_id)
        if subject_id is not None:
            allowed = allowed_map.get((subject_id, slot.class_id))
            if allowed is not None and (slot.ts.weekday, slot.ts.session) not in allowed:
                violations.append((slot.class_id, subject_id, slot.ts.weekday, slot.ts.session, slot.ts.period))
    return violations


def find_single_pair_violations(slots: list, assignment: dict, single_pair_ids: set) -> list:
    """Returns [(class_id, subject_id, [pair_days], [excess_days]), ...] for any single-pair
    subject that has more than 1 pair in a week or daily count > 2."""
    class_subj_day_count = defaultdict(lambda: defaultdict(int))
    for slot in slots:
        subject_id = assignment.get(slot.slot_id)
        if subject_id is not None and subject_id in single_pair_ids:
            class_subj_day_count[(slot.class_id, subject_id)][slot.ts.weekday] += 1

    violations = []
    for (class_id, subject_id), day_counts in class_subj_day_count.items():
        pair_days = [wd for wd, c in day_counts.items() if c >= 2]
        invalid_days = [wd for wd, c in day_counts.items() if c > 2]
        if len(pair_days) > 1 or invalid_days:
            violations.append((class_id, subject_id, pair_days, invalid_days))
    return violations


def find_teacher_day_cap_violations(slots: list, assignment: dict, assigned_teacher: dict, max_per_day: int = 5) -> list:
    """Returns [(teacher_id, weekday, total_periods), ...] for any teacher whose total periods
    taught across both morning and afternoon on a single day exceeds max_per_day."""
    teacher_day_periods = defaultdict(int)
    for slot in slots:
        subject_id = assignment.get(slot.slot_id)
        if subject_id is not None:
            teacher_id = assigned_teacher.get((subject_id, slot.class_id))
            if teacher_id is not None and teacher_id > 0:
                teacher_day_periods[(teacher_id, slot.ts.weekday)] += 1

    violations = []
    for (tid, wd), count in teacher_day_periods.items():
        if count > max_per_day:
            violations.append((tid, wd, count))
    return violations


def find_heavy_afternoon_period3_violations(slots: list, assignment: dict, heavy_ids: set) -> list:
    """Returns [(class_id, subject_id, weekday, session, period), ...] for any heavy subject
    placed at afternoon period 3."""
    violations = []
    for slot in slots:
        subject_id = assignment.get(slot.slot_id)
        if subject_id is not None and subject_id in heavy_ids:
            if slot.ts.session == "C" and slot.ts.period == 3:
                violations.append((slot.class_id, subject_id, slot.ts.weekday, slot.ts.session, slot.ts.period))
    return violations


def _is_teacher_busy_on_morning(teacher_id: int, wd: int, slots: list, assigned_teacher: dict, ban_busy: set) -> bool:
    if not ban_busy:
        return False
    morn_slots = [s for s in slots if s.ts.weekday == wd and s.ts.session == "S"]
    if not morn_slots:
        return False
    classes_for_teacher = {c_id for (subj_id, c_id), t_id in assigned_teacher.items() if t_id == teacher_id}
    candidate_slots = [s for s in morn_slots if s.class_id in classes_for_teacher]
    if not candidate_slots:
        return any((teacher_id, s.ts.ts_id) in ban_busy for s in morn_slots)
    has_busy = any((teacher_id, s.ts.ts_id) in ban_busy for s in candidate_slots)
    all_busy = all((teacher_id, s.ts.ts_id) in ban_busy for s in candidate_slots)
    return has_busy and all_busy


def find_teacher_missing_mandatory_morning_violations(slots: list, assignment: dict, assigned_teacher: dict,
                                                        mandatory_mornings: tuple = (2, 5, 6),
                                                        min_weekly_periods: int = 10,
                                                        strict_weekdays: tuple = (),
                                                        exempt_teacher_ids: frozenset = frozenset(),
                                                        ban_busy: set = None) -> list:
    """Returns [(teacher_id, weekday), ...] for teachers at/above min_weekly_periods
    who end up with zero periods on a mandatory morning -- Tiêu chí II.3: catches an
    accidental empty forbidden morning beyond the teacher's one designated off-slot.
    Mirrors core.scheduler.quality._count_teacher_missing_mandatory_mornings exactly,
    so this check and the engine's post-generation gate (core/scheduler/engine.py)
    never disagree -- INCLUDING the threshold, which callers must pass through from
    config.min_weekly_periods_for_mandatory_morning (2026-09-04).
    ban_busy: tập các ô GV đã tích bận (2026-09-06); GV đã tích bận toàn bộ sáng được miễn trừ."""
    teacher_morns = defaultdict(lambda: defaultdict(int))
    teacher_totals = defaultdict(int)
    for slot in slots:
        subject_id = assignment.get(slot.slot_id)
        if subject_id is None:
            continue
        teacher_id = assigned_teacher.get((subject_id, slot.class_id))
        if teacher_id is None or teacher_id <= 0:
            continue
        teacher_totals[teacher_id] += 1
        if slot.ts.session == "S" and (slot.ts.weekday in mandatory_mornings
                                        or slot.ts.weekday in strict_weekdays):
            teacher_morns[teacher_id][slot.ts.weekday] += 1

    violations = []
    for teacher_id, total in teacher_totals.items():
        if teacher_id not in exempt_teacher_ids:
            for wd in strict_weekdays:
                if teacher_morns[teacher_id][wd] == 0:
                    if ban_busy and _is_teacher_busy_on_morning(teacher_id, wd, slots, assigned_teacher, ban_busy):
                        continue
                    violations.append((teacher_id, wd))
        if total >= min_weekly_periods:
            for wd in mandatory_mornings:
                if wd in strict_weekdays:
                    continue
                if teacher_morns[teacher_id][wd] == 0:
                    if ban_busy and _is_teacher_busy_on_morning(teacher_id, wd, slots, assigned_teacher, ban_busy):
                        continue
                    violations.append((teacher_id, wd))
    return violations


def find_teacher_lone_session_violations(slots: list, assignment: dict, assigned_teacher: dict,
                                          min_weekly_periods: int = 15,
                                          exempt_teacher_ids: frozenset = frozenset()) -> list:
    """Returns [(teacher_id, weekday, session), ...] for any teacher session with
    exactly 1 period -- Tiêu chí II.4, exempting teachers below min_weekly_periods.
    Mirrors core.scheduler.quality._count_teacher_lone_sessions exactly, INCLUDING
    exempt_teacher_ids (config.lone_session_exempt_teacher_ids) -- omitting this
    parameter here let a teacher the engine/CP-SAT deliberately excused (per the
    school's own config) get flagged again by this independent display-side check,
    silently disagreeing with the "no lỗi" the solver's own hard-gate reported
    (2026-09-05 root-cause fix)."""
    t_sess = defaultdict(int)
    teacher_totals = defaultdict(int)
    for slot in slots:
        subject_id = assignment.get(slot.slot_id)
        if subject_id is None:
            continue
        teacher_id = assigned_teacher.get((subject_id, slot.class_id))
        if teacher_id is None or teacher_id <= 0 or teacher_id in exempt_teacher_ids:
            continue
        t_sess[(teacher_id, slot.ts.weekday, slot.ts.session)] += 1
        teacher_totals[teacher_id] += 1

    return [
        (tid, wd, sess) for (tid, wd, sess), count in t_sess.items()
        if count == 1 and teacher_totals[tid] >= min_weekly_periods
    ]


def find_teacher_lone_day_violations(slots: list, assignment: dict, assigned_teacher: dict,
                                      min_weekly_periods: int = 15,
                                      exempt_teacher_ids: frozenset = frozenset()) -> list:
    """Returns [(teacher_id, weekday), ...] for any teacher day with exactly 1 period
    total -- Tiêu chí II.4, exempting teachers below min_weekly_periods. Mirrors
    core.scheduler.quality._count_teacher_lone_days exactly, INCLUDING
    exempt_teacher_ids (see find_teacher_lone_session_violations's docstring)."""
    teacher_days = defaultdict(int)
    teacher_totals = defaultdict(int)
    for slot in slots:
        subject_id = assignment.get(slot.slot_id)
        if subject_id is None:
            continue
        teacher_id = assigned_teacher.get((subject_id, slot.class_id))
        if teacher_id is None or teacher_id <= 0 or teacher_id in exempt_teacher_ids:
            continue
        teacher_days[(teacher_id, slot.ts.weekday)] += 1
        teacher_totals[teacher_id] += 1

    return [
        (tid, wd) for (tid, wd), count in teacher_days.items()
        if count == 1 and teacher_totals[tid] >= min_weekly_periods
    ]


def find_teacher_split_day_violations(slots: list, assignment: dict, assigned_teacher: dict,
                                       min_weekly_periods: int = 15,
                                       exempt_teacher_ids: frozenset = frozenset()) -> list:
    """Returns [(teacher_id, weekday), ...] for any teacher day with periods in BOTH
    sessions where at least one session has exactly 1 period (e.g. 1 AM + 1 PM, but
    also the asymmetric case like 1 AM + 3 PM) -- Tiêu chí II.8, exempting teachers
    below min_weekly_periods (same threshold as II.4 -- a teacher with very few
    periods/week is structurally likely to land on a split day, so this shares II.4's
    exemption per the 2026-09-02 Task 4 fix-round ruling). Mirrors
    core.scheduler.quality._count_teacher_split_sessions's condition EXACTLY --
    `S>0 and C>0 and (S==1 or C==1)`, NOT the narrower `S==1 and C==1` -- getting this
    wrong here would silently disagree with the engine's hard gate, defeating the
    entire point of this task (post-fix-round, that function also gained this same
    min_weekly_periods parameter). Also honors exempt_teacher_ids (see
    find_teacher_lone_session_violations's docstring, 2026-09-05)."""
    teacher_day_sessions = defaultdict(lambda: defaultdict(int))
    teacher_totals = defaultdict(int)
    for slot in slots:
        subject_id = assignment.get(slot.slot_id)
        if subject_id is None:
            continue
        teacher_id = assigned_teacher.get((subject_id, slot.class_id))
        if teacher_id is None or teacher_id <= 0 or teacher_id in exempt_teacher_ids:
            continue
        teacher_day_sessions[(teacher_id, slot.ts.weekday)][slot.ts.session] += 1
        teacher_totals[teacher_id] += 1

    violations = []
    for (teacher_id, wd), sess_counts in teacher_day_sessions.items():
        s_count = sess_counts.get("S", 0)
        c_count = sess_counts.get("C", 0)
        if (s_count == 1 and c_count == 1
                and teacher_totals[teacher_id] >= min_weekly_periods):
            violations.append((teacher_id, wd))
    return violations


def find_teacher_4_consecutive_morning_violations(slots: list, assignment: dict, assigned_teacher: dict,
                                                    max_load_for_penalty: int = 20) -> list:
    """Returns [(teacher_id, weekday), ...] for any teacher with >=4 periods in one
    morning session -- Tiêu chí II.14, exempting teachers above max_load_for_penalty.
    Mirrors core.scheduler.quality._count_teacher_4_consecutive_mornings exactly."""
    t_morn_periods = defaultdict(list)
    teacher_totals = defaultdict(int)
    for slot in slots:
        subject_id = assignment.get(slot.slot_id)
        if subject_id is None:
            continue
        teacher_id = assigned_teacher.get((subject_id, slot.class_id))
        if teacher_id is None or teacher_id <= 0:
            continue
        teacher_totals[teacher_id] += 1
        if slot.ts.session == "S":
            t_morn_periods[(teacher_id, slot.ts.weekday)].append(slot.ts.period)

    violations = []
    for (teacher_id, wd), periods in t_morn_periods.items():
        if len(periods) >= 4 and teacher_totals[teacher_id] <= max_load_for_penalty:
            violations.append((teacher_id, wd))
    return violations


def compute_tkb_health_score(inp: SchedulingInput, assignment: dict) -> dict:
    """Đánh giá toàn diện sức khỏe TKB theo thang điểm 100 với 3 trụ cột:
    1. Sư phạm học sinh (Pedagogical Quality - 40%)
    2. Tiện nghi & Công bằng Giáo viên (Teacher Ergonomics & Fairness - 35%)
    3. Tuân thủ HĐSP & Kế hoạch (HĐSP Compliance - 25%)
    """
    eff_assigned = _build_effective_assigned_teacher(inp)
    slot_teacher = {
        s.slot_id: eff_assigned.get((assignment[s.slot_id], s.class_id))
        for s in inp.slots if s.slot_id in assignment and assignment[s.slot_id] is not None
    }
    bgh_ids = frozenset(t.teacher_id for t in inp.teachers if is_bgh(t))
    class_map = {c.class_id: c.name for c in inp.classes}
    subj_map = {s.subject_id: s.name for s in inp.subjects}
    teacher_map = {t.teacher_id: t.name for t in inp.teachers}

    recommendations = []

    # ─────────────────────────────────────────────────────────────
    # Trụ cột 1: SƯ PHẠM HỌC SINH (100đ)
    # ─────────────────────────────────────────────────────────────
    ped_penalty = 0.0

    # 1.1 Giãn cách môn 2-3 tiết/tuần
    cls_subj_days = defaultdict(set)
    for s in inp.slots:
        subj = assignment.get(s.slot_id)
        if subj not in (None, -1):
            cls_subj_days[(s.class_id, subj)].add(s.ts.weekday)

    consec_subject_violations = []
    for (cls_id, subj_id), days in cls_subj_days.items():
        n = inp.need.get((subj_id, cls_id), 0)
        # Bỏ qua HĐTN
        subj_obj = next((sb for sb in inp.subjects if sb.subject_id == subj_id), None)
        if subj_obj and subj_obj.role_code == ROLE_HDTN:
            continue
        if n in (2, 3):
            sorted_days = sorted(days)
            for i in range(len(sorted_days) - 1):
                if sorted_days[i + 1] == sorted_days[i] + 1:
                    w1, w2 = sorted_days[i], sorted_days[i + 1]
                    consec_subject_violations.append((cls_id, subj_id, w1, w2))
                    c_name = class_map.get(cls_id, f"Lớp #{cls_id}")
                    s_name = subj_map.get(subj_id, f"Môn #{subj_id}")
                    w1_str = WEEKDAY_NAMES.get(w1, f"T{w1}")
                    w2_str = WEEKDAY_NAMES.get(w2, f"T{w2}")
                    if len(consec_subject_violations) <= 3:
                        recommendations.append({
                            "type": "info",
                            "category": "Sư phạm",
                            "message": f"{c_name}: Môn {s_name} học 2 ngày liên tiếp ({w1_str} - {w2_str}) — khuyến nghị giãn cách thêm nếu điều kiện khung cho phép.",
                        })
    # Tiêu chí phụ: chỉ trừ nhẹ tối đa 5 điểm toàn trường để không lấn át tiêu chuẩn chính của trường
    ped_penalty += min(5.0, len(consec_subject_violations) * 0.5)

    # 1.2 Trần môn nặng liên tiếp (> 3 tiết)
    heavy_ids = {s.subject_id for s in inp.subjects if s.role_code in (ROLE_NANG, ROLE_NANG_KEP)}
    heavy_run_violations = []
    if heavy_ids:
        max_heavy = getattr(inp.config, "max_heavy_consecutive", 3)
        heavy_run_violations = find_max_heavy_violations(inp.slots, assignment, heavy_ids, max_heavy)
        for (cid, wd, sess, start_p, length) in heavy_run_violations:
            c_name = class_map.get(cid, f"Lớp #{cid}")
            sess_name = "Sáng" if sess == "S" else "Chiều"
            wd_str = WEEKDAY_NAMES.get(wd, f"Thứ {wd}")
            recommendations.append({
                "type": "warning",
                "category": "Sư phạm",
                "message": f"{c_name}: Có chuỗi {length} tiết môn Nặng liên tiếp vào {wd_str} {sess_name} (bắt đầu từ tiết {start_p}).",
            })
    ped_penalty += len(heavy_run_violations) * 15.0

    # 1.3 Môn nặng tiết 3 chiều
    heavy_p3_violations = []
    if getattr(inp.config, "avoid_heavy_afternoon_period3", True) and heavy_ids:
        heavy_p3_violations = find_heavy_afternoon_period3_violations(inp.slots, assignment, heavy_ids)
        for (cid, sid, wd, sess, per) in heavy_p3_violations:
            c_name = class_map.get(cid, f"Lớp #{cid}")
            s_name = subj_map.get(sid, f"Môn #{sid}")
            wd_str = WEEKDAY_NAMES.get(wd, f"Thứ {wd}")
            recommendations.append({
                "type": "warning",
                "category": "Sư phạm",
                "message": f"{c_name}: Môn {s_name} xếp vào tiết 3 chiều ({wd_str}) — học sinh dễ mệt mỏi cuối ngày.",
            })
    ped_penalty += len(heavy_p3_violations) * 10.0

    # 1.4 GDTC ngoài khung giờ
    gdtc_id = next((s.subject_id for s in inp.subjects if s.role_code == ROLE_GDTC), None)
    gdtc_violations = []
    if gdtc_id:
        gdtc_violations = find_invalid_gdtc_periods(
            inp.slots, assignment, gdtc_id,
            getattr(inp.config, "gdtc_morning_allowed_periods", (1, 2, 3, 4)),
            getattr(inp.config, "gdtc_afternoon_allowed_periods", (2, 3)),
        )
        for (cid, wd, sess, per) in gdtc_violations:
            c_name = class_map.get(cid, f"Lớp #{cid}")
            sess_name = "Sáng" if sess == "S" else "Chiều"
            wd_str = WEEKDAY_NAMES.get(wd, f"Thứ {wd}")
            recommendations.append({
                "type": "warning",
                "category": "Sư phạm",
                "message": f"{c_name}: Tiết GDTC xếp vào tiết {per} {sess_name} ({wd_str}) ngoài khung giờ thể chất chuẩn.",
            })
    ped_penalty += len(gdtc_violations) * 10.0

    pedagogical_score = max(0.0, min(100.0, 100.0 - ped_penalty))

    # ─────────────────────────────────────────────────────────────
    # Trụ cột 2: TIỆN NGHI & CÔNG BẰNG GIÁO VIÊN (100đ)
    # ─────────────────────────────────────────────────────────────
    teacher_penalty = 0.0

    # 2.1 Tiết trống giữa buổi & Lũy tiến gaps
    gaps_list = find_teacher_gaps(inp.slots, assignment, inp.assigned_teacher)
    extra_gap1, extra_gap2 = _count_teacher_excess_gaps(inp.slots, assignment, slot_teacher)
    gap_deduction = min(30.0, len(gaps_list) * 1.5) + min(10.0, extra_gap1 * 1.0) + min(10.0, extra_gap2 * 2.0)
    teacher_penalty += gap_deduction
    for tid, wd, sess, p_list in gaps_list[:5]:
        tname = teacher_map.get(tid, f"GV #{tid}")
        sess_name = "Sáng" if sess == "S" else "Chiều"
        wd_str = WEEKDAY_NAMES.get(wd, f"Thứ {wd}")
        recommendations.append({
            "type": "warning",
            "category": "Giáo viên",
            "message": f"{tname}: Bị trống tiết vào {wd_str} {sess_name} (tiết dạy: {', '.join(str(p) for p in p_list)}).",
        })

    # 2.2 Chống nhảy ca gắt (chiều muộn -> sáng sớm) - Tiêu chí phụ
    t_late = set()
    t_early = set()
    for s in inp.slots:
        subj = assignment.get(s.slot_id)
        if subj not in (None, -1):
            tid = slot_teacher.get(s.slot_id)
            if tid is not None and tid > 0:
                if s.ts.session == "C" and s.ts.period in (4, 5):
                    t_late.add((tid, s.ts.weekday, s.ts.period))
                elif s.ts.session == "S" and s.ts.period == 1:
                    t_early.add((tid, s.ts.weekday))

    b2b_violations = []
    for (tid, wd, p_late) in t_late:
        if (tid, wd + 1) in t_early:
            b2b_violations.append((tid, wd, p_late))
            tname = teacher_map.get(tid, f"GV #{tid}")
            wd_str = WEEKDAY_NAMES.get(wd, f"Thứ {wd}")
            wd_next_str = WEEKDAY_NAMES.get(wd + 1, f"Thứ {wd+1}")
            if len(b2b_violations) <= 3:
                recommendations.append({
                    "type": "info",
                    "category": "Giáo viên",
                    "message": f"{tname}: Dạy chiều muộn {wd_str} (tiết {p_late}) và sáng sớm hôm sau {wd_next_str} (tiết 1) — thời gian nghỉ ngơi hơi sát.",
                })
    teacher_penalty += min(3.0, len(b2b_violations) * 1.0)

    # 2.3 Trần dạy 5 tiết/ngày
    max_teacher_day = getattr(inp.config, "max_teacher_periods_per_day", 5)
    day_cap_violations = find_teacher_day_cap_violations(inp.slots, assignment, inp.assigned_teacher, max_teacher_day)
    for tid, wd, count in day_cap_violations:
        tname = teacher_map.get(tid, f"GV #{tid}")
        wd_str = WEEKDAY_NAMES.get(wd, f"Thứ {wd}")
        recommendations.append({
            "type": "error",
            "category": "Giáo viên",
            "message": f"{tname}: Dạy {count} tiết vào {wd_str} (vượt trần {max_teacher_day} tiết/ngày).",
        })
    teacher_penalty += len(day_cap_violations) * 15.0

    # 2.4 Dạy 4 tiết sáng liên tiếp
    consec_morning_violations = []
    if getattr(inp.config, "avoid_teacher_4_consecutive_morning", True):
        consec_morning_violations = find_teacher_4_consecutive_morning_violations(inp.slots, assignment, inp.assigned_teacher)
        for tid, wd in consec_morning_violations:
            tname = teacher_map.get(tid, f"GV #{tid}")
            wd_str = WEEKDAY_NAMES.get(wd, f"Thứ {wd}")
            recommendations.append({
                "type": "info",
                "category": "Giáo viên",
                "message": f"{tname}: Dạy 4 tiết liên tục sáng {wd_str}.",
            })
    teacher_penalty += len(consec_morning_violations) * 5.0

    teacher_score = max(0.0, min(100.0, 100.0 - teacher_penalty))

    # ─────────────────────────────────────────────────────────────
    # Trụ cột 3: TUÂN THỦ HĐSP & KẾ HOẠCH (100đ)
    # ─────────────────────────────────────────────────────────────
    compliance_penalty = 0.0

    # 3.1 Trùng lịch
    conflicts = find_teacher_conflicts(inp.slots, assignment, inp.assigned_teacher)
    compliance_penalty += len(conflicts) * 100.0
    for tid, wd, sess, per, c_list in conflicts:
        tname = teacher_map.get(tid, f"GV #{tid}")
        sess_name = "Sáng" if sess == "S" else "Chiều"
        wd_str = WEEKDAY_NAMES.get(wd, f"Thứ {wd}")
        c_names = ", ".join(class_map.get(cid, f"Lớp #{cid}") for cid in c_list)
        recommendations.append({
            "type": "error",
            "category": "Tuân thủ",
            "message": f"{tname}: Bị trùng lịch tại {wd_str} {sess_name} tiết {per} giữa các lớp {c_names}.",
        })

    # 3.2 Vi phạm giờ bận
    busy_violations = find_teacher_unavailability_violations(inp.slots, assignment, inp.assigned_teacher, inp.ban_busy)
    compliance_penalty += len(busy_violations) * 50.0
    for tid, cid, wd, sess, per in busy_violations:
        tname = teacher_map.get(tid, f"GV #{tid}")
        c_name = class_map.get(cid, f"Lớp #{cid}")
        sess_name = "Sáng" if sess == "S" else "Chiều"
        wd_str = WEEKDAY_NAMES.get(wd, f"Thứ {wd}")
        recommendations.append({
            "type": "error",
            "category": "Tuân thủ",
            "message": f"{tname}: Xếp lịch dạy {c_name} vào khung giờ đã báo bận ({wd_str} {sess_name} tiết {per}).",
        })

    # 3.3 Buổi lẻ 1 tiết (II.4) & Ngày lẻ (II.4)
    min_lone_load = getattr(inp.config, "min_weekly_periods_for_lone_penalty", 8)
    lone_exempt_ids = getattr(inp.config, "lone_session_exempt_teacher_ids", frozenset()) or frozenset()
    lone_sessions = find_teacher_lone_session_violations(inp.slots, assignment, inp.assigned_teacher, min_lone_load, lone_exempt_ids)
    lone_days = find_teacher_lone_day_violations(inp.slots, assignment, inp.assigned_teacher, min_lone_load, lone_exempt_ids)
    compliance_penalty += (len(lone_sessions) + len(lone_days)) * 15.0

    # 3.4 Ngày chia lẻ (II.8)
    split_days = find_teacher_split_day_violations(inp.slots, assignment, inp.assigned_teacher, min_lone_load, lone_exempt_ids)
    compliance_penalty += len(split_days) * 15.0

    # 3.5 Thiếu sáng bắt buộc (II.3)
    missing_morning = find_teacher_missing_mandatory_morning_violations(
        inp.slots, assignment, inp.assigned_teacher,
        getattr(inp.config, "mandatory_morning_weekdays", (2, 5, 6)),
        getattr(inp.config, "min_weekly_periods_for_mandatory_morning", 10),
        getattr(inp.config, "strict_morning_weekdays", ()) or (),
        bgh_ids,
        ban_busy=getattr(inp, "ban_busy", None),
    )
    compliance_penalty += min(20.0, len(missing_morning) * 4.0)

    compliance_score = max(0.0, min(100.0, 100.0 - compliance_penalty))

    # ─────────────────────────────────────────────────────────────
    # Tổng kết điểm & xếp loại
    # ─────────────────────────────────────────────────────────────
    overall_score = round(0.40 * pedagogical_score + 0.35 * teacher_score + 0.25 * compliance_score, 1)

    if overall_score >= 90.0:
        rating = "Xuất sắc"
        badge_color = "#28a745"
    elif overall_score >= 80.0:
        rating = "Tốt"
        badge_color = "#17a2b8"
    elif overall_score >= 70.0:
        rating = "Khá"
        badge_color = "#ffc107"
    else:
        rating = "Cần cải thiện"
        badge_color = "#dc3545"

    if not recommendations:
        recommendations.append({
            "type": "success",
            "category": "Tổng quan",
            "message": "Thời khóa biểu đạt tiêu chuẩn xuất sắc: các môn học phân bổ khoa học, giáo viên không bị phân mảnh lịch dạy.",
        })

    return {
        "overall_score": overall_score,
        "pedagogical_score": round(pedagogical_score, 1),
        "teacher_score": round(teacher_score, 1),
        "compliance_score": round(compliance_score, 1),
        "rating": rating,
        "badge_color": badge_color,
        "metrics": {
            "consecutive_subject_days": len(consec_subject_violations),
            "heavy_excess_runs": len(heavy_run_violations),
            "heavy_afternoon_p3": len(heavy_p3_violations),
            "gdtc_violations": len(gdtc_violations),
            "teacher_gaps_total": len(gaps_list),
            "teacher_excess_gaps": extra_gap1 + extra_gap2,
            "teacher_back_to_back": len(b2b_violations),
            "teacher_4_consec_mornings": len(consec_morning_violations),
            "teacher_day_cap_violations": len(day_cap_violations),
            "conflicts": len(conflicts),
            "busy_violations": len(busy_violations),
            "lone_sessions": len(lone_sessions),
            "lone_days": len(lone_days),
            "split_days": len(split_days),
            "missing_mornings": len(missing_morning),
        },
        "recommendations": recommendations,
    }

