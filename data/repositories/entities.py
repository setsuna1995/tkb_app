"""CRUD operations for classes, subjects, and teachers."""
from __future__ import annotations

import sqlite3
from typing import Optional
from core.models import ClassRoom, Subject, Teacher

_KEEP = object()  # sentinel: "caller didn't pass this kwarg, leave the column untouched on UPDATE"


def list_classes(conn: sqlite3.Connection) -> list[ClassRoom]:
    rows = conn.execute("SELECT class_id, name, sort_order FROM classes ORDER BY sort_order, class_id").fetchall()
    return [ClassRoom(r["class_id"], r["name"], r["sort_order"]) for r in rows]


def get_class_by_name(conn: sqlite3.Connection, name: str) -> Optional[int]:
    row = conn.execute("SELECT class_id FROM classes WHERE name=?", (name,)).fetchone()
    return row["class_id"] if row else None


def upsert_class(conn: sqlite3.Connection, name: str, sort_order: int = 0, class_id: Optional[int] = None) -> int:
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


def list_subjects(conn: sqlite3.Connection) -> list[Subject]:
    rows = conn.execute(
        "SELECT subject_id, name, role_code, sort_order FROM subjects ORDER BY sort_order, subject_id"
    ).fetchall()
    return [Subject(r["subject_id"], r["name"], r["role_code"], r["sort_order"]) for r in rows]


def get_subject_by_name(conn: sqlite3.Connection, name: str) -> Optional[int]:
    row = conn.execute("SELECT subject_id FROM subjects WHERE name=?", (name,)).fetchone()
    return row["subject_id"] if row else None


def upsert_subject(conn: sqlite3.Connection, name: str, role_code: int = 0, sort_order: int = 0,
                   subject_id: Optional[int] = None) -> int:
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


def list_teachers(conn: sqlite3.Connection) -> list[Teacher]:
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(teachers)")}
    has_reduction = "reduction_override" in cols
    rows = conn.execute(
        "SELECT teacher_id, name, role, must_monday, is_gvcn, "
        f"off_sessions_override, pinned_full_day_off, pinned_afternoon_off{', reduction_override' if has_reduction else ''} "
        "FROM teachers ORDER BY name"
    ).fetchall()
    return [Teacher(
        r["teacher_id"], r["name"], r["role"], bool(r["must_monday"]), bool(r["is_gvcn"]),
        off_sessions_override=r["off_sessions_override"],
        pinned_full_day_off=r["pinned_full_day_off"],
        pinned_afternoon_off=r["pinned_afternoon_off"],
        reduction_override=r["reduction_override"] if has_reduction else None,
    ) for r in rows]


def upsert_teacher(conn: sqlite3.Connection, name: str, role: str = "", must_monday: bool = False,
                    is_gvcn: bool = False, teacher_id: Optional[int] = None,
                    off_sessions_override=_KEEP, pinned_full_day_off=_KEEP, pinned_afternoon_off=_KEEP,
                    reduction_override=_KEEP) -> int:
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(teachers)")}
    if "reduction_override" not in cols:
        conn.execute("ALTER TABLE teachers ADD COLUMN reduction_override INTEGER")
        conn.commit()

    if teacher_id is not None:
        set_clauses = ["name=?", "role=?", "must_monday=?", "is_gvcn=?"]
        params = [name, role, int(must_monday), int(is_gvcn)]
        for col, val in (
            ("off_sessions_override", off_sessions_override),
            ("pinned_full_day_off", pinned_full_day_off),
            ("pinned_afternoon_off", pinned_afternoon_off),
            ("reduction_override", reduction_override),
        ):
            if val is not _KEEP:
                set_clauses.append(f"{col}=?")
                params.append(val)
        params.append(teacher_id)
        conn.execute(f"UPDATE teachers SET {', '.join(set_clauses)} WHERE teacher_id=?", params)
        conn.commit()
        return teacher_id
    cur = conn.execute(
        "INSERT INTO teachers (name, role, must_monday, is_gvcn, "
        "off_sessions_override, pinned_full_day_off, pinned_afternoon_off, reduction_override) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (name, role, int(must_monday), int(is_gvcn),
         None if off_sessions_override is _KEEP else off_sessions_override,
         None if pinned_full_day_off is _KEEP else pinned_full_day_off,
         None if pinned_afternoon_off is _KEEP else pinned_afternoon_off,
         None if reduction_override is _KEEP else reduction_override),
    )
    conn.commit()
    return cur.lastrowid


def get_teacher_by_name(conn: sqlite3.Connection, name: str) -> Optional[int]:
    row = conn.execute("SELECT teacher_id FROM teachers WHERE name=?", (name,)).fetchone()
    return row["teacher_id"] if row else None


def delete_teacher(conn: sqlite3.Connection, teacher_id: int) -> None:
    conn.execute("DELETE FROM teachers WHERE teacher_id=?", (teacher_id,))
    conn.commit()
