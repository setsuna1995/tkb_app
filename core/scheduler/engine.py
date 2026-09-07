"""Orchestrator for school timetable scheduling using Google OR-Tools CP-SAT solver."""
from __future__ import annotations

import logging
from typing import Optional

from core.models import ScheduleResult, SchedulingConfig, SchedulingInput, is_bgh
from core.scheduler.constants import (
    FAILURE_MESSAGE, NGUONG_KHOA, SO_LAN_THU, SO_PA_TOT,
)
from core.scheduler.quality import (
    _count_teacher_lone_days, _count_teacher_lone_sessions,
    _count_teacher_missing_mandatory_mornings, _count_teacher_split_sessions,
)
from core.scheduler.state import _State


def _check_hard_post_generation_rules(inp: SchedulingInput, state: _State, config: SchedulingConfig) -> tuple[list, int]:
    """Post-generation hard gate for the HĐSP rules that need full-schedule
    visibility (II.3, II.4, II.8). Returns (violated_rule_ids, total)."""
    violated = []
    total = 0
    mand_morns = getattr(config, "mandatory_morning_weekdays", (2, 5, 6))
    pinned_day_offs = {t.teacher_id: t.pinned_full_day_off for t in getattr(inp, "teachers", ()) if getattr(t, "pinned_full_day_off", None) is not None}
    missing = _count_teacher_missing_mandatory_mornings(
        inp.slots, state.assigned, state.slot_teacher, mand_morns,
        min_weekly_periods=getattr(config, "min_weekly_periods_for_mandatory_morning", 10),
        strict_weekdays=getattr(config, "strict_morning_weekdays", ()) or (),
        exempt_teacher_ids=frozenset(t.teacher_id for t in inp.teachers if is_bgh(t)),
        ban_busy=getattr(inp, "ban_busy", None),
        pinned_day_offs=pinned_day_offs,
    )
    if missing > 0:
        violated.append("II.3")
    total += missing
    if getattr(config, "avoid_teacher_lone_periods", True):
        min_lone_load = getattr(config, "min_weekly_periods_for_lone_penalty", 8)
        lone_exempt = getattr(config, "lone_session_exempt_teacher_ids", frozenset()) or frozenset()
        lone_sessions = _count_teacher_lone_sessions(inp.slots, state.assigned, state.slot_teacher,
                                                     min_weekly_periods=min_lone_load, exempt_teacher_ids=lone_exempt)
        lone_days = _count_teacher_lone_days(inp.slots, state.assigned, state.slot_teacher,
                                              min_weekly_periods=min_lone_load, exempt_teacher_ids=lone_exempt)
        if lone_sessions > 0 or lone_days > 0:
            violated.append("II.4")
        total += lone_sessions + lone_days
        split = _count_teacher_split_sessions(inp.slots, state.assigned, state.slot_teacher,
                                               min_weekly_periods=min_lone_load, exempt_teacher_ids=lone_exempt)
        if split > 0:
            violated.append("II.8")
        total += split
    return violated, total


def run(inp: SchedulingInput, *, max_attempts: int = SO_LAN_THU,
        target_successes: int = SO_PA_TOT, lock_threshold: int = NGUONG_KHOA,
        progress_cb=None) -> ScheduleResult:
    """Điều phối xếp TKB toàn trường bằng bộ giải tối ưu toàn cục CP-SAT (Google OR-Tools).

    Toàn bộ bài toán được mô hình hóa và giải quyết tối ưu bằng CP-SAT solver
    (core/scheduler/cpsat_model.py). Động cơ cũ (heuristic random-greedy và local swaps)
    đã được loại bỏ hoàn toàn.
    Các tham số (max_attempts, target_successes, lock_threshold) được giữ lại nhằm
    duy trì tương thích ngược API với các caller và test suite cũ.
    """
    from core.scheduler import cpsat_model

    config = inp.config
    time_limit = getattr(config, "cpsat_time_limit_seconds", 45)

    try:
        built = cpsat_model.build_model(inp)
        result = cpsat_model.solve_to_result(built, time_limit_s=time_limit, progress_cb=progress_cb)
        if result is not None:
            return result

        return ScheduleResult(
            success=False,
            attempts_tried=1,
            successes_found=0,
            cells_total=len(inp.slots),
            failure_reason="Bộ giải CP-SAT không tìm được phương án thỏa mãn các ràng buộc cứng trong thời gian cho phép.",
            solver_name="cpsat",
        )
    except cpsat_model.CpSatUnavailable:
        return ScheduleResult(
            success=False,
            attempts_tried=0,
            successes_found=0,
            cells_total=len(inp.slots),
            failure_reason="Bộ giải CP-SAT yêu cầu thư viện 'ortools' (chưa được cài đặt trong môi trường Python hiện tại).",
            solver_name="cpsat",
        )
    except Exception as exc:
        logging.exception("Lỗi trong quá trình chạy bộ giải CP-SAT: %s", exc)
        return ScheduleResult(
            success=False,
            attempts_tried=1,
            successes_found=0,
            cells_total=len(inp.slots),
            failure_reason=f"Lỗi khi chạy bộ giải CP-SAT: {exc}",
            solver_name="cpsat",
        )
