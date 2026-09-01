"""Port & Enhancement of ModCanBangTai: teacher load-balancing ADVISOR and CLASS-LEVEL synchronizer.

In educational timetables, teaching assignments are strictly managed at the
CLASS level for each subject (môn x lớp). A teacher assigned to a subject in a class
teaches ALL periods of that class across both even (Chẵn) and odd (Lẻ) weeks.
Fractional period splitting within a class is never permitted.

This module proposes load-balancing adjustments:
1. One-way class transfer: Move full (subject, class) from over-cap teacher to a qualified teacher with slack.
2. Two-way class swap: Swap two classes of different period weights between two teachers of the same subject
   when 1-way transfer is too coarse (e.g. 4-period class vs 3-period class for a 1-period net reduction).
3. Under-floor compensation: Raise loads for teachers below the minimum floor.
4. Direct application helper: Apply suggestions cleanly to the assignments dictionary/database.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Suggestion:
    over_teacher_id: int
    over_amount: float
    subject_id: int
    class_id: int
    periods: float
    to_teacher_id: int
    to_teacher_load: float
    to_teacher_cap: int
    reason: str = "vuot_tran"   # "vuot_tran" | "duoi_san"
    action_type: str = "transfer"  # "transfer" | "swap"
    periods_c: int = 0
    periods_l: int = 0
    from_teacher_new_load: float = 0.0
    to_teacher_new_load: float = 0.0
    swap_subject_id: Optional[int] = None
    swap_class_id: Optional[int] = None
    swap_periods_c: int = 0
    swap_periods_l: int = 0
    swap_periods: float = 0.0


@dataclass
class UnresolvedOverload:
    over_teacher_id: int
    remaining_over: float


@dataclass
class UnresolvedUnderload:
    under_teacher_id: int
    remaining_under: float


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


def suggest_rebalance(
    assignments: dict,
    periods_per_week: dict,
    parity: str,
    teacher_caps: dict,
    floor_margin: int = 3,
    allow_swap: bool = True,
) -> tuple[list[Suggestion], list[UnresolvedOverload], list[UnresolvedUnderload]]:
    """Suggests class-level rebalancing (1-way transfer and 2-way class swap).

    Invariants:
    - Entire class (subject_id, class_id) is moved/swapped as a whole.
    - All periods across week C and week L are moved together.
    - Operates on local copy of assignments & loads; does not mutate input dicts.
    """
    load_c = compute_teacher_loads(assignments, periods_per_week, "C")
    load_l = compute_teacher_loads(assignments, periods_per_week, "L")
    load = {tid: (load_c.get(tid, 0) + load_l.get(tid, 0)) / 2 for tid in set(load_c) | set(load_l)}

    def get_periods_c(subject_id: int, class_id: int) -> int:
        return periods_per_week.get((subject_id, class_id, "C"), 0)

    def get_periods_l(subject_id: int, class_id: int) -> int:
        return periods_per_week.get((subject_id, class_id, "L"), 0)

    def avg_periods(subject_id: int, class_id: int) -> float:
        return (get_periods_c(subject_id, class_id) + get_periods_l(subject_id, class_id)) / 2

    # Track local assignment state for multi-step proposals
    curr_assignments = dict(assignments)
    suggestions: list[Suggestion] = []
    unresolved_over: list[UnresolvedOverload] = []
    subject_teachers = build_subject_teachers(curr_assignments)

    def is_under_floor(tid: int) -> bool:
        cap = teacher_caps.get(tid, 0)
        return bool(cap) and load.get(tid, 0) < cap - floor_margin

    # Pass 1: Relieve over-cap teachers via 1-way Class Transfer
    # Prefer a recipient who is currently under the floor
    for over_teacher, over_load in sorted(load.items(), key=lambda x: -x[1]):
        cap = teacher_caps.get(over_teacher, 0)
        if not cap or over_load <= cap:
            continue
        can_giam = load[over_teacher] - cap

        # Candidate classes assigned to over_teacher
        over_classes = [
            (s_id, c_id) for (s_id, c_id), t_id in curr_assignments.items()
            if t_id == over_teacher and avg_periods(s_id, c_id) > 0
        ]
        # Sort classes descending by periods to relieve large overloads first
        over_classes.sort(key=lambda sc: -avg_periods(sc[0], sc[1]))

        for (subject_id, class_id) in over_classes:
            if can_giam <= 0:
                break
            # Verify assignment still belongs to over_teacher
            if curr_assignments.get((subject_id, class_id)) != over_teacher:
                continue

            periods = avg_periods(subject_id, class_id)
            c_p = get_periods_c(subject_id, class_id)
            l_p = get_periods_l(subject_id, class_id)
            if periods <= 0:
                continue

            best_teacher = None
            best_key = None  # (not_under_floor, -slack, tid)
            for candidate in subject_teachers.get(subject_id, set()):
                if candidate == over_teacher:
                    continue
                candidate_cap = teacher_caps.get(candidate, 0)
                if not candidate_cap:
                    continue
                slack = candidate_cap - load.get(candidate, 0)
                if slack < periods:
                    continue
                key = (not is_under_floor(candidate), -slack, candidate)
                if best_key is None or key < best_key:
                    best_key = key
                    best_teacher = candidate

            if best_teacher is not None:
                old_over_load = load[over_teacher]
                old_to_load = load[best_teacher]
                new_over_load = old_over_load - periods
                new_to_load = old_to_load + periods

                suggestions.append(Suggestion(
                    over_teacher_id=over_teacher,
                    over_amount=old_over_load - cap,
                    subject_id=subject_id,
                    class_id=class_id,
                    periods=periods,
                    to_teacher_id=best_teacher,
                    to_teacher_load=old_to_load,
                    to_teacher_cap=teacher_caps.get(best_teacher, 0),
                    reason="duoi_san" if is_under_floor(best_teacher) else "vuot_tran",
                    action_type="transfer",
                    periods_c=c_p,
                    periods_l=l_p,
                    from_teacher_new_load=new_over_load,
                    to_teacher_new_load=new_to_load,
                ))
                load[over_teacher] = new_over_load
                load[best_teacher] = new_to_load
                curr_assignments[(subject_id, class_id)] = best_teacher
                can_giam = max(0.0, load[over_teacher] - cap)

        # Pass 1.5 / Pass 2: If still over cap and allow_swap is enabled, try 2-way Class Swapping
        if allow_swap and can_giam > 0:
            remaining_classes = [
                (s_id, c_id) for (s_id, c_id), t_id in curr_assignments.items()
                if t_id == over_teacher and avg_periods(s_id, c_id) > 0
            ]
            for (subject_id, class_id) in remaining_classes:
                if can_giam <= 0:
                    break
                p1 = avg_periods(subject_id, class_id)
                c_p1 = get_periods_c(subject_id, class_id)
                l_p1 = get_periods_l(subject_id, class_id)

                best_swap_candidate = None
                best_swap_class = None
                best_swap_delta = None

                for candidate in subject_teachers.get(subject_id, set()):
                    if candidate == over_teacher:
                        continue
                    candidate_cap = teacher_caps.get(candidate, 0)
                    if not candidate_cap:
                        continue

                    # Look for candidate's classes of the same subject with p2 < p1
                    for (s2_id, c2_id), t2_id in curr_assignments.items():
                        if t2_id != candidate or s2_id != subject_id:
                            continue
                        p2 = avg_periods(s2_id, c2_id)
                        if p2 >= p1:
                            continue
                        delta = p1 - p2
                        # Check recipient room
                        slack = candidate_cap - load.get(candidate, 0)
                        if slack < delta:
                            continue
                        # Check over_teacher does not drop below floor
                        if load.get(over_teacher, 0) - delta < cap - floor_margin:
                            continue

                        # We want delta that brings over_teacher closest to 0 over
                        diff_from_target = abs(can_giam - delta)
                        key = (diff_from_target, not is_under_floor(candidate), candidate)
                        if best_swap_delta is None or key < best_swap_delta:
                            best_swap_delta = key
                            best_swap_candidate = candidate
                            best_swap_class = c2_id

                if best_swap_candidate is not None and best_swap_class is not None:
                    p2 = avg_periods(subject_id, best_swap_class)
                    c_p2 = get_periods_c(subject_id, best_swap_class)
                    l_p2 = get_periods_l(subject_id, best_swap_class)
                    delta = p1 - p2

                    old_over_load = load[over_teacher]
                    old_to_load = load[best_swap_candidate]
                    new_over_load = old_over_load - delta
                    new_to_load = old_to_load + delta

                    suggestions.append(Suggestion(
                        over_teacher_id=over_teacher,
                        over_amount=old_over_load - cap,
                        subject_id=subject_id,
                        class_id=class_id,
                        periods=p1,
                        to_teacher_id=best_swap_candidate,
                        to_teacher_load=old_to_load,
                        to_teacher_cap=teacher_caps.get(best_swap_candidate, 0),
                        reason="vuot_tran",
                        action_type="swap",
                        periods_c=c_p1,
                        periods_l=l_p1,
                        from_teacher_new_load=new_over_load,
                        to_teacher_new_load=new_to_load,
                        swap_subject_id=subject_id,
                        swap_class_id=best_swap_class,
                        swap_periods_c=c_p2,
                        swap_periods_l=l_p2,
                        swap_periods=p2,
                    ))
                    load[over_teacher] = new_over_load
                    load[best_swap_candidate] = new_to_load
                    curr_assignments[(subject_id, class_id)] = best_swap_candidate
                    curr_assignments[(subject_id, best_swap_class)] = over_teacher
                    can_giam = max(0.0, load[over_teacher] - cap)

        rem_over = max(0.0, load[over_teacher] - cap)
        if rem_over > 0:
            unresolved_over.append(UnresolvedOverload(over_teacher_id=over_teacher, remaining_over=rem_over))

    # Pass 3: Relieve teachers still under the floor via 1-way Class Transfer
    unresolved_under: list[UnresolvedUnderload] = []
    for under_teacher in [tid for tid in sorted(load.keys()) if is_under_floor(tid)]:
        cap_u = teacher_caps.get(under_teacher, 0)
        needed = (cap_u - floor_margin) - load.get(under_teacher, 0)
        if needed <= 0:
            continue

        for (subject_id, class_id), teacher_id in list(curr_assignments.items()):
            if needed <= 0:
                break
            if teacher_id is None or teacher_id == under_teacher:
                continue
            if under_teacher not in subject_teachers.get(subject_id, set()):
                continue

            periods = avg_periods(subject_id, class_id)
            c_p = get_periods_c(subject_id, class_id)
            l_p = get_periods_l(subject_id, class_id)
            if periods <= 0:
                continue

            donor_cap = teacher_caps.get(teacher_id, 0)
            if not donor_cap:
                continue
            if load.get(teacher_id, 0) - periods < donor_cap - floor_margin:
                continue  # Would push donor below floor

            old_donor_load = load[teacher_id]
            old_under_load = load[under_teacher]
            new_donor_load = old_donor_load - periods
            new_under_load = old_under_load + periods

            suggestions.append(Suggestion(
                over_teacher_id=teacher_id,
                over_amount=0,
                subject_id=subject_id,
                class_id=class_id,
                periods=periods,
                to_teacher_id=under_teacher,
                to_teacher_load=old_under_load,
                to_teacher_cap=cap_u,
                reason="duoi_san",
                action_type="transfer",
                periods_c=c_p,
                periods_l=l_p,
                from_teacher_new_load=new_donor_load,
                to_teacher_new_load=new_under_load,
            ))
            load[teacher_id] = new_donor_load
            load[under_teacher] = new_under_load
            curr_assignments[(subject_id, class_id)] = under_teacher
            needed = max(0.0, (cap_u - floor_margin) - load.get(under_teacher, 0))

        rem_under = max(0.0, (cap_u - floor_margin) - load.get(under_teacher, 0))
        if rem_under > 0:
            unresolved_under.append(UnresolvedUnderload(under_teacher_id=under_teacher, remaining_under=rem_under))

    return suggestions, unresolved_over, unresolved_under


def apply_suggestion_to_assignments(assignments: dict, suggestion: Suggestion) -> dict:
    """Returns a new dictionary with the suggestion applied."""
    updated = dict(assignments)
    if suggestion.action_type == "transfer":
        updated[(suggestion.subject_id, suggestion.class_id)] = suggestion.to_teacher_id
    elif suggestion.action_type == "swap":
        updated[(suggestion.subject_id, suggestion.class_id)] = suggestion.to_teacher_id
        if suggestion.swap_subject_id is not None and suggestion.swap_class_id is not None:
            updated[(suggestion.swap_subject_id, suggestion.swap_class_id)] = suggestion.over_teacher_id
    return updated


def apply_all_suggestions(assignments: dict, suggestions: list[Suggestion]) -> dict:
    """Sequentially applies all suggestions and returns the resulting assignments dict."""
    res = dict(assignments)
    for s in suggestions:
        res = apply_suggestion_to_assignments(res, s)
    return res
