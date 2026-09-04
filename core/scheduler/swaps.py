"""Local search swap-repair and lone period repair routines."""
from __future__ import annotations

from collections import defaultdict
from typing import Optional
from core.models import SchedulingConfig, Slot
from core.scheduler.feasibility import _feasible
from core.scheduler.heuristics import _pick_best_simple
from core.scheduler.placement import _put_at, _remove_at
from core.scheduler.state import _State


def _try_swap_repair(class_id: int, slot: Slot, state: _State, role_index,
                      subjects: list, assigned_teacher: dict,
                      slots_by_class: dict, day_capacity: Optional[dict] = None,
                      config: Optional[SchedulingConfig] = None,
                      subject_class_allowed_cells: Optional[dict] = None) -> bool:
    ts = slot.ts
    for other in slots_by_class[class_id]:
        if other.slot_id == slot.slot_id:
            continue
        if state.assigned.get(other.slot_id, None) in (None, -1) or state.pinned.get(other.slot_id):
            continue
        moved_subject, moved_teacher = _remove_at(state, other, role_index)
        if _feasible(class_id, ts, moved_subject, moved_teacher, state, role_index, day_capacity, config,
                      subject_class_allowed_cells):
            _put_at(state, slot, moved_subject, moved_teacher, role_index)
            refill = _pick_best_simple(class_id, other, state, role_index, subjects, assigned_teacher,
                                        day_capacity, config, subject_class_allowed_cells)
            if refill is not None:
                _put_at(state, other, refill[0], refill[1], role_index)
                return True
            _remove_at(state, slot, role_index)
            _put_at(state, other, moved_subject, moved_teacher, role_index)
        else:
            _put_at(state, other, moved_subject, moved_teacher, role_index)
    return False


def _repair_lone_periods(inp, state: _State, role_index,
                          assigned_teacher: dict, slots_by_class: dict,
                          day_capacity: Optional[dict], config: Optional[SchedulingConfig] = None,
                          subject_class_allowed_cells: Optional[dict] = None) -> None:
    for slot in inp.slots:
        ts = slot.ts
        if ts.period != 2:
            continue
        class_id = slot.class_id
        if not state.occupied.get((class_id, ts.weekday, ts.session, 1), False):
            continue
        current = state.assigned.get(slot.slot_id)
        if current not in (None, -1):
            continue
        if current == -1:
            state.assigned[slot.slot_id] = None
            state.rem_slot_count[class_id] += 1
        pick = _pick_best_simple(class_id, slot, state, role_index, inp.subjects, assigned_teacher,
                                  day_capacity, config, subject_class_allowed_cells)
        if pick is not None:
            _put_at(state, slot, pick[0], pick[1], role_index)
        else:
            _try_swap_repair(class_id, slot, state, role_index, inp.subjects,
                              assigned_teacher, slots_by_class, day_capacity, config,
                              subject_class_allowed_cells)


def _has_lone_period(inp, state: _State) -> bool:
    filled_count: dict = defaultdict(int)
    total_count: dict = defaultdict(int)
    for slot in inp.slots:
        key = (slot.class_id, slot.ts.weekday, slot.ts.session)
        total_count[key] += 1
        if state.assigned.get(slot.slot_id, None) not in (None, -1):
            filled_count[key] += 1
    return any(count == 1 and total_count[key] >= 2 for key, count in filled_count.items())


def _repair_teacher_lone_sessions(inp, state: _State, role_index,
                                   assigned_teacher: dict, slots_by_class: dict,
                                   day_capacity: Optional[dict] = None,
                                   config: Optional[SchedulingConfig] = None,
                                   subject_class_allowed_cells: Optional[dict] = None,
                                   slot_by_coord: Optional[dict] = None,
                                   min_weekly_periods: int = 0) -> None:
    """Finds all teacher sessions with exactly 1 period, and attempts to eliminate them
    either by:
    1. Evacuate: Moving that 1 period to another session where the teacher already teaches,
       leaving the original session with 0 periods (giving the teacher a full session off).
    2. Consolidate: Moving a period of this teacher from another session into this session,
       making this session have >= 2 periods.

    min_weekly_periods (default 0 = "no exemption, repair everyone", same
    default-off convention as quality.py's counters): a teacher whose total
    weekly load is below this threshold is exempt from the II.4 hard gate
    (see engine.py/quality.py) anyway, so their lone sessions are excluded
    from consideration here too -- otherwise this bounded repair loop
    (max_rounds=3, first-improving-move only) wastes attempts on teachers
    who can never violate the gate, leaving fewer rounds for teachers who
    actually count (fix-wave Important #6, 2026-09-03).
    """
    config = config or SchedulingConfig()
    if not getattr(config, "avoid_teacher_lone_periods", True):
        return

    if slot_by_coord is None:
        slot_by_coord = {(s.class_id, s.ts.weekday, s.ts.session, s.ts.period): s for s in inp.slots}

    teacher_totals: dict = defaultdict(int)
    for (tid, _wd, _sess), periods in state.teacher_session_periods.items():
        teacher_totals[tid] += len(periods)

    max_rounds = 3
    for _ in range(max_rounds):
        lone_teacher_sessions = [
            (tid, wd, sess)
            for (tid, wd, sess), periods in list(state.teacher_session_periods.items())
            if len(periods) == 1 and tid > 0
            and (min_weekly_periods <= 0 or teacher_totals[tid] >= min_weekly_periods)
        ]
        if not lone_teacher_sessions:
            break

        improved = False
        for tid, wd_lone, sess_lone in lone_teacher_sessions:
            periods_lone = state.teacher_session_periods.get((tid, wd_lone, sess_lone), [])
            if len(periods_lone) != 1:
                continue
            period_lone = periods_lone[0]

            lone_slot = None
            for slot in inp.slots:
                if (slot.ts.weekday == wd_lone and slot.ts.session == sess_lone
                        and slot.ts.period == period_lone and state.slot_teacher.get(slot.slot_id) == tid):
                    lone_slot = slot
                    break

            if lone_slot is None or state.pinned.get(lone_slot.slot_id):
                continue

            cid_lone = lone_slot.class_id
            sid_lone = state.assigned.get(lone_slot.slot_id)
            if sid_lone in (None, -1):
                continue

            block_n = role_index.block_size.get(sid_lone, 1)
            if block_n > 1 and len(state.placed.get((cid_lone, sid_lone, wd_lone), [])) > 1:
                continue

            # Strategy 1: Evacuate lone_slot to another session where teacher `tid` already teaches
            target_sessions = [
                (wd, sess) for (t, wd, sess), pers in state.teacher_session_periods.items()
                if t == tid and (wd != wd_lone or sess != sess_lone)
                and 1 <= len(pers) < config.max_periods_per_session
            ]

            for wd_tgt, sess_tgt in target_sessions:
                for other_slot in slots_by_class[cid_lone]:
                    if (other_slot.ts.weekday != wd_tgt or other_slot.ts.session != sess_tgt
                            or state.pinned.get(other_slot.slot_id)):
                        continue
                    sid_other = state.assigned.get(other_slot.slot_id)
                    if sid_other in (None, -1):
                        continue
                    tid_other = state.slot_teacher.get(other_slot.slot_id)
                    if tid_other is None or tid_other == tid:
                        continue

                    block_n_other = role_index.block_size.get(sid_other, 1)
                    if block_n_other > 1 and len(state.placed.get((cid_lone, sid_other, wd_tgt), [])) > 1:
                        continue

                    _remove_at(state, lone_slot, role_index)
                    _remove_at(state, other_slot, role_index)

                    feas_lone_at_other = _feasible(
                        cid_lone, other_slot.ts, sid_lone, tid, state, role_index,
                        day_capacity, config, subject_class_allowed_cells
                    )
                    feas_other_at_lone = _feasible(
                        cid_lone, lone_slot.ts, sid_other, tid_other, state, role_index,
                        day_capacity, config, subject_class_allowed_cells
                    )

                    if feas_lone_at_other and feas_other_at_lone:
                        _put_at(state, other_slot, sid_lone, tid, role_index)
                        _put_at(state, lone_slot, sid_other, tid_other, role_index)
                        improved = True
                        break
                    else:
                        _put_at(state, lone_slot, sid_lone, tid, role_index)
                        _put_at(state, other_slot, sid_other, tid_other, role_index)

                if improved:
                    break

            # Strategy 2: Consolidate by moving a period of `tid` in another class `cid_other` to (wd_lone, sess_lone)
            if not improved:
                for cls in inp.classes:
                    cid_other = cls.class_id
                    if cid_other == cid_lone:
                        continue
                    # Find a slot in cid_other where `tid` teaches at another session
                    for other_slot in slots_by_class.get(cid_other, []):
                        if (other_slot.ts.weekday == wd_lone and other_slot.ts.session == sess_lone
                                or state.pinned.get(other_slot.slot_id)):
                            continue
                        if state.slot_teacher.get(other_slot.slot_id) != tid:
                            continue
                        sid_other = state.assigned.get(other_slot.slot_id)
                        if sid_other in (None, -1):
                            continue

                        block_n_other = role_index.block_size.get(sid_other, 1)
                        if block_n_other > 1 and len(state.placed.get((cid_other, sid_other, other_slot.ts.weekday), [])) > 1:
                            continue

                        # Find a target slot in cid_other at (wd_lone, sess_lone)
                        for target_slot in slots_by_class.get(cid_other, []):
                            if (target_slot.ts.weekday != wd_lone or target_slot.ts.session != sess_lone
                                    or state.pinned.get(target_slot.slot_id)):
                                continue
                            sid_target = state.assigned.get(target_slot.slot_id)
                            if sid_target in (None, -1):
                                continue
                            tid_target = state.slot_teacher.get(target_slot.slot_id)
                            if tid_target is None or tid_target == tid:
                                continue

                            block_n_target = role_index.block_size.get(sid_target, 1)
                            if block_n_target > 1 and len(state.placed.get((cid_other, sid_target, wd_lone), [])) > 1:
                                continue

                            _remove_at(state, other_slot, role_index)
                            _remove_at(state, target_slot, role_index)

                            feas_other_at_target = _feasible(
                                cid_other, target_slot.ts, sid_other, tid, state, role_index,
                                day_capacity, config, subject_class_allowed_cells
                            )
                            feas_target_at_other = _feasible(
                                cid_other, other_slot.ts, sid_target, tid_target, state, role_index,
                                day_capacity, config, subject_class_allowed_cells
                            )

                            if feas_other_at_target and feas_target_at_other:
                                _put_at(state, target_slot, sid_other, tid, role_index)
                                _put_at(state, other_slot, sid_target, tid_target, role_index)
                                improved = True
                                break
                            else:
                                _put_at(state, other_slot, sid_other, tid, role_index)
                                _put_at(state, target_slot, sid_target, tid_target, role_index)

                        if improved:
                            break
                    if improved:
                        break

        if not improved:
            break


def _repair_teacher_missing_mandatory_mornings(inp, state: _State, role_index,
                                                assigned_teacher: dict, slots_by_class: dict,
                                                day_capacity: Optional[dict] = None,
                                                config: Optional[SchedulingConfig] = None,
                                                subject_class_allowed_cells: Optional[dict] = None,
                                                slot_by_coord: Optional[dict] = None,
                                                mandatory_mornings: tuple = (2, 5, 6),
                                                min_weekly_periods: int = 10) -> None:
    """Finds every teacher whose total weekly load is >= min_weekly_periods (the
    II.3 hard-gate threshold -- see quality.py:_count_teacher_missing_mandatory_mornings)
    and who has ZERO periods on one of the mandatory mornings (mandatory_mornings,
    default Mon/Thu/Fri), and attempts to fill it by swapping ONE of that teacher's
    existing periods on a NON-mandatory weekday into the missing mandatory morning
    slot -- a same-class swap with whoever else is teaching that (weekday, session)
    cell, mirroring _repair_teacher_lone_sessions's Strategy 1 (Evacuate).

    After a successful swap, the destination slot is PINNED. Rationale: the
    swapped-in period can be the teacher's only period in that (weekday, session)
    -- a fresh "lone session" by II.4's definition if the teacher's total load is
    also >= the II.4 threshold -- and _repair_teacher_lone_sessions (which already
    skips pinned slots at both the lone-slot and target-slot checks) runs right
    after this one in engine.py; without the pin it would be free to evacuate the
    exact period this repair just placed, silently undoing the II.3 fix.

    A straight 1-for-1 swap never changes either teacher's total weekly period
    count, so teacher_totals (computed once up front, same convention as the
    sibling function above) stays valid for the whole repair pass.
    """
    config = config or SchedulingConfig()

    teacher_totals: dict = defaultdict(int)
    for (tid, _wd, _sess), periods in state.teacher_session_periods.items():
        teacher_totals[tid] += len(periods)

    max_rounds = 3
    for _ in range(max_rounds):
        missing_pairs = [
            (tid, wd)
            for tid, total in teacher_totals.items()
            if tid > 0 and total >= min_weekly_periods
            for wd in mandatory_mornings
            if len(state.teacher_session_periods.get((tid, wd, "S"), [])) == 0
        ]
        if not missing_pairs:
            break

        improved = False
        for tid, wd_missing in missing_pairs:
            source_candidates = [
                (wd_src, period_src)
                for (t, wd_src, sess_src), periods in list(state.teacher_session_periods.items())
                if t == tid and sess_src == "S" and wd_src not in mandatory_mornings
                for period_src in periods
            ]

            for wd_src, period_src in source_candidates:
                source_slot = None
                for slot in inp.slots:
                    if (slot.ts.weekday == wd_src and slot.ts.session == "S"
                            and slot.ts.period == period_src and state.slot_teacher.get(slot.slot_id) == tid):
                        source_slot = slot
                        break

                if source_slot is None or state.pinned.get(source_slot.slot_id):
                    continue

                cid = source_slot.class_id
                sid_src = state.assigned.get(source_slot.slot_id)
                if sid_src in (None, -1):
                    continue

                block_n_src = role_index.block_size.get(sid_src, 1)
                if block_n_src > 1 and len(state.placed.get((cid, sid_src, wd_src), [])) > 1:
                    continue

                for dest_slot in slots_by_class[cid]:
                    if (dest_slot.ts.weekday != wd_missing or dest_slot.ts.session != "S"
                            or state.pinned.get(dest_slot.slot_id)):
                        continue
                    sid_dst = state.assigned.get(dest_slot.slot_id)
                    if sid_dst in (None, -1):
                        continue
                    tid_dst = state.slot_teacher.get(dest_slot.slot_id)
                    if tid_dst is None or tid_dst == tid:
                        continue

                    block_n_dst = role_index.block_size.get(sid_dst, 1)
                    if block_n_dst > 1 and len(state.placed.get((cid, sid_dst, wd_missing), [])) > 1:
                        continue

                    _remove_at(state, source_slot, role_index)
                    _remove_at(state, dest_slot, role_index)

                    feas_src_at_dest = _feasible(
                        cid, dest_slot.ts, sid_src, tid, state, role_index,
                        day_capacity, config, subject_class_allowed_cells
                    )
                    feas_dst_at_src = _feasible(
                        cid, source_slot.ts, sid_dst, tid_dst, state, role_index,
                        day_capacity, config, subject_class_allowed_cells
                    )

                    if feas_src_at_dest and feas_dst_at_src:
                        _put_at(state, dest_slot, sid_src, tid, role_index)
                        _put_at(state, source_slot, sid_dst, tid_dst, role_index)
                        state.pinned[dest_slot.slot_id] = True
                        improved = True
                        break
                    else:
                        _put_at(state, source_slot, sid_src, tid, role_index)
                        _put_at(state, dest_slot, sid_dst, tid_dst, role_index)

                if improved:
                    break
            if improved:
                break

        if not improved:
            break
