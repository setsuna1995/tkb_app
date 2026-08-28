from core import setup_status


# ---------------------------------------------------------------------------
# check_khai_bao
# ---------------------------------------------------------------------------

def test_check_khai_bao_reports_missing_pieces():
    result = setup_status.check_khai_bao(num_classes=0, num_subjects=2, num_teachers=0)
    assert result.ok is False
    assert "lớp" in result.detail
    assert "giáo viên" in result.detail
    assert "môn" not in result.detail


def test_check_khai_bao_ok_when_all_present():
    result = setup_status.check_khai_bao(num_classes=5, num_subjects=8, num_teachers=12)
    assert result.ok is True


# ---------------------------------------------------------------------------
# check_phan_cong
# ---------------------------------------------------------------------------

def test_check_phan_cong_flags_pairs_with_periods_but_no_teacher():
    periods_per_week = {(1, 10, "C"): 3, (1, 10, "L"): 3}
    assignments = {}  # (subject_id, class_id) -> teacher_id -- chưa phân công gì
    result = setup_status.check_phan_cong(periods_per_week, assignments)
    assert result.ok is False
    assert "1" in result.detail


def test_check_phan_cong_ok_when_all_nonzero_pairs_assigned():
    periods_per_week = {(1, 10, "C"): 3, (1, 10, "L"): 3, (2, 10, "C"): 0}
    assignments = {(1, 10): 99}  # (2, 10) có 0 tiết cả 2 tuần nên không cần GV
    result = setup_status.check_phan_cong(periods_per_week, assignments)
    assert result.ok is True


def test_check_phan_cong_treats_none_teacher_as_unassigned():
    periods_per_week = {(1, 10, "C"): 2}
    assignments = {(1, 10): None}
    result = setup_status.check_phan_cong(periods_per_week, assignments)
    assert result.ok is False


# ---------------------------------------------------------------------------
# check_dinh_muc
# ---------------------------------------------------------------------------

def test_check_dinh_muc_flags_teacher_over_cap():
    quota_view = [{"name": "Cô A", "cap": 19, "over": 3, "under": 0}]
    result = setup_status.check_dinh_muc(quota_view)
    assert result.ok is False
    assert "vượt trần" in result.detail


def test_check_dinh_muc_flags_teacher_under_floor():
    quota_view = [{"name": "Cô A", "cap": 19, "over": -5, "under": 2}]
    result = setup_status.check_dinh_muc(quota_view)
    assert result.ok is False
    assert "dưới sàn" in result.detail


def test_check_dinh_muc_ok_when_within_bounds():
    quota_view = [{"name": "Cô A", "cap": 19, "over": -2, "under": 0}]
    result = setup_status.check_dinh_muc(quota_view)
    assert result.ok is True


# ---------------------------------------------------------------------------
# check_khung_tiet
# ---------------------------------------------------------------------------

def test_check_khung_tiet_flags_class_short_on_heavier_parity():
    class_totals = {10: 30}  # khung 30 ô/tuần
    # Lớp 10: tuần Chẵn 28 tiết (vừa), tuần Lẻ 32 tiết (KHÔNG vừa) -- tuần Lẻ là tuần nặng hơn
    class_quota_by_parity = {10: {"C": 28, "L": 32}}
    result = setup_status.check_khung_tiet(class_totals, class_quota_by_parity)
    assert result.ok is False


def test_check_khung_tiet_ok_when_heavier_parity_fits():
    class_totals = {10: 30}
    class_quota_by_parity = {10: {"C": 28, "L": 30}}
    result = setup_status.check_khung_tiet(class_totals, class_quota_by_parity)
    assert result.ok is True


# ---------------------------------------------------------------------------
# check_gv_ban -- không chặn, chỉ mang tính tham khảo (0 tiết bận vẫn hợp lệ)
# ---------------------------------------------------------------------------

def test_check_gv_ban_always_ok_but_reports_counts():
    result = setup_status.check_gv_ban(num_teachers=12, num_teachers_with_busy=5)
    assert result.ok is True
    assert "5" in result.detail
    assert "12" in result.detail


def test_check_gv_ban_ok_even_when_nobody_declared_busy():
    result = setup_status.check_gv_ban(num_teachers=12, num_teachers_with_busy=0)
    assert result.ok is True
