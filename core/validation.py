"""Port of the KiemTra sheet's checks: per (subject,class) quota diff (expect
0), and teacher double-booking detection (mirrors TKB_GV's hidden COUNTIFS
helper columns).
"""
from __future__ import annotations

from collections import defaultdict
from typing import Optional


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


def find_teacher_missing_mandatory_morning_violations(slots: list, assignment: dict, assigned_teacher: dict,
                                                        mandatory_mornings: tuple = (2, 5, 6),
                                                        min_weekly_periods: int = 10,
                                                        strict_weekdays: tuple = (),
                                                        exempt_teacher_ids: frozenset = frozenset()) -> list:
    """Returns [(teacher_id, weekday), ...] for teachers at/above min_weekly_periods
    who end up with zero periods on a mandatory morning -- Tiêu chí II.3: catches an
    accidental empty forbidden morning beyond the teacher's one designated off-slot.
    Mirrors core.scheduler.quality._count_teacher_missing_mandatory_mornings exactly,
    so this check and the engine's post-generation gate (core/scheduler/engine.py)
    never disagree -- INCLUDING the threshold, which callers must pass through from
    config.min_weekly_periods_for_mandatory_morning (2026-09-04)."""
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
                    violations.append((teacher_id, wd))
        if total >= min_weekly_periods:
            for wd in mandatory_mornings:
                if wd in strict_weekdays:
                    continue
                if teacher_morns[teacher_id][wd] == 0:
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
        if (s_count > 0 and c_count > 0 and (s_count == 1 or c_count == 1)
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
