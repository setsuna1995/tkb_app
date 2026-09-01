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
