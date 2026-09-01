"""Curriculum quotas, assignments (PhanCong), and periods per week (SoTiet)."""
from __future__ import annotations

import sqlite3
from typing import Optional
from data.repositories.config import get_meta, set_meta
from data.repositories.entities import list_teachers

DEFAULT_BASE_CAP = 19
DEFAULT_MIN_FLOOR = 16


def get_base_cap(conn: sqlite3.Connection) -> int:
    val = get_meta(conn, "base_cap")
    try:
        return int(val) if val is not None and str(val).strip() != "" else DEFAULT_BASE_CAP
    except (ValueError, TypeError):
        return DEFAULT_BASE_CAP


def set_base_cap(conn: sqlite3.Connection, value: int) -> None:
    set_meta(conn, "base_cap", str(int(value)))


def get_min_floor(conn: sqlite3.Connection) -> int:
    val = get_meta(conn, "min_floor")
    try:
        return int(val) if val is not None and str(val).strip() != "" else DEFAULT_MIN_FLOOR
    except (ValueError, TypeError):
        return DEFAULT_MIN_FLOOR


def set_min_floor(conn: sqlite3.Connection, value: int) -> None:
    set_meta(conn, "min_floor", str(int(value)))


def get_role_reduction(conn: sqlite3.Connection) -> dict:
    rows = conn.execute("SELECT role_name, reduction FROM role_reduction").fetchall()
    return {r["role_name"]: r["reduction"] for r in rows}


def set_role_reduction(conn: sqlite3.Connection, role_name: str, reduction: int) -> None:
    conn.execute(
        "INSERT INTO role_reduction (role_name, reduction) VALUES (?, ?) "
        "ON CONFLICT(role_name) DO UPDATE SET reduction=excluded.reduction",
        (role_name, reduction),
    )
    conn.commit()


def get_assignments(conn: sqlite3.Connection) -> dict:
    rows = conn.execute("SELECT subject_id, class_id, teacher_id FROM assignments").fetchall()
    return {(r["subject_id"], r["class_id"]): r["teacher_id"] for r in rows}


def set_assignment(conn: sqlite3.Connection, subject_id: int, class_id: int, teacher_id: Optional[int]) -> None:
    conn.execute(
        "INSERT INTO assignments (subject_id, class_id, teacher_id) VALUES (?, ?, ?) "
        "ON CONFLICT(subject_id, class_id) DO UPDATE SET teacher_id=excluded.teacher_id",
        (subject_id, class_id, teacher_id),
    )
    conn.commit()


def get_periods_per_week(conn: sqlite3.Connection) -> dict:
    rows = conn.execute("SELECT subject_id, class_id, parity, periods FROM periods_per_week").fetchall()
    return {(r["subject_id"], r["class_id"], r["parity"]): r["periods"] for r in rows}


def set_periods_per_week(conn: sqlite3.Connection, subject_id: int, class_id: int, parity: str, periods: int) -> None:
    conn.execute(
        "INSERT INTO periods_per_week (subject_id, class_id, parity, periods) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(subject_id, class_id, parity) DO UPDATE SET periods=excluded.periods",
        (subject_id, class_id, parity, periods),
    )
    conn.commit()


def get_teacher_quota_view(conn: sqlite3.Connection, parity: str) -> list:
    """Recreates DinhMuc_GV: cap = trần chuẩn - reduction(role);
    load = sum(assignments x periods_per_week) cho tuần `parity`.
    """
    from data.repositories.entities import list_classes, list_subjects
    base_cap = get_base_cap(conn)
    min_floor = get_min_floor(conn)
    reductions = get_role_reduction(conn)
    teachers = list_teachers(conn)
    classes = list_classes(conn)
    subjects = list_subjects(conn)
    class_map = {c.class_id: c.name for c in classes}
    subject_map = {s.subject_id: s.name for s in subjects}
    ppw = get_periods_per_week(conn)
    assignments = get_assignments(conn)

    loads_by_parity = {"C": {}, "L": {}}
    teacher_assignments = {}
    for (subject_id, class_id), teacher_id in assignments.items():
        if teacher_id is None:
            continue
        c_periods = ppw.get((subject_id, class_id, "C"), 0)
        l_periods = ppw.get((subject_id, class_id, "L"), 0)
        loads_by_parity["C"][teacher_id] = loads_by_parity["C"].get(teacher_id, 0) + c_periods
        loads_by_parity["L"][teacher_id] = loads_by_parity["L"].get(teacher_id, 0) + l_periods
        if teacher_id not in teacher_assignments:
            teacher_assignments[teacher_id] = []
        teacher_assignments[teacher_id].append({
            "class_id": class_id,
            "class_name": class_map.get(class_id, f"Lớp #{class_id}"),
            "subject_id": subject_id,
            "subject_name": subject_map.get(subject_id, f"Môn #{subject_id}"),
            "periods_chan": c_periods,
            "periods_le": l_periods,
        })

    view = []
    for t in teachers:
        reduction = t.reduction_override if t.reduction_override is not None else reductions.get(t.role, 0)
        cap = base_cap - reduction
        load_c = loads_by_parity["C"].get(t.teacher_id, 0)
        load_l = loads_by_parity["L"].get(t.teacher_id, 0)
        load_avg = (load_c + load_l) / 2
        load_current = load_c if parity == "C" else load_l
        view.append({
            "teacher_id": t.teacher_id, "name": t.name, "role": t.role,
            "reduction": reduction, "cap": cap, "load": load_current,
            "load_chan": load_c, "load_le": load_l, "load_avg": load_avg,
            "over": load_avg - cap,
            "over_current": load_current - cap,
            "under": min_floor - (load_avg + reduction),
            "under_current": min_floor - (load_current + reduction),
            "must_monday": t.must_monday, "is_gvcn": t.is_gvcn,
            "assignments": teacher_assignments.get(t.teacher_id, []),
        })
    return view


def get_teacher_caps(conn: sqlite3.Connection) -> dict:
    base_cap = get_base_cap(conn)
    reductions = get_role_reduction(conn)
    return {
        t.teacher_id: base_cap - (t.reduction_override if t.reduction_override is not None else reductions.get(t.role, 0))
        for t in list_teachers(conn)
    }
