"""Scoring heuristics and candidate selection for greedy placement."""
from __future__ import annotations

import random
from typing import Optional, Tuple
from core.models import SchedulingConfig, Slot
from core.scheduler.constants import (
    AFTERNOON_MISMATCH_PENALTY, BLOCK_COMPLETE_BONUS, HEAVY_MORNING_BONUS,
    IDLE_DAY_BONUS, TEACHER_AFTERNOON_BALANCE_BONUS, TEACHER_CONSECUTIVE_BONUS,
    TEACHER_GAP_PENALTY, TEACHER_LONE_SESSION_HEURISTIC_PENALTY,
    TEACHER_MANDATORY_MORNING_BONUS, TEACHER_SESSION_PAIR_BONUS,
    TEACHER_SPLIT_DAY_PENALTY,
)
from core.scheduler.feasibility import _feasible
from core.scheduler.state import _State


def _calculate_teacher_gap_penalty(teacher_id: int, weekday: int, session: str, period: int, state: _State) -> int:
    """Trả về điểm phạt/thưởng khi đặt giáo viên vào tiết này:
    - Thưởng (trả về số âm) nếu tiết này liền kề hoặc lấp đầy lỗ hổng hiện có của GV trong buổi.
    - Phạt (trả về số dương tỷ lệ theo khoảng cách) nếu tiết này tạo ra tiết trống/lủng xa.
    - Trả về 0 nếu GV chưa có tiết nào trong buổi này.
    """
    p_list = state.teacher_session_periods.get((teacher_id, weekday, session))
    if not p_list:
        return 0
    min_p = min(p_list)
    max_p = max(p_list)
    if period in (min_p - 1, max_p + 1):
        return -TEACHER_CONSECUTIVE_BONUS
    elif min_p < period < max_p:
        return -180  # thưởng lấp đầy lỗ hổng ở giữa
    elif period > max_p + 1:
        dist = period - (max_p + 1)
        return TEACHER_GAP_PENALTY * dist
    elif period < min_p - 1:
        dist = (min_p - 1) - period
        return TEACHER_GAP_PENALTY * dist
    return 0


def _pick_best_scored(class_id: int, slot: Slot, state: _State, role_index,
                       subjects: list, assigned_teacher: dict, pu: float, rng: random.Random,
                       day_capacity: Optional[dict] = None,
                       config: Optional[SchedulingConfig] = None,
                       subject_class_allowed_cells: Optional[dict] = None) -> Optional[Tuple[int, int]]:
    config = config or SchedulingConfig()
    ts = slot.ts
    best_subject = None
    best_teacher = None
    best_score = float("-inf")
    for subj in subjects:
        key = (subj.subject_id, class_id)
        if state.remaining_need.get(key, 0) <= 0:
            continue
        if subj.subject_id == role_index.hdtn_id and (class_id, ts.weekday) in state.shl_days:
            continue
        block_n = role_index.block_size.get(subj.subject_id, 1)
        if (block_n >= 2 and not state.placed[(class_id, subj.subject_id, ts.weekday)]
                and state.remaining_need[key] >= block_n):
            continue
        teacher_id = assigned_teacher[key]
        if not _feasible(class_id, ts, subj.subject_id, teacher_id, state, role_index, day_capacity, config,
                          subject_class_allowed_cells):
            continue
        score = state.remaining_need[key] * 100 + rng.random()
        if ts.weekday > 2 and state.placed[(class_id, subj.subject_id, ts.weekday - 1)]:
            score -= 50
            if subj.subject_id == role_index.gdtc_id:
                score -= 100
        if ts.weekday < 7 and state.placed[(class_id, subj.subject_id, ts.weekday + 1)]:
            score -= 50
            if subj.subject_id == role_index.gdtc_id:
                score -= 100
        if (state.session_count[(teacher_id, ts.weekday, "S")]
                + state.session_count[(teacher_id, ts.weekday, "C")]) == 0:
            score += IDLE_DAY_BONUS
        if (subj.subject_id in role_index.heavy_ids and config.heavy_subject_priority_periods > 0
                and ts.session == "S" and ts.period <= config.heavy_subject_priority_periods):
            score += HEAVY_MORNING_BONUS
        if (ts.session == "C" and config.afternoon_preferred_subject_ids
                and subj.subject_id not in config.afternoon_preferred_subject_ids):
            score -= AFTERNOON_MISMATCH_PENALTY
        if role_index.block_size.get(subj.subject_id, 1) >= 2 and state.placed[(class_id, subj.subject_id, ts.weekday)]:
            score += BLOCK_COMPLETE_BONUS

        if getattr(config, "avoid_teacher_gaps", True):
            gap_penalty = _calculate_teacher_gap_penalty(teacher_id, ts.weekday, ts.session, ts.period, state)
            score -= gap_penalty

        if subj.subject_id == role_index.hdtn_id and getattr(config, "hdtn_period2_afternoon", True):
            if ts.session == "C":
                score += 150
            else:
                score -= 150

        if getattr(config, "avoid_teacher_4_consecutive_morning", True) and ts.session == "S":
            morning_p = len(state.teacher_session_periods.get((teacher_id, ts.weekday, "S"), []))
            if morning_p >= 3:
                teacher_tot = state.teacher_rem_need.get(teacher_id, 0)
                if teacher_tot <= 20:
                    score -= 220

        if getattr(config, "avoid_teacher_lone_periods", True):
            current_in_session = len(state.teacher_session_periods.get((teacher_id, ts.weekday, ts.session), []))
            if current_in_session == 1:
                score += TEACHER_SESSION_PAIR_BONUS
            elif current_in_session == 0:
                teacher_rem_need = state.teacher_rem_need.get(teacher_id, 0)
                # Opening a BRAND-NEW session for this teacher only pays off if they
                # still have enough periods left to put a second one here later --
                # otherwise this cell becomes a lone session (II.4). The penalty used
                # to fire only at rem_need <= 1 (the teacher is literally out of
                # periods), which missed the much more common case of a teacher with
                # a few periods left spreading them thin across several new sessions.
                # Graduated 2026-09-04 after a real timetable showed 26 lone sessions,
                # most of them created at placement time rather than left over by the
                # repair pass.
                if teacher_rem_need <= 1:
                    score -= TEACHER_LONE_SESSION_HEURISTIC_PENALTY
                elif teacher_rem_need <= 3:
                    score -= TEACHER_LONE_SESSION_HEURISTIC_PENALTY // 2
            if ts.session == "C" and current_in_session == 0:
                morning_count = len(state.teacher_session_periods.get((teacher_id, ts.weekday, "S"), []))
                if morning_count == 1:
                    score -= TEACHER_SPLIT_DAY_PENALTY

        if getattr(config, "balance_afternoon_teachers", True) and ts.session == "C":
            if state.teacher_week_afternoon_count.get(teacher_id, 0) == 0:
                score += TEACHER_AFTERNOON_BALANCE_BONUS

        mandatory_mornings = getattr(config, "mandatory_morning_weekdays", (2, 5, 6))
        if ts.session == "S" and ts.weekday in mandatory_mornings:
            if len(state.teacher_session_periods.get((teacher_id, ts.weekday, "S"), [])) == 0:
                teacher_total_need = state.teacher_rem_need.get(teacher_id, 0)
                if teacher_total_need >= 12:
                    score += TEACHER_MANDATORY_MORNING_BONUS

        if slot.old_subject_id == subj.subject_id and rng.random() > pu:
            score += 1_000_000
        if score > best_score:
            best_score = score
            best_subject = subj.subject_id
            best_teacher = teacher_id
    if best_subject is None:
        return None
    return best_subject, best_teacher


def _pick_best_simple(class_id: int, slot: Slot, state: _State, role_index,
                       subjects: list, assigned_teacher: dict,
                       day_capacity: Optional[dict] = None,
                       config: Optional[SchedulingConfig] = None,
                       subject_class_allowed_cells: Optional[dict] = None) -> Optional[Tuple[int, int]]:
    ts = slot.ts
    best_subject = None
    best_teacher = None
    best_remaining = -1
    for subj in subjects:
        key = (subj.subject_id, class_id)
        remaining = state.remaining_need.get(key, 0)
        if remaining <= 0:
            continue
        if subj.subject_id == role_index.hdtn_id and (class_id, ts.weekday) in state.shl_days:
            continue
        teacher_id = assigned_teacher[key]
        if not _feasible(class_id, ts, subj.subject_id, teacher_id, state, role_index, day_capacity, config,
                          subject_class_allowed_cells):
            continue
        if remaining > best_remaining:
            best_remaining = remaining
            best_subject = subj.subject_id
            best_teacher = teacher_id
    if best_subject is None:
        return None
    return best_subject, best_teacher
