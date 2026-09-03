from core.rules_registry import RULES, HARD_POST_GENERATION_IDS, RuleTier


def test_registry_contains_all_six_rules():
    assert set(RULES.keys()) == {"II.3", "II.4", "II.7", "II.8", "II.9", "II.14"}


def test_hard_post_generation_ids_matches_user_confirmed_classification():
    """User confirmed 2026-09-03: only II.4 stays hard-gated (blocks save).
    II.3/II.7/II.8/II.9/II.14 are soft -- still scored and minimized by the
    engine, but never reject an attempt or block save. Demoted from the
    2026-09-02 classification (which hard-gated II.3/II.8/II.14 too) because
    the final whole-branch review found II.8 mathematically subsumed by II.4,
    and the user asked to prioritize II.4 above II.3/II.8/II.14."""
    assert set(HARD_POST_GENERATION_IDS) == {"II.4"}
    for rule_id in ("II.3", "II.7", "II.8", "II.9", "II.14"):
        assert RULES[rule_id].tier is RuleTier.SOFT


def test_every_rule_has_a_vietnamese_title():
    for rule in RULES.values():
        assert rule.title_vi
        assert isinstance(rule.title_vi, str)
