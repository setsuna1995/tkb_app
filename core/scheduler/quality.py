"""Teacher schedule quality scoring and penalty calculation."""
from __future__ import annotations

from collections import defaultdict
from core.models import SchedulingConfig, Slot
from core.scheduler.constants import TEACHER_LONE_SESSION_SPREAD_PENALTY


def _count_teacher_gaps(slots: list[Slot], assigned: dict, slot_teacher: dict) -> int:
    teacher_sessions = defaultdict(list)
    for slot in slots:
        subj = assigned.get(slot.slot_id)
        if subj not in (None, -1):
            tid = slot_teacher.get(slot.slot_id)
            if tid is not None:
                teacher_sessions[(tid, slot.ts.weekday, slot.ts.session)].append(slot.ts.period)
    total_gaps = 0
    for periods in teacher_sessions.values():
        if len(periods) >= 2:
            span = max(periods) - min(periods) + 1
            total_gaps += (span - len(periods))
    return total_gaps


def _count_teacher_lone_days(slots: list[Slot], assigned: dict, slot_teacher: dict, min_weekly_periods: int = 0,
                              exempt_teacher_ids: frozenset = frozenset()) -> int:
    """exempt_teacher_ids: GV được miễn trừ luật buổi lẻ theo tên, không theo
    ngưỡng tải -- dành cho GV vốn phải có mặt ở trường vì nhiệm vụ khác (phụ
    trách thiết bị, thư viện...), nên một buổi 1 tiết không bắt họ đi lại thêm.
    Cấu hình trên trang Cấu hình xếp lịch, không hard-code (2026-09-04)."""
    teacher_days = defaultdict(int)
    teacher_totals = defaultdict(int)
    for slot in slots:
        subj = assigned.get(slot.slot_id)
        if subj not in (None, -1):
            tid = slot_teacher.get(slot.slot_id)
            if tid is not None and tid > 0:
                teacher_days[(tid, slot.ts.weekday)] += 1
                teacher_totals[tid] += 1
    return sum(1 for (tid, wd), count in teacher_days.items()
               if count == 1 and teacher_totals[tid] >= min_weekly_periods
               and tid not in exempt_teacher_ids)


def _count_teacher_concentrated_lone_sessions(slots: list[Slot], assigned: dict, slot_teacher: dict,
                                               min_weekly_periods: int = 0,
                                               exempt_teacher_ids: frozenset = frozenset()) -> int:
    """Counts lone sessions BEYOND THE FIRST for each teacher.

    _count_teacher_lone_sessions is linear: three teachers with one lone session
    each scores exactly the same as one teacher carrying all three. The school's
    preference (2026-09-04) is the former -- spread the unavoidable ones one per
    teacher rather than dumping them on one person -- so this adds the extra term
    the linear count is missing. Purely a scoring signal; it is NOT part of the
    II.4 hard gate, which still counts every lone session once.
    """
    t_sess = defaultdict(int)
    teacher_totals = defaultdict(int)
    for slot in slots:
        subj = assigned.get(slot.slot_id)
        if subj not in (None, -1):
            tid = slot_teacher.get(slot.slot_id)
            if tid is not None and tid > 0:
                t_sess[(tid, slot.ts.weekday, slot.ts.session)] += 1
                teacher_totals[tid] += 1

    lone_per_teacher = defaultdict(int)
    for (tid, _wd, _sess), count in t_sess.items():
        if (count == 1 and teacher_totals[tid] >= min_weekly_periods
                and tid not in exempt_teacher_ids):
            lone_per_teacher[tid] += 1
    return sum(max(0, n - 1) for n in lone_per_teacher.values())


def _count_teacher_lone_sessions(slots: list[Slot], assigned: dict, slot_teacher: dict, min_weekly_periods: int = 0,
                                  exempt_teacher_ids: frozenset = frozenset()) -> int:
    """exempt_teacher_ids: xem _count_teacher_lone_days."""
    t_sess = defaultdict(int)
    teacher_totals = defaultdict(int)
    for slot in slots:
        subj = assigned.get(slot.slot_id)
        if subj not in (None, -1):
            tid = slot_teacher.get(slot.slot_id)
            if tid is not None and tid > 0:
                t_sess[(tid, slot.ts.weekday, slot.ts.session)] += 1
                teacher_totals[tid] += 1
    return sum(1 for (tid, wd, sess), count in t_sess.items()
               if count == 1 and teacher_totals[tid] >= min_weekly_periods
               and tid not in exempt_teacher_ids)


def _count_teacher_split_sessions(slots: list[Slot], assigned: dict, slot_teacher: dict, min_weekly_periods: int = 0,
                                   exempt_teacher_ids: frozenset = frozenset()) -> int:
    """exempt_teacher_ids: xem _count_teacher_lone_days."""
    teacher_day_sessions = defaultdict(lambda: defaultdict(int))
    teacher_totals = defaultdict(int)
    for slot in slots:
        subj = assigned.get(slot.slot_id)
        if subj not in (None, -1):
            tid = slot_teacher.get(slot.slot_id)
            if tid is not None and tid > 0:
                teacher_day_sessions[(tid, slot.ts.weekday)][slot.ts.session] += 1
                teacher_totals[tid] += 1
    return sum(
        1 for (tid, wd), sess_counts in teacher_day_sessions.items()
        if sess_counts.get("S", 0) > 0 and sess_counts.get("C", 0) > 0
        and (sess_counts.get("S", 0) == 1 or sess_counts.get("C", 0) == 1)
        and teacher_totals[tid] >= min_weekly_periods
        and tid not in exempt_teacher_ids
    )


def _count_teacher_4_consecutive_mornings(slots: list[Slot], assigned: dict, slot_teacher: dict, max_load_for_penalty: int = 20) -> int:
    t_morn_periods = defaultdict(list)
    teacher_totals = defaultdict(int)
    for slot in slots:
        subj = assigned.get(slot.slot_id)
        if subj not in (None, -1):
            tid = slot_teacher.get(slot.slot_id)
            if tid is not None and tid > 0:
                teacher_totals[tid] += 1
                if slot.ts.session == "S":
                    t_morn_periods[(tid, slot.ts.weekday)].append(slot.ts.period)
    count_4 = 0
    for (tid, wd), periods in t_morn_periods.items():
        if len(periods) >= 4 and teacher_totals[tid] <= max_load_for_penalty:
            count_4 += 1
    return count_4


def _count_teacher_missing_mandatory_mornings(slots: list[Slot], assigned: dict, slot_teacher: dict,
                                               mandatory_mornings: tuple = (2, 5, 6),
                                               min_weekly_periods: int = 10,
                                               strict_weekdays: tuple = (),
                                               exempt_teacher_ids: frozenset = frozenset()) -> int:
    """min_weekly_periods: chỉ ép GV có tải >= ngưỡng này phải có mặt các sáng bắt
    buộc. Mặc định 10 = đúng hằng số cũ nằm cứng trong hàm này; nay cấu hình được
    trên trang Cấu hình xếp lịch (2026-09-04).

    strict_weekdays: các sáng mà MỌI GV đều phải có tiết, bỏ qua ngưỡng tải
    (yêu cầu của trường 2026-09-04: sáng Thứ 2 và Thứ 6 toàn thể GV phải có tiết).
    exempt_teacher_ids: GV được miễn khỏi phần strict này -- dành cho BGH, tải của
    họ quá ít để trải đủ các sáng. Danh sách do caller tính từ chức vụ GV."""
    teacher_morns = defaultdict(lambda: defaultdict(int))
    teacher_totals = defaultdict(int)
    for s in slots:
        subj = assigned.get(s.slot_id)
        if subj not in (None, -1):
            tid = slot_teacher.get(s.slot_id)
            if tid is not None and tid > 0:
                teacher_totals[tid] += 1
                if s.ts.session == "S" and (s.ts.weekday in mandatory_mornings
                                             or s.ts.weekday in strict_weekdays):
                    teacher_morns[tid][s.ts.weekday] += 1

    missing = 0
    for tid, total in teacher_totals.items():
        # Sáng "strict": mọi GV đều phải có tiết, trừ BGH (exempt_teacher_ids).
        if tid not in exempt_teacher_ids:
            for wd in strict_weekdays:
                if teacher_morns[tid][wd] == 0:
                    missing += 1
        # Sáng bắt buộc thường: chỉ ép GV đủ tải, và không đếm trùng các sáng strict.
        if total >= min_weekly_periods:
            for wd in mandatory_mornings:
                if wd in strict_weekdays:
                    continue
                if teacher_morns[tid][wd] == 0:
                    missing += 1
    return missing


def _count_teacher_missing_afternoon_duty(slots: list[Slot], assigned: dict, slot_teacher: dict) -> int:
    classes_with_afternoon = {s.class_id for s in slots if s.ts.session == "C"}
    teacher_afternoon_count = defaultdict(int)
    teacher_total_count = defaultdict(int)
    teacher_classes = defaultdict(set)

    for s in slots:
        subj = assigned.get(s.slot_id)
        if subj not in (None, -1):
            tid = slot_teacher.get(s.slot_id)
            if tid is not None and tid > 0:
                teacher_total_count[tid] += 1
                teacher_classes[tid].add(s.class_id)
                if s.ts.session == "C":
                    teacher_afternoon_count[tid] += 1

    missing = 0
    for tid, total in teacher_total_count.items():
        if total >= 4 and any(cid in classes_with_afternoon for cid in teacher_classes[tid]):
            if teacher_afternoon_count[tid] == 0:
                missing += 1
    return missing


def _teacher_quality_penalty(slots: list[Slot], assigned: dict, slot_teacher: dict, config: SchedulingConfig) -> int:
    penalty = 0
    mand_morns = getattr(config, "mandatory_morning_weekdays", (2, 5, 6))
    min_lone_load = getattr(config, "min_weekly_periods_for_lone_penalty", 8)
    lone_exempt = getattr(config, "lone_session_exempt_teacher_ids", frozenset()) or frozenset()
    if getattr(config, "avoid_teacher_gaps", True):
        penalty += _count_teacher_gaps(slots, assigned, slot_teacher) * 350
    if getattr(config, "avoid_teacher_lone_periods", True):
        penalty += _count_teacher_lone_sessions(slots, assigned, slot_teacher, min_weekly_periods=min_lone_load,
                                                 exempt_teacher_ids=lone_exempt) * 500
        # 200 -> 700 (2026-09-04): at 200 a "1 morning + 1 afternoon" day scored
        # 1200 while the SAME two lone periods split across two separate days
        # scored 1500 -- i.e. the scoring preferred making a teacher come in twice
        # in one day for two periods. The school wants the opposite, so a split day
        # must cost more than the 2x250 lone-day charge it avoids.
        penalty += _count_teacher_split_sessions(slots, assigned, slot_teacher, min_weekly_periods=min_lone_load,
                                                  exempt_teacher_ids=lone_exempt) * 700
        penalty += _count_teacher_lone_days(slots, assigned, slot_teacher, min_weekly_periods=min_lone_load,
                                             exempt_teacher_ids=lone_exempt) * 250
        penalty += _count_teacher_concentrated_lone_sessions(
            slots, assigned, slot_teacher, min_weekly_periods=min_lone_load, exempt_teacher_ids=lone_exempt
        ) * TEACHER_LONE_SESSION_SPREAD_PENALTY
    if getattr(config, "avoid_teacher_4_consecutive_morning", True):
        penalty += _count_teacher_4_consecutive_mornings(slots, assigned, slot_teacher, max_load_for_penalty=20) * 300
    penalty += _count_teacher_missing_mandatory_mornings(
        slots, assigned, slot_teacher, mand_morns,
        min_weekly_periods=getattr(config, "min_weekly_periods_for_mandatory_morning", 10),
    ) * 800
    if getattr(config, "balance_afternoon_teachers", True):
        penalty += _count_teacher_missing_afternoon_duty(slots, assigned, slot_teacher) * 200
    return penalty
