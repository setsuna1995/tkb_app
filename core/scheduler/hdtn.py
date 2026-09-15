"""Helper utilities for resolving Hoạt động trải nghiệm (HĐTN) pinned slots."""
from __future__ import annotations

from typing import Optional
from core.models import SchedulingConfig, Slot


def get_hdtn_pinned_slots_for_class(
    class_id: int,
    class_slots: list[Slot],
    config: SchedulingConfig,
    need_hdtn: int,
    hdtn_thematic_week: bool = False,
) -> list[Slot]:
    """Trả về danh sách các Slot được ghim cho môn HĐTN của một lớp theo cấu hình config.

    Môn HĐTN thường có tối đa 3 tiết/tuần:
    - Tiết 1: Sinh hoạt dưới cờ (Chào cờ). Mặc định: Thứ 2, Sáng, Tiết 1.
    - Tiết 3: Sinh hoạt lớp (SHL). Mặc định: Tiết cuối sáng Thứ 6 (nếu học chiều) hoặc Thứ 7 (nếu chỉ học sáng).
    - Tiết 2: Hoạt động trải nghiệm theo chủ đề. Mặc định: None (tự do, thuật toán tự xếp).
    """
    if hdtn_thematic_week or need_hdtn <= 0:
        return []

    pinned: list[Slot] = []
    used_slot_ids = set()

    # ── Tiết 1: Sinh hoạt dưới cờ (Chào cờ) ──
    p1_wd = getattr(config, "hdtn_p1_weekday", None) or getattr(config, "chao_co_weekday", 2)
    p1_sess = getattr(config, "hdtn_p1_session", "S")
    p1_period = getattr(config, "hdtn_p1_period", None) or getattr(config, "chao_co_period", 1)

    s1 = next(
        (s for s in class_slots if s.ts.weekday == p1_wd and s.ts.session == p1_sess and s.ts.period == p1_period),
        None,
    )
    if s1 is not None and s1.slot_id not in used_slot_ids:
        pinned.append(s1)
        used_slot_ids.add(s1.slot_id)

    if need_hdtn < 2:
        return pinned

    # ── Tiết 3: Sinh hoạt lớp (SHL) ──
    # Với chương trình 2 hay 3 tiết, tiết cố định cơ bản luôn là Sinh hoạt lớp
    p3_wd = getattr(config, "hdtn_p3_weekday", None)
    if p3_wd is not None:
        p3_sess = getattr(config, "hdtn_p3_session", "S")
        p3_period = getattr(config, "hdtn_p3_period", None)
        if p3_period is not None and p3_period > 0:
            s3 = next(
                (s for s in class_slots
                 if s.ts.weekday == p3_wd and s.ts.session == p3_sess and s.ts.period == p3_period),
                None,
            )
        else:
            candidates = [
                s for s in class_slots
                if s.ts.weekday == p3_wd and s.ts.session == p3_sess and s.slot_id not in used_slot_ids
            ]
            s3 = max(candidates, key=lambda s: s.ts.period) if candidates else None

        if s3 is not None and s3.slot_id not in used_slot_ids:
            pinned.append(s3)
            used_slot_ids.add(s3.slot_id)
    else:
        # Mặc định: Tiết cuối sáng Thứ 6 (nếu học chiều) hoặc Thứ 7 (nếu chỉ học sáng)
        class_has_chieu = any(s.ts.session == "C" for s in class_slots)
        target_wd = 6 if class_has_chieu else 7
        day_slots = [
            s for s in class_slots
            if s.ts.session == "S" and s.ts.weekday == target_wd and s.slot_id not in used_slot_ids
        ]
        if day_slots:
            s3 = max(day_slots, key=lambda s: s.ts.period)
            if s3 is not None and s3.slot_id not in used_slot_ids:
                pinned.append(s3)
                used_slot_ids.add(s3.slot_id)

    if need_hdtn < 3:
        return pinned

    # ── Tiết 2: Hoạt động giáo dục theo chủ đề (tiết thứ 3 khi need >= 3) ──
    p2_wd = getattr(config, "hdtn_p2_weekday", None)
    if p2_wd is not None:
        p2_sess = getattr(config, "hdtn_p2_session", "S")
        p2_period = getattr(config, "hdtn_p2_period", None)
        if p2_period is not None and p2_period > 0:
            s2 = next(
                (s for s in class_slots
                 if s.ts.weekday == p2_wd and s.ts.session == p2_sess and s.ts.period == p2_period),
                None,
            )
        else:
            candidates = [
                s for s in class_slots
                if s.ts.weekday == p2_wd and s.ts.session == p2_sess and s.slot_id not in used_slot_ids
            ]
            s2 = max(candidates, key=lambda s: s.ts.period) if candidates else None

        if s2 is not None and s2.slot_id not in used_slot_ids:
            pinned.append(s2)
            used_slot_ids.add(s2.slot_id)

    return pinned
