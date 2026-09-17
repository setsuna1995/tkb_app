from dataclasses import replace

from core.models import Slot, TimeSlot
from core.rules import HARD_POST_GENERATION_IDS, RULES
from core.rules.params import Threshold, resolve_effective_params
from core.rules.violations import BREACH, FORCED, SHORTFALL, Violation, classify
from tests.rule_helpers import make_input

WIDEN_REASON = "lớp 101 cần 14 tiết nặng trên 4 buổi sáng, tối thiểu 4 tiết/buổi"


def _params_with_heavy_cap(effective: int):
    slots = [Slot(1, 101, TimeSlot(1, 2, "S", 1)), Slot(2, 101, TimeSlot(2, 2, "C", 1))]
    params = resolve_effective_params(make_input(slots))
    widened = {
        (101, "S"): Threshold(declared=3, effective=effective, reason=WIDEN_REASON if effective != 3 else ""),
        (101, "C"): Threshold.unrelaxed(3),
    }
    return replace(params, max_heavy_consecutive=widened)


def _heavy_run(session="S", length=4):
    return Violation("C.HEAVY_CONSEC", class_id=101, weekday=3, session=session, period=1, count=length)


def test_soft_rule_is_a_shortfall_never_a_breach():
    [classified] = classify([Violation("II.7", teacher_id=1)], _params_with_heavy_cap(3))
    assert classified.level == SHORTFALL


def test_hard_violation_without_widened_threshold_stays_breach():
    [classified] = classify([_heavy_run()], _params_with_heavy_cap(3))
    assert classified.level == BREACH and classified.evidence == ""


def test_widened_threshold_at_the_same_scope_makes_it_forced_with_evidence():
    [classified] = classify([_heavy_run()], _params_with_heavy_cap(4))
    assert classified.level == FORCED
    assert classified.evidence == WIDEN_REASON


def test_widening_elsewhere_does_not_excuse_this_scope():
    [classified] = classify([_heavy_run(session="C")], _params_with_heavy_cap(4))
    assert classified.level == BREACH


def test_violation_beyond_the_widened_threshold_stays_breach():
    [classified] = classify([_heavy_run(length=5)], _params_with_heavy_cap(4))
    assert classified.level == BREACH


def test_classify_never_drops_a_violation():
    violations = [_heavy_run(), _heavy_run(session="C"), Violation("II.7", teacher_id=1)]
    assert len(classify(violations, _params_with_heavy_cap(4))) == len(violations)


def test_only_hdsp_hard_gate_rules_block_save_for_now():
    assert {rule_id for rule_id, rule in RULES.items() if rule.blocks_save} == set(HARD_POST_GENERATION_IDS)
