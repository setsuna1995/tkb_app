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
