from core.roles import is_academic_subject


def test_is_academic_subject():
    # Nhóm Toán
    assert is_academic_subject("Toán") is True
    assert is_academic_subject("Toán học") is True
    assert is_academic_subject("Toán 6") is True

    # Nhóm Ngữ văn
    assert is_academic_subject("Ngữ văn") is True
    assert is_academic_subject("Văn") is True
    assert is_academic_subject("Ngữ Văn 7") is True

    # Nhóm Ngoại ngữ / Tiếng Anh
    assert is_academic_subject("Ngoại ngữ") is True
    assert is_academic_subject("Tiếng Anh") is True
    assert is_academic_subject("Tiếng Anh 8 (Global Success)") is True
    assert is_academic_subject("Anh") is True

    # Nhóm Khoa học tự nhiên
    assert is_academic_subject("Khoa học tự nhiên") is True
    assert is_academic_subject("Khoa học tự nhiên (Vật lý)") is True
    assert is_academic_subject("Khoa học tự nhiên (Hóa học)") is True
    assert is_academic_subject("Khoa học tự nhiên (Sinh học)") is True
    assert is_academic_subject("KHTN") is True

    # Nhóm môn không phải học thuật cốt lõi
    assert is_academic_subject("Giáo dục thể chất") is False
    assert is_academic_subject("Tin học") is False
    assert is_academic_subject("Âm nhạc") is False
    assert is_academic_subject("Mỹ thuật") is False
    assert is_academic_subject("Giáo dục công dân") is False
    assert is_academic_subject("Công nghệ") is False
    assert is_academic_subject("Hoạt động trải nghiệm, hướng nghiệp") is False
    assert is_academic_subject("Lịch sử và Địa lý") is False
