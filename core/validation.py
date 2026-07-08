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
