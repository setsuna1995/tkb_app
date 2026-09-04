"""Block placement heuristics and post-pass repair for multi-period subjects."""
from __future__ import annotations

from typing import Optional, Tuple
from core import frame as frame_mod
from core.models import SchedulingConfig, Slot, WEEKDAYS
from core.scheduler.feasibility import _feasible
from core.scheduler.heuristics import _pick_best_simple
from core.scheduler.placement import _put_at, _remove_at
from core.scheduler.state import _State


def _merge_one_block_period(class_id: int, subject_id: int, wd_from: int, wd_to: int,
                             state: _State, role_index, subjects: list, assigned_teacher: dict,
                             slot_by_coord: dict, day_capacity: Optional[dict],
                             config: Optional[SchedulingConfig],
                             subject_class_allowed_cells: Optional[dict]) -> bool:
    from_positions = state.placed[(class_id, subject_id, wd_from)]
    to_positions = state.placed[(class_id, subject_id, wd_to)]
    if not from_positions or not to_positions:
        return False
    session_from, period_from = from_positions[-1]
    session_to = to_positions[0][0]
    to_periods = sorted(p_period for _p_session, p_period in to_positions)
    source = slot_by_coord[(class_id, wd_from, session_from, period_from)]
    teacher_id = assigned_teacher[(subject_id, class_id)]
    source_has_later_content = any(
        state.occupied.get((class_id, wd_from, session_from, p), False)
        for p in range(period_from + 1, frame_mod.MAX_PERIODS_PER_SESSION + 1)
    )

    for target_period in (to_periods[-1] + 1, to_periods[0] - 1):
        target = slot_by_coord.get((class_id, wd_to, session_to, target_period))
        if target is None:
            continue
        occupant = state.assigned.get(target.slot_id)
        was_slack = occupant == -1
        displaced_subject, displaced_teacher = (None, None)
        if was_slack:
            state.assigned[target.slot_id] = None
            state.rem_slot_count[class_id] += 1
        elif occupant is not None:
            displaced_subject, displaced_teacher = _remove_at(state, target, role_index)
        _remove_at(state, source, role_index)
        if _feasible(class_id, target.ts, subject_id, teacher_id, state, role_index, day_capacity, config,
                      subject_class_allowed_cells):
            _put_at(state, target, subject_id, teacher_id, role_index)
            if displaced_subject is None:
                pick = _pick_best_simple(class_id, source, state, role_index, subjects, assigned_teacher,
                                          day_capacity, config, subject_class_allowed_cells)
                if pick is not None:
                    _put_at(state, source, pick[0], pick[1], role_index)
                    return True
                if (not source_has_later_content
                        and state.rem_slot_count[class_id] > state.rem_need_count[class_id]):
                    state.assigned[source.slot_id] = -1
                    state.rem_slot_count[class_id] -= 1
                    return True
                _remove_at(state, target, role_index)
                if was_slack:
                    state.assigned[target.slot_id] = -1
                    state.rem_slot_count[class_id] -= 1
                _put_at(state, source, subject_id, teacher_id, role_index)
                return False
            if _feasible(class_id, source.ts, displaced_subject, displaced_teacher, state, role_index,
                          day_capacity, config, subject_class_allowed_cells):
                _put_at(state, source, displaced_subject, displaced_teacher, role_index)
                return True
            pick = _pick_best_simple(class_id, source, state, role_index, subjects, assigned_teacher,
                                      day_capacity, config, subject_class_allowed_cells)
            if pick is not None:
                _put_at(state, source, pick[0], pick[1], role_index)
                return True
            if not source_has_later_content and state.rem_slot_count[class_id] > state.rem_need_count[class_id]:
                state.assigned[source.slot_id] = -1
                state.rem_slot_count[class_id] -= 1
                return True
            _remove_at(state, target, role_index)
            _put_at(state, source, subject_id, teacher_id, role_index)
            _put_at(state, target, displaced_subject, displaced_teacher, role_index)
            return False
        _put_at(state, source, subject_id, teacher_id, role_index)
        if was_slack:
            state.assigned[target.slot_id] = -1
            state.rem_slot_count[class_id] -= 1
        elif displaced_subject is not None:
            _put_at(state, target, displaced_subject, displaced_teacher, role_index)
    return False


def _block_partial_state(state: _State, class_id: int, subject_id: int, block_n: int,
                        is_single_pair: bool = False) -> Tuple[int, int, list]:
    total_placed = sum(len(state.placed[(class_id, subject_id, wd)]) for wd in WEEKDAYS)
    if is_single_pair:
        pair_days = [wd for wd in WEEKDAYS if len(state.placed[(class_id, subject_id, wd)]) >= block_n]
        partial_days = [wd for wd in WEEKDAYS if len(state.placed[(class_id, subject_id, wd)]) == 1]
        if len(pair_days) >= 1:
            allowed_partial_days = max(0, total_placed - 2)
        else:
            allowed_partial_days = max(0, total_placed - 2) - 1
        return total_placed, allowed_partial_days, partial_days
    else:
        allowed_partial_days = 1 if total_placed % block_n else 0
        partial_days = [wd for wd in WEEKDAYS
                         if 0 < len(state.placed[(class_id, subject_id, wd)]) < block_n]
        return total_placed, allowed_partial_days, partial_days


def _repair_unpaired_blocks(inp, state: _State, role_index,
                             assigned_teacher: dict, slot_by_coord: dict,
                             day_capacity: Optional[dict], config: Optional[SchedulingConfig] = None,
                             subject_class_allowed_cells: Optional[dict] = None) -> None:
    for cls in inp.classes:
        class_id = cls.class_id
        for subject_id, block_n in role_index.block_size.items():
            if block_n < 2:
                continue
            is_single_pair = bool(getattr(role_index, "single_pair_ids", None) and subject_id in role_index.single_pair_ids)
            total_placed, allowed_partial_days, partial_days = _block_partial_state(
                state, class_id, subject_id, block_n, is_single_pair=is_single_pair)
            if total_placed == 0:
                continue
            max_iterations = len(WEEKDAYS) * block_n
            iterations = 0
            while len(partial_days) > allowed_partial_days and iterations < max_iterations:
                iterations += 1
                merged = False
                for wd_a in partial_days:
                    for wd_b in partial_days:
                        if wd_b == wd_a:
                            continue
                        if len(state.placed[(class_id, subject_id, wd_b)]) >= block_n:
                            continue
                        if _merge_one_block_period(class_id, subject_id, wd_a, wd_b, state, role_index,
                                                    inp.subjects, assigned_teacher, slot_by_coord,
                                                    day_capacity, config, subject_class_allowed_cells):
                            merged = True
                            break
                    if merged:
                        break
                if not merged:
                    break
                _total, _allowed, partial_days = _block_partial_state(
                    state, class_id, subject_id, block_n, is_single_pair=is_single_pair)


def _has_unpaired_block(inp, state: _State, role_index) -> bool:
    for cls in inp.classes:
        class_id = cls.class_id
        for subject_id, block_n in role_index.block_size.items():
            if block_n < 2:
                continue
            is_single_pair = bool(getattr(role_index, "single_pair_ids", None) and subject_id in role_index.single_pair_ids)
            total_placed, allowed_partial_days, partial_days = _block_partial_state(
                state, class_id, subject_id, block_n, is_single_pair=is_single_pair)
            if total_placed == 0:
                continue
            if len(partial_days) > allowed_partial_days:
                return True
    return False


def _try_place_block_atomically(class_id: int, slot: Slot, state: _State, role_index,
                                  subjects: list, assigned_teacher: dict,
                                  day_capacity: Optional[dict], config: Optional[SchedulingConfig],
                                  subject_class_allowed_cells: Optional[dict],
                                  slot_by_coord: dict) -> bool:
    ts = slot.ts
    candidates = []
    for subj in subjects:
        block_n = role_index.block_size.get(subj.subject_id, 1)
        if block_n < 2:
            continue
        if getattr(role_index, "single_pair_ids", None) and subj.subject_id in role_index.single_pair_ids:
            if any(len(state.placed[(class_id, subj.subject_id, wd)]) >= 2 for wd in WEEKDAYS):
                continue
        key = (subj.subject_id, class_id)
        remaining = state.remaining_need.get(key, 0)
        if remaining < block_n:
            continue
        if state.placed[(class_id, subj.subject_id, ts.weekday)]:
            continue
        # HĐTN may share the SHL day (see heuristics.py) -- no exclusion here either.
        teacher_id = assigned_teacher[key]
        if not _feasible(class_id, ts, subj.subject_id, teacher_id, state, role_index, day_capacity, config,
                          subject_class_allowed_cells):
            continue
        candidates.append((subj.subject_id, teacher_id, block_n))
    if not candidates:
        return False
    candidates.sort(key=lambda c: (
        0 if slot.old_subject_id == c[0] else 1,
        -state.remaining_need.get((c[0], class_id), 0),
    ))
    for subject_id, teacher_id, block_n in candidates:
        window = [slot]
        ok = True
        for offset in range(1, block_n):
            next_slot = slot_by_coord.get((class_id, ts.weekday, ts.session, ts.period + offset))
            if next_slot is None or state.assigned.get(next_slot.slot_id) is not None:
                ok = False
                break
            window.append(next_slot)
        if not ok:
            continue
        placed_so_far = []
        for w_slot in window:
            if _feasible(class_id, w_slot.ts, subject_id, teacher_id, state, role_index, day_capacity, config,
                          subject_class_allowed_cells):
                _put_at(state, w_slot, subject_id, teacher_id, role_index)
                placed_so_far.append(w_slot)
            else:
                ok = False
                break
        if ok:
            return True
        for w_slot in reversed(placed_so_far):
            _remove_at(state, w_slot, role_index)
    return False
