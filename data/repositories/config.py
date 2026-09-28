"""Application metadata and scheduling configuration repository."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Optional, Any
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


def _parse_bool(raw: Any, default: bool) -> bool:
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    s = str(raw).strip().lower()
    if not s:
        return default
    if s in ("1", "true", "t", "yes", "y", "on"):
        return True
    if s in ("0", "false", "f", "no", "n", "off"):
        return False
    return default


def _parse_int(raw: Any, default: Any = None) -> Any:
    if raw is None:
        return default
    if isinstance(raw, int) and not isinstance(raw, bool):
        return raw
    s = str(raw).strip()
    if not s:
        return default
    try:
        return int(s)
    except (ValueError, TypeError):
        return default


def _parse_off_cells(raw: Any) -> frozenset:
    if not raw:
        return frozenset()
    cells = set()
    for token in str(raw).split(","):
        token = token.strip()
        if not token:
            continue
        if len(token) >= 2 and token[:-1].isdigit() and token[-1] in ("S", "C"):
            cells.add((int(token[:-1]), token[-1]))
    return frozenset(cells)


def _format_off_cells(cells) -> str:
    return ",".join(f"{wd}{session}" for wd, session in sorted(cells))


def _parse_weekday_tuple(raw: Any) -> tuple:
    if not raw:
        return ()
    wds = []
    for x in str(raw).split(","):
        s = x.strip()
        if s.isdigit():
            wds.append(int(s))
    return tuple(wds)


def _format_weekday_tuple(weekdays) -> str:
    return ",".join(str(wd) for wd in weekdays)


def _parse_id_set(raw: Any) -> frozenset:
    if not raw:
        return frozenset()
    ids = set()
    for x in str(raw).split(","):
        s = x.strip()
        if s.isdigit():
            ids.add(int(s))
    return frozenset(ids)


def _format_id_set(ids) -> str:
    return ",".join(str(i) for i in sorted(ids))


def _parse_period_tuple(raw: Any) -> tuple:
    if not raw:
        return ()
    return tuple(int(x) for x in str(raw).split(",") if x.strip().isdigit())


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
    lone_exempt_raw = get_meta(conn, "sched_lone_session_exempt_teacher_ids")
    compact_sched_raw = get_meta(conn, "sched_compact_schedule_teacher_ids")
    mand_morning_min_raw = get_meta(conn, "sched_min_weekly_periods_for_mandatory_morning")
    strict_morning_raw = get_meta(conn, "sched_strict_morning_weekdays")
    avoid_teacher_gaps_raw = get_meta(conn, "sched_avoid_teacher_gaps")
    avoid_teacher_lone_periods_raw = get_meta(conn, "sched_avoid_teacher_lone_periods")
    balance_afternoon_teachers_raw = get_meta(conn, "sched_balance_afternoon_teachers")
    mandatory_mornings_raw = get_meta(conn, "sched_mandatory_morning_weekdays")
    avoid_gdtc_consecutive_raw = get_meta(conn, "sched_avoid_gdtc_consecutive_days")
    gdtc_morning_raw = get_meta(conn, "sched_gdtc_morning_allowed_periods")
    gdtc_afternoon_raw = get_meta(conn, "sched_gdtc_afternoon_allowed_periods")
    gvcn_p2_exempt_raw = get_meta(conn, "sched_gvcn_monday_period2_exempt_class_ids")
    return SchedulingConfig(
        gdtc_avoid_period=_parse_int(
            get_meta(conn, "sched_gdtc_avoid_period"), default.gdtc_avoid_period
        ),
        gdtc_morning_allowed_periods=(
            _parse_period_tuple(gdtc_morning_raw) if gdtc_morning_raw is not None
            else default.gdtc_morning_allowed_periods
        ),
        gdtc_afternoon_allowed_periods=(
            _parse_period_tuple(gdtc_afternoon_raw) if gdtc_afternoon_raw is not None
            else default.gdtc_afternoon_allowed_periods
        ),
        chao_co_weekday=_parse_int(
            get_meta(conn, "sched_hdtn_p1_weekday") or get_meta(conn, "sched_chao_co_weekday"),
            default.chao_co_weekday,
        ),
        chao_co_period=_parse_int(
            get_meta(conn, "sched_hdtn_p1_period") or get_meta(conn, "sched_chao_co_period"),
            default.chao_co_period,
        ),
        chao_co_session=str(get_meta(conn, "sched_hdtn_p1_session") or default.chao_co_session),
        hdtn_p1_weekday=_parse_int(
            get_meta(conn, "sched_hdtn_p1_weekday") or get_meta(conn, "sched_chao_co_weekday"),
            default.hdtn_p1_weekday,
        ),
        hdtn_p1_session=str(get_meta(conn, "sched_hdtn_p1_session") or default.hdtn_p1_session),
        hdtn_p1_period=_parse_int(
            get_meta(conn, "sched_hdtn_p1_period") or get_meta(conn, "sched_chao_co_period"),
            default.hdtn_p1_period,
        ),
        hdtn_p2_weekday=_parse_int(
            get_meta(conn, "sched_hdtn_p2_weekday"), default.hdtn_p2_weekday
        ),
        hdtn_p2_session=(
            str(get_meta(conn, "sched_hdtn_p2_session"))
            if get_meta(conn, "sched_hdtn_p2_session") is not None and str(get_meta(conn, "sched_hdtn_p2_session")).strip() != ""
            else default.hdtn_p2_session
        ),
        hdtn_p2_period=_parse_int(
            get_meta(conn, "sched_hdtn_p2_period"), default.hdtn_p2_period
        ),
        hdtn_p3_weekday=_parse_int(
            get_meta(conn, "sched_hdtn_p3_weekday"), default.hdtn_p3_weekday
        ),
        hdtn_p3_session=(
            str(get_meta(conn, "sched_hdtn_p3_session"))
            if get_meta(conn, "sched_hdtn_p3_session") is not None and str(get_meta(conn, "sched_hdtn_p3_session")).strip() != ""
            else default.hdtn_p3_session
        ),
        hdtn_p3_period=_parse_int(
            get_meta(conn, "sched_hdtn_p3_period"), default.hdtn_p3_period
        ),
        hdtn_mode=str(get_meta(conn, "sched_hdtn_mode") or default.hdtn_mode),
        hdtn_thematic_mode=str(get_meta(conn, "sched_hdtn_thematic_mode") or default.hdtn_thematic_mode),
        hdtn_thematic_weekday=_parse_int(
            get_meta(conn, "sched_hdtn_thematic_weekday"), default.hdtn_thematic_weekday
        ),
        hdtn_thematic_session=str(get_meta(conn, "sched_hdtn_thematic_session") or default.hdtn_thematic_session),
        hdtn_thematic_start_period=_parse_int(
            get_meta(conn, "sched_hdtn_thematic_start_period"), default.hdtn_thematic_start_period
        ),
        max_heavy_consecutive=_parse_int(
            get_meta(conn, "sched_max_heavy_consecutive"), default.max_heavy_consecutive
        ),
        max_periods_per_session=_parse_int(
            get_meta(conn, "sched_max_periods_per_session"), default.max_periods_per_session
        ),
        teacher_off_sessions_per_week=_parse_int(
            get_meta(conn, "sched_teacher_off_sessions_per_week"), default.teacher_off_sessions_per_week
        ),
        teacher_off_sessions_mode=str(
            get_meta(conn, "sched_teacher_off_sessions_mode") or default.teacher_off_sessions_mode
        ),
        forbidden_off_cells=_parse_off_cells(forbidden_raw) if forbidden_raw else default.forbidden_off_cells,
        reserved_off_weekdays_chieu=(
            _parse_weekday_tuple(reserved_raw) if reserved_raw else default.reserved_off_weekdays_chieu
        ),
        heavy_subject_priority_periods=_parse_int(
            get_meta(conn, "sched_heavy_subject_priority_periods"), default.heavy_subject_priority_periods
        ),
        afternoon_preferred_subject_ids=(
            _parse_id_set(afternoon_preferred_raw) if afternoon_preferred_raw
            else default.afternoon_preferred_subject_ids
        ),
        heavy_subjects_morning_only=_parse_bool(
            get_meta(conn, "sched_heavy_subjects_morning_only"), default.heavy_subjects_morning_only
        ),
        strict_morning_weekdays=(
            _parse_weekday_tuple(strict_morning_raw) if strict_morning_raw is not None
            else default.strict_morning_weekdays
        ),
        min_weekly_periods_for_mandatory_morning=_parse_int(
            mand_morning_min_raw, default.min_weekly_periods_for_mandatory_morning
        ),
        lone_session_exempt_teacher_ids=(
            _parse_id_set(lone_exempt_raw) if lone_exempt_raw is not None
            else default.lone_session_exempt_teacher_ids
        ),
        compact_schedule_teacher_ids=(
            _parse_id_set(compact_sched_raw) if compact_sched_raw is not None
            else default.compact_schedule_teacher_ids
        ),
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
        avoid_teacher_gaps=_parse_bool(
            avoid_teacher_gaps_raw, default.avoid_teacher_gaps
        ),
        avoid_teacher_lone_periods=_parse_bool(
            avoid_teacher_lone_periods_raw, default.avoid_teacher_lone_periods
        ),
        balance_afternoon_teachers=_parse_bool(
            balance_afternoon_teachers_raw, default.balance_afternoon_teachers
        ),
        mandatory_morning_weekdays=(
            _parse_weekday_tuple(mandatory_mornings_raw) if mandatory_mornings_raw is not None
            else default.mandatory_morning_weekdays
        ),
        avoid_gdtc_consecutive_days=_parse_bool(
            avoid_gdtc_consecutive_raw, default.avoid_gdtc_consecutive_days
        ),
        max_teacher_periods_per_day=_parse_int(
            get_meta(conn, "sched_max_teacher_periods_per_day"), default.max_teacher_periods_per_day
        ),
        max_heavy_per_session=_parse_int(
            get_meta(conn, "sched_max_heavy_per_session"), default.max_heavy_per_session
        ),
        hdtn_period2_afternoon=_parse_bool(
            get_meta(conn, "sched_hdtn_period2_afternoon"), default.hdtn_period2_afternoon
        ),
        avoid_heavy_afternoon_period3=_parse_bool(
            get_meta(conn, "sched_avoid_heavy_afternoon_period3"), default.avoid_heavy_afternoon_period3
        ),
        avoid_teacher_4_consecutive_morning=_parse_bool(
            get_meta(conn, "sched_avoid_teacher_4_consecutive_morning"), default.avoid_teacher_4_consecutive_morning
        ),
        min_weekly_periods_for_lone_penalty=_parse_int(
            get_meta(conn, "sched_min_weekly_periods_for_lone_penalty"), default.min_weekly_periods_for_lone_penalty
        ),
        use_cpsat=_parse_bool(
            get_meta(conn, "sched_use_cpsat"), default.use_cpsat
        ),
        cpsat_time_limit_seconds=_parse_int(
            get_meta(conn, "sched_cpsat_time_limit_seconds"), default.cpsat_time_limit_seconds
        ),
        cpsat_minimize_changes=_parse_bool(
            get_meta(conn, "sched_cpsat_minimize_changes"), default.cpsat_minimize_changes
        ),
        cpsat_workers=_parse_int(
            get_meta(conn, "sched_cpsat_workers"), default.cpsat_workers
        ),
        gvcn_monday_period2_enabled=_parse_bool(
            get_meta(conn, "sched_gvcn_monday_period2_enabled"), default.gvcn_monday_period2_enabled
        ),
        gvcn_monday_period2_exempt_class_ids=(
            _parse_id_set(gvcn_p2_exempt_raw) if gvcn_p2_exempt_raw is not None
            else default.gvcn_monday_period2_exempt_class_ids
        ),
        balance_morning_academic_load=_parse_bool(
            get_meta(conn, "sched_balance_morning_academic_load"), default.balance_morning_academic_load
        ),
        max_academic_per_morning=_parse_int(
            get_meta(conn, "sched_max_academic_per_morning"), default.max_academic_per_morning
        ),
        min_academic_per_morning=_parse_int(
            get_meta(conn, "sched_min_academic_per_morning"), default.min_academic_per_morning
        ),
    )


def set_scheduling_config(conn: sqlite3.Connection, config: SchedulingConfig) -> None:
    set_meta(conn, "sched_gdtc_avoid_period", str(config.gdtc_avoid_period))
    set_meta(conn, "sched_gdtc_morning_allowed_periods", _format_period_tuple(config.gdtc_morning_allowed_periods))
    set_meta(conn, "sched_gdtc_afternoon_allowed_periods", _format_period_tuple(config.gdtc_afternoon_allowed_periods))
    set_meta(conn, "sched_chao_co_weekday", str(config.hdtn_p1_weekday))
    set_meta(conn, "sched_chao_co_period", str(config.hdtn_p1_period))
    set_meta(conn, "sched_hdtn_p1_weekday", str(config.hdtn_p1_weekday))
    set_meta(conn, "sched_hdtn_p1_session", str(config.hdtn_p1_session))
    set_meta(conn, "sched_hdtn_p1_period", str(config.hdtn_p1_period))
    set_meta(conn, "sched_hdtn_p2_weekday", str(config.hdtn_p2_weekday) if config.hdtn_p2_weekday is not None else "")
    set_meta(conn, "sched_hdtn_p2_session", str(config.hdtn_p2_session) if config.hdtn_p2_session is not None else "")
    set_meta(conn, "sched_hdtn_p2_period", str(config.hdtn_p2_period) if config.hdtn_p2_period is not None else "")
    set_meta(conn, "sched_hdtn_p3_weekday", str(config.hdtn_p3_weekday) if config.hdtn_p3_weekday is not None else "")
    set_meta(conn, "sched_hdtn_p3_session", str(config.hdtn_p3_session) if config.hdtn_p3_session is not None else "")
    set_meta(conn, "sched_hdtn_p3_period", str(config.hdtn_p3_period) if config.hdtn_p3_period is not None else "")
    set_meta(conn, "sched_hdtn_mode", str(config.hdtn_mode))
    set_meta(conn, "sched_hdtn_thematic_mode", str(config.hdtn_thematic_mode))
    set_meta(conn, "sched_hdtn_thematic_weekday", str(config.hdtn_thematic_weekday) if config.hdtn_thematic_weekday is not None else "")
    set_meta(conn, "sched_hdtn_thematic_session", str(config.hdtn_thematic_session) if config.hdtn_thematic_session is not None else "S")
    set_meta(conn, "sched_hdtn_thematic_start_period", str(config.hdtn_thematic_start_period) if config.hdtn_thematic_start_period is not None else "")
    set_meta(conn, "sched_max_heavy_consecutive", str(config.max_heavy_consecutive))
    set_meta(conn, "sched_max_periods_per_session", str(config.max_periods_per_session))
    set_meta(conn, "sched_teacher_off_sessions_per_week", str(config.teacher_off_sessions_per_week))
    set_meta(conn, "sched_teacher_off_sessions_mode", str(config.teacher_off_sessions_mode))
    set_meta(conn, "sched_forbidden_off_cells", _format_off_cells(config.forbidden_off_cells))
    set_meta(conn, "sched_reserved_off_weekdays_chieu", _format_weekday_tuple(config.reserved_off_weekdays_chieu))
    set_meta(conn, "sched_heavy_subject_priority_periods", str(config.heavy_subject_priority_periods))
    set_meta(conn, "sched_afternoon_preferred_subject_ids", _format_id_set(config.afternoon_preferred_subject_ids))
    set_meta(conn, "sched_heavy_subjects_morning_only", str(int(config.heavy_subjects_morning_only)))
    set_meta(conn, "sched_morning_only_subject_ids", _format_id_set(config.morning_only_subject_ids))
    set_meta(conn, "sched_lone_session_exempt_teacher_ids", _format_id_set(config.lone_session_exempt_teacher_ids))
    set_meta(conn, "sched_compact_schedule_teacher_ids", _format_id_set(config.compact_schedule_teacher_ids))
    set_meta(conn, "sched_min_weekly_periods_for_mandatory_morning", str(config.min_weekly_periods_for_mandatory_morning))
    set_meta(conn, "sched_strict_morning_weekdays", _format_weekday_tuple(config.strict_morning_weekdays))
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
    set_meta(conn, "sched_use_cpsat", str(int(config.use_cpsat)))
    set_meta(conn, "sched_cpsat_time_limit_seconds", str(config.cpsat_time_limit_seconds))
    set_meta(conn, "sched_cpsat_minimize_changes", str(int(config.cpsat_minimize_changes)))
    set_meta(conn, "sched_cpsat_workers", str(config.cpsat_workers))
    set_meta(conn, "sched_gvcn_monday_period2_enabled", str(int(config.gvcn_monday_period2_enabled)))
    set_meta(conn, "sched_gvcn_monday_period2_exempt_class_ids", _format_id_set(config.gvcn_monday_period2_exempt_class_ids))
    set_meta(conn, "sched_balance_morning_academic_load", str(int(config.balance_morning_academic_load)))
    set_meta(conn, "sched_max_academic_per_morning", str(config.max_academic_per_morning))
    set_meta(conn, "sched_min_academic_per_morning", str(config.min_academic_per_morning))
