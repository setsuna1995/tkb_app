"""Repository for schedule baseline (TKB_Nhap), run execution logs, and TKB results."""
from __future__ import annotations

import sqlite3
from typing import Optional
from data.repositories.config import _now


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


def save_run(conn: sqlite3.Connection, week_no: int, seed: int, parity: str,
             cells_changed: int, cells_total: int, succeeded: bool, message: str) -> int:
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


def get_latest_run(conn: sqlite3.Connection) -> Optional[dict]:
    row = conn.execute("SELECT * FROM run_log ORDER BY run_id DESC LIMIT 1").fetchone()
    return dict(row) if row else None


def get_latest_run_by_parity(conn: sqlite3.Connection, parity: str) -> Optional[dict]:
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


def get_latest_run_by_week(conn: sqlite3.Connection, week_no: int) -> Optional[dict]:
    row = conn.execute(
        "SELECT * FROM run_log WHERE week_no=? AND succeeded=1 ORDER BY run_id DESC LIMIT 1",
        (week_no,),
    ).fetchone()
    return dict(row) if row else None


def list_saved_weeks(conn: sqlite3.Connection) -> list[int]:
    rows = conn.execute(
        "SELECT DISTINCT week_no FROM run_log WHERE succeeded=1 ORDER BY week_no"
    ).fetchall()
    return [r["week_no"] for r in rows]


def list_runs_for_week(conn: sqlite3.Connection, week_no: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM run_log WHERE week_no=? ORDER BY run_id DESC",
        (week_no,),
    ).fetchall()
    return [dict(r) for r in rows]
