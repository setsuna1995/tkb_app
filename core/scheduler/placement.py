"""Slot assignment and removal primitives for the scheduling solver."""
from __future__ import annotations

from typing import Tuple
from core.models import SchedulingInput, Slot
from core.scheduler.state import _State


def _build_effective_assigned_teacher(inp: SchedulingInput) -> dict:
    """Fill in a synthetic, per-(subject,class)-unique teacher id for any cell
    PhanCong left blank -- mirrors the VBA's '?class#subject' placeholder so the
    subject can still be scheduled without creating a fake cross-class conflict.
    """
    effective = dict(inp.assigned_teacher)
    for subj in inp.subjects:
        for cls in inp.classes:
            key = (subj.subject_id, cls.class_id)
            if inp.need.get(key, 0) > 0 and key not in effective:
                effective[key] = -(subj.subject_id * 100_000 + cls.class_id)
    return effective


def _put_at(state: _State, slot: Slot, subject_id: int, teacher_id: int, role_index) -> None:
    ts = slot.ts
    state.assigned[slot.slot_id] = subject_id
    state.slot_teacher[slot.slot_id] = teacher_id
    state.remaining_need[(subject_id, slot.class_id)] -= 1
    state.teacher_rem_need[teacher_id] -= 1
    state.busy.add((teacher_id, ts.ts_id))
    state.session_count[(teacher_id, ts.weekday, ts.session)] += 1
    state.teacher_day_count[(teacher_id, ts.weekday)] += 1
    state.teacher_session_periods[(teacher_id, ts.weekday, ts.session)].append(ts.period)
    if ts.session == "C":
        state.teacher_week_afternoon_count[teacher_id] += 1
    state.placed[(slot.class_id, subject_id, ts.weekday)].append((ts.session, ts.period))
    state.day_count[(slot.class_id, ts.weekday)] += 1
    state.occupied[(slot.class_id, ts.weekday, ts.session, ts.period)] = True
    if subject_id in role_index.heavy_ids:
        state.heavy_at[(slot.class_id, ts.weekday, ts.session, ts.period)] = True
        state.session_heavy_count[(slot.class_id, ts.weekday, ts.session)] += 1
    state.rem_need_count[slot.class_id] -= 1
    state.rem_slot_count[slot.class_id] -= 1


def _remove_at(state: _State, slot: Slot, role_index) -> Tuple[int, int]:
    subject_id = state.assigned[slot.slot_id]
    teacher_id = state.slot_teacher.pop(slot.slot_id)
    ts = slot.ts
    state.assigned[slot.slot_id] = None
    state.remaining_need[(subject_id, slot.class_id)] += 1
    state.teacher_rem_need[teacher_id] += 1
    state.busy.discard((teacher_id, ts.ts_id))
    state.session_count[(teacher_id, ts.weekday, ts.session)] -= 1
    state.teacher_day_count[(teacher_id, ts.weekday)] -= 1
    state.teacher_session_periods[(teacher_id, ts.weekday, ts.session)].remove(ts.period)
    if ts.session == "C":
        state.teacher_week_afternoon_count[teacher_id] -= 1
    state.placed[(slot.class_id, subject_id, ts.weekday)].remove((ts.session, ts.period))
    state.day_count[(slot.class_id, ts.weekday)] -= 1
    state.occupied[(slot.class_id, ts.weekday, ts.session, ts.period)] = False
    if subject_id in role_index.heavy_ids:
        state.heavy_at[(slot.class_id, ts.weekday, ts.session, ts.period)] = False
        state.session_heavy_count[(slot.class_id, ts.weekday, ts.session)] -= 1
    state.rem_need_count[slot.class_id] += 1
    state.rem_slot_count[slot.class_id] += 1
    return subject_id, teacher_id
