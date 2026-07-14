"""CRUD + view helpers over the SQLite schema, and the composite builder that
assembles a core.models.SchedulingInput from the current DB state.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from core import frame as frame_mod
from core.models import ClassRoom, SchedulingInput, Slot, Subject, Teacher, TimeSlot, WEEKDAYS


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# classes / subjects / teachers
# ---------------------------------------------------------------------------

def list_classes(conn: sqlite3.Connection) -> list:
    rows = conn.execute("SELECT class_id, name, sort_order FROM classes ORDER BY sort_order, class_id").fetchall()
    return [ClassRoom(r["class_id"], r["name"], r["sort_order"]) for r in rows]


def get_class_by_name(conn: sqlite3.Connection, name: str):
    row = conn.execute("SELECT class_id FROM classes WHERE name=?", (name,)).fetchone()
    return row["class_id"] if row else None


def upsert_class(conn: sqlite3.Connection, name: str, sort_order: int = 0, class_id=None) -> int:
    if class_id is not None:
        conn.execute("UPDATE classes SET name=?, sort_order=? WHERE class_id=?", (name, sort_order, class_id))
        conn.commit()
        return class_id
    cur = conn.execute("INSERT INTO classes (name, sort_order) VALUES (?, ?)", (name, sort_order))
    conn.commit()
    return cur.lastrowid


def delete_class(conn: sqlite3.Connection, class_id: int) -> None:
    conn.execute("DELETE FROM classes WHERE class_id=?", (class_id,))
    conn.commit()


def list_subjects(conn: sqlite3.Connection) -> list:
    rows = conn.execute(
        "SELECT subject_id, name, role_code, sort_order FROM subjects ORDER BY sort_order, subject_id"
    ).fetchall()
    return [Subject(r["subject_id"], r["name"], r["role_code"], r["sort_order"]) for r in rows]


def get_subject_by_name(conn: sqlite3.Connection, name: str):
    row = conn.execute("SELECT subject_id FROM subjects WHERE name=?", (name,)).fetchone()
    return row["subject_id"] if row else None


def upsert_subject(conn: sqlite3.Connection, name: str, role_code: int = 0, sort_order: int = 0, subject_id=None) -> int:
    if subject_id is not None:
        conn.execute(
            "UPDATE subjects SET name=?, role_code=?, sort_order=? WHERE subject_id=?",
            (name, role_code, sort_order, subject_id),
        )
        conn.commit()
        return subject_id
    cur = conn.execute(
        "INSERT INTO subjects (name, role_code, sort_order) VALUES (?, ?, ?)", (name, role_code, sort_order)
    )
    conn.commit()
    return cur.lastrowid


def delete_subject(conn: sqlite3.Connection, subject_id: int) -> None:
    conn.execute("DELETE FROM subjects WHERE subject_id=?", (subject_id,))
    conn.commit()


def list_teachers(conn: sqlite3.Connection) -> list:
    rows = conn.execute(
        "SELECT teacher_id, name, role, must_monday, is_gvcn FROM teachers ORDER BY name"
    ).fetchall()
    return [Teacher(r["teacher_id"], r["name"], r["role"], bool(r["must_monday"]), bool(r["is_gvcn"]))
            for r in rows]


def upsert_teacher(conn: sqlite3.Connection, name: str, role: str = "", must_monday: bool = False,
                    is_gvcn: bool = False, teacher_id=None) -> int:
    if teacher_id is not None:
        conn.execute(
            "UPDATE teachers SET name=?, role=?, must_monday=?, is_gvcn=? WHERE teacher_id=?",
            (name, role, int(must_monday), int(is_gvcn), teacher_id),
        )
        conn.commit()
        return teacher_id
    cur = conn.execute(
        "INSERT INTO teachers (name, role, must_monday, is_gvcn) VALUES (?, ?, ?, ?)",
        (name, role, int(must_monday), int(is_gvcn)),
    )
    conn.commit()
    return cur.lastrowid


def get_teacher_by_name(conn: sqlite3.Connection, name: str):
    row = conn.execute("SELECT teacher_id FROM teachers WHERE name=?", (name,)).fetchone()
    return row["teacher_id"] if row else None


def delete_teacher(conn: sqlite3.Connection, teacher_id: int) -> None:
    conn.execute("DELETE FROM teachers WHERE teacher_id=?", (teacher_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# role_reduction + computed teacher quota view (DinhMuc_GV)
# ---------------------------------------------------------------------------

DEFAULT_BASE_CAP = 19
DEFAULT_MIN_FLOOR = 16


def get_base_cap(conn: sqlite3.Connection) -> int:
    return int(get_meta(conn, "base_cap") or DEFAULT_BASE_CAP)


def set_base_cap(conn: sqlite3.Connection, value: int) -> None:
    set_meta(conn, "base_cap", str(int(value)))


def get_min_floor(conn: sqlite3.Connection) -> int:
    return int(get_meta(conn, "min_floor") or DEFAULT_MIN_FLOOR)


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


def get_teacher_quota_view(conn: sqlite3.Connection, parity: str) -> list:
    """Recreates DinhMuc_GV: cap = trần chuẩn (mặc định 19, xem get_base_cap) - reduction(role);
    load = sum(assignments x periods_per_week) cho tuần `parity` (chỉ để hiển thị). Vượt trần /
    dưới sàn được xét theo TRUNG BÌNH tải của cả tuần Chẵn và Lẻ -- một GV có thể lệch tải giữa
    2 tuần (vd Chẵn nhiều, Lẻ ít) nhưng nếu trung bình đã đúng định mức thì không báo vượt/thiếu.
    """
    base_cap = get_base_cap(conn)
    min_floor = get_min_floor(conn)
    reductions = get_role_reduction(conn)
    teachers = list_teachers(conn)
    ppw = get_periods_per_week(conn)
    assignments = get_assignments(conn)

    loads_by_parity = {"C": {}, "L": {}}
    for (subject_id, class_id), teacher_id in assignments.items():
        if teacher_id is None:
            continue
        for par in ("C", "L"):
            periods = ppw.get((subject_id, class_id, par), 0)
            loads_by_parity[par][teacher_id] = loads_by_parity[par].get(teacher_id, 0) + periods

    view = []
    for t in teachers:
        reduction = reductions.get(t.role, 0)
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
            "under": min_floor - (load_avg + reduction),
            "must_monday": t.must_monday, "is_gvcn": t.is_gvcn,
        })
    return view


def get_teacher_caps(conn: sqlite3.Connection) -> dict:
    base_cap = get_base_cap(conn)
    reductions = get_role_reduction(conn)
    return {t.teacher_id: base_cap - reductions.get(t.role, 0) for t in list_teachers(conn)}


# ---------------------------------------------------------------------------
# assignments (PhanCong) / periods_per_week (SoTiet)
# ---------------------------------------------------------------------------

def get_assignments(conn: sqlite3.Connection) -> dict:
    rows = conn.execute("SELECT subject_id, class_id, teacher_id FROM assignments").fetchall()
    return {(r["subject_id"], r["class_id"]): r["teacher_id"] for r in rows}


def set_assignment(conn: sqlite3.Connection, subject_id: int, class_id: int, teacher_id) -> None:
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


# ---------------------------------------------------------------------------
# teacher_unavailability (GV_Ban)
# ---------------------------------------------------------------------------

def list_unavailability(conn: sqlite3.Connection) -> list:
    rows = conn.execute(
        "SELECT row_id, teacher_id, weekday, session, period FROM teacher_unavailability"
    ).fetchall()
    return [dict(r) for r in rows]


def add_unavailability(conn: sqlite3.Connection, teacher_id: int, weekday: str = "*",
                        session: str = "*", period: str = "*") -> int:
    cur = conn.execute(
        "INSERT INTO teacher_unavailability (teacher_id, weekday, session, period) VALUES (?, ?, ?, ?)",
        (teacher_id, weekday, session, period),
    )
    conn.commit()
    return cur.lastrowid


def delete_unavailability(conn: sqlite3.Connection, row_id: int) -> None:
    conn.execute("DELETE FROM teacher_unavailability WHERE row_id=?", (row_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# frame_template (Khung)
# ---------------------------------------------------------------------------

def get_frame_template(conn: sqlite3.Connection, class_id: int) -> tuple:
    row = conn.execute(
        "SELECT morning_periods, afternoon_periods, study_sunday, allow_saturday, "
        "short_weekday, short_morning_periods, short_afternoon_periods "
        "FROM frame_template WHERE class_id=?",
        (class_id,),
    ).fetchone()
    if row is None:
        return (5, 3, 0, 0, None, None, None)
    return (
        row["morning_periods"], row["afternoon_periods"], row["study_sunday"], row["allow_saturday"],
        row["short_weekday"], row["short_morning_periods"], row["short_afternoon_periods"],
    )


def get_all_frame_templates(conn: sqlite3.Connection) -> dict:
    rows = conn.execute(
        "SELECT class_id, morning_periods, afternoon_periods, study_sunday, allow_saturday, "
        "short_weekday, short_morning_periods, short_afternoon_periods FROM frame_template"
    ).fetchall()
    return {
        r["class_id"]: (
            r["morning_periods"], r["afternoon_periods"], r["study_sunday"], r["allow_saturday"],
            r["short_weekday"], r["short_morning_periods"], r["short_afternoon_periods"],
        )
        for r in rows
    }


def set_frame_template(conn: sqlite3.Connection, class_id: int, morning_periods: int,
                        afternoon_periods: int, study_sunday: bool = False,
                        allow_saturday: bool = False, short_weekday: int | None = None,
                        short_morning_periods: int | None = None,
                        short_afternoon_periods: int | None = None) -> None:
    frame_mod.validate_periods(morning_periods, afternoon_periods, short_morning_periods, short_afternoon_periods)
    conn.execute(
        "INSERT INTO frame_template (class_id, morning_periods, afternoon_periods, study_sunday, allow_saturday, "
        "short_weekday, short_morning_periods, short_afternoon_periods) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(class_id) DO UPDATE SET "
        "morning_periods=excluded.morning_periods, afternoon_periods=excluded.afternoon_periods, "
        "study_sunday=excluded.study_sunday, allow_saturday=excluded.allow_saturday, "
        "short_weekday=excluded.short_weekday, short_morning_periods=excluded.short_morning_periods, "
        "short_afternoon_periods=excluded.short_afternoon_periods",
        (class_id, morning_periods, afternoon_periods, int(study_sunday), int(allow_saturday),
         short_weekday, short_morning_periods, short_afternoon_periods),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# tkb_nhap (editable baseline)
# ---------------------------------------------------------------------------

def get_tkb_nhap(conn: sqlite3.Connection) -> dict:
    rows = conn.execute("SELECT class_id, weekday, session, period, subject_id FROM tkb_nhap").fetchall()
    return {(r["class_id"], r["weekday"], r["session"], r["period"]): r["subject_id"] for r in rows}


def bulk_replace_tkb_nhap(conn: sqlite3.Connection, cells: dict) -> None:
    """cells: (class_id, weekday, session, period) -> Optional[subject_id]. Replaces the whole table."""
    conn.execute("DELETE FROM tkb_nhap")
    conn.executemany(
        "INSERT INTO tkb_nhap (class_id, weekday, session, period, subject_id) VALUES (?, ?, ?, ?, ?)",
        [(cid, wd, sess, per, sid) for (cid, wd, sess, per), sid in cells.items()],
    )
    conn.commit()


# ---------------------------------------------------------------------------
# tuan_config / seed_history
# ---------------------------------------------------------------------------

def get_tuan_config(conn: sqlite3.Connection) -> tuple:
    row = conn.execute("SELECT seed, parity FROM tuan_config WHERE id=1").fetchone()
    return (row["seed"], row["parity"]) if row else (0, "C")


def set_tuan_config(conn: sqlite3.Connection, seed: int, parity: str) -> None:
    conn.execute(
        "INSERT INTO tuan_config (id, seed, parity) VALUES (1, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET seed=excluded.seed, parity=excluded.parity",
        (seed, parity),
    )
    conn.commit()


def list_seed_history(conn: sqlite3.Connection) -> list:
    rows = conn.execute(
        "SELECT week_no, seed, parity, created_at FROM seed_history ORDER BY week_no"
    ).fetchall()
    return [dict(r) for r in rows]


def add_seed_history(conn: sqlite3.Connection, week_no: int, seed: int, parity: str) -> None:
    conn.execute(
        "INSERT INTO seed_history (week_no, seed, parity, created_at) VALUES (?, ?, ?, ?)",
        (week_no, seed, parity, _now()),
    )
    conn.commit()


def clear_seed_history(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM seed_history")
    conn.execute("UPDATE tuan_config SET seed=0 WHERE id=1")
    conn.commit()


# ---------------------------------------------------------------------------
# run_log / tkb_result
# ---------------------------------------------------------------------------

def save_run(conn: sqlite3.Connection, week_no, seed, parity, cells_changed, cells_total,
             succeeded: bool, message) -> int:
    cur = conn.execute(
        "INSERT INTO run_log (week_no, seed, parity, cells_changed, cells_total, succeeded, message, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (week_no, seed, parity, cells_changed, cells_total, int(succeeded), message, _now()),
    )
    conn.commit()
    return cur.lastrowid


def save_tkb_result(conn: sqlite3.Connection, run_id: int, cells: dict) -> None:
    conn.executemany(
        "INSERT INTO tkb_result (run_id, class_id, weekday, session, period, subject_id) VALUES (?, ?, ?, ?, ?, ?)",
        [(run_id, cid, wd, sess, per, sid) for (cid, wd, sess, per), sid in cells.items()],
    )
    conn.commit()


def get_latest_run(conn: sqlite3.Connection):
    row = conn.execute("SELECT * FROM run_log ORDER BY run_id DESC LIMIT 1").fetchone()
    return dict(row) if row else None


def get_latest_run_by_parity(conn: sqlite3.Connection, parity: str):
    row = conn.execute(
        "SELECT * FROM run_log WHERE parity=? AND succeeded=1 ORDER BY run_id DESC LIMIT 1",
        (parity,),
    ).fetchone()
    return dict(row) if row else None


def get_tkb_result(conn: sqlite3.Connection, run_id: int) -> dict:
    rows = conn.execute(
        "SELECT class_id, weekday, session, period, subject_id FROM tkb_result WHERE run_id=?", (run_id,)
    ).fetchall()
    return {(r["class_id"], r["weekday"], r["session"], r["period"]): r["subject_id"] for r in rows}


# ---------------------------------------------------------------------------
# app_meta
# ---------------------------------------------------------------------------

def get_meta(conn: sqlite3.Connection, key: str, default=None):
    row = conn.execute("SELECT value FROM app_meta WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO app_meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Composite: build a core.models.SchedulingInput from the current DB state
# ---------------------------------------------------------------------------

def _canonical_timeslots() -> list:
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
                            extra_kep_ids: frozenset = frozenset()) -> SchedulingInput:
    classes = list_classes(conn)
    subjects = list_subjects(conn)
    teachers = list_teachers(conn)

    need = {(s, c): p for (s, c, par), p in get_periods_per_week(conn).items() if par == parity and p > 0}
    assigned_teacher = {key: tid for key, tid in get_assignments(conn).items() if tid is not None}

    all_ts = _canonical_timeslots()
    ts_by_key = {(t.weekday, t.session, t.period): t for t in all_ts}

    tkb_nhap = get_tkb_nhap(conn)
    frame_templates = get_all_frame_templates(conn)

    slots = []
    used_ts_ids = set()
    slot_id = 0
    for cls in classes:
        morning, afternoon, study_sunday, allow_saturday, short_weekday, short_morning, short_afternoon = \
            frame_templates.get(cls.class_id, (5, 3, 0, 0, None, None, None))
        for (wd, session, period) in frame_mod.active_cells(
            morning, afternoon, bool(study_sunday), bool(allow_saturday),
            short_weekday, short_morning, short_afternoon,
        ):
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
        extra_kep_ids=extra_kep_ids,
    )
