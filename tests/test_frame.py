import pytest

from core import frame
from data import db, repository as repo


@pytest.fixture()
def conn(tmp_path):
    connection = db.get_connection(str(tmp_path / "test.db"))
    db.init_db(connection)
    yield connection
    connection.close()


# ---------------------------------------------------------------------------
# active_cells() với short_weekday
# ---------------------------------------------------------------------------

def test_active_cells_short_weekday_reduces_only_that_day():
    cells = frame.active_cells(5, 0, short_weekday=7, short_morning_periods=4)
    periods_on_saturday = sorted(p for wd, session, p in cells if wd == 7 and session == "S")
    assert periods_on_saturday == [1, 2, 3, 4]
    # các ngày khác không đổi, vẫn đủ 5 tiết
    for wd in (2, 3, 4, 5, 6):
        periods = sorted(p for w, session, p in cells if w == wd and session == "S")
        assert periods == [1, 2, 3, 4, 5]


def test_active_cells_without_short_weekday_is_uniform():
    cells_uniform = frame.active_cells(5, 0)
    cells_explicit_none = frame.active_cells(5, 0, short_weekday=None)
    assert cells_uniform == cells_explicit_none


def test_total_cells_per_class_reflects_short_weekday_reduction():
    total_uniform = frame.total_cells_per_class(5, 0)
    total_with_short_day = frame.total_cells_per_class(5, 0, short_weekday=7, short_morning_periods=4)
    assert total_with_short_day == total_uniform - 1


# ---------------------------------------------------------------------------
# suggest_short_day()
# ---------------------------------------------------------------------------

def test_suggest_short_day_returns_none_when_quota_fills_frame_exactly():
    assert frame.suggest_short_day(5, 0, quota_total=30) is None  # 5 tiết x 6 ngày = 30


def test_suggest_short_day_prefers_saturday_for_1_buoi_class():
    result = frame.suggest_short_day(5, 0, quota_total=29)  # thiếu 1 tiết so với 30
    assert result == (7, 4, None)


def test_suggest_short_day_consolidates_whole_deficit_into_one_day():
    # thiếu 2 tiết -- dồn cả 2 vào Thứ 7 (còn 3 tiết) thay vì rải 2 ngày mỗi ngày thiếu 1
    result = frame.suggest_short_day(5, 0, quota_total=28)
    assert result == (7, 3, None)


def test_suggest_short_day_returns_none_when_deficit_would_leave_lone_period():
    # 30 - 4 = 26 -> Thứ 7 sẽ chỉ còn 5-4=1 tiết, vi phạm luật "không lỗ 1 tiết" -- không đề xuất
    assert frame.suggest_short_day(5, 0, quota_total=26) is None


def test_suggest_short_day_returns_none_when_deficit_exceeds_any_day_capacity():
    assert frame.suggest_short_day(5, 0, quota_total=10) is None  # thiếu 20 tiết, vượt quá 1 ngày


def test_suggest_short_day_falls_back_when_saturday_not_a_school_day():
    # lớp 2 buổi (afternoon > 0) mặc định nghỉ Thứ 7 -- fallback sang ngày khác. Thứ 6 là ứng
    # viên đầu tiên nhưng buổi chiều Thứ 6 luôn bị khoá (RESERVED_OFF_WEEKDAYS_CHIEU) nên phần
    # thiếu được trừ vào buổi sáng Thứ 6.
    uniform_total = frame.total_cells_per_class(4, 3)  # = 29 (5 ngày học, Thứ 5/6 chỉ có sáng)
    result = frame.suggest_short_day(4, 3, quota_total=uniform_total - 1)
    assert result == (6, 3, None)


# ---------------------------------------------------------------------------
# validate_periods() với short_*_periods
# ---------------------------------------------------------------------------

def test_validate_periods_rejects_lone_period_on_short_day_fields():
    frame.validate_periods(5, 0, short_morning_periods=4)  # hợp lệ
    with pytest.raises(ValueError):
        frame.validate_periods(5, 0, short_morning_periods=1)


# ---------------------------------------------------------------------------
# Round-trip qua repository (DB)
# ---------------------------------------------------------------------------

def test_frame_template_short_day_round_trips_through_repository(conn):
    class_id = repo.upsert_class(conn, "6A")
    repo.set_frame_template(conn, class_id, 5, 0, short_weekday=7, short_morning_periods=4)

    morning, afternoon, study_sunday, allow_saturday, short_wd, short_m, short_a = \
        repo.get_frame_template(conn, class_id)
    assert (morning, afternoon) == (5, 0)
    assert (short_wd, short_m, short_a) == (7, 4, None)


def test_frame_template_short_day_can_be_cleared(conn):
    class_id = repo.upsert_class(conn, "6A")
    repo.set_frame_template(conn, class_id, 5, 0, short_weekday=7, short_morning_periods=4)
    repo.set_frame_template(conn, class_id, 5, 0)  # áp lại không có short_weekday -> reset

    _, _, _, _, short_wd, short_m, short_a = repo.get_frame_template(conn, class_id)
    assert (short_wd, short_m, short_a) == (None, None, None)
