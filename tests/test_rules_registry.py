from core.rules_registry import RULES, HARD_POST_GENERATION_IDS, RuleTier


def test_registry_contains_all_six_rules():
    assert set(RULES.keys()) == {"II.3", "II.4", "II.7", "II.8", "II.9", "II.14"}


def test_hard_post_generation_ids_matches_user_confirmed_classification():
    """User confirmed 2026-09-03 (third revision, same day): II.3, II.4, and
    II.8 are hard-gated (block save); II.7/II.9/II.14 are soft -- still scored
    and minimized by the engine, but never reject an attempt or block save.
    II.3 (mandatory-morning-teaching-presence, after its title_vi mislabeling
    was corrected) was briefly soft earlier the same day but the user
    confirmed it must also be mandatory ("bắt buộc phải có mặt sáng T2 T5
    T6")."""
    assert set(HARD_POST_GENERATION_IDS) == {"II.3", "II.4", "II.8"}
    for rule_id in ("II.7", "II.9", "II.14"):
        assert RULES[rule_id].tier is RuleTier.SOFT


def test_every_rule_has_a_vietnamese_title():
    for rule in RULES.values():
        assert rule.title_vi
        assert isinstance(rule.title_vi, str)
