"""Every rule threshold the model enforces and the detectors count against,
resolved once per SchedulingInput.

Before 2026-09-17 each layer read config with scattered getattr calls and its
own defaults (the lone-session threshold defaulted to 15, 0 and 8 in three
places). Counting a violation always uses Threshold.declared -- the value the
school configured. Threshold.effective is what the model actually enforced and
is only used to decide whether a violation was forced (core/rules/violations.py).
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace

from core.models import RoleIndex, SchedulingConfig, SchedulingInput, is_bgh
from core.roles import resolve_roles
from core.scheduler.placement import _build_effective_assigned_teacher

MAX_LOAD_FOR_4CONSEC_PENALTY = 20
# II.14 exempts teachers above 20 periods/week. Hardcoded in objectives.py before 2026-09-17.

RULE_FLAG_NAMES = (
    "avoid_teacher_lone_periods",
    "avoid_teacher_gaps",
    "avoid_teacher_4_consecutive_morning",
    "avoid_heavy_afternoon_period3",
    "avoid_gdtc_consecutive_days",
    "balance_morning_academic_load",
    "balance_afternoon_teachers",
    "heavy_subjects_morning_only",
)


@dataclass(frozen=True)
class Threshold:
    declared: int      # from config -- the standard violations are COUNTED against
    effective: int     # what the model actually enforced -- only used to CLASSIFY
    reason: str = ""   # required whenever effective != declared

    def __post_init__(self):
        if self.effective != self.declared and not self.reason:
            raise ValueError("chênh lệch ngưỡng phải có lý do")

    @classmethod
    def unrelaxed(cls, value: int) -> "Threshold":
        return cls(declared=value, effective=value)


@dataclass(frozen=True)
class EffectiveParams:
    min_weekly_periods_for_lone_penalty: int
    min_weekly_periods_for_mandatory_morning: int
    max_load_for_4consec_penalty: int
    lone_exempt_ids: frozenset
    bgh_ids: frozenset
    pinned_day_offs: dict              # teacher_id -> weekday approved as a full day off
    teacher_load: dict                 # teacher_id -> periods/week, real teachers only
    max_heavy_consecutive: dict        # (class_id, session) -> Threshold
    max_academic_per_morning: dict     # class_id -> Threshold
    max_teacher_periods_per_day: int
    max_periods_per_session: int
    min_academic_per_morning: int
    mandatory_morning_weekdays: tuple
    strict_morning_weekdays: tuple
    gdtc_morning_allowed_periods: tuple
    gdtc_afternoon_allowed_periods: tuple
    morning_only_subject_ids: frozenset     # includes heavy subjects when heavy_subjects_morning_only
    non_consecutive_subject_ids: frozenset  # includes GDTC when avoid_gdtc_consecutive_days
    flags: dict                             # name in RULE_FLAG_NAMES -> bool

    def as_effective(self) -> "EffectiveParams":
        """Copy whose declared thresholds are what the model enforced.
        Test-only: production code always counts against config."""
        return replace(
            self,
            max_heavy_consecutive=_at_effective(self.max_heavy_consecutive),
            max_academic_per_morning=_at_effective(self.max_academic_per_morning),
        )


def _at_effective(thresholds: dict) -> dict:
    return {key: Threshold.unrelaxed(threshold.effective) for key, threshold in thresholds.items()}


def resolve_effective_params(inp: SchedulingInput) -> EffectiveParams:
    config = inp.config
    roles = resolve_roles(inp.subjects, inp.extra_kep_ids, inp.hdtn_thematic_week,
                          config.single_pair_subject_ids)
    flags = {name: bool(getattr(config, name)) for name in RULE_FLAG_NAMES}
    return EffectiveParams(
        min_weekly_periods_for_lone_penalty=config.min_weekly_periods_for_lone_penalty,
        min_weekly_periods_for_mandatory_morning=config.min_weekly_periods_for_mandatory_morning,
        max_load_for_4consec_penalty=MAX_LOAD_FOR_4CONSEC_PENALTY,
        lone_exempt_ids=frozenset(config.lone_session_exempt_teacher_ids or ()),
        bgh_ids=frozenset(t.teacher_id for t in inp.teachers if is_bgh(t)),
        pinned_day_offs={t.teacher_id: t.pinned_full_day_off for t in inp.teachers
                         if t.pinned_full_day_off is not None},
        teacher_load=_teacher_load(inp),
        max_heavy_consecutive={key: Threshold.unrelaxed(config.max_heavy_consecutive)
                               for key in {(s.class_id, s.ts.session) for s in inp.slots}},
        max_academic_per_morning={class_id: Threshold.unrelaxed(config.max_academic_per_morning)
                                  for class_id in {s.class_id for s in inp.slots}},
        max_teacher_periods_per_day=config.max_teacher_periods_per_day,
        max_periods_per_session=config.max_periods_per_session,
        min_academic_per_morning=config.min_academic_per_morning,
        mandatory_morning_weekdays=tuple(config.mandatory_morning_weekdays or ()),
        strict_morning_weekdays=tuple(config.strict_morning_weekdays or ()),
        gdtc_morning_allowed_periods=tuple(config.gdtc_morning_allowed_periods or ()),
        gdtc_afternoon_allowed_periods=tuple(config.gdtc_afternoon_allowed_periods or ()),
        morning_only_subject_ids=_morning_only_ids(config, roles, flags),
        non_consecutive_subject_ids=_non_consecutive_ids(config, roles, flags),
        flags=flags,
    )


def _teacher_load(inp: SchedulingInput) -> dict:
    effective_teacher = _build_effective_assigned_teacher(inp)
    load = defaultdict(int)
    for key, periods in inp.need.items():
        teacher_id = effective_teacher.get(key)
        if periods > 0 and teacher_id is not None and teacher_id > 0:
            load[teacher_id] += periods
    return dict(load)


def _morning_only_ids(config: SchedulingConfig, roles: RoleIndex, flags: dict) -> frozenset:
    ids = set(config.morning_only_subject_ids or ())
    if flags["heavy_subjects_morning_only"]:
        ids |= roles.heavy_ids
    return frozenset(ids)


def _non_consecutive_ids(config: SchedulingConfig, roles: RoleIndex, flags: dict) -> frozenset:
    ids = set(config.non_consecutive_subject_ids or ())
    if flags["avoid_gdtc_consecutive_days"] and roles.gdtc_id is not None:
        ids.add(roles.gdtc_id)
    return frozenset(ids)
