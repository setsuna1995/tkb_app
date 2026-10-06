from core.models import ScheduleResult, SchedulingConfig


def test_min_weekly_periods_for_lone_penalty_defaults_to_8():
    """II.4's low-load exemption must be ON by default, but narrow: lowered from
    15 to 8 (user decision 2026-09-04) after a real exported timetable showed 26
    lone sessions of which only 3 were counted as violations -- 11 of the
    school's 17 teachers carry 10-14 periods/week, so a threshold of 15 exempted
    two thirds of the staff and let II.4 pass on schedules the school considers
    unacceptable. 8 still exempts genuinely unavoidable cases (a specialist
    teaching 4 periods/week cannot avoid a lone session)."""
    config = SchedulingConfig()
    assert config.min_weekly_periods_for_lone_penalty == 8


def test_heavy_subject_priority_periods_defaults_to_4():
    """II.5 (GDTC+Toán+Văn ưu tiên sáng) must have the morning-priority
    bonus enabled by default, covering the whole typical morning session."""
    config = SchedulingConfig()
    assert config.heavy_subject_priority_periods == 4


def test_schedule_result_has_relaxed_rules_field():
    result = ScheduleResult(success=True)
    assert result.relaxed_rules == []

    result_with_relaxation = ScheduleResult(success=True, relaxed_rules=[{"rule_id": "II.3"}])
    assert result_with_relaxation.relaxed_rules == [{"rule_id": "II.3"}]


def test_yellow_highlighted_defaults_match_user_request():
    """Kiểm tra 3 mục khoanh vàng theo yêu cầu người dùng:
    1. Bỏ ưu tiên GVCN dạy tiết 2 Thứ 2 làm mặc định (False).
    2. Sáng MỌI GV bắt buộc chỉ còn Thứ 2 (2,); Mức áp dụng buổi nghỉ tắt (none / 0).
    3. Môn bắt buộc xếp sáng (cấm chiều) để trống mặc định (không tự ép Toán, Văn).
    """
    config = SchedulingConfig()
    assert config.gvcn_monday_period2_enabled is False
    assert config.strict_morning_weekdays == (2,)
    assert config.teacher_off_sessions_per_week == 0
    assert config.teacher_off_sessions_mode == "none"
    assert config.morning_only_subject_ids == frozenset()


def test_config_export_and_import_roundtrip():
    """Kiểm tra xuất và nạp cấu hình độc lập qua Excel bảo toàn 100% dữ liệu."""
    import sqlite3
    from data import db
    from data import repository as repo
    from io_excel.exporter import export_config_xlsx
    from io_excel.importer import import_scheduling_config_from_excel

    conn = db.get_connection(":memory:")
    db.init_db(conn)

    # Thêm dữ liệu mẫu lớp, môn để tạo luật riêng môn/lớp
    repo.upsert_class(conn, "6A1")
    repo.upsert_class(conn, "6A2")
    s_tin = repo.upsert_subject(conn, "Tin học", 2)
    classes = repo.list_classes(conn)
    c_ids = [c.class_id for c in classes]

    repo.upsert_subject_class_rule(conn, s_tin, c_ids, [(2, "C"), (3, "C")])

    # Thiết lập một config tùy chỉnh
    custom_cfg = SchedulingConfig(
        gvcn_monday_period2_enabled=True,
        strict_morning_weekdays=(2, 5),
        teacher_off_sessions_per_week=2,
        teacher_off_sessions_mode="hard",
        morning_only_subject_ids=frozenset({s_tin}),
        cpsat_time_limit_seconds=60,
    )
    repo.set_scheduling_config(conn, custom_cfg)

    # Xuất ra file Excel bytes
    xlsx_bytes = export_config_xlsx(conn)
    assert len(xlsx_bytes) > 0

    # Khởi tạo một DB sạch khác
    conn2 = db.get_connection(":memory:")
    db.init_db(conn2)
    for c in classes:
        repo.upsert_class(conn2, c.name)
    repo.upsert_subject(conn2, "Tin học", 2)

    # Nạp lại từ file Excel bytes
    res = import_scheduling_config_from_excel(conn2, xlsx_bytes)
    assert res["imported"] is True
    assert res["rules_count"] == 1

    loaded_cfg = repo.get_scheduling_config(conn2)
    assert loaded_cfg.gvcn_monday_period2_enabled is True
    assert loaded_cfg.strict_morning_weekdays == (2, 5)
    assert loaded_cfg.teacher_off_sessions_per_week == 2
    assert loaded_cfg.teacher_off_sessions_mode == "hard"
    assert loaded_cfg.cpsat_time_limit_seconds == 60

    loaded_rules = repo.list_subject_class_rules(conn2)
    assert len(loaded_rules) == 1
    assert set(loaded_rules[0]["cells"]) == {(2, "C"), (3, "C")}

