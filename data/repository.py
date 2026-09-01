"""Facade repository module providing backward-compatible CRUD and builder functions.

Sub-domain implementations live in data.repositories:
- entities: classes, subjects, teachers
- curriculum: assignments, quotas, role reductions, teacher quota view
- constraints: gv_ban, khung_tiet, allowed_cells, subject_class_rules
- config: meta, tuan_config, seed_history, scheduling_config
- runs: tkb_nhap, run_log, tkb_result
- builder: build_scheduling_input
"""
from __future__ import annotations

from data.repositories.entities import (
    _KEEP, delete_class, delete_subject, delete_teacher,
    get_class_by_name, get_subject_by_name, get_teacher_by_name,
    list_classes, list_subjects, list_teachers,
    upsert_class, upsert_subject, upsert_teacher,
)
from data.repositories.curriculum import (
    DEFAULT_BASE_CAP, DEFAULT_MIN_FLOOR,
    bulk_set_weekly_curriculum, get_assignments, get_base_cap, get_min_floor,
    get_periods_for_week, get_periods_per_week, get_role_reduction,
    get_teacher_caps, get_teacher_quota_view, get_weekly_curriculum,
    list_configured_weeks, set_assignment, set_base_cap, set_min_floor,
    set_periods_per_week, set_role_reduction, set_weekly_curriculum,
)
from data.repositories.constraints import (
    add_unavailability, clear_unavailability, compress_busy_cells,
    delete_subject_class_rule, get_all_class_allowed_cells,
    get_all_frame_templates, get_class_allowed_cells, get_frame_template,
    get_subject_class_allowed_cells, get_teacher_busy_cells,
    list_subject_class_rules, list_unavailability, set_class_allowed_cells,
    set_frame_template, set_teacher_busy_cells, upsert_subject_class_rule,
)
from data.repositories.config import (
    _format_id_set, _format_off_cells, _format_period_tuple,
    _format_weekday_tuple, _now, _parse_id_set, _parse_off_cells,
    _parse_period_tuple, _parse_weekday_tuple,
    add_seed_history, clear_seed_history, get_meta, get_scheduling_config,
    get_tuan_config, list_seed_history, set_meta, set_scheduling_config,
    set_tuan_config,
)
from data.repositories.runs import (
    bulk_replace_tkb_nhap, get_latest_run, get_latest_run_by_parity,
    get_tkb_nhap, get_tkb_result, save_run, save_tkb_result,
)
from data.repositories.builder import (
    _canonical_timeslots, _weekday_matches, build_scheduling_input,
)

__all__ = [
    # entities
    "list_classes", "get_class_by_name", "upsert_class", "delete_class",
    "list_subjects", "get_subject_by_name", "upsert_subject", "delete_subject",
    "list_teachers", "get_teacher_by_name", "upsert_teacher", "delete_teacher", "_KEEP",
    # curriculum
    "DEFAULT_BASE_CAP", "DEFAULT_MIN_FLOOR",
    "get_base_cap", "set_base_cap", "get_min_floor", "set_min_floor",
    "get_role_reduction", "set_role_reduction",
    "get_teacher_quota_view", "get_teacher_caps",
    "get_assignments", "set_assignment", "get_periods_per_week", "set_periods_per_week",
    "get_weekly_curriculum", "set_weekly_curriculum", "bulk_set_weekly_curriculum",
    "get_periods_for_week", "list_configured_weeks",
    # constraints
    "list_unavailability", "add_unavailability", "clear_unavailability",
    "get_teacher_busy_cells", "compress_busy_cells", "set_teacher_busy_cells",
    "get_frame_template", "get_all_frame_templates", "set_frame_template",
    "get_class_allowed_cells", "get_all_class_allowed_cells", "set_class_allowed_cells",
    "list_subject_class_rules", "upsert_subject_class_rule", "delete_subject_class_rule",
    "get_subject_class_allowed_cells",
    # config
    "_now", "get_meta", "set_meta",
    "get_tuan_config", "set_tuan_config",
    "list_seed_history", "add_seed_history", "clear_seed_history",
    "get_scheduling_config", "set_scheduling_config",
    "_parse_off_cells", "_format_off_cells",
    "_parse_weekday_tuple", "_format_weekday_tuple",
    "_parse_id_set", "_format_id_set",
    "_parse_period_tuple", "_format_period_tuple",
    # runs
    "get_tkb_nhap", "bulk_replace_tkb_nhap",
    "save_run", "save_tkb_result", "get_latest_run", "get_latest_run_by_parity", "get_tkb_result",
    # builder
    "_canonical_timeslots", "_weekday_matches", "build_scheduling_input",
]
