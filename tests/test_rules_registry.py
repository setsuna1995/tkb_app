from core.rules_registry import RULES, HARD_POST_GENERATION_IDS, RuleTier


def test_registry_contains_all_six_rules():
    assert set(RULES.keys()) == {"II.3", "II.4", "II.7", "II.8", "II.9", "II.14"}


def test_hard_post_generation_ids_matches_user_confirmed_classification():
    """User confirmed 2026-09-03 (second revision, same day): II.4 and II.8
    are hard-gated (block save); II.3/II.7/II.9/II.14 are soft -- still scored
    and minimized by the engine, but never reject an attempt or block save.
    II.8 was briefly demoted to soft earlier the same day (final whole-branch
    review found it mathematically subsumed by II.4) but the user asked for
    it back as mandatory (\"là bắt buộc\")."""
    assert set(HARD_POST_GENERATION_IDS) == {"II.4", "II.8"}
    for rule_id in ("II.3", "II.7", "II.9", "II.14"):
        assert RULES[rule_id].tier is RuleTier.SOFT


def test_every_rule_has_a_vietnamese_title():
    for rule in RULES.values():
        assert rule.title_vi
        assert isinstance(rule.title_vi, str)
