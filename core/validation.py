"""Port of the KiemTra sheet's checks: per (subject,class) quota diff (expect
0), and teacher double-booking detection (mirrors TKB_GV's hidden COUNTIFS
helper columns).
"""
from __future__ import annotations

from collections import defaultdict


def compute_actual_counts(slots: list, assignment: dict) -> dict:
    counts = defaultdict(int)
    for slot in slots:
        subject_id = assignment.get(slot.slot_id)
        if subject_id is not None:
            counts[(subject_id, slot.class_id)] += 1
    return counts


def compute_quota_diff(slots: list, assignment: dict, periods_per_week: dict, parity: str) -> dict:
    """Returns (subject_id, class_id) -> actual - quota. Expect all zeros."""
    actual = compute_actual_counts(slots, assignment)
    keys = set(actual.keys()) | {(s_id, c_id) for (s_id, c_id, p) in periods_per_week if p == parity}
    diff = {}
    for key in keys:
        quota = periods_per_week.get((key[0], key[1], parity), 0)
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



