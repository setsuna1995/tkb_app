"""SQLite schema + connection helpers.

Nothing that's a formula in the original workbook is stored here (teacher
load/cap, KiemTra diffs) -- those are computed on read in repository.py.
"""
from __future__ import annotations

import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS classes (
    class_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL UNIQUE,
    sort_order   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS subjects (
    subject_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL UNIQUE,
    role_code    INTEGER NOT NULL DEFAULT 0 CHECK (role_code BETWEEN 0 AND 5),
    sort_order   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS teachers (
    teacher_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL UNIQUE,
    role         TEXT NOT NULL DEFAULT '',
    must_monday  INTEGER NOT NULL DEFAULT 0,
    is_gvcn      INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS role_reduction (
    role_name    TEXT PRIMARY KEY,
    reduction    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS assignments (
    subject_id   INTEGER NOT NULL REFERENCES subjects(subject_id) ON DELETE CASCADE,
    class_id     INTEGER NOT NULL REFERENCES classes(class_id) ON DELETE CASCADE,
    teacher_id   INTEGER REFERENCES teachers(teacher_id) ON DELETE SET NULL,
    PRIMARY KEY (subject_id, class_id)
);

CREATE TABLE IF NOT EXISTS periods_per_week (
    subject_id   INTEGER NOT NULL REFERENCES subjects(subject_id) ON DELETE CASCADE,
    class_id     INTEGER NOT NULL REFERENCES classes(class_id) ON DELETE CASCADE,
    parity       TEXT NOT NULL CHECK (parity IN ('C', 'L')),
    periods      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (subject_id, class_id, parity)
);

CREATE TABLE IF NOT EXISTS teacher_unavailability (
    row_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    teacher_id   INTEGER NOT NULL REFERENCES teachers(teacher_id) ON DELETE CASCADE,
    weekday      TEXT NOT NULL DEFAULT '*',
    session      TEXT NOT NULL DEFAULT '*',
    period       TEXT NOT NULL DEFAULT '*'
);

CREATE TABLE IF NOT EXISTS frame_template (
    class_id           INTEGER PRIMARY KEY REFERENCES classes(class_id) ON DELETE CASCADE,
    morning_periods    INTEGER NOT NULL DEFAULT 5,
    afternoon_periods  INTEGER NOT NULL DEFAULT 3,
    study_sunday       INTEGER NOT NULL DEFAULT 0,
    allow_saturday     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS tkb_nhap (
    class_id     INTEGER NOT NULL REFERENCES classes(class_id) ON DELETE CASCADE,
    weekday      INTEGER NOT NULL,
    session      TEXT NOT NULL,
    period       INTEGER NOT NULL,
    subject_id   INTEGER REFERENCES subjects(subject_id) ON DELETE SET NULL,
    PRIMARY KEY (class_id, weekday, session, period)
);

CREATE TABLE IF NOT EXISTS tuan_config (
    id           INTEGER PRIMARY KEY CHECK (id = 1),
    seed         INTEGER NOT NULL DEFAULT 0,
    parity       TEXT NOT NULL DEFAULT 'C' CHECK (parity IN ('C', 'L'))
);

CREATE TABLE IF NOT EXISTS seed_history (
    week_no      INTEGER PRIMARY KEY,
    seed         INTEGER NOT NULL,
    parity       TEXT NOT NULL,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tkb_result (
    run_id       INTEGER NOT NULL,
    class_id     INTEGER NOT NULL REFERENCES classes(class_id) ON DELETE CASCADE,
    weekday      INTEGER NOT NULL,
    session      TEXT NOT NULL,
    period       INTEGER NOT NULL,
    subject_id   INTEGER REFERENCES subjects(subject_id) ON DELETE SET NULL,
    PRIMARY KEY (run_id, class_id, weekday, session, period)
);

CREATE TABLE IF NOT EXISTS run_log (
    run_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    week_no       INTEGER,
    seed          INTEGER,
    parity        TEXT,
    cells_changed INTEGER,
    cells_total   INTEGER,
    succeeded     INTEGER NOT NULL,
    message       TEXT,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_meta (
    key          TEXT PRIMARY KEY,
    value        TEXT
);
"""

DEFAULT_ROLE_REDUCTION = {
    "GVCN": 4,
    "Tổ trưởng": 3,
    "Tổ phó": 1,
    "Tổng phụ trách": 8,
}


def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    """ALTER TABLE ADD COLUMN for DBs created before this column existed --
    CREATE TABLE IF NOT EXISTS above is a no-op on an already-existing table.
    """
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    _ensure_column(conn, "frame_template", "allow_saturday", "allow_saturday INTEGER NOT NULL DEFAULT 0")
    conn.execute("INSERT OR IGNORE INTO tuan_config (id, seed, parity) VALUES (1, 0, 'C')")
    for role_name, reduction in DEFAULT_ROLE_REDUCTION.items():
        conn.execute(
            "INSERT OR IGNORE INTO role_reduction (role_name, reduction) VALUES (?, ?)",
            (role_name, reduction),
        )
    conn.commit()
