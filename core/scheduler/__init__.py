"""Modular scheduling engine package.

Provides backward-compatible exports for all scheduler components.
"""
from core.scheduler.constants import (
    AFTERNOON_MISMATCH_PENALTY, BAT_LIEN_MACH, BAT_NGHI_1_BUOI,
    BLOCK_COMPLETE_BONUS, CAP_TIET_NGAY, FAILURE_MESSAGE,
    FORBIDDEN_OFF_CELLS, HEAVY_MORNING_BONUS, IDLE_DAY_BONUS,
    MAX_GV_BUOI, NGUONG_KHOA, SO_LAN_THU, SO_PA_TOT,
    TEACHER_AFTERNOON_BALANCE_BONUS, TEACHER_CONSECUTIVE_BONUS,
    TEACHER_GAP_PENALTY, TEACHER_LONE_SESSION_HEURISTIC_PENALTY,
    TEACHER_MANDATORY_MORNING_BONUS,
    TEACHER_SESSION_PAIR_BONUS, TEACHER_SPLIT_DAY_PENALTY,
)
from core.scheduler.state import _State
from core.scheduler.placement import (
    _build_effective_assigned_teacher, _put_at, _remove_at,
)
from core.scheduler.feasibility import _feasible
from core.scheduler.heuristics import (
    _calculate_teacher_gap_penalty, _pick_best_scored, _pick_best_simple,
)
from core.scheduler.blocks import (
    _block_partial_state, _has_unpaired_block, _merge_one_block_period,
    _repair_unpaired_blocks, _try_place_block_atomically,
)
from core.scheduler.swaps import (
    _has_lone_period, _repair_lone_periods, _repair_teacher_lone_sessions,
    _try_swap_repair,
)
from core.scheduler.teacher_off import _assign_off_slots
from core.scheduler.quality import (
    _count_teacher_gaps, _count_teacher_lone_days,
    _count_teacher_lone_sessions, _count_teacher_missing_afternoon_duty,
    _count_teacher_missing_mandatory_mornings, _count_teacher_split_sessions,
    _teacher_quality_penalty,
)
from core.scheduler.engine import run

__all__ = [
    "run",
    "_State",
    "_feasible",
    "_put_at",
    "_remove_at",
    "_build_effective_assigned_teacher",
    "_pick_best_scored",
    "_pick_best_simple",
    "_calculate_teacher_gap_penalty",
    "_try_place_block_atomically",
    "_repair_unpaired_blocks",
    "_has_unpaired_block",
    "_merge_one_block_period",
    "_block_partial_state",
    "_try_swap_repair",
    "_repair_lone_periods",
    "_repair_teacher_lone_sessions",
    "_has_lone_period",
    "_assign_off_slots",
    "_teacher_quality_penalty",
    "_count_teacher_gaps",
    "_count_teacher_lone_days",
    "_count_teacher_lone_sessions",
    "_count_teacher_split_sessions",
    "_count_teacher_missing_mandatory_mornings",
    "_count_teacher_missing_afternoon_duty",
    "MAX_GV_BUOI",
    "SO_LAN_THU",
    "SO_PA_TOT",
    "NGUONG_KHOA",
    "CAP_TIET_NGAY",
    "BAT_NGHI_1_BUOI",
    "BAT_LIEN_MACH",
    "IDLE_DAY_BONUS",
    "HEAVY_MORNING_BONUS",
    "AFTERNOON_MISMATCH_PENALTY",
    "BLOCK_COMPLETE_BONUS",
    "TEACHER_CONSECUTIVE_BONUS",
    "TEACHER_GAP_PENALTY",
    "TEACHER_SESSION_PAIR_BONUS",
    "TEACHER_LONE_SESSION_HEURISTIC_PENALTY",
    "TEACHER_SPLIT_DAY_PENALTY",
    "TEACHER_AFTERNOON_BALANCE_BONUS",
    "TEACHER_MANDATORY_MORNING_BONUS",
    "FORBIDDEN_OFF_CELLS",
    "FAILURE_MESSAGE",
]
