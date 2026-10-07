"""Chẩn đoán nút thắt: vì sao phương án TKB chưa đẹp hơn được.

Phân biệt 4 loại: thiếu thời gian giải (time), mâu thuẫn dung lượng (capacity),
tiêu chí phải nới lỏng / vi phạm nhiều (rule), và GV tập trung vi phạm (teacher).
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Optional

from core.models import ScheduleResult, SchedulingInput
from core.rules import RULES

GAP_WORTH_MORE_TIME = 0.05   # dưới 5% khoảng cách tới cận dưới thì thêm giờ gần như vô ích
TEACHER_MIN_SHARE = 0.15

RULE_KNOBS = {
    "II.3": "Cấu hình → Hiện diện: bớt thứ bắt buộc có mặt, nâng ngưỡng tiết/tuần, hoặc bật 'Cho phép 1 tiết lẻ vào buổi bắt buộc'.",
    "II.4": "Cấu hình → Hiện diện: nâng ngưỡng tiết/tuần phạt lẻ tiết, hoặc thêm GV đặc thù vào danh sách miễn trừ buổi lẻ.",
    "II.8": "Cấu hình → Hiện diện: thêm GV vào danh sách miễn trừ, hoặc giảm lịch báo bận khiến GV phải chia sáng/chiều.",
}
DEFAULT_ACTION = "Xem chi tiết trong mục Kiểm định chất lượng bên dưới."


@dataclass(frozen=True)
class Bottleneck:
    kind: str
    severity: float
    title: str
    evidence: str
    action: str
    rule_id: Optional[str] = None
    teacher_id: Optional[int] = None


def _title(rule_id: str) -> str:
    return RULES[rule_id].title_vi if rule_id in RULES else rule_id


def search_headroom(result: ScheduleResult) -> Optional[float]:
    """Tỉ lệ điểm phạt còn có thể giảm tối đa (theo cận dưới CP-SAT). 0.0 = đã tối ưu, None = không có số liệu."""
    d = result.diagnostics or {}
    if d.get("final_status") == "OPTIMAL":
        return 0.0
    obj, bound = d.get("objective"), d.get("best_bound")
    if obj is None or bound is None:
        return None
    if obj <= 0:
        return 0.0
    return round(max(0.0, (obj - bound) / obj), 4)


def more_time_can_help(result: ScheduleResult) -> bool:
    if any(not r.get("proven_infeasible") for r in result.relaxed_rules):
        return True  # nới lỏng do hết giờ chứ chưa chứng minh bất khả
    gap = search_headroom(result)
    return gap is None or gap > 0.0


def analyze_bottlenecks(inp: SchedulingInput, result: ScheduleResult, violations: list,
                        limit: int = 5) -> list[Bottleneck]:
    # ponytail: severity là thang heuristic cố định; chuyển sang đo "what-if" (giải lại khi nới 1 luật) nếu xếp hạng sai thực tế
    d = result.diagnostics or {}
    found: list[Bottleneck] = []

    gap = search_headroom(result)
    if gap is not None and gap >= GAP_WORTH_MORE_TIME:
        found.append(Bottleneck(
            "time", 50 + 100 * gap, "Bộ giải dừng khi chưa chắc chắn tối ưu",
            f"Điểm phạt {d['objective']:.0f}, cận dưới lý thuyết {d['best_bound']:.0f} "
            f"→ còn có thể cải thiện tối đa ~{gap:.0%}.",
            "Bấm “⏱️ Giải thêm thời gian” — bộ giải tiếp tục từ phương án hiện tại.",
        ))

    for row in d.get("morning_capacity", []):
        if row["cap"] > 0 and row["need"] > row["cap"]:
            found.append(Bottleneck(
                "capacity", 200, f"Sáng Thứ {row['weekday']} không đủ chỗ cho GV bắt buộc có mặt",
                f"{row['teachers']} GV phải có mặt cần tối thiểu {row['need']} tiết, nhưng chỉ có {row['cap']} ô.",
                RULE_KNOBS["II.3"], rule_id="II.3",
            ))

    relaxed = {r["rule_id"] for r in result.relaxed_rules}
    for item in result.relaxed_rules:
        rid, proven = item["rule_id"], item.get("proven_infeasible", False)
        found.append(Bottleneck(
            "rule", 150 if proven else 120, f"Phải nới lỏng {rid}: {_title(rid)}",
            "Đã chứng minh không thể đạt đồng thời với các ràng buộc khác." if proven
            else "Không tìm được nghiệm giữ cứng tiêu chí này trong thời gian cho phép — thử thêm thời gian trước.",
            RULE_KNOBS.get(rid, DEFAULT_ACTION), rule_id=rid,
        ))

    for rid, n in Counter(v.rule_id for v in violations).most_common(3):
        if rid not in relaxed:
            found.append(Bottleneck("rule", float(n), f"{rid}: {_title(rid)}",
                                    f"{n} vi phạm trong phương án này.",
                                    RULE_KNOBS.get(rid, DEFAULT_ACTION), rule_id=rid))

    found.extend(_teacher_hotspots(inp, result, violations))
    return sorted(found, key=lambda b: -b.severity)[:limit]


def _teacher_hotspots(inp: SchedulingInput, result: ScheduleResult, violations: list, top: int = 3) -> list[Bottleneck]:
    per_teacher = defaultdict(list)
    for v in violations:
        if v.teacher_id is not None and v.teacher_id > 0:
            per_teacher[v.teacher_id].append(v.rule_id)
    total = sum(len(r) for r in per_teacher.values())
    if not total:
        return []

    teachers = {t.teacher_id: t for t in inp.teachers}
    ts_by_id = {ts.ts_id: ts for ts in inp.timeslots}
    load = getattr(result.effective_params, "teacher_load", None) or {}
    out = []
    for tid, rids in sorted(per_teacher.items(), key=lambda kv: -len(kv[1]))[:top]:
        share = len(rids) / total
        if len(rids) < 2 or share < TEACHER_MIN_SHARE:
            continue
        t = teachers.get(tid)
        busy = len({(ts_by_id[ts_id].weekday, ts_by_id[ts_id].session)
                    for (b_tid, ts_id) in inp.ban_busy if b_tid == tid and ts_id in ts_by_id})
        day_off = f", ghim nghỉ trọn Thứ {t.pinned_full_day_off}" if t and t.pinned_full_day_off else ""
        rule_txt = ", ".join(f"{r}×{c}" for r, c in Counter(rids).most_common())
        out.append(Bottleneck(
            "teacher", 10.0 * len(rids), f"GV {t.name if t else tid} là điểm nghẽn",
            f"Gánh {len(rids)}/{total} vi phạm ({share:.0%}): {rule_txt}. "
            f"Tải {load.get(tid, '?')} tiết/tuần, báo bận {busy} buổi{day_off}.",
            "Rà lại lịch báo bận / ghim nghỉ của GV này; nếu là GV đặc thù (thiết bị, thư viện) thì thêm vào danh sách miễn trừ.",
            teacher_id=tid,
        ))
    return out
