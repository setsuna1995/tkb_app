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
# is_short_day_config_valid() -- áp lại preset/tùy chỉnh không được vô tình xoá
# mất ngày lệch tiết đã cấu hình trước đó nếu nó vẫn hợp lý với khung mới.
# ---------------------------------------------------------------------------

def test_short_day_config_with_no_override_is_always_valid():
    assert frame.is_short_day_config_valid(5, 0, False, None, None, None) is True


def test_short_day_config_stays_valid_when_reapplying_same_frame():
    # áp lại đúng preset "Sáng 5" cho 1 lớp đã có ngày lệch Thứ 7 chỉ 4 tiết -- vẫn hợp lệ
    assert frame.is_short_day_config_valid(5, 0, False, 7, 4, None) is True


def test_short_day_config_invalid_when_saturday_no_longer_a_school_day():
    # đổi từ 1 buổi (S5) sang 2 buổi (S4_C3) làm Thứ 7 không còn là ngày học -- ngày lệch cũ hỏng
    assert frame.is_short_day_config_valid(4, 3, False, 7, 4, None) is False


def test_short_day_config_invalid_when_short_periods_no_longer_less_than_base():
    # đổi khung sang Sáng 4 -- short_morning_periods=4 cũ không còn nhỏ hơn base nữa
    assert frame.is_short_day_config_valid(4, 0, False, 7, 4, None) is False


def test_short_day_config_invalid_when_chieu_reserved_weekday():
    # short_weekday=6 (Thứ 6) không thể override buổi chiều vì luôn bị khoá
    assert frame.is_short_day_config_valid(4, 3, False, 6, None, 2) is False


# ---------------------------------------------------------------------------
# active_cells() tự bỏ qua ngày lệch không hợp lệ (self-healing) thay vì áp sai
# ---------------------------------------------------------------------------

def test_active_cells_ignores_invalid_short_weekday_instead_of_applying_it():
    # Thứ 7 không active khi 2 buổi/ngày (mặc định nghỉ Thứ 7) -- short_weekday=7 vô nghĩa ở đây,
    # active_cells() phải tự bỏ qua override thay vì cố áp nó (không có gì để "rút bớt" cả).
    cells_with_invalid_override = frame.active_cells(4, 3, short_weekday=7, short_morning_periods=2)
    cells_uniform = frame.active_cells(4, 3)
    assert cells_with_invalid_override == cells_uniform


def test_short_day_survives_switching_through_incompatible_frame_and_back(conn):
    class_id = repo.upsert_class(conn, "6A")

    # (a) Khung "Sáng 5" + ngày lệch Thứ 7 chỉ 4 tiết.
    repo.set_frame_template(conn, class_id, 5, 0, short_weekday=7, short_morning_periods=4)

    # (b) "Chuyển khung" sang Sáng 4 + Chiều 3 -- truyền NGUYÊN VẸN short_weekday cũ (đúng hành vi
    # mới ở pages/05_Khung_tiet.py: không tự xoá khi ghi, chỉ bỏ qua khi dùng).
    m, a, ss, allow_sat, short_wd, short_m, short_a = repo.get_frame_template(conn, class_id)
    repo.set_frame_template(conn, class_id, 4, 3, allow_saturday=bool(allow_sat),
                             short_weekday=short_wd, short_morning_periods=short_m,
                             short_afternoon_periods=short_a)
    m, a, ss, allow_sat, short_wd, short_m, short_a = repo.get_frame_template(conn, class_id)
    assert (short_wd, short_m, short_a) == (7, 4, None)  # vẫn còn lưu trong DB, chưa bị xoá
    cells_incompatible = frame.active_cells(m, a, bool(ss), bool(allow_sat), short_wd, short_m, short_a)
    assert cells_incompatible == frame.active_cells(m, a, bool(ss), bool(allow_sat))  # bị bỏ qua khi dùng

    # (c) "Chuyển lại" khung Sáng 5 -- vẫn truyền nguyên short_weekday cũ.
    repo.set_frame_template(conn, class_id, 5, 0, allow_saturday=bool(allow_sat),
                             short_weekday=short_wd, short_morning_periods=short_m,
                             short_afternoon_periods=short_a)
    m, a, ss, allow_sat, short_wd, short_m, short_a = repo.get_frame_template(conn, class_id)
    assert (short_wd, short_m, short_a) == (7, 4, None)
    cells_restored = frame.active_cells(m, a, bool(ss), bool(allow_sat), short_wd, short_m, short_a)
    periods_on_saturday = sorted(p for wd, session, p in cells_restored if wd == 7 and session == "S")
    assert periods_on_saturday == [1, 2, 3, 4]  # ngày lệch tiết tự động hoạt động lại


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
