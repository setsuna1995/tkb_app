"""Quota checks (KiemTra sheet port) and the TKB health score.

Rule violations are detected in core/rules/detectors.py; this module only
compares quotas and turns detector output into a 100-point score.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Optional

from core.models import ROLE_HDTN, WEEKDAY_NAMES, SchedulingInput
from core.rules.detectors import run_detectors
from core.rules.params import resolve_effective_params
from core.rules.view import build_schedule_view
from core.rules.violations import group_by_rule
from core.scheduler.quality import (
    _count_subject_consecutive_days,
    _count_teacher_back_to_back_shifts,
    _count_teacher_excess_gaps,
)


def compute_actual_counts(slots: list, assignment: dict) -> dict:
    counts = defaultdict(int)
    for slot in slots:
        subject_id = assignment.get(slot.slot_id)
        if subject_id is not None:
            counts[(subject_id, slot.class_id)] += 1
    return counts


def compute_quota_diff(slots: list, assignment: dict, periods_per_week: dict, parity: Optional[str] = None) -> dict:
    """Returns (subject_id, class_id) -> actual - quota. Expect all zeros.
    Supports either:
    - 2-tuple dict: (subject_id, class_id) -> periods
    - 3-tuple dict: (subject_id, class_id, parity) -> periods (requires parity or defaults to 'C')
    """
    actual = compute_actual_counts(slots, assignment)
    sample_key = next(iter(periods_per_week.keys()), None)
    if sample_key and len(sample_key) == 2:
        keys = set(actual.keys()) | set(periods_per_week.keys())
        diff = {}
        for key in keys:
            quota = periods_per_week.get(key, 0)
            diff[key] = actual.get(key, 0) - quota
        return diff
    else:
        effective_parity = parity or "C"
        keys = set(actual.keys()) | {(s_id, c_id) for (s_id, c_id, p) in periods_per_week if p == effective_parity}
        diff = {}
        for key in keys:
            quota = periods_per_week.get((key[0], key[1], effective_parity), 0)
            diff[key] = actual.get(key, 0) - quota
        return diff


def _recommendations(violations: list, kind: str, category: str) -> list:
    return [{"type": kind, "category": category, "message": v.detail} for v in violations]


def compute_tkb_health_score(inp: SchedulingInput, assignment: dict) -> dict:
    """Đánh giá toàn diện sức khỏe TKB theo thang điểm 100 với 3 trụ cột:
    1. Sư phạm học sinh (Pedagogical Quality - 40%)
    2. Tiện nghi & Công bằng Giáo viên (Teacher Ergonomics & Fairness - 35%)
    3. Tuân thủ HĐSP & Kế hoạch (HĐSP Compliance - 25%)

    Mọi luật HĐSP đến từ core.rules.detectors -- hàm này chỉ chấm điểm, không tự
    cài đặt lại luật. Điểm theo thang sư phạm, khác thang tối ưu của bộ giải.
    """
    view = build_schedule_view(inp, assignment)
    found = group_by_rule(run_detectors(view, resolve_effective_params(inp)))
    class_map = {c.class_id: c.name for c in inp.classes}
    subj_map = {s.subject_id: s.name for s in inp.subjects}
    teacher_map = {t.teacher_id: t.name for t in inp.teachers}

    recommendations = []

    # ─────────────────────────────────────────────────────────────
    # Trụ cột 1: SƯ PHẠM HỌC SINH (100đ)
    # ─────────────────────────────────────────────────────────────
    ped_penalty = 0.0

    # 1.1 Giãn cách môn 2-3 tiết/tuần
    cls_subj_days = defaultdict(set)
    for s, subj, _teacher in view.placed():
        cls_subj_days[(s.class_id, subj)].add(s.ts.weekday)

    consec_subject_violations = []
    for (cls_id, subj_id), days in cls_subj_days.items():
        n = inp.need.get((subj_id, cls_id), 0)
        # Bỏ qua HĐTN
        subj_obj = next((sb for sb in inp.subjects if sb.subject_id == subj_id), None)
        if subj_obj and subj_obj.role_code == ROLE_HDTN:
            continue
        if n in (2, 3):
            sorted_days = sorted(days)
            for i in range(len(sorted_days) - 1):
                if sorted_days[i + 1] == sorted_days[i] + 1:
                    w1, w2 = sorted_days[i], sorted_days[i + 1]
                    consec_subject_violations.append((cls_id, subj_id, w1, w2))
                    c_name = class_map.get(cls_id, f"Lớp #{cls_id}")
                    s_name = subj_map.get(subj_id, f"Môn #{subj_id}")
                    w1_str = WEEKDAY_NAMES.get(w1, f"T{w1}")
                    w2_str = WEEKDAY_NAMES.get(w2, f"T{w2}")
                    if len(consec_subject_violations) <= 3:
                        recommendations.append({
                            "type": "info",
                            "category": "Sư phạm",
                            "message": f"{c_name}: Môn {s_name} học 2 ngày liên tiếp ({w1_str} - {w2_str}) — khuyến nghị giãn cách thêm nếu điều kiện khung cho phép.",
                        })
    # Tiêu chí phụ: chỉ trừ nhẹ tối đa 5 điểm toàn trường để không lấn át tiêu chuẩn chính của trường
    ped_penalty += min(5.0, len(consec_subject_violations) * 0.5)

    # 1.2 Trần môn nặng liên tiếp
    heavy_run_violations = found.get("C.HEAVY_CONSEC", [])
    recommendations += _recommendations(heavy_run_violations, "warning", "Sư phạm")
    ped_penalty += len(heavy_run_violations) * 15.0

    # 1.3 Môn nặng tiết 3 chiều
    heavy_p3_violations = found.get("C.HEAVY_P3", [])
    recommendations += _recommendations(heavy_p3_violations, "warning", "Sư phạm")
    ped_penalty += len(heavy_p3_violations) * 10.0

    # 1.4 GDTC ngoài khung giờ
    gdtc_violations = found.get("C.GDTC_PERIOD", [])
    recommendations += _recommendations(gdtc_violations, "warning", "Sư phạm")
    ped_penalty += len(gdtc_violations) * 10.0

    # 1.5 Cân bằng tải môn học thuật buổi sáng
    acad_overload_violations = found.get("ACAD.MAX", [])
    acad_underload_violations = found.get("ACAD.MIN", [])
    recommendations += _recommendations(acad_overload_violations, "warning", "Sư phạm")
    recommendations += _recommendations(acad_underload_violations, "info", "Sư phạm")
    ped_penalty += min(20.0, len(acad_overload_violations) * 10.0 + len(acad_underload_violations) * 2.0)

    pedagogical_score = max(0.0, min(100.0, 100.0 - ped_penalty))

    # ─────────────────────────────────────────────────────────────
    # Trụ cột 2: TIỆN NGHI & CÔNG BẰNG GIÁO VIÊN (100đ)
    # ─────────────────────────────────────────────────────────────
    teacher_penalty = 0.0

    # 2.1 Tiết trống giữa buổi & Lũy tiến gaps (không có buổi trống thì không có gap lũy tiến)
    gaps_list = found.get("II.7", [])
    extra_gap1, extra_gap2 = (
        _count_teacher_excess_gaps(inp.slots, view.assignment, view.slot_teacher) if gaps_list else (0, 0)
    )
    teacher_penalty += min(30.0, len(gaps_list) * 1.5) + min(10.0, extra_gap1 * 1.0) + min(10.0, extra_gap2 * 2.0)
    recommendations += _recommendations(gaps_list[:5], "warning", "Giáo viên")

    # 2.2 Chống nhảy ca gắt (chiều muộn -> sáng sớm) - Tiêu chí phụ
    t_late = set()
    t_early = set()
    for s, _subj, tid in view.placed():
        if tid is None:
            continue
        if s.ts.session == "C" and s.ts.period in (4, 5):
            t_late.add((tid, s.ts.weekday, s.ts.period))
        elif s.ts.session == "S" and s.ts.period == 1:
            t_early.add((tid, s.ts.weekday))

    b2b_violations = []
    for (tid, wd, p_late) in t_late:
        if (tid, wd + 1) in t_early:
            b2b_violations.append((tid, wd, p_late))
            tname = teacher_map.get(tid, f"GV #{tid}")
            wd_str = WEEKDAY_NAMES.get(wd, f"Thứ {wd}")
            wd_next_str = WEEKDAY_NAMES.get(wd + 1, f"Thứ {wd+1}")
            if len(b2b_violations) <= 3:
                recommendations.append({
                    "type": "info",
                    "category": "Giáo viên",
                    "message": f"{tname}: Dạy chiều muộn {wd_str} (tiết {p_late}) và sáng sớm hôm sau {wd_next_str} (tiết 1) — thời gian nghỉ ngơi hơi sát.",
                })
    teacher_penalty += min(3.0, len(b2b_violations) * 1.0)

    # 2.3 Trần dạy tiết/ngày
    day_cap_violations = found.get("T.DAY_CAP", [])
    recommendations += _recommendations(day_cap_violations, "error", "Giáo viên")
    teacher_penalty += len(day_cap_violations) * 15.0

    # 2.4 Dạy 4 tiết sáng liên tiếp
    # Tự động thích ứng theo cơ cấu ca học:
    # - Trường toàn sáng 4 tiết: Dạy 4 tiết là trọn vẹn 1 buổi học chuẩn (tiết 1-4), không trừ điểm.
    # - Trường 2 ca hoặc sáng 5 tiết: Khuyến nghị mức info, trừ điểm nhẹ tối đa 15 điểm.
    has_afternoon = any(s.ts.session == "C" for s in inp.slots)
    max_morning_p = max((s.ts.period for s in inp.slots if s.ts.session == "S"), default=4)
    is_morning_only_4p = (not has_afternoon and max_morning_p <= 4)

    consec_morning_violations = found.get("II.14", [])
    if not is_morning_only_4p:
        recommendations += _recommendations(consec_morning_violations, "info", "Giáo viên")
        teacher_penalty += min(15.0, len(consec_morning_violations) * 3.0)

    teacher_score = max(0.0, min(100.0, 100.0 - teacher_penalty))

    # ─────────────────────────────────────────────────────────────
    # Trụ cột 3: TUÂN THỦ HĐSP & KẾ HOẠCH (100đ)
    # ─────────────────────────────────────────────────────────────
    compliance_penalty = 0.0

    # 3.1 Trùng lịch
    conflicts = found.get("T.CONFLICT", [])
    compliance_penalty += len(conflicts) * 100.0
    recommendations += _recommendations(conflicts, "error", "Tuân thủ")

    # 3.2 Vi phạm giờ bận
    busy_violations = found.get("T.BUSY", [])
    compliance_penalty += len(busy_violations) * 50.0
    recommendations += _recommendations(busy_violations, "error", "Tuân thủ")

    # 3.3 Buổi lẻ 1 tiết & Ngày lẻ (II.4)
    lone_sessions = [v for v in found.get("II.4", []) if v.session is not None]
    lone_days = [v for v in found.get("II.4", []) if v.session is None]
    compliance_penalty += (len(lone_sessions) + len(lone_days)) * 15.0

    # 3.4 Ngày chia lẻ (II.8)
    split_days = found.get("II.8", [])
    compliance_penalty += len(split_days) * 15.0

    # 3.5 Thiếu sáng bắt buộc (II.3)
    missing_morning = found.get("II.3", [])
    compliance_penalty += min(20.0, len(missing_morning) * 4.0)

    compliance_score = max(0.0, min(100.0, 100.0 - compliance_penalty))

    # ─────────────────────────────────────────────────────────────
    # Tổng kết điểm & xếp loại
    # ─────────────────────────────────────────────────────────────
    overall_score = round(0.40 * pedagogical_score + 0.35 * teacher_score + 0.25 * compliance_score, 1)

    if overall_score >= 90.0:
        rating = "Xuất sắc"
        badge_color = "#28a745"
    elif overall_score >= 80.0:
        rating = "Tốt"
        badge_color = "#17a2b8"
    elif overall_score >= 70.0:
        rating = "Khá"
        badge_color = "#ffc107"
    else:
        rating = "Cần cải thiện"
        badge_color = "#dc3545"

    if not recommendations:
        recommendations.append({
            "type": "success",
            "category": "Tổng quan",
            "message": "Thời khóa biểu đạt tiêu chuẩn xuất sắc: các môn học phân bổ khoa học, giáo viên không bị phân mảnh lịch dạy.",
        })

    return {
        "overall_score": overall_score,
        "pedagogical_score": round(pedagogical_score, 1),
        "teacher_score": round(teacher_score, 1),
        "compliance_score": round(compliance_score, 1),
        "rating": rating,
        "badge_color": badge_color,
        "metrics": {
            "consecutive_subject_days": len(consec_subject_violations),
            "heavy_excess_runs": len(heavy_run_violations),
            "heavy_afternoon_p3": len(heavy_p3_violations),
            "gdtc_violations": len(gdtc_violations),
            "morning_academic_overload": len(acad_overload_violations),
            "morning_academic_underload": len(acad_underload_violations),
            "teacher_gaps_total": len(gaps_list),
            "teacher_excess_gaps": extra_gap1 + extra_gap2,
            "teacher_back_to_back": len(b2b_violations),
            "teacher_4_consec_mornings": len(consec_morning_violations),
            "teacher_day_cap_violations": len(day_cap_violations),
            "conflicts": len(conflicts),
            "busy_violations": len(busy_violations),
            "lone_sessions": len(lone_sessions),
            "lone_days": len(lone_days),
            "split_days": len(split_days),
            "missing_mornings": len(missing_morning),
        },
        "recommendations": recommendations,
    }
