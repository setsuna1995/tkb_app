"""Composite builder that assembles a core.models.SchedulingInput from database state."""
from __future__ import annotations

import sqlite3
from core import frame as frame_mod
from core.models import SchedulingInput, Slot, TimeSlot, WEEKDAYS
from data.repositories.config import get_scheduling_config
from data.repositories.constraints import (
    get_all_class_allowed_cells, get_all_frame_templates,
    get_subject_class_allowed_cells, list_unavailability,
)
from data.repositories.curriculum import get_assignments, get_periods_per_week
from data.repositories.entities import list_classes, list_subjects, list_teachers
from data.repositories.runs import get_tkb_nhap


def _canonical_timeslots() -> list[TimeSlot]:
    result = []
    ts_id = 0
    for wd in WEEKDAYS + (8,):
        for session in ("S", "C"):
            for period in range(1, 6):
                ts_id += 1
                result.append(TimeSlot(ts_id, wd, session, period))
    return result


def _weekday_matches(row_weekday: str, ts_weekday: int) -> bool:
    if row_weekday == "*":
        return True
    if row_weekday == "CN":
        return ts_weekday == 8
    return str(ts_weekday) == str(row_weekday)


def build_scheduling_input(conn: sqlite3.Connection, parity: str, seed: int = 0,
                            extra_kep_ids: frozenset = frozenset(),
                            hdtn_thematic_week: bool = False) -> SchedulingInput:
    classes = list_classes(conn)
    subjects = list_subjects(conn)
    teachers = list_teachers(conn)
    config = get_scheduling_config(conn)
    subject_class_allowed_cells = get_subject_class_allowed_cells(conn)

    need = {(s, c): p for (s, c, par), p in get_periods_per_week(conn).items() if par == parity and p > 0}
    assigned_teacher = {key: tid for key, tid in get_assignments(conn).items() if tid is not None}

    all_ts = _canonical_timeslots()
    ts_by_key = {(t.weekday, t.session, t.period): t for t in all_ts}

    tkb_nhap = get_tkb_nhap(conn)
    frame_templates = get_all_frame_templates(conn)
    all_class_allowed_cells = get_all_class_allowed_cells(conn)

    slots = []
    used_ts_ids = set()
    slot_id = 0
    for cls in classes:
        allowed_cells = all_class_allowed_cells.get(cls.class_id)
        if allowed_cells:
            # Generate from explicit allowed cells
            for (wd, session, period) in sorted(allowed_cells):
                if (wd, session, period) not in ts_by_key:
                    continue
                ts = ts_by_key[(wd, session, period)]
                used_ts_ids.add(ts.ts_id)
                slot_id += 1
                old_subject = tkb_nhap.get((cls.class_id, wd, session, period))
                slots.append(Slot(slot_id, cls.class_id, ts, old_subject_id=old_subject))
        else:
            # Fallback to frame_template logic
            morning, afternoon, study_sunday, allow_saturday, short_weekday, short_morning, short_afternoon = \
                frame_templates.get(cls.class_id, (5, 3, 0, 0, None, None, None))
            for (wd, session, period) in frame_mod.active_cells(
                morning, afternoon, bool(study_sunday), bool(allow_saturday),
                short_weekday, short_morning, short_afternoon,
                reserved_off_weekdays_chieu=config.reserved_off_weekdays_chieu,
            ):
                if (wd, session, period) not in ts_by_key:
                    continue
                ts = ts_by_key[(wd, session, period)]
                used_ts_ids.add(ts.ts_id)
                slot_id += 1
                old_subject = tkb_nhap.get((cls.class_id, wd, session, period))
                slots.append(Slot(slot_id, cls.class_id, ts, old_subject_id=old_subject))

    timeslots = sorted((t for t in all_ts if t.ts_id in used_ts_ids), key=lambda t: t.order_key)

    ban_busy = set()
    for row in list_unavailability(conn):
        for ts in timeslots:
            if (_weekday_matches(row["weekday"], ts.weekday)
                    and (row["session"] == "*" or row["session"] == ts.session)
                    and (row["period"] == "*" or str(row["period"]) == str(ts.period))):
                ban_busy.add((row["teacher_id"], ts.ts_id))

    return SchedulingInput(
        classes=classes, subjects=subjects, teachers=teachers, need=need,
        assigned_teacher=assigned_teacher, ban_busy=ban_busy,
        slots=slots, timeslots=timeslots, seed=seed,
        extra_kep_ids=extra_kep_ids, hdtn_thematic_week=hdtn_thematic_week, config=config,
        subject_class_allowed_cells=subject_class_allowed_cells,
    )
