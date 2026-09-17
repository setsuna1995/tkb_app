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
from core.rules import RULES
from core.rules.params import EffectiveParams
from core.rules.view import ScheduleView
from core.rules.violations import Violation

SESSION_NAMES = {"S": "Sáng", "C": "Chiều"}
MIN_FREE_MORNING_PERIODS = 2      # fewer free periods than this = cannot avoid a lone session (II.4)
LONG_MORNING_RUN = 4              # II.14
MIN_PERIODS_FOR_GAP = 2
PAIR_SIZE = 2
AFTERNOON_HEAVY_FORBIDDEN_PERIOD = 3   # II.15
MIN_MORNING_PERIODS_FOR_ACADEMIC_FLOOR = 3


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


# C.GDTC_PERIOD -- mirrors constraints.py:_add_subject_constraints rule 3
def detect_gdtc_periods(view: ScheduleView, params: EffectiveParams) -> list:
    allowed = {"S": params.gdtc_morning_allowed_periods, "C": params.gdtc_afternoon_allowed_periods}
    return [
        Violation("C.GDTC_PERIOD", class_id=slot.class_id, subject_id=subject_id, weekday=slot.ts.weekday,
                  session=slot.ts.session, period=slot.ts.period,
                  detail=f"{view.class_name(slot.class_id)}: tiết GDTC ở tiết {slot.ts.period} "
                         f"{_session(slot.ts.session)} ({_day(slot.ts.weekday)}) ngoài khung giờ cho phép")
        for slot, subject_id, _teacher in view.placed()
        if subject_id == view.roles.gdtc_id and allowed.get(slot.ts.session)
        and slot.ts.period not in allowed[slot.ts.session]
    ]


# C.NON_CONSEC_DAYS -- mirrors constraints.py:_add_subject_constraints rule 4
def detect_non_consecutive_days(view: ScheduleView, params: EffectiveParams) -> list:
    days = defaultdict(set)
    for slot, subject_id, _teacher in view.placed():
        if subject_id in params.non_consecutive_subject_ids:
            days[slot.class_id, subject_id].add(slot.ts.weekday)
    return [
        Violation("C.NON_CONSEC_DAYS", class_id=cid, subject_id=sid, weekday=wd,
                  detail=f"{view.class_name(cid)}: môn {view.subject_name(sid)} học 2 ngày liền "
                         f"({_day(wd)} - {_day(wd + 1)})")
        for (cid, sid), weekdays in days.items() for wd in sorted(weekdays) if wd + 1 in weekdays
    ]


# C.MORNING_ONLY -- mirrors constraints.py:_add_subject_constraints rules 1-2
def detect_morning_only(view: ScheduleView, params: EffectiveParams) -> list:
    return [
        Violation("C.MORNING_ONLY", class_id=slot.class_id, subject_id=subject_id, weekday=slot.ts.weekday,
                  session=slot.ts.session, period=slot.ts.period,
                  detail=f"{view.class_name(slot.class_id)}: môn {view.subject_name(subject_id)} chỉ học sáng "
                         f"nhưng xếp chiều {_day(slot.ts.weekday)} tiết {slot.ts.period}")
        for slot, subject_id, _teacher in view.placed()
        if subject_id in params.morning_only_subject_ids and slot.ts.session == "C"
    ]


def _runs(sorted_periods: list) -> list:
    """(start, length) of each maximal run of consecutive periods."""
    runs = []
    for period in sorted_periods:
        if runs and period == runs[-1][0] + runs[-1][1]:
            runs[-1] = (runs[-1][0], runs[-1][1] + 1)
        else:
            runs.append((period, 1))
    return runs


# C.HEAVY_CONSEC -- mirrors constraints.py:_add_subject_constraints rule 6 (sliding window)
def detect_heavy_consecutive(view: ScheduleView, params: EffectiveParams) -> list:
    heavy_periods = defaultdict(set)
    for slot, subject_id, _teacher in view.placed():
        if subject_id in view.roles.heavy_ids:
            heavy_periods[slot.class_id, slot.ts.weekday, slot.ts.session].add(slot.ts.period)
    violations = []
    for (cid, wd, sess), periods in heavy_periods.items():
        cap = params.max_heavy_consecutive[cid, sess].declared
        violations += [
            Violation("C.HEAVY_CONSEC", class_id=cid, weekday=wd, session=sess, period=start, count=length,
                      detail=f"{view.class_name(cid)}: {length} tiết môn Nặng liên tiếp {_day(wd)} {_session(sess)} "
                             f"từ tiết {start} (trần cấu hình {cap})")
            for start, length in _runs(sorted(periods)) if length > cap
        ]
    return violations


# C.HEAVY_P3 (Tiêu chí II.15) -- mirrors constraints.py:_add_subject_constraints rule 7
def detect_heavy_afternoon_period3(view: ScheduleView, params: EffectiveParams) -> list:
    return [
        Violation("C.HEAVY_P3", class_id=slot.class_id, subject_id=subject_id, weekday=slot.ts.weekday,
                  session="C", period=slot.ts.period,
                  detail=f"{view.class_name(slot.class_id)}: môn {view.subject_name(subject_id)} xếp tiết 3 chiều "
                         f"{_day(slot.ts.weekday)} — học sinh dễ mệt cuối ngày")
        for slot, subject_id, _teacher in view.placed()
        if subject_id in view.roles.heavy_ids and slot.ts.session == "C"
        and slot.ts.period == AFTERNOON_HEAVY_FORBIDDEN_PERIOD
    ]


# C.SUBJECT_CELLS -- mirrors constraints.py:_add_subject_constraints rule 8. Reads the same
# inp.subject_class_allowed_cells the solver used, not a second DB query (spec V7).
def detect_subject_cells(view: ScheduleView, params: EffectiveParams) -> list:
    violations = []
    for slot, subject_id, _teacher in view.placed():
        allowed = view.allowed_cells.get((subject_id, slot.class_id))
        if allowed is not None and (slot.ts.weekday, slot.ts.session) not in allowed:
            violations.append(Violation(
                "C.SUBJECT_CELLS", class_id=slot.class_id, subject_id=subject_id, weekday=slot.ts.weekday,
                session=slot.ts.session, period=slot.ts.period,
                detail=f"{view.class_name(slot.class_id)}: môn {view.subject_name(subject_id)} xếp "
                       f"{_day(slot.ts.weekday)} {_session(slot.ts.session)} ngoài các buổi được phép",
            ))
    return violations


# C.SINGLE_PAIR -- mirrors constraints.py:_add_block_constraints (single-pair branch).
# Adjacency and the zero-pair case are NOT checked yet -- that is spec V2, Plan 3.
def detect_single_pair(view: ScheduleView, params: EffectiveParams) -> list:
    per_day = defaultdict(Counter)
    for slot, subject_id, _teacher in view.placed():
        if subject_id in view.roles.single_pair_ids:
            per_day[slot.class_id, subject_id][slot.ts.weekday] += 1
    violations = []
    for (cid, sid), counts in per_day.items():
        pair_days = sorted(wd for wd, n in counts.items() if n >= PAIR_SIZE)
        excess_days = sorted(wd for wd, n in counts.items() if n > PAIR_SIZE)
        if len(pair_days) > 1 or excess_days:
            violations.append(Violation(
                "C.SINGLE_PAIR", class_id=cid, subject_id=sid, count=len(pair_days),
                detail=f"{view.class_name(cid)}: môn {view.subject_name(sid)} có {len(pair_days)} ngày xếp cặp "
                       f"({', '.join(_day(wd) for wd in pair_days)})"
                       + (f", quá 2 tiết vào {', '.join(_day(wd) for wd in excess_days)}" if excess_days else ""),
            ))
    return violations


def _morning_academic_counts(view: ScheduleView) -> Counter:
    return Counter((slot.class_id, slot.ts.weekday) for slot, subject_id, _teacher in view.placed()
                   if slot.ts.session == "S" and subject_id in view.academic_ids)


# ACAD.MAX -- mirrors constraints.py:_add_class_constraints rule 8 (upper bound)
def detect_academic_overload(view: ScheduleView, params: EffectiveParams) -> list:
    violations = []
    for (cid, wd), n in sorted(_morning_academic_counts(view).items()):
        cap = params.max_academic_per_morning[cid].declared
        if n > cap:
            violations.append(Violation(
                "ACAD.MAX", class_id=cid, weekday=wd, session="S", count=n,
                detail=f"{view.class_name(cid)}: sáng {_day(wd)} có {n} tiết học thuật (trần {cap}) — học sinh bị quá tải",
            ))
    return violations


# ACAD.MIN -- mirrors objectives.py section 6d (soft floor)
def detect_academic_underload(view: ScheduleView, params: EffectiveParams) -> list:
    counts = _morning_academic_counts(view)
    morning_sizes = Counter((s.class_id, s.ts.weekday) for s in view.slots if s.ts.session == "S")
    minimum = params.min_academic_per_morning
    return [
        Violation("ACAD.MIN", class_id=cid, weekday=wd, session="S", count=counts[cid, wd],
                  detail=f"{view.class_name(cid)}: sáng {_day(wd)} chỉ có {counts[cid, wd]} tiết học thuật "
                         f"(khuyến nghị ≥ {minimum}) — phân bố tải chưa đều")
        for (cid, wd), size in sorted(morning_sizes.items())
        if size >= MIN_MORNING_PERIODS_FOR_ACADEMIC_FLOOR and counts[cid, wd] < minimum
    ]


DETECTORS: dict = {
    "II.3": (detect_teacher_missing_mandatory_mornings,),
    "II.4": (detect_teacher_lone_sessions, detect_teacher_lone_days),
    "II.7": (detect_teacher_gaps,),
    "II.8": (detect_teacher_split_days,),
    "II.14": (detect_teacher_4_consecutive_mornings,),
    "T.CONFLICT": (detect_teacher_conflicts,),
    "T.BUSY": (detect_teacher_busy,),
    "T.DAY_CAP": (detect_teacher_day_cap,),
    "C.GDTC_PERIOD": (detect_gdtc_periods,),
    "C.NON_CONSEC_DAYS": (detect_non_consecutive_days,),
    "C.MORNING_ONLY": (detect_morning_only,),
    "C.HEAVY_CONSEC": (detect_heavy_consecutive,),
    "C.HEAVY_P3": (detect_heavy_afternoon_period3,),
    "C.SUBJECT_CELLS": (detect_subject_cells,),
    "C.SINGLE_PAIR": (detect_single_pair,),
    "ACAD.MAX": (detect_academic_overload,),
    "ACAD.MIN": (detect_academic_underload,),
}


def detect_rule(rule_id: str, view: ScheduleView, params: EffectiveParams) -> list:
    """Violations of one rule, or none when the school turned the rule off."""
    flag = RULES[rule_id].config_flag
    if flag is not None and not params.flags[flag]:
        return []
    return [violation for detector in DETECTORS[rule_id] for violation in detector(view, params)]


def run_detectors(view: ScheduleView, params: EffectiveParams) -> list:
    return [violation for rule_id in DETECTORS for violation in detect_rule(rule_id, view, params)]
