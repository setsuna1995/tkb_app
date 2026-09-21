"""Bộ công cụ hỗ trợ tinh chỉnh và đối sánh phương án TKB (Interactive Refinement Studio).

Cung cấp:
- compute_candidate_metrics: Đánh giá nhanh KPI của một phương án TKB.
- validate_and_swap_slots: Kiểm tra tính hợp lệ và hoán đổi 2 tiết (Smart Swap).
"""
from __future__ import annotations

from collections import defaultdict
from typing import Optional, Tuple

from core.models import SchedulingInput, ScheduleResult
from core.rules.detectors import run_detectors
from core.rules.params import resolve_effective_params
from core.rules.view import build_schedule_view
from core.rules.violations import BREACH, SHORTFALL, classify
from core.scheduler.placement import _build_effective_assigned_teacher
from core.validation import compute_tkb_health_score


def compute_candidate_metrics(inp: SchedulingInput, result: ScheduleResult) -> dict:
    """Tính toán bộ chỉ số KPI tổng hợp cho một phương án TKB.
    
    Trả về dict gồm:
    - health_score: Điểm chất lượng TKB (0 - 100)
    - hole_periods: Tổng số tiết lủng/trống giữa buổi của toàn bộ GV
    - over_4_periods: Số lượt GV dạy > 4 tiết/buổi
    - shortfalls_count: Số vi phạm tiêu chí sư phạm mềm
    - breaches_count: Số vi phạm nghiêm trọng
    - is_valid: True nếu đạt 100% ràng buộc cứng
    """
    if not result or not result.success:
        return {
            "health_score": 0,
            "hole_periods": 999,
            "over_4_periods": 999,
            "shortfalls_count": 999,
            "breaches_count": 999,
            "is_valid": False,
        }

    # 1. Điểm sức khỏe chung
    health_score = compute_tkb_health_score(inp, result.assignment)

    # 2. Phát hiện vi phạm quy tắc sư phạm
    params = getattr(result, "effective_params", None) or resolve_effective_params(inp)
    violations = classify(run_detectors(build_schedule_view(inp, result.assignment), params), params)
    breaches = [v for v in violations if v.level == BREACH]
    shortfalls = [v for v in violations if v.level == SHORTFALL]

    # 3. Thống kê tiết lủng GV và dạy dồn buổi
    slot_by_id = {s.slot_id: s for s in inp.slots}
    eff_assigned = _build_effective_assigned_teacher(inp)
    
    # teacher_id -> (weekday, session) -> list of periods
    t_periods = defaultdict(lambda: defaultdict(list))
    for slot_id, subj_id in result.assignment.items():
        if subj_id is None or slot_id not in slot_by_id:
            continue
        s = slot_by_id[slot_id]
        tid = eff_assigned.get((subj_id, s.class_id))
        if tid is not None and tid > 0:
            t_periods[tid][(s.ts.weekday, s.ts.session)].append(s.ts.period)

    hole_periods = 0
    over_4_periods = 0
    for tid, sess_map in t_periods.items():
        for (wd, sess), per_list in sess_map.items():
            if len(per_list) > 4:
                over_4_periods += 1
            if len(per_list) >= 2:
                sorted_p = sorted(per_list)
                # Khoảng cách từ tiết đầu đến tiết cuối trừ đi số tiết thực dạy
                span = sorted_p[-1] - sorted_p[0] + 1
                hole_periods += max(0, span - len(sorted_p))

    return {
        "health_score": health_score,
        "hole_periods": hole_periods,
        "over_4_periods": over_4_periods,
        "shortfalls_count": len(shortfalls),
        "breaches_count": len(breaches),
        "is_valid": len(breaches) == 0,
    }


def validate_and_swap_slots(
    assignment: dict,
    slot_a_id: int,
    slot_b_id: int,
    inp: SchedulingInput,
) -> Tuple[bool, str, dict]:
    """Kiểm tra tính an toàn và thực hiện đổi chéo môn học giữa 2 ô (Smart Swap).
    
    Đảm bảo:
    1. Không vi phạm ô bị khóa cứng (locked_slots).
    2. Không làm phát sinh xung đột giáo viên dạy 2 nơi cùng tiết.
    3. Không xếp giáo viên vào tiết mà giáo viên đó đã báo bận.
    
    Trả về (is_success, message, new_assignment).
    """
    if slot_a_id == slot_b_id:
        return False, "Hai ô chọn trùng nhau, không cần hoán đổi.", assignment

    slot_by_id = {s.slot_id: s for s in inp.slots}
    if slot_a_id not in slot_by_id or slot_b_id not in slot_by_id:
        return False, "Không tìm thấy thông tin ô tiết tương ứng.", assignment

    slot_a = slot_by_id[slot_a_id]
    slot_b = slot_by_id[slot_b_id]

    # Kiểm tra ô bị khóa
    locked = getattr(inp, "locked_slots", {}) or {}
    if slot_a_id in locked or slot_b_id in locked:
        return False, "Một trong hai ô đã bị khóa cố định, không thể đổi chéo.", assignment

    subj_a = assignment.get(slot_a_id)
    subj_b = assignment.get(slot_b_id)

    if subj_a == subj_b:
        return False, "Hai ô đang chứa cùng một môn học.", assignment

    eff_assigned = _build_effective_assigned_teacher(inp)
    tid_a = eff_assigned.get((subj_a, slot_a.class_id)) if subj_a else None
    tid_b = eff_assigned.get((subj_b, slot_b.class_id)) if subj_b else None

    # Kiểm tra GV A có bị bận tại thời điểm của slot B không
    if tid_a is not None and tid_a > 0:
        if (tid_a, slot_b.ts.ts_id) in inp.ban_busy:
            return False, f"Giáo viên của môn ở ô 1 đã báo bận tại thời điểm của ô 2.", assignment

    # Kiểm tra GV B có bị bận tại thời điểm của slot A không
    if tid_b is not None and tid_b > 0:
        if (tid_b, slot_a.ts.ts_id) in inp.ban_busy:
            return False, f"Giáo viên của môn ở ô 2 đã báo bận tại thời điểm của ô 1.", assignment

    # Kiểm tra xung đột trùng lịch của GV A tại thời điểm slot B (với các lớp khác)
    if tid_a is not None and tid_a > 0:
        for other_sid, other_subj in assignment.items():
            if other_sid == slot_a_id or other_sid == slot_b_id or not other_subj:
                continue
            other_slot = slot_by_id.get(other_sid)
            if other_slot and other_slot.ts.ts_id == slot_b.ts.ts_id:
                other_tid = eff_assigned.get((other_subj, other_slot.class_id))
                if other_tid == tid_a:
                    return False, f"Giáo viên môn ô 1 đã có tiết dạy tại lớp khác vào thời điểm ô 2.", assignment

    # Kiểm tra xung đột trùng lịch của GV B tại thời điểm slot A (với các lớp khác)
    if tid_b is not None and tid_b > 0:
        for other_sid, other_subj in assignment.items():
            if other_sid == slot_a_id or other_sid == slot_b_id or not other_subj:
                continue
            other_slot = slot_by_id.get(other_sid)
            if other_slot and other_slot.ts.ts_id == slot_a.ts.ts_id:
                other_tid = eff_assigned.get((other_subj, other_slot.class_id))
                if other_tid == tid_b:
                    return False, f"Giáo viên môn ô 2 đã có tiết dạy tại lớp khác vào thời điểm ô 1.", assignment

    # Thực hiện hoán đổi
    new_assignment = dict(assignment)
    if subj_b is not None:
        new_assignment[slot_a_id] = subj_b
    else:
        new_assignment.pop(slot_a_id, None)

    if subj_a is not None:
        new_assignment[slot_b_id] = subj_a
    else:
        new_assignment.pop(slot_b_id, None)

    return True, "Đổi chéo thành công và hợp lệ 100%.", new_assignment
