"""Registry of every HĐSP rule a detector checks (core/rules/detectors.py) and
how a violation of it is treated.

RuleTier says who enforces the rule; RuleSpec.config_flag names the
SchedulingConfig switch that turns it off. Detectors, the solver's hard gate
and the UI all read this one table.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class RuleTier(Enum):
    HARD_POST_GENERATION = "hard_post_generation"  # HĐSP hard gate: forced to zero, relaxed only by diagnosis
    HARD_MODEL = "hard_model"  # CP-SAT always enforces it; a violation found afterwards means the model and the check disagree
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
    "T.CONFLICT": RuleSpec(
        id="T.CONFLICT",
        title_vi="GV không dạy 2 lớp trong cùng một tiết",
        tier=RuleTier.HARD_MODEL,
    ),
    "T.BUSY": RuleSpec(
        id="T.BUSY",
        title_vi="Không xếp GV vào giờ đã báo bận",
        tier=RuleTier.HARD_MODEL,
    ),
    "T.DAY_CAP": RuleSpec(
        id="T.DAY_CAP",
        title_vi="GV không dạy quá số tiết/ngày theo cấu hình (Tiêu chí II.2)",
        tier=RuleTier.HARD_MODEL,
    ),
    "C.GDTC_PERIOD": RuleSpec(
        id="C.GDTC_PERIOD",
        title_vi="GDTC chỉ xếp trong khung tiết cho phép",
        tier=RuleTier.HARD_MODEL,
    ),
    "C.NON_CONSEC_DAYS": RuleSpec(
        id="C.NON_CONSEC_DAYS",
        title_vi="Môn cấm học liền ngày (gồm GDTC) không xếp 2 ngày liên tiếp",
        tier=RuleTier.HARD_MODEL,
    ),
    "C.MORNING_ONLY": RuleSpec(
        id="C.MORNING_ONLY",
        title_vi="Môn chỉ học buổi sáng không xếp vào buổi chiều",
        tier=RuleTier.HARD_MODEL,
    ),
    "C.HEAVY_CONSEC": RuleSpec(
        id="C.HEAVY_CONSEC",
        title_vi="Môn Nặng không quá số tiết liên tiếp theo cấu hình",
        tier=RuleTier.HARD_MODEL,
    ),
    "C.HEAVY_P3": RuleSpec(
        id="C.HEAVY_P3",
        title_vi="Môn Nặng không xếp tiết 3 buổi chiều (Tiêu chí II.15)",
        tier=RuleTier.HARD_MODEL,
        config_flag="avoid_heavy_afternoon_period3",
    ),
    "C.SUBJECT_CELLS": RuleSpec(
        id="C.SUBJECT_CELLS",
        title_vi="Môn chỉ xếp vào các buổi được phép theo luật môn/lớp",
        tier=RuleTier.HARD_MODEL,
    ),
    "C.SINGLE_PAIR": RuleSpec(
        id="C.SINGLE_PAIR",
        title_vi="Môn 1 cặp có đúng một cặp 2 tiết, không quá 2 tiết/ngày",
        tier=RuleTier.HARD_MODEL,
    ),
    "ACAD.MAX": RuleSpec(
        id="ACAD.MAX",
        title_vi="Buổi sáng không quá số tiết học thuật theo cấu hình",
        tier=RuleTier.HARD_MODEL,
        config_flag="balance_morning_academic_load",
    ),
    "ACAD.MIN": RuleSpec(
        id="ACAD.MIN",
        title_vi="Buổi sáng nên có tối thiểu số tiết học thuật theo cấu hình",
        tier=RuleTier.SOFT,
        config_flag="balance_morning_academic_load",
    ),
}

HARD_POST_GENERATION_IDS: tuple = tuple(
    rule.id for rule in RULES.values() if rule.tier is RuleTier.HARD_POST_GENERATION
)
