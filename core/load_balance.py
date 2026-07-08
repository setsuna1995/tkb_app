"""Port of ModCanBangTai.bas: teacher load-balancing ADVISOR.

Finds teachers over their quota cap and proposes moving a (subject, class)
assignment to another teacher who already teaches that subject somewhere and
has enough slack. Also proposes moves that bring under-the-floor teachers
back up (load < cap - floor_margin), preferring a single move that fixes an
over-cap AND an under-floor teacher at once (fewest total changes). Never
mutates assignments -- returns suggestions only, for a human to review and
apply manually (same design as the VBA: it writes to a separate
"DeXuat_CanBang" sheet, never touches PhanCong).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Suggestion:
    over_teacher_id: int
    over_amount: int
    subject_id: int
    class_id: int
    periods: int
    to_teacher_id: int
    to_teacher_load: int
    to_teacher_cap: int
    reason: str = "vuot_tran"   # "vuot_tran" (giảm tải GV vượt trần) | "duoi_san" (bù GV dưới sàn)


@dataclass
class UnresolvedOverload:
    over_teacher_id: int
    remaining_over: int


@dataclass
class UnresolvedUnderload:
    under_teacher_id: int
    remaining_under: int


def compute_teacher_loads(assignments: dict, periods_per_week: dict, parity: str) -> dict:
    """assignments: (subject_id,class_id)->teacher_id.
    periods_per_week: (subject_id,class_id,parity)->periods.
    Returns teacher_id -> total assigned periods for the given parity.
    """
    load = {}
    for (subject_id, class_id), teacher_id in assignments.items():
        if teacher_id is None:
            continue
        periods = periods_per_week.get((subject_id, class_id, parity), 0)
        load[teacher_id] = load.get(teacher_id, 0) + periods
    return load


def build_subject_teachers(assignments: dict) -> dict:
    """assignments: (subject_id,class_id)->teacher_id. Returns subject_id -> set(teacher_id)."""
    subject_teachers = {}
    for (subject_id, _class_id), teacher_id in assignments.items():
        if teacher_id is None:
            continue
        subject_teachers.setdefault(subject_id, set()).add(teacher_id)
    return subject_teachers


def rank_substitute_candidates(candidate_teacher_ids, subject_id: int, subject_teachers: dict) -> list:
    """Sort candidates so teachers already teaching `subject_id` somewhere come first
    (stable secondary order by teacher_id). Does not filter -- same-subject is priority only."""
    same_subject = subject_teachers.get(subject_id, set())
    return sorted(candidate_teacher_ids, key=lambda tid: (tid not in same_subject, tid))


def suggest_rebalance(assignments: dict, periods_per_week: dict, parity: str,
                       teacher_caps: dict, floor_margin: int = 3) -> tuple:
    """teacher_caps: teacher_id -> cap (0/None = no cap enforced, like Trần=0 in VBA).
    floor_margin: cap - floor_margin = sàn tối thiểu (mặc định 19-16=3; truyền
    base_cap - min_floor thực tế của trường nếu đã tuỳ chỉnh 2 số này).

    Vượt trần / dưới sàn được xét theo TRUNG BÌNH tải của tuần Chẵn và Lẻ (một GV có
    thể lệch tải giữa 2 tuần nhưng nếu trung bình đã đúng định mức thì không cần điều
    chỉnh) -- `parity` không còn ảnh hưởng logic, chỉ giữ lại cho tương thích chữ ký cũ.
    Số tiết mỗi đề xuất cũng là trung bình 2 tuần của đúng phân công đó (có thể lẻ .5).

    Returns (suggestions: list[Suggestion], unresolved_over: list[UnresolvedOverload],
    unresolved_under: list[UnresolvedUnderload]).
    Mutates a local copy of loads only; never touches `assignments`.
    """
    load_c = compute_teacher_loads(assignments, periods_per_week, "C")
    load_l = compute_teacher_loads(assignments, periods_per_week, "L")
    load = {tid: (load_c.get(tid, 0) + load_l.get(tid, 0)) / 2 for tid in set(load_c) | set(load_l)}

    def avg_periods(subject_id, class_id) -> float:
        return (periods_per_week.get((subject_id, class_id, "C"), 0)
                + periods_per_week.get((subject_id, class_id, "L"), 0)) / 2

    suggestions = []
    unresolved_over = []
    subject_teachers = build_subject_teachers(assignments)

    def is_under_floor(tid) -> bool:
        cap = teacher_caps.get(tid, 0)
        return bool(cap) and load.get(tid, 0) < cap - floor_margin

    # Pass 1: relieve over-cap teachers, preferring a recipient who is currently
    # under the floor (one move then fixes two problems at once).
    for over_teacher, over_load in list(load.items()):
        cap = teacher_caps.get(over_teacher, 0)
        if not cap or over_load <= cap:
            continue
        can_giam = over_load - cap
        for (subject_id, class_id), teacher_id in list(assignments.items()):
            if can_giam <= 0:
                break
            if teacher_id != over_teacher:
                continue
            periods = avg_periods(subject_id, class_id)
            if periods <= 0:
                continue
            best_teacher = None
            best_key = None  # (not_under_floor, -slack) -- dưới sàn trước, rồi nhiều dư địa nhất
            for candidate in subject_teachers.get(subject_id, set()):
                if candidate == over_teacher:
                    continue
                candidate_cap = teacher_caps.get(candidate, 0)
                if not candidate_cap:
                    continue
                slack = candidate_cap - load.get(candidate, 0)
                if slack < periods:
                    continue
                key = (not is_under_floor(candidate), -slack)
                if best_key is None or key < best_key:
                    best_key = key
                    best_teacher = candidate
            if best_teacher is not None:
                suggestions.append(Suggestion(
                    over_teacher_id=over_teacher,
                    over_amount=over_load - cap,
                    subject_id=subject_id,
                    class_id=class_id,
                    periods=periods,
                    to_teacher_id=best_teacher,
                    to_teacher_load=load[best_teacher],
                    to_teacher_cap=teacher_caps.get(best_teacher, 0),
                    reason="duoi_san" if is_under_floor(best_teacher) else "vuot_tran",
                ))
                load[over_teacher] -= periods
                load[best_teacher] += periods
                can_giam -= periods
        if can_giam > 0:
            unresolved_over.append(UnresolvedOverload(over_teacher_id=over_teacher, remaining_over=can_giam))

    # Pass 2: teachers still under the floor (not helped by any over-cap donor
    # above) -- look for a comfortable donor (qualified for the subject, and
    # giving up the periods would not push THEM under their own floor).
    unresolved_under = []
    for under_teacher in [tid for tid in load if is_under_floor(tid)]:
        cap_u = teacher_caps.get(under_teacher, 0)
        needed = (cap_u - floor_margin) - load.get(under_teacher, 0)
        if needed <= 0:
            continue
        for (subject_id, class_id), teacher_id in list(assignments.items()):
            if needed <= 0:
                break
            if teacher_id is None or teacher_id == under_teacher:
                continue
            if under_teacher not in subject_teachers.get(subject_id, set()):
                continue
            periods = avg_periods(subject_id, class_id)
            if periods <= 0:
                continue
            donor_cap = teacher_caps.get(teacher_id, 0)
            if not donor_cap:
                continue
            if load.get(teacher_id, 0) - periods < donor_cap - floor_margin:
                continue  # sẽ đẩy GV cho xuống dưới sàn của chính họ -- bỏ qua
            suggestions.append(Suggestion(
                over_teacher_id=teacher_id,
                over_amount=0,
                subject_id=subject_id,
                class_id=class_id,
                periods=periods,
                to_teacher_id=under_teacher,
                to_teacher_load=load[under_teacher],
                to_teacher_cap=cap_u,
                reason="duoi_san",
            ))
            load[teacher_id] -= periods
            load[under_teacher] += periods
            needed -= periods
        if needed > 0:
            unresolved_under.append(UnresolvedUnderload(under_teacher_id=under_teacher, remaining_under=needed))

    return suggestions, unresolved_over, unresolved_under
