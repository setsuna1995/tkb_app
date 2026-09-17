"""Single source of truth for which HĐSP rules are hard-gated (reject and
retry the scheduling attempt, or explicitly report as relaxed when retrying
structurally cannot help) versus soft (scored only, never blocks).

Only covers the rules touched by the 2026-09-02 hard-gate feature (see
.superpowers/sdd/2026-09-02-hard-gate-hdsp-rules/progress.md) -- the full
32-rule catalogue lives in
.superpowers/sdd/2026-09-01-rules-audit-v2/task-1-report.md and does not need
a code registry today.

This module is metadata only: it does not implement or replace any
constraint-checking logic in feasibility.py/heuristics.py/quality.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class RuleTier(Enum):
    HARD_POST_GENERATION = "hard_post_generation"  # whole-schedule check; reject attempt + retry, or report as relaxed
    SOFT = "soft"  # scored only; never blocks an attempt or the save button


@dataclass(frozen=True)
class RuleSpec:
    id: str
    title_vi: str
    tier: RuleTier
    config_flag: Optional[str] = None  # SchedulingConfig attribute that enables/disables this rule, if any


RULES: dict[str, RuleSpec] = {
    "II.3": RuleSpec(
        id="II.3",
        # Corrected 2026-09-03: the previous title_vi ("Mỗi GV có 1 buổi nghỉ...")
        # described the WEEKLY OFF-SLOT mechanism (core/scheduler/teacher_off.py),
        # not what this rule_id actually checks
        # (core/scheduler/quality.py:_count_teacher_missing_mandatory_mornings) --
        # this mislabeling caused real user confusion. The off-slot mechanism has
        # no rule_id of its own; its shortfall is no longer reported at all (user
        # decision 2026-09-03, second revision -- not a hard requirement).
        title_vi="GV tải >=10 tiết/tuần phải có mặt dạy vào sáng Thứ 2, Thứ 5, Thứ 6",
        tier=RuleTier.HARD_POST_GENERATION,
        config_flag=None,
    ),
    "II.4": RuleSpec(
        id="II.4",
        # 2026-09-05: "<15 tiết/tuần" trong title cũ không khớp ngưỡng thực thi
        # (config.min_weekly_periods_for_lone_penalty, mặc định 8) -- gây hiểu lầm
        # rằng GV 8-14 tiết/tuần được miễn trong khi thực tế vẫn bị chặn.
        title_vi="Hạn chế GV dạy 1 tiết/buổi hoặc 1 tiết/ngày (trừ GV dưới ngưỡng cấu hình, mặc định 8 tiết/tuần)",
        tier=RuleTier.HARD_POST_GENERATION,
        config_flag="avoid_teacher_lone_periods",
    ),
    "II.7": RuleSpec(
        id="II.7",
        title_vi="Hạn chế GV dạy tiết 1, nghỉ tiết 2-3, rồi dạy lại tiết 4",
        tier=RuleTier.SOFT,
        config_flag="avoid_teacher_gaps",
    ),
    "II.8": RuleSpec(
        id="II.8",
        title_vi="Không xếp GV dạy sáng 1 tiết + chiều 1 tiết trong cùng ngày",
        tier=RuleTier.HARD_POST_GENERATION,
        config_flag="avoid_teacher_lone_periods",
    ),
    "II.9": RuleSpec(
        id="II.9",
        title_vi="Không để GV nghỉ trọn toàn bộ các buổi chiều trong tuần",
        tier=RuleTier.SOFT,
        config_flag="balance_afternoon_teachers",
    ),
    "II.14": RuleSpec(
        id="II.14",
        title_vi="Hạn chế GV dạy 4 tiết liên tục buổi sáng (trừ GV >20 tiết/tuần)",
        tier=RuleTier.SOFT,
        config_flag="avoid_teacher_4_consecutive_morning",
    ),
}

HARD_POST_GENERATION_IDS: tuple = tuple(
    rule.id for rule in RULES.values() if rule.tier is RuleTier.HARD_POST_GENERATION
)
