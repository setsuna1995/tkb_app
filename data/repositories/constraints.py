"""Repository for scheduling constraints: unavailability (GV_Ban), class frames, and subject-class rules."""
from __future__ import annotations

import sqlite3
from typing import Optional
from core import frame as frame_mod
from core.models import ROLE_HDTN
from data.repositories.config import _format_off_cells, _parse_off_cells


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


def clear_unavailability(conn: sqlite3.Connection, teacher_id: Optional[int] = None) -> None:
    if teacher_id is None:
        conn.execute("DELETE FROM teacher_unavailability")
    else:
        conn.execute("DELETE FROM teacher_unavailability WHERE teacher_id=?", (teacher_id,))
    conn.commit()


def get_teacher_busy_cells(conn: sqlite3.Connection, teacher_id: int) -> set[tuple[int, str, int]]:
    """Returns set of (weekday, session, period) where teacher is unavailable.
    weekday: 2..8 (int), session: 'S' or 'C' (str), period: 1..5 (int)
    """
    rows = conn.execute(
        "SELECT weekday, session, period FROM teacher_unavailability WHERE teacher_id=?",
        (teacher_id,),
    ).fetchall()
    busy = set()
    for r in rows:
        w_raw = str(r["weekday"]).strip()
        s_raw = str(r["session"]).strip().upper()
        p_raw = str(r["period"]).strip()

        if w_raw == "*":
            wds = list(range(2, 8))
        elif w_raw == "CN" or w_raw == "8":
            wds = [8]
        elif w_raw.isdigit():
            wds = [int(w_raw)]
        else:
            wds = []

        if s_raw == "*":
            sessions = ["S", "C"]
        elif s_raw in ("S", "C"):
            sessions = [s_raw]
        else:
            sessions = []

        if p_raw == "*":
            periods = list(range(1, 6))
        elif p_raw.isdigit():
            periods = [int(p_raw)]
        else:
            periods = []

        for w in wds:
            for s in sessions:
                for p in periods:
                    busy.add((w, s, p))
    return busy


def compress_busy_cells(cells: set[tuple[int, str, int]]) -> list[tuple[str, str, str]]:
    """Converts a set of (wd, session, period) into compact (weekday, session, period) rules
    using '*' wildcards where full days, full sessions, or all-week same periods are checked.
    """
    rules = []
    all_sp = {(s, p) for s in ("S", "C") for p in range(1, 6)}
    handled_cells = set()

    for wd in range(2, 8):
        sp_set = {(s, p) for (w, s, p) in cells if w == wd}
        if sp_set == all_sp:
            rules.append((str(wd), "*", "*"))
            handled_cells.update({(wd, s, p) for s, p in all_sp})
        else:
            for s in ("S", "C"):
                s_pers = {p for sess, p in sp_set if sess == s}
                if s_pers == set(range(1, 6)):
                    rules.append((str(wd), s, "*"))
                    handled_cells.update({(wd, s, p) for p in range(1, 6)})

    rem_cells = set(cells) - handled_cells

    for s in ("S", "C"):
        for p in range(1, 6):
            if all((wd, s, p) in rem_cells for wd in range(2, 8)):
                rules.append(("*", s, str(p)))
                for wd in range(2, 8):
                    rem_cells.discard((wd, s, p))

    for (wd, s, p) in sorted(rem_cells):
        rules.append((str(wd), str(s), str(p)))
    return rules


def set_teacher_busy_cells(conn: sqlite3.Connection, teacher_id: int, busy_cells: set[tuple[int, str, int]]) -> None:
    clear_unavailability(conn, teacher_id)
    rules = compress_busy_cells(busy_cells)
    for (wd, sess, per) in rules:
        add_unavailability(conn, teacher_id, wd, sess, per)


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


def get_class_allowed_cells(conn: sqlite3.Connection, class_id: int) -> list[tuple[int, str, int]]:
    rows = conn.execute(
        "SELECT weekday, session, period FROM class_allowed_cells WHERE class_id=?",
        (class_id,)
    ).fetchall()
    return [(r["weekday"], r["session"], r["period"]) for r in rows]


def get_all_class_allowed_cells(conn: sqlite3.Connection) -> dict[int, list[tuple[int, str, int]]]:
    rows = conn.execute(
        "SELECT class_id, weekday, session, period FROM class_allowed_cells"
    ).fetchall()
    result = {}
    for r in rows:
        cid = r["class_id"]
        if cid not in result:
            result[cid] = []
        result[cid].append((r["weekday"], r["session"], r["period"]))
    return result


def set_class_allowed_cells(conn: sqlite3.Connection, class_id: int, cells: list[tuple[int, str, int]]) -> None:
    conn.execute("DELETE FROM class_allowed_cells WHERE class_id=?", (class_id,))
    conn.executemany(
        "INSERT INTO class_allowed_cells (class_id, weekday, session, period) VALUES (?, ?, ?, ?)",
        [(class_id, wd, s, p) for wd, s, p in cells]
    )
    conn.commit()


def set_frame_template(conn: sqlite3.Connection, class_id: int, morning_periods: int,
                        afternoon_periods: int, study_sunday: bool = False,
                        allow_saturday: bool = False, short_weekday: Optional[int] = None,
                        short_morning_periods: Optional[int] = None,
                        short_afternoon_periods: Optional[int] = None) -> None:
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


def list_subject_class_rules(conn: sqlite3.Connection) -> list:
    rows = conn.execute(
        "SELECT rule_id, subject_id, class_ids, cells FROM subject_class_slot_rules ORDER BY rule_id"
    ).fetchall()
    return [
        {
            "rule_id": r["rule_id"],
            "subject_id": r["subject_id"],
            "class_ids": [int(x) for x in r["class_ids"].split(",") if x.strip()],
            "cells": _parse_off_cells(r["cells"]),
        }
        for r in rows
    ]


def upsert_subject_class_rule(conn: sqlite3.Connection, subject_id: int, class_ids, cells,
                              rule_id: Optional[int] = None) -> int:
    if not cells:
        raise ValueError("Luật phải có ít nhất 1 (thứ, buổi) được phép.")
    if not class_ids:
        raise ValueError("Luật phải áp dụng cho ít nhất 1 lớp.")
    row = conn.execute("SELECT role_code FROM subjects WHERE subject_id=?", (subject_id,)).fetchone()
    if row and row["role_code"] == ROLE_HDTN:
        raise ValueError("Không thể tạo luật cho môn HDTN (đã có vị trí ghim cố định riêng).")
    class_ids_str = ",".join(str(cid) for cid in sorted(class_ids))
    cells_str = _format_off_cells(cells)
    if rule_id is not None:
        conn.execute(
            "UPDATE subject_class_slot_rules SET subject_id=?, class_ids=?, cells=? WHERE rule_id=?",
            (subject_id, class_ids_str, cells_str, rule_id),
        )
        conn.commit()
        return rule_id
    cur = conn.execute(
        "INSERT INTO subject_class_slot_rules (subject_id, class_ids, cells) VALUES (?, ?, ?)",
        (subject_id, class_ids_str, cells_str),
    )
    conn.commit()
    return cur.lastrowid


def delete_subject_class_rule(conn: sqlite3.Connection, rule_id: int) -> None:
    conn.execute("DELETE FROM subject_class_slot_rules WHERE rule_id=?", (rule_id,))
    conn.commit()


def get_subject_class_allowed_cells(conn: sqlite3.Connection) -> dict:
    result = {}
    for rule in list_subject_class_rules(conn):
        for class_id in rule["class_ids"]:
            key = (rule["subject_id"], class_id)
            result[key] = result.get(key, frozenset()) | rule["cells"]
    return result
