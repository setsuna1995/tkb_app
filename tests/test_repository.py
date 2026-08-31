import pytest

from core.models import ROLE_HDTN, ROLE_THUONG, SchedulingConfig
from data import db, repository as repo


@pytest.fixture()
def conn(tmp_path):
    connection = db.get_connection(str(tmp_path / "test.db"))
    db.init_db(connection)
    yield connection
    connection.close()


def test_get_scheduling_config_returns_defaults_when_never_saved(conn):
    assert repo.get_scheduling_config(conn) == SchedulingConfig()


def test_set_then_get_scheduling_config_round_trips(conn):
    custom = SchedulingConfig(
        gdtc_avoid_period=3,
        chao_co_weekday=3,
        chao_co_period=2,
        max_heavy_consecutive=2,
        max_periods_per_session=5,
        teacher_off_sessions_per_week=2,
        forbidden_off_cells=frozenset({(2, "S"), (4, "C")}),
        reserved_off_weekdays_chieu=(4, 5),
    )
    repo.set_scheduling_config(conn, custom)
    assert repo.get_scheduling_config(conn) == custom


def test_set_then_get_scheduling_config_round_trips_soft_bias_fields(conn):
    custom = SchedulingConfig(
        heavy_subject_priority_periods=2,
        afternoon_preferred_subject_ids=frozenset({3, 7}),
    )
    repo.set_scheduling_config(conn, custom)
    assert repo.get_scheduling_config(conn) == custom


def test_set_then_get_scheduling_config_round_trips_heavy_subjects_morning_only(conn):
    custom = SchedulingConfig(heavy_subjects_morning_only=True)
    repo.set_scheduling_config(conn, custom)
    assert repo.get_scheduling_config(conn) == custom
    assert repo.get_scheduling_config(conn).heavy_subjects_morning_only is True


def test_set_then_get_scheduling_config_round_trips_morning_only_subject_ids(conn):
    custom = SchedulingConfig(morning_only_subject_ids=frozenset({1, 2, 4, 7}))
    repo.set_scheduling_config(conn, custom)
    loaded = repo.get_scheduling_config(conn)
    assert loaded == custom
    assert loaded.morning_only_subject_ids == frozenset({1, 2, 4, 7})


def test_set_then_get_scheduling_config_round_trips_teacher_quality_fields(conn):
    custom = SchedulingConfig(
        avoid_teacher_gaps=False,
        avoid_teacher_lone_periods=False,
        balance_afternoon_teachers=False,
        mandatory_morning_weekdays=(2, 3, 5, 6),
    )
    repo.set_scheduling_config(conn, custom)
    loaded = repo.get_scheduling_config(conn)
    assert loaded.avoid_teacher_gaps is False
    assert loaded.avoid_teacher_lone_periods is False
    assert loaded.balance_afternoon_teachers is False
    assert loaded.mandatory_morning_weekdays == (2, 3, 5, 6)



def test_upsert_and_list_teacher_round_trips_off_override_and_pins(conn):
    tid = repo.upsert_teacher(
        conn, "GV The duc", role="", must_monday=False, is_gvcn=False,
        off_sessions_override=3, pinned_full_day_off=5, pinned_afternoon_off=3,
    )
    teachers = {t.teacher_id: t for t in repo.list_teachers(conn)}
    t = teachers[tid]
    assert t.off_sessions_override == 3
    assert t.pinned_full_day_off == 5
    assert t.pinned_afternoon_off == 3


def test_teacher_off_override_and_pins_default_to_none(conn):
    tid = repo.upsert_teacher(conn, "GV Thuong")
    teachers = {t.teacher_id: t for t in repo.list_teachers(conn)}
    t = teachers[tid]
    assert t.off_sessions_override is None
    assert t.pinned_full_day_off is None
    assert t.pinned_afternoon_off is None


def test_upsert_teacher_without_new_kwargs_preserves_existing_pins_and_override(conn):
    # Regression for the Excel re-import bug: io_excel/importer.py's DinhMuc_GV
    # loop calls upsert_teacher(conn, name, role=..., must_monday=..., is_gvcn=...,
    # teacher_id=tid) on an UPDATE, never mentioning the 3 new columns -- that must
    # NOT wipe a previously-saved off_sessions_override/pinned_full_day_off/
    # pinned_afternoon_off back to NULL.
    tid = repo.upsert_teacher(conn, "GV The duc", role="", must_monday=False, is_gvcn=False,
                               off_sessions_override=3, pinned_full_day_off=4, pinned_afternoon_off=3)
    # Simulate an Excel re-import call: same shape as io_excel/importer.py's call, no new kwargs at all.
    repo.upsert_teacher(conn, "GV The duc", role="", must_monday=False, is_gvcn=False, teacher_id=tid)
    teachers = {t.teacher_id: t for t in repo.list_teachers(conn)}
    t = teachers[tid]
    assert t.off_sessions_override == 3
    assert t.pinned_full_day_off == 4
    assert t.pinned_afternoon_off == 3


def test_upsert_teacher_can_still_explicitly_clear_pins_and_override(conn):
    tid = repo.upsert_teacher(conn, "GV The duc", off_sessions_override=3, pinned_full_day_off=4,
                               pinned_afternoon_off=3)
    repo.upsert_teacher(conn, "GV The duc", teacher_id=tid,
                        off_sessions_override=None, pinned_full_day_off=None, pinned_afternoon_off=None)
    teachers = {t.teacher_id: t for t in repo.list_teachers(conn)}
    t = teachers[tid]
    assert t.off_sessions_override is None
    assert t.pinned_full_day_off is None
    assert t.pinned_afternoon_off is None


def test_subject_class_rule_crud_round_trips(conn):
    subject_id = repo.upsert_subject(conn, "Nhac", ROLE_THUONG)
    rule_id = repo.upsert_subject_class_rule(conn, subject_id=subject_id, class_ids=[3, 7, 9],
                                              cells={(3, "C"), (6, "C")})
    rules = repo.list_subject_class_rules(conn)
    assert len(rules) == 1
    assert rules[0]["rule_id"] == rule_id
    assert rules[0]["subject_id"] == subject_id
    assert rules[0]["class_ids"] == [3, 7, 9]
    assert rules[0]["cells"] == frozenset({(3, "C"), (6, "C")})


def test_subject_class_rule_update_by_rule_id(conn):
    subject_id = repo.upsert_subject(conn, "Nhac", ROLE_THUONG)
    rule_id = repo.upsert_subject_class_rule(conn, subject_id, [3], {(3, "C")})
    repo.upsert_subject_class_rule(conn, subject_id, [3, 7], {(3, "C"), (4, "C")}, rule_id=rule_id)
    rules = repo.list_subject_class_rules(conn)
    assert len(rules) == 1
    assert rules[0]["class_ids"] == [3, 7]
    assert rules[0]["cells"] == frozenset({(3, "C"), (4, "C")})


def test_subject_class_rule_delete(conn):
    subject_id = repo.upsert_subject(conn, "Nhac", ROLE_THUONG)
    rule_id = repo.upsert_subject_class_rule(conn, subject_id, [3], {(3, "C")})
    repo.delete_subject_class_rule(conn, rule_id)
    assert repo.list_subject_class_rules(conn) == []


def test_get_subject_class_allowed_cells_expands_per_class_and_merges_rules(conn):
    subject_id = repo.upsert_subject(conn, "Nhac", ROLE_THUONG)
    repo.upsert_subject_class_rule(conn, subject_id=subject_id, class_ids=[3, 7], cells={(3, "C")})
    repo.upsert_subject_class_rule(conn, subject_id=subject_id, class_ids=[3], cells={(6, "C")})  # cùng (môn, lớp 3) -> hợp nhất
    allowed = repo.get_subject_class_allowed_cells(conn)
    assert allowed[(subject_id, 3)] == frozenset({(3, "C"), (6, "C")})
    assert allowed[(subject_id, 7)] == frozenset({(3, "C")})
    assert (subject_id, 9) not in allowed


def test_get_subject_class_allowed_cells_empty_when_no_rules(conn):
    assert repo.get_subject_class_allowed_cells(conn) == {}


def test_build_scheduling_input_attaches_subject_class_allowed_cells(conn):
    class_id = repo.upsert_class(conn, "6A")
    subject_id = repo.upsert_subject(conn, "Nhac", ROLE_THUONG)
    repo.upsert_subject_class_rule(conn, subject_id, [class_id], {(3, "C")})

    inp = repo.build_scheduling_input(conn, parity="C")
    assert inp.subject_class_allowed_cells == {(subject_id, class_id): frozenset({(3, "C")})}


def test_upsert_subject_class_rule_rejects_empty_cells(conn):
    subject_id = repo.upsert_subject(conn, "Nhac", ROLE_THUONG)
    with pytest.raises(ValueError):
        repo.upsert_subject_class_rule(conn, subject_id, [1], frozenset())


def test_upsert_subject_class_rule_rejects_empty_class_ids(conn):
    subject_id = repo.upsert_subject(conn, "Nhac", ROLE_THUONG)
    with pytest.raises(ValueError):
        repo.upsert_subject_class_rule(conn, subject_id, [], {(3, "C")})


def test_upsert_subject_class_rule_rejects_hdtn_subject(conn):
    hdtn_id = repo.upsert_subject(conn, "HDTN", ROLE_HDTN)
    with pytest.raises(ValueError):
        repo.upsert_subject_class_rule(conn, hdtn_id, [1], {(3, "C")})
