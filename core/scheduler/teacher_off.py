"""Assignment of weekly off-session slots for teachers."""
from __future__ import annotations

import random
from collections import defaultdict
from typing import Optional
from core.models import WEEKDAYS
from core.scheduler.constants import FORBIDDEN_OFF_CELLS


def _assign_off_slots(teacher_ids: set, teachers_by_id: dict, rng: random.Random,
                       gvcn_shl_cell: Optional[dict] = None,
                       off_slot_count: int = 1,
                       forbidden_off_cells: frozenset = FORBIDDEN_OFF_CELLS,
                       mandatory_morning_weekdays: tuple = (2, 5, 6)) -> dict:
    """Pick each teacher's off-slot(s) for the week: off_slot_count (weekday, session)
    pairs, each on a DIFFERENT weekday when possible (never 2 off-sessions on the
    same day, i.e. never a full day off), drawn from every cell except
    FORBIDDEN_OFF_CELLS (plus the teacher's own must_monday/is_gvcn exclusions and mandatory_morning_weekdays).
    """
    gvcn_shl_cell = gvcn_shl_cell or {}
    gv_off_slots = {}
    mandatory_mornings = set(mandatory_morning_weekdays)
    for tid in teacher_ids:
        t = teachers_by_id.get(tid)
        must_monday = t.must_monday if t else False
        is_gvcn = t.is_gvcn if t else False
        is_tpt_or_bgh = bool(t and any(k in (t.role or "") for k in ["TPT", "Tổng phụ trách", "Hiệu trưởng", "Phó hiệu trưởng"]))
        forbidden = set(forbidden_off_cells) | {(wd, "S") for wd in mandatory_mornings}
        if is_tpt_or_bgh:
            forbidden |= {(wd, "S") for wd in range(2, 8)}
        if must_monday:
            forbidden.add((2, "C"))
        if is_gvcn:
            forbidden.add(gvcn_shl_cell.get(tid, (7, "C")))

        pinned_cells = set()
        pinned_weekdays = set()
        if t and t.pinned_full_day_off is not None:
            wd = t.pinned_full_day_off
            if wd in WEEKDAYS and (wd, "S") not in forbidden and (wd, "C") not in forbidden:
                pinned_cells |= {(wd, "S"), (wd, "C")}
                pinned_weekdays.add(wd)
        if t and t.pinned_afternoon_off is not None:
            wd = t.pinned_afternoon_off
            if wd in WEEKDAYS and (wd, "C") not in forbidden and wd not in pinned_weekdays:
                pinned_cells.add((wd, "C"))
                pinned_weekdays.add(wd)

        effective_count = t.off_sessions_override if (t and t.off_sessions_override is not None) else off_slot_count
        remaining_count = max(0, effective_count - len(pinned_cells))

        by_weekday = defaultdict(list)
        for wd in (2, 3, 4, 5, 6, 7):
            if wd in pinned_weekdays:
                continue
            for session in ("S", "C"):
                if (wd, session) not in forbidden:
                    by_weekday[wd].append(session)
            eligible_weekdays = [wd for wd, sessions in by_weekday.items() if sessions]

        if len(eligible_weekdays) >= remaining_count:
            chosen_weekdays = rng.sample(eligible_weekdays, remaining_count)
            gv_off_slots[tid] = pinned_cells | {(wd, rng.choice(by_weekday[wd])) for wd in chosen_weekdays}
        else:
            all_eligible_cells = [(wd, s) for wd in eligible_weekdays for s in by_weekday[wd]]
            picks = rng.sample(all_eligible_cells, min(remaining_count, len(all_eligible_cells)))
            gv_off_slots[tid] = pinned_cells | set(picks)
    return gv_off_slots
