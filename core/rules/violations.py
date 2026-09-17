"""What a rule violation is, independent of how it was found."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Iterable, Literal, Optional

from core.rules import RULES, RuleTier

if TYPE_CHECKING:
    from core.rules.params import EffectiveParams

BREACH = "BREACH"        # hard rule broken with no proof it was unavoidable -- blocks save when the rule says so
FORCED = "FORCED"        # hard rule broken, and the model proved it could not do better -- carries evidence
SHORTFALL = "SHORTFALL"  # soft criterion not met -- never blocks save

Level = Literal["BREACH", "FORCED", "SHORTFALL"]


@dataclass(frozen=True)
class Violation:
    rule_id: str
    level: Level = BREACH
    teacher_id: Optional[int] = None
    class_id: Optional[int] = None
    subject_id: Optional[int] = None
    weekday: Optional[int] = None
    session: Optional[str] = None
    period: Optional[int] = None
    count: Optional[int] = None   # size of the violation when it has one (run length, periods taught...)
    detail: str = ""              # Vietnamese, shown to the user as-is
    evidence: str = ""            # required when level == FORCED: why it could not be fewer


def group_by_rule(violations: Iterable[Violation]) -> dict:
    groups: dict = {}
    for violation in violations:
        groups.setdefault(violation.rule_id, []).append(violation)
    return groups


# Where a violation's own scope has an adaptive threshold. Only these rules can be
# FORCED from a threshold; Plan 2 adds result.relaxations as the second evidence source.
_SCOPED_THRESHOLD = {
    "C.HEAVY_CONSEC": lambda params, v: params.max_heavy_consecutive.get((v.class_id, v.session)),
    "ACAD.MAX": lambda params, v: params.max_academic_per_morning.get(v.class_id),
}


def classify(violations: list, params: "EffectiveParams") -> list:
    """Attach a level to the BREACHes detectors return.

    SOFT rules become SHORTFALL. A hard violation becomes FORCED only when the
    threshold at its OWN scope was widened by the model, with a reason, and the
    violation fits within the widened value. Nothing is ever dropped.
    """
    return [_classify_one(violation, params) for violation in violations]


def _classify_one(violation: Violation, params: "EffectiveParams") -> Violation:
    if RULES[violation.rule_id].tier is RuleTier.SOFT:
        return replace(violation, level=SHORTFALL)
    evidence = _threshold_evidence(violation, params)
    return replace(violation, level=FORCED, evidence=evidence) if evidence else violation


def _threshold_evidence(violation: Violation, params: "EffectiveParams") -> str:
    lookup = _SCOPED_THRESHOLD.get(violation.rule_id)
    threshold = lookup(params, violation) if lookup else None
    if threshold is None or threshold.effective == threshold.declared or violation.count is None:
        return ""
    return threshold.reason if violation.count <= threshold.effective else ""
