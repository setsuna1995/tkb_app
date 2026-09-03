# Task 3: `core/rules_registry.py` — Rule Tier Registry

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a single small module that declares, for the rules touched
by this feature, which enforcement tier they belong to (hard-gated-with-retry
vs soft-only-report). This is the "single source of truth" the user asked
for — Task 5's UI will import `HARD_POST_GENERATION_IDS` from here to decide
which validator violations block the save button, instead of that decision
being hardcoded ad-hoc in the UI file. This does **not** replace or rewrite
any existing constraint logic in `feasibility.py`/`heuristics.py`/`quality.py`
— it is metadata only.

**Scope note:** This registry only needs to cover the rules THIS feature
touches (II.3, II.4, II.7, II.8, II.9, II.14) — it is not a rewrite of the
full 32-rule catalogue already documented in
`.superpowers/sdd/2026-09-01-rules-audit-v2/task-1-report.md`. Expanding it
to the full catalogue is explicitly out of scope (YAGNI) unless a future
task needs it.

**Files:**
- Create: `core/rules_registry.py`
- Test: `tests/test_rules_registry.py` (new file)

**Interfaces:**
- Produces: `RuleTier` (Enum: `HARD_POST_GENERATION`, `SOFT`),
  `RuleSpec` (frozen dataclass: `id: str`, `title_vi: str`, `tier: RuleTier`,
  `config_flag: Optional[str]`), `RULES: dict[str, RuleSpec]`,
  `HARD_POST_GENERATION_IDS: tuple[str, ...]` (derived from `RULES`).
  **Task 5 imports `RULES` and `HARD_POST_GENERATION_IDS` from this module
  by these exact names** — do not rename without updating Task 5's brief.

---

- [ ] **Step 1: Write the failing test**

Create `tests/test_rules_registry.py`:

```python
from core.rules_registry import RULES, HARD_POST_GENERATION_IDS, RuleTier


def test_registry_contains_all_six_rules():
    assert set(RULES.keys()) == {"II.3", "II.4", "II.7", "II.8", "II.9", "II.14"}


def test_hard_post_generation_ids_matches_user_confirmed_classification():
    """User confirmed 2026-09-02: II.3/II.4/II.8/II.14 hard-gated;
    II.7/II.9 stay soft (structural conflict with II.4 otherwise)."""
    assert set(HARD_POST_GENERATION_IDS) == {"II.3", "II.4", "II.8", "II.14"}
    for rule_id in ("II.7", "II.9"):
        assert RULES[rule_id].tier is RuleTier.SOFT


def test_every_rule_has_a_vietnamese_title():
    for rule in RULES.values():
        assert rule.title_vi
        assert isinstance(rule.title_vi, str)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_rules_registry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.rules_registry'`

- [ ] **Step 3: Create `core/rules_registry.py`**

```python
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
        title_vi="Mỗi GV có 1 buổi nghỉ chủ nhật xanh (trừ sáng Thứ 2, Thứ 5, Thứ 6)",
        tier=RuleTier.HARD_POST_GENERATION,
        config_flag=None,
    ),
    "II.4": RuleSpec(
        id="II.4",
        title_vi="Hạn chế GV dạy 1 tiết/buổi hoặc 1 tiết/ngày (trừ GV <15 tiết/tuần)",
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
        tier=RuleTier.HARD_POST_GENERATION,
        config_flag="avoid_teacher_4_consecutive_morning",
    ),
}

HARD_POST_GENERATION_IDS: tuple = tuple(
    rule.id for rule in RULES.values() if rule.tier is RuleTier.HARD_POST_GENERATION
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_rules_registry.py -v`
Expected: all 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add core/rules_registry.py tests/test_rules_registry.py
git commit -m "feat: add rules_registry.py as single source of truth for rule tiers"
```

- [ ] **Step 6: Write task-3-report.md**

Brief summary (Vietnamese) confirming the registry is in place and lists the
6 rule IDs and their tiers.
