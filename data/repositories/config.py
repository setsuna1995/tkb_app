"""Application metadata and scheduling configuration repository."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Optional
from core.models import SchedulingConfig


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_meta(conn: sqlite3.Connection, key: str, default=None):
    try:
        row = conn.execute("SELECT value FROM app_meta WHERE key=?", (str(key),)).fetchone()
        return row["value"] if row else default
    except Exception:
        return default


def set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO app_meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (str(key), str(value)),
    )
    conn.commit()


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
        "INSERT OR REPLACE INTO seed_history (week_no, seed, parity, created_at) VALUES (?, ?, ?, ?)",
        (week_no, seed, parity, _now()),
    )
    conn.commit()


def clear_seed_history(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM seed_history")
    conn.execute("UPDATE tuan_config SET seed=0 WHERE id=1")
    conn.commit()


def _parse_off_cells(raw: str) -> frozenset:
    cells = set()
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        cells.add((int(token[:-1]), token[-1]))
    return frozenset(cells)


def _format_off_cells(cells) -> str:
    return ",".join(f"{wd}{session}" for wd, session in sorted(cells))


def _parse_weekday_tuple(raw: str) -> tuple:
    return tuple(int(x) for x in raw.split(",") if x.strip())


def _format_weekday_tuple(weekdays) -> str:
    return ",".join(str(wd) for wd in weekdays)


def _parse_id_set(raw: str) -> frozenset:
    return frozenset(int(x) for x in raw.split(",") if x.strip())


def _format_id_set(ids) -> str:
    return ",".join(str(i) for i in sorted(ids))


def _parse_period_tuple(raw: str) -> tuple:
    if not raw:
        return ()
    return tuple(int(x) for x in raw.split(",") if x.strip() and x.strip().isdigit())


def _format_period_tuple(periods) -> str:
    return ",".join(str(p) for p in sorted(periods))


def get_scheduling_config(conn: sqlite3.Connection) -> SchedulingConfig:
    from data.repositories.entities import list_subjects
    default = SchedulingConfig()
    forbidden_raw = get_meta(conn, "sched_forbidden_off_cells")
    reserved_raw = get_meta(conn, "sched_reserved_off_weekdays_chieu")
    afternoon_preferred_raw = get_meta(conn, "sched_afternoon_preferred_subject_ids")
    morning_only_raw = get_meta(conn, "sched_morning_only_subject_ids")
    non_consecutive_raw = get_meta(conn, "sched_non_consecutive_subject_ids")
    single_pair_raw = get_meta(conn, "sched_single_pair_subject_ids")
    avoid_teacher_gaps_raw = get_meta(conn, "sched_avoid_teacher_gaps")
    avoid_teacher_lone_periods_raw = get_meta(conn, "sched_avoid_teacher_lone_periods")
    balance_afternoon_teachers_raw = get_meta(conn, "sched_balance_afternoon_teachers")
    mandatory_mornings_raw = get_meta(conn, "sched_mandatory_morning_weekdays")
    avoid_gdtc_consecutive_raw = get_meta(conn, "sched_avoid_gdtc_consecutive_days")
    gdtc_morning_raw = get_meta(conn, "sched_gdtc_morning_allowed_periods")
    gdtc_afternoon_raw = get_meta(conn, "sched_gdtc_afternoon_allowed_periods")
    return SchedulingConfig(
        gdtc_avoid_period=int(get_meta(conn, "sched_gdtc_avoid_period") or default.gdtc_avoid_period),
        gdtc_morning_allowed_periods=(
            _parse_period_tuple(gdtc_morning_raw) if gdtc_morning_raw is not None
            else default.gdtc_morning_allowed_periods
        ),
        gdtc_afternoon_allowed_periods=(
            _parse_period_tuple(gdtc_afternoon_raw) if gdtc_afternoon_raw is not None
            else default.gdtc_afternoon_allowed_periods
        ),
        chao_co_weekday=int(get_meta(conn, "sched_chao_co_weekday") or default.chao_co_weekday),
        chao_co_period=int(get_meta(conn, "sched_chao_co_period") or default.chao_co_period),
        max_heavy_consecutive=int(get_meta(conn, "sched_max_heavy_consecutive") or default.max_heavy_consecutive),
        max_periods_per_session=int(
            get_meta(conn, "sched_max_periods_per_session") or default.max_periods_per_session
        ),
        teacher_off_sessions_per_week=int(
            get_meta(conn, "sched_teacher_off_sessions_per_week") or default.teacher_off_sessions_per_week
        ),
        forbidden_off_cells=_parse_off_cells(forbidden_raw) if forbidden_raw else default.forbidden_off_cells,
        reserved_off_weekdays_chieu=(
            _parse_weekday_tuple(reserved_raw) if reserved_raw else default.reserved_off_weekdays_chieu
        ),
        heavy_subject_priority_periods=int(
            get_meta(conn, "sched_heavy_subject_priority_periods") or default.heavy_subject_priority_periods
        ),
        afternoon_preferred_subject_ids=(
            _parse_id_set(afternoon_preferred_raw) if afternoon_preferred_raw
            else default.afternoon_preferred_subject_ids
        ),
        heavy_subjects_morning_only=bool(int(get_meta(conn, "sched_heavy_subjects_morning_only") or 0)),
        morning_only_subject_ids=(
            _parse_id_set(morning_only_raw) if morning_only_raw is not None
            else frozenset(
                s.subject_id for s in list_subjects(conn)
                if "Toán" in s.name or "Ngữ văn" in s.name or "Văn" in s.name
            ) if conn else default.morning_only_subject_ids
        ),
        non_consecutive_subject_ids=(
            _parse_id_set(non_consecutive_raw) if non_consecutive_raw is not None
            else default.non_consecutive_subject_ids
        ),
        single_pair_subject_ids=(
            _parse_id_set(single_pair_raw) if single_pair_raw is not None
            else default.single_pair_subject_ids
        ),
        avoid_teacher_gaps=(
            bool(int(avoid_teacher_gaps_raw)) if avoid_teacher_gaps_raw is not None
            else default.avoid_teacher_gaps
        ),
        avoid_teacher_lone_periods=(
            bool(int(avoid_teacher_lone_periods_raw)) if avoid_teacher_lone_periods_raw is not None
            else default.avoid_teacher_lone_periods
        ),
        balance_afternoon_teachers=(
            bool(int(balance_afternoon_teachers_raw)) if balance_afternoon_teachers_raw is not None
            else default.balance_afternoon_teachers
        ),
        mandatory_morning_weekdays=(
            _parse_weekday_tuple(mandatory_mornings_raw) if mandatory_mornings_raw is not None
            else default.mandatory_morning_weekdays
        ),
        avoid_gdtc_consecutive_days=(
            bool(int(avoid_gdtc_consecutive_raw)) if avoid_gdtc_consecutive_raw is not None
            else default.avoid_gdtc_consecutive_days
        ),
        max_teacher_periods_per_day=int(
            get_meta(conn, "sched_max_teacher_periods_per_day") or default.max_teacher_periods_per_day
        ),
        max_heavy_per_session=int(
            get_meta(conn, "sched_max_heavy_per_session") or default.max_heavy_per_session
        ),
        hdtn_period2_afternoon=(
            bool(int(get_meta(conn, "sched_hdtn_period2_afternoon"))) if get_meta(conn, "sched_hdtn_period2_afternoon") is not None
            else default.hdtn_period2_afternoon
        ),
        avoid_heavy_afternoon_period3=(
            bool(int(get_meta(conn, "sched_avoid_heavy_afternoon_period3"))) if get_meta(conn, "sched_avoid_heavy_afternoon_period3") is not None
            else default.avoid_heavy_afternoon_period3
        ),
        avoid_teacher_4_consecutive_morning=(
            bool(int(get_meta(conn, "sched_avoid_teacher_4_consecutive_morning"))) if get_meta(conn, "sched_avoid_teacher_4_consecutive_morning") is not None
            else default.avoid_teacher_4_consecutive_morning
        ),
        min_weekly_periods_for_lone_penalty=int(
            get_meta(conn, "sched_min_weekly_periods_for_lone_penalty") or default.min_weekly_periods_for_lone_penalty
        ),
    )


def set_scheduling_config(conn: sqlite3.Connection, config: SchedulingConfig) -> None:
    set_meta(conn, "sched_gdtc_avoid_period", str(config.gdtc_avoid_period))
    set_meta(conn, "sched_gdtc_morning_allowed_periods", _format_period_tuple(config.gdtc_morning_allowed_periods))
    set_meta(conn, "sched_gdtc_afternoon_allowed_periods", _format_period_tuple(config.gdtc_afternoon_allowed_periods))
    set_meta(conn, "sched_chao_co_weekday", str(config.chao_co_weekday))
    set_meta(conn, "sched_chao_co_period", str(config.chao_co_period))
    set_meta(conn, "sched_max_heavy_consecutive", str(config.max_heavy_consecutive))
    set_meta(conn, "sched_max_periods_per_session", str(config.max_periods_per_session))
    set_meta(conn, "sched_teacher_off_sessions_per_week", str(config.teacher_off_sessions_per_week))
    set_meta(conn, "sched_forbidden_off_cells", _format_off_cells(config.forbidden_off_cells))
    set_meta(conn, "sched_reserved_off_weekdays_chieu", _format_weekday_tuple(config.reserved_off_weekdays_chieu))
    set_meta(conn, "sched_heavy_subject_priority_periods", str(config.heavy_subject_priority_periods))
    set_meta(conn, "sched_afternoon_preferred_subject_ids", _format_id_set(config.afternoon_preferred_subject_ids))
    set_meta(conn, "sched_heavy_subjects_morning_only", str(int(config.heavy_subjects_morning_only)))
    set_meta(conn, "sched_morning_only_subject_ids", _format_id_set(config.morning_only_subject_ids))
    set_meta(conn, "sched_non_consecutive_subject_ids", _format_id_set(config.non_consecutive_subject_ids))
    set_meta(conn, "sched_single_pair_subject_ids", _format_id_set(config.single_pair_subject_ids))
    set_meta(conn, "sched_avoid_teacher_gaps", str(int(config.avoid_teacher_gaps)))
    set_meta(conn, "sched_avoid_teacher_lone_periods", str(int(config.avoid_teacher_lone_periods)))
    set_meta(conn, "sched_balance_afternoon_teachers", str(int(config.balance_afternoon_teachers)))
    set_meta(conn, "sched_mandatory_morning_weekdays", _format_weekday_tuple(config.mandatory_morning_weekdays))
    set_meta(conn, "sched_avoid_gdtc_consecutive_days", str(int(config.avoid_gdtc_consecutive_days)))
    set_meta(conn, "sched_max_teacher_periods_per_day", str(config.max_teacher_periods_per_day))
    set_meta(conn, "sched_max_heavy_per_session", str(config.max_heavy_per_session))
    set_meta(conn, "sched_hdtn_period2_afternoon", str(int(config.hdtn_period2_afternoon)))
    set_meta(conn, "sched_avoid_heavy_afternoon_period3", str(int(config.avoid_heavy_afternoon_period3)))
    set_meta(conn, "sched_avoid_teacher_4_consecutive_morning", str(int(config.avoid_teacher_4_consecutive_morning)))
    set_meta(conn, "sched_min_weekly_periods_for_lone_penalty", str(config.min_weekly_periods_for_lone_penalty))
