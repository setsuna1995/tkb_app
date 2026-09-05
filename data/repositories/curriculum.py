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


def get_weekly_curriculum(conn: sqlite3.Connection, class_id: Optional[int] = None, week_no: Optional[int] = None) -> dict[tuple[int, int, int], int]:
    query = "SELECT subject_id, class_id, week_no, periods FROM weekly_curriculum WHERE 1=1"
    params = []
    if class_id is not None:
        query += " AND class_id = ?"
        params.append(class_id)
    if week_no is not None:
        query += " AND week_no = ?"
        params.append(week_no)
    rows = conn.execute(query, params).fetchall()
    return {(r["subject_id"], r["class_id"], r["week_no"]): r["periods"] for r in rows}


def set_weekly_curriculum(conn: sqlite3.Connection, subject_id: int, class_id: int, week_no: int, periods: int) -> None:
    conn.execute(
        "INSERT INTO weekly_curriculum (subject_id, class_id, week_no, periods) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(subject_id, class_id, week_no) DO UPDATE SET periods=excluded.periods",
        (subject_id, class_id, week_no, periods),
    )
    conn.commit()


def bulk_set_weekly_curriculum(conn: sqlite3.Connection, entries: list[tuple[int, int, int, int]]) -> None:
    conn.executemany(
        "INSERT INTO weekly_curriculum (subject_id, class_id, week_no, periods) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(subject_id, class_id, week_no) DO UPDATE SET periods=excluded.periods",
        entries,
    )
    conn.commit()


def list_configured_weeks(conn: sqlite3.Connection) -> list[int]:
    rows = conn.execute("SELECT DISTINCT week_no FROM weekly_curriculum ORDER BY week_no").fetchall()
    return [r["week_no"] for r in rows]


def get_periods_for_week(conn: sqlite3.Connection, week_no: int, parity: Optional[str] = None) -> dict[tuple[int, int], int]:
    """Returns {(subject_id, class_id): periods} for the specified week_no.
    If weekly_curriculum has entries for week_no, returns those.
    Otherwise, gracefully falls back to periods_per_week for the matching parity (even -> 'C', odd -> 'L').
    """
    rows = conn.execute(
        "SELECT subject_id, class_id, periods FROM weekly_curriculum WHERE week_no = ?",
        (week_no,),
    ).fetchall()
    if rows:
        return {(r["subject_id"], r["class_id"]): r["periods"] for r in rows}

    effective_parity = parity if parity is not None else ("C" if week_no % 2 == 0 else "L")
    ppw = get_periods_per_week(conn)
    return {(s, c): p for (s, c, par), p in ppw.items() if par == effective_parity}


def get_teacher_quota_view(conn: sqlite3.Connection, parity: str = "C", week_no: Optional[int] = None) -> list:
    """Recreates DinhMuc_GV: cap = trần chuẩn - reduction(role);
    Calculates detailed 35-week workloads, semester averages (HK1, HK2),
    full-year averages, peak/lowest weeks, and week-specific loads.
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
    all_weekly = get_weekly_curriculum(conn)

    # Pre-calculate period lookup for all 35 weeks for every (s, c)
    # (s, c, w) -> periods
    period_cache_35 = {}
    for (s_id, c_id) in assignments.keys():
        for w in range(1, 36):
            if (s_id, c_id, w) in all_weekly:
                period_cache_35[(s_id, c_id, w)] = all_weekly[(s_id, c_id, w)]
            else:
                par = "C" if w % 2 == 0 else "L"
                period_cache_35[(s_id, c_id, w)] = ppw.get((s_id, c_id, par), 0)

    loads_by_parity = {"C": {}, "L": {}}
    loads_35_by_teacher = {t.teacher_id: {w: 0 for w in range(1, 36)} for t in teachers}
    teacher_assignments = {}

    for (subject_id, class_id), teacher_id in assignments.items():
        if teacher_id is None:
            continue
        c_periods = ppw.get((subject_id, class_id, "C"), 0)
        l_periods = ppw.get((subject_id, class_id, "L"), 0)
        loads_by_parity["C"][teacher_id] = loads_by_parity["C"].get(teacher_id, 0) + c_periods
        loads_by_parity["L"][teacher_id] = loads_by_parity["L"].get(teacher_id, 0) + l_periods

        if teacher_id not in loads_35_by_teacher:
            loads_35_by_teacher[teacher_id] = {w: 0 for w in range(1, 36)}

        asgn_weekly = {}
        for w in range(1, 36):
            p_w = period_cache_35.get((subject_id, class_id, w), 0)
            loads_35_by_teacher[teacher_id][w] += p_w
            asgn_weekly[w] = p_w

        w_period = asgn_weekly.get(week_no, c_periods if parity == "C" else l_periods) if week_no is not None else (c_periods if parity == "C" else l_periods)

        if teacher_id not in teacher_assignments:
            teacher_assignments[teacher_id] = []
        teacher_assignments[teacher_id].append({
            "class_id": class_id,
            "class_name": class_map.get(class_id, f"Lớp #{class_id}"),
            "subject_id": subject_id,
            "subject_name": subject_map.get(subject_id, f"Môn #{subject_id}"),
            "periods_chan": c_periods,
            "periods_le": l_periods,
            "periods_week": w_period,
            "weekly_periods": asgn_weekly,
        })

    view = []
    for t in teachers:
        if t.reduction_override is not None:
            reduction = t.reduction_override
            cap = max(0, base_cap - reduction)
            floor = max(0, min_floor - reduction)
        else:
            role_str = (t.role or "").strip()
            role_lower = role_str.lower()
            if "hiệu trưởng" in role_lower and "phó" not in role_lower:
                # TT 28/2009: Hiệu trưởng dạy 2 tiết/tuần
                cap = 2
                floor = 2
                reduction = reductions.get(role_str, max(0, base_cap - 2))
            elif "phó hiệu trưởng" in role_lower or "hiệu phó" in role_lower:
                # TT 28/2009: Phó hiệu trưởng dạy 4 tiết/tuần
                cap = 4
                floor = 4
                reduction = reductions.get(role_str, max(0, base_cap - 4))
            else:
                reduction = reductions.get(role_str, 0)
                cap = max(0, base_cap - reduction)
                floor = max(0, min_floor - reduction)

        load_c = loads_by_parity["C"].get(t.teacher_id, 0)
        load_l = loads_by_parity["L"].get(t.teacher_id, 0)
        load_avg_legacy = (load_c + load_l) / 2

        t_weekly = loads_35_by_teacher.get(t.teacher_id, {w: 0 for w in range(1, 36)})
        total_year_periods = sum(t_weekly.values())
        load_full_year_avg = total_year_periods / 35.0
        load_hk1_avg = sum(t_weekly[w] for w in range(1, 19)) / 18.0
        load_hk2_avg = sum(t_weekly[w] for w in range(19, 36)) / 17.0

        max_week = max(t_weekly, key=t_weekly.get) if t_weekly else 1
        max_load = t_weekly.get(max_week, 0)
        min_week = min(t_weekly, key=t_weekly.get) if t_weekly else 1
        min_load = t_weekly.get(min_week, 0)

        load_current = t_weekly.get(week_no, load_c if parity == "C" else load_l) if week_no is not None else (load_c if parity == "C" else load_l)

        view.append({
            "teacher_id": t.teacher_id, "name": t.name, "role": t.role,
            "reduction": reduction, "floor": floor, "cap": cap, "load": load_current,
            "load_chan": load_c, "load_le": load_l, "load_avg": load_avg_legacy,
            "load_full_year_avg": load_full_year_avg,
            "load_hk1_avg": load_hk1_avg,
            "load_hk2_avg": load_hk2_avg,
            "weekly_loads": t_weekly,
            "max_week": max_week,
            "max_load": max_load,
            "min_week": min_week,
            "min_load": min_load,
            "over": load_avg_legacy - cap,
            "over_current": load_current - cap,
            "over_hk1": load_hk1_avg - cap,
            "over_hk2": load_hk2_avg - cap,
            "over_year": load_full_year_avg - cap,
            "under": floor - load_avg_legacy,
            "under_current": floor - load_current,
            "under_year": floor - load_full_year_avg,
            "must_monday": t.must_monday, "is_gvcn": t.is_gvcn,
            "assignments": teacher_assignments.get(t.teacher_id, []),
        })
    return view


def get_teacher_caps(conn: sqlite3.Connection) -> dict:
    base_cap = get_base_cap(conn)
    reductions = get_role_reduction(conn)
    caps = {}
    for t in list_teachers(conn):
        if t.reduction_override is not None:
            caps[t.teacher_id] = max(0, base_cap - t.reduction_override)
        else:
            role_str = (t.role or "").strip()
            role_lower = role_str.lower()
            if "hiệu trưởng" in role_lower and "phó" not in role_lower:
                caps[t.teacher_id] = 2
            elif "phó hiệu trưởng" in role_lower or "hiệu phó" in role_lower:
                caps[t.teacher_id] = 4
            else:
                caps[t.teacher_id] = max(0, base_cap - reductions.get(role_str, 0))
    return caps


def get_teacher_floors(conn: sqlite3.Connection) -> dict:
    min_floor = get_min_floor(conn)
    reductions = get_role_reduction(conn)
    floors = {}
    for t in list_teachers(conn):
        if t.reduction_override is not None:
            floors[t.teacher_id] = max(0, min_floor - t.reduction_override)
        else:
            role_str = (t.role or "").strip()
            role_lower = role_str.lower()
            if "hiệu trưởng" in role_lower and "phó" not in role_lower:
                floors[t.teacher_id] = 2
            elif "phó hiệu trưởng" in role_lower or "hiệu phó" in role_lower:
                floors[t.teacher_id] = 4
            else:
                floors[t.teacher_id] = max(0, min_floor - reductions.get(role_str, 0))
    return floors
