"""Tests for Excel weekly curriculum importer."""
import os
import sqlite3
import pytest
from data import db
from data import repository as repo

# Standard school fixture setup
@pytest.fixture
def school_conn():
    c = db.get_connection(":memory:")
    db.init_db(c)
    
    classes = ["6A5", "6A6", "7A4", "7A5", "8A5", "8A6", "9A5", "9A6"]
    for i, name in enumerate(classes):
        repo.upsert_class(c, name, i)
        
    subjects = [
        "Toán học", "Ngữ văn", "Ngoại ngữ",
        "Khoa học tự nhiên (Vật lý)", "Khoa học tự nhiên (Hóa học)", "Khoa học tự nhiên (Sinh học)",
        "Lịch sử và Địa Lý (Lịch sử)", "Lịch sử và Địa Lý (Địa lý)",
        "GDCD", "Công nghệ", "Tin học", "Giáo dục thể chất",
        "Nội dung giáo dục của địa phương", "Hoạt động trải nghiệm, hướng nghiệp",
        "Nghệ thuật (Âm nhạc)", "Nghệ thuật (Mỹ thuật)",
    ]
    for i, name in enumerate(subjects):
        repo.upsert_subject(c, name, 0, i)
    return c


def test_import_weekly_curriculum_real_excel(school_conn):
    excel_path = "Định lượng số tiết theo tuần năm học 2026_2027.xlsx"
    if not os.path.exists(excel_path):
        pytest.skip(f"Excel file {excel_path} not found")

    from io_excel.weekly_importer import import_weekly_curriculum_from_excel

    report = import_weekly_curriculum_from_excel(school_conn, excel_path)
    assert report["records_imported"] > 0
    assert report["weeks_count"] == 35
    assert len(report["classes_updated"]) == 8

    # Verify Class 6A5 has 29 periods in all 35 weeks
    c_6a5_id = repo.get_class_by_name(school_conn, "6A5")
    assert c_6a5_id is not None
    cur_6a5 = repo.get_weekly_curriculum(school_conn, class_id=c_6a5_id)
    
    for w in range(1, 36):
        total_w = sum(cur_6a5.get((s.subject_id, c_6a5_id, w), 0) for s in repo.list_subjects(school_conn))
        assert total_w == 29, f"6A5 week {w} has {total_w} periods, expected 29"

    # Verify Class 8A5 has 30 periods in weeks 1..9 & 28..35, and 29 periods in weeks 10..27
    c_8a5_id = repo.get_class_by_name(school_conn, "8A5")
    assert c_8a5_id is not None
    cur_8a5 = repo.get_weekly_curriculum(school_conn, class_id=c_8a5_id)

    for w in range(1, 10):
        total_w = sum(cur_8a5.get((s.subject_id, c_8a5_id, w), 0) for s in repo.list_subjects(school_conn))
        assert total_w == 30, f"8A5 week {w} has {total_w} periods, expected 30"

    for w in range(10, 28):
        total_w = sum(cur_8a5.get((s.subject_id, c_8a5_id, w), 0) for s in repo.list_subjects(school_conn))
        assert total_w == 29, f"8A5 week {w} has {total_w} periods, expected 29"

    for w in range(28, 36):
        total_w = sum(cur_8a5.get((s.subject_id, c_8a5_id, w), 0) for s in repo.list_subjects(school_conn))
        assert total_w == 30, f"8A5 week {w} has {total_w} periods, expected 30"
