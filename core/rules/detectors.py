"""Post-generation detectors: one function per rule, each counting violations
of a finished schedule against the school's DECLARED thresholds.

Detectors know nothing about relaxation -- every Violation they return is a
BREACH. Whether a breach was forced is decided afterwards by
core.rules.violations.classify, so evidence can never make a violation vanish.

Each detector names the CP-SAT construct it mirrors. Change both sides
together and run tests/test_rule_equivalence.py.
"""
from __future__ import annotations

from collections import Counter, defaultdict

from core.models import WEEKDAY_NAMES
from core.rules.params import EffectiveParams
from core.rules.view import ScheduleView
from core.rules.violations import Violation

SESSION_NAMES = {"S": "Sáng", "C": "Chiều"}
MIN_FREE_MORNING_PERIODS = 2      # fewer free periods than this = cannot avoid a lone session (II.4)
LONG_MORNING_RUN = 4              # II.14
MIN_PERIODS_FOR_GAP = 2


def _day(weekday: int) -> str:
    return WEEKDAY_NAMES.get(weekday, f"Thứ {weekday}")


def _session(session: str) -> str:
    return SESSION_NAMES.get(session, str(session))


def _teacher_totals(view: ScheduleView, skip_ids: frozenset = frozenset()) -> Counter:
    return Counter(t for _slot, _subject, t in view.placed() if t is not None and t not in skip_ids)


def _teacher_session_counts(view: ScheduleView, skip_ids: frozenset = frozenset()) -> Counter:
    return Counter((t, slot.ts.weekday, slot.ts.session) for slot, _subject, t in view.placed()
                   if t is not None and t not in skip_ids)


# T.CONFLICT -- mirrors constraints.py:_add_teacher_constraints rule 1 (AddAtMostOne per teacher/timeslot)
def detect_teacher_conflicts(view: ScheduleView, params: EffectiveParams) -> list:
    classes_at = defaultdict(list)
    for slot, _subject_id, teacher_id in view.placed():
        if teacher_id is not None:
            classes_at[teacher_id, slot.ts.weekday, slot.ts.session, slot.ts.period].append(slot.class_id)
    return [
        Violation("T.CONFLICT", teacher_id=tid, weekday=wd, session=sess, period=period, count=len(class_ids),
                  detail=f"{view.teacher_name(tid)}: trùng lịch {_day(wd)} {_session(sess)} tiết {period} "
                         f"giữa các lớp {', '.join(view.class_name(c) for c in class_ids)}")
        for (tid, wd, sess, period), class_ids in classes_at.items() if len(class_ids) > 1
    ]


# T.BUSY -- mirrors constraints.py:_add_teacher_constraints rule 2 (ban_busy -> x == 0)
def detect_teacher_busy(view: ScheduleView, params: EffectiveParams) -> list:
    return [
        Violation("T.BUSY", teacher_id=tid, class_id=slot.class_id, subject_id=subject_id,
                  weekday=slot.ts.weekday, session=slot.ts.session, period=slot.ts.period,
                  detail=f"{view.teacher_name(tid)}: xếp dạy {view.class_name(slot.class_id)} vào giờ đã báo bận "
                         f"({_day(slot.ts.weekday)} {_session(slot.ts.session)} tiết {slot.ts.period})")
        for slot, subject_id, tid in view.placed()
        if tid is not None and (tid, slot.ts.ts_id) in view.ban_busy
    ]


# T.DAY_CAP (Tiêu chí II.2) -- mirrors constraints.py:_add_teacher_constraints rule 4
def detect_teacher_day_cap(view: ScheduleView, params: EffectiveParams) -> list:
    cap = params.max_teacher_periods_per_day
    per_day = Counter((t, slot.ts.weekday) for slot, _subject, t in view.placed() if t is not None)
    return [
        Violation("T.DAY_CAP", teacher_id=tid, weekday=wd, count=n,
                  detail=f"{view.teacher_name(tid)}: dạy {n} tiết vào {_day(wd)} (vượt trần {cap} tiết/ngày)")
        for (tid, wd), n in per_day.items() if n > cap
    ]


# II.7 -- mirrors objectives.py section 3 (penalty_terms["II.7"])
def detect_teacher_gaps(view: ScheduleView, params: EffectiveParams) -> list:
    periods = defaultdict(list)
    for slot, _subject_id, teacher_id in view.placed():
        if teacher_id is not None:
            periods[teacher_id, slot.ts.weekday, slot.ts.session].append(slot.ts.period)
    return [
        Violation("II.7", teacher_id=tid, weekday=wd, session=sess,
                  detail=f"{view.teacher_name(tid)}: bị trống tiết {_day(wd)} {_session(sess)} "
                         f"(tiết dạy: {', '.join(str(p) for p in sorted(ps))})")
        for (tid, wd, sess), ps in periods.items()
        if len(ps) >= MIN_PERIODS_FOR_GAP and max(ps) - min(ps) + 1 > len(ps)
    ]


# II.14 -- mirrors objectives.py section 4 (penalty_terms["II.14"])
def detect_teacher_4_consecutive_mornings(view: ScheduleView, params: EffectiveParams) -> list:
    totals = _teacher_totals(view)
    mornings = Counter((t, slot.ts.weekday) for slot, _subject, t in view.placed()
                       if t is not None and slot.ts.session == "S")
    return [
        Violation("II.14", teacher_id=tid, weekday=wd, session="S", count=n,
                  detail=f"{view.teacher_name(tid)}: dạy {n} tiết liên tục sáng {_day(wd)}")
        for (tid, wd), n in mornings.items()
        if n >= LONG_MORNING_RUN and totals[tid] <= params.max_load_for_4consec_penalty
    ]


# II.4 (buổi lẻ) -- mirrors objectives.py section 1, lone[t, wd, sess] in penalty_terms["II.4"]
def detect_teacher_lone_sessions(view: ScheduleView, params: EffectiveParams) -> list:
    totals = _teacher_totals(view, params.lone_exempt_ids)
    return [
        Violation("II.4", teacher_id=tid, weekday=wd, session=sess, count=n,
                  detail=f"{view.teacher_name(tid)}: {_day(wd)} {_session(sess)} chỉ có 1 tiết (buổi lẻ)")
        for (tid, wd, sess), n in _teacher_session_counts(view, params.lone_exempt_ids).items()
        if n == 1 and totals[tid] >= params.min_weekly_periods_for_lone_penalty
    ]


# II.4 (ngày lẻ) -- mirrors objectives.py section 1, lone_day terms in penalty_terms["II.4"]
def detect_teacher_lone_days(view: ScheduleView, params: EffectiveParams) -> list:
    totals = _teacher_totals(view, params.lone_exempt_ids)
    per_day = Counter((t, slot.ts.weekday) for slot, _subject, t in view.placed()
                      if t is not None and t not in params.lone_exempt_ids)
    return [
        Violation("II.4", teacher_id=tid, weekday=wd, count=n,
                  detail=f"{view.teacher_name(tid)}: {_day(wd)} cả ngày chỉ có đúng 1 tiết")
        for (tid, wd), n in per_day.items()
        if n == 1 and totals[tid] >= params.min_weekly_periods_for_lone_penalty
    ]


# II.8 -- mirrors objectives.py section 1, split terms in penalty_terms["II.8"].
# Narrow meaning S == 1 and C == 1 (user decision Q1, 2026-09-17).
def detect_teacher_split_days(view: ScheduleView, params: EffectiveParams) -> list:
    totals = _teacher_totals(view, params.lone_exempt_ids)
    per_session = _teacher_session_counts(view, params.lone_exempt_ids)
    days = dict.fromkeys((tid, wd) for (tid, wd, _sess) in per_session)
    return [
        Violation("II.8", teacher_id=tid, weekday=wd,
                  detail=f"{view.teacher_name(tid)}: {_day(wd)} sáng 1 tiết + chiều 1 tiết")
        for (tid, wd) in days
        if per_session[tid, wd, "S"] == 1 and per_session[tid, wd, "C"] == 1
        and totals[tid] >= params.min_weekly_periods_for_lone_penalty
    ]


def is_teacher_busy_morning(view: ScheduleView, teacher_id: int, weekday: int) -> bool:
    """A teacher counts as busy on a morning when fewer than 2 free periods remain there
    (II.4 forbids a 1-period session). Same meaning as constraints.py:_is_teacher_busy_morning;
    the two copies merge in Plan 3 (spec §5.4.4)."""
    if not view.ban_busy:
        return False
    morning = [s for s in view.slots if s.ts.weekday == weekday and s.ts.session == "S"]
    if not morning:
        return False
    own_classes = view.teacher_classes.get(teacher_id, frozenset())
    candidates = [s for s in morning if s.class_id in own_classes] or morning
    free_periods = {s.ts.period for s in candidates if (teacher_id, s.ts.ts_id) not in view.ban_busy}
    return len(free_periods) < MIN_FREE_MORNING_PERIODS


# II.3 -- mirrors objectives.py section 2 (penalty_terms["II.3"])
def detect_teacher_missing_mandatory_mornings(view: ScheduleView, params: EffectiveParams) -> list:
    watched = set(params.mandatory_morning_weekdays) | set(params.strict_morning_weekdays)
    present = {(t, slot.ts.weekday) for slot, _subject, t in view.placed()
               if t is not None and slot.ts.session == "S" and slot.ts.weekday in watched}
    violations = []
    for tid, total in _teacher_totals(view).items():
        for wd in _required_mornings(tid, total, params):
            if (tid, wd) in present or params.pinned_day_offs.get(tid) == wd or is_teacher_busy_morning(view, tid, wd):
                continue
            violations.append(Violation(
                "II.3", teacher_id=tid, weekday=wd, session="S",
                detail=f"{view.teacher_name(tid)}: không có tiết dạy sáng {_day(wd)} (sáng bắt buộc có mặt)",
            ))
    return violations


def _required_mornings(teacher_id: int, total: int, params: EffectiveParams) -> tuple:
    strict = () if teacher_id in params.bgh_ids else params.strict_morning_weekdays
    if total < params.min_weekly_periods_for_mandatory_morning:
        return tuple(strict)
    mandatory = tuple(wd for wd in params.mandatory_morning_weekdays if wd not in params.strict_morning_weekdays)
    return (*strict, *mandatory)
