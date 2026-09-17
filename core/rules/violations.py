"""What a rule violation is, independent of how it was found."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal, Optional

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
