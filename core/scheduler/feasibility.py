"""Hard constraint validation for placing a subject/teacher in a slot."""
from __future__ import annotations

from typing import Optional
from core import frame as frame_mod
from core.models import SchedulingConfig, TimeSlot, WEEKDAYS
from core.scheduler.constants import BAT_LIEN_MACH, BAT_NGHI_1_BUOI, CAP_TIET_NGAY
from core.scheduler.state import _State


def _feasible(class_id: int, ts: TimeSlot, subject_id: int, teacher_id: int,
              state: _State, role_index, day_capacity: Optional[dict] = None,
              config: Optional[SchedulingConfig] = None,
              subject_class_allowed_cells: Optional[dict] = None) -> bool:
    config = config or SchedulingConfig()
    # luật môn/lớp/buổi: nếu cặp (môn, lớp) có danh sách ô cho phép thì mọi ô khác
    # bị cấm cứng. Không có luật (None / thiếu key) => không ràng buộc, y như cũ.
    if subject_class_allowed_cells:
        allowed = subject_class_allowed_cells.get((subject_id, class_id))
        if allowed is not None and (ts.weekday, ts.session) not in allowed:
            return False
    if (teacher_id, ts.ts_id) in state.busy:
        return False
    if state.session_count[(teacher_id, ts.weekday, ts.session)] >= config.max_periods_per_session:
        return False
    max_teacher_day = getattr(config, "max_teacher_periods_per_day", 5)
    if state.teacher_day_count[(teacher_id, ts.weekday)] >= max_teacher_day:
        return False
    if BAT_NGHI_1_BUOI and (ts.weekday, ts.session) in state.gv_off_slots.get(teacher_id, ()):
        return False
    if subject_id == role_index.gdtc_id:
        morning_allowed = getattr(config, "gdtc_morning_allowed_periods", (1, 2, 3, 4))
        afternoon_allowed = getattr(config, "gdtc_afternoon_allowed_periods", (2, 3))
        if ts.session == "S" and morning_allowed and ts.period not in morning_allowed:
            return False
        if ts.session == "C" and afternoon_allowed and ts.period not in afternoon_allowed:
            return False
        if ts.period == config.gdtc_avoid_period:
            return False
    if getattr(config, "heavy_subjects_morning_only", False) and subject_id in role_index.heavy_ids and ts.session == "C":
        return False
    if getattr(config, "avoid_heavy_afternoon_period3", True) and subject_id in role_index.heavy_ids and ts.session == "C" and ts.period == 3:
        return False
    morning_only = getattr(config, "morning_only_subject_ids", None)
    if morning_only and subject_id in morning_only and ts.session == "C":
        return False
    
    non_consecutive = getattr(config, "non_consecutive_subject_ids", None) or frozenset()
    avoid_gdtc = getattr(config, "avoid_gdtc_consecutive_days", True)
    if (subject_id in non_consecutive) or (avoid_gdtc and subject_id == role_index.gdtc_id):
        if ts.weekday > 2 and state.placed.get((class_id, subject_id, ts.weekday - 1)):
            return False
        if ts.weekday < 8 and state.placed.get((class_id, subject_id, ts.weekday + 1)):
            return False

    cap_today = day_capacity.get((class_id, ts.weekday), CAP_TIET_NGAY) if day_capacity else CAP_TIET_NGAY
    if state.day_count[(class_id, ts.weekday)] >= cap_today:
        return False
    if BAT_LIEN_MACH and ts.period > 1:
        if not state.occupied.get((class_id, ts.weekday, ts.session, ts.period - 1), False):
            return False
    positions = state.placed[(class_id, subject_id, ts.weekday)]
    cap_d = role_index.block_size.get(subject_id, 1)
    if len(positions) >= cap_d:
        return False
    if getattr(role_index, "single_pair_ids", None) and subject_id in role_index.single_pair_ids and len(positions) == 1:
        other_pair_days = [wd for wd in WEEKDAYS if wd != ts.weekday and len(state.placed[(class_id, subject_id, wd)]) >= 2]
        if other_pair_days:
            return False
    if positions:
        if any(p_session != ts.session for p_session, _p_period in positions):
            return False
        periods = sorted(p_period for _p_session, p_period in positions)
        if ts.period not in (periods[0] - 1, periods[-1] + 1):
            return False
    if subject_id in role_index.heavy_ids:
        max_heavy_sess = getattr(config, "max_heavy_per_session", 3)
        if state.session_heavy_count[(class_id, ts.weekday, ts.session)] >= max_heavy_sess:
            return False
        window = config.max_heavy_consecutive + 1
        last_start = frame_mod.MAX_PERIODS_PER_SESSION - config.max_heavy_consecutive
        for w in range(1, last_start + 1):
            if w <= ts.period <= w + window - 1:
                all_heavy = True
                for offset in range(window):
                    pos = w + offset
                    if not (state.heavy_at.get((class_id, ts.weekday, ts.session, pos), False) or pos == ts.period):
                        all_heavy = False
                        break
                if all_heavy:
                    return False
    return True
