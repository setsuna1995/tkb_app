import os

import pytest

from data import db, repository as repo
from io_excel.importer import import_xlsm

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "TKB_9lop_moi.xlsm")


@pytest.fixture()
def conn(tmp_path):
    connection = db.get_connection(str(tmp_path / "test.db"))
    db.init_db(connection)
    yield connection
    connection.close()


def test_import_real_workbook_counts(conn):
    report = import_xlsm(conn, FIXTURE)
    assert report.counts["classes"] == 9
    assert report.counts["subjects"] == 16
    assert report.counts["teachers"] == 19
    assert report.counts["tkb_nhap_cells"] > 0


def test_import_real_workbook_known_values(conn):
    import_xlsm(conn, FIXTURE)

    classes = {c.name: c.class_id for c in repo.list_classes(conn)}
    subjects = {s.name: s.subject_id for s in repo.list_subjects(conn)}
    teachers = {t.name: t for t in repo.list_teachers(conn)}

    assignments = repo.get_assignments(conn)
    toan_6a_teacher = assignments[(subjects["Toán học"], classes["6A"])]
    assert teachers_by_id(conn)[toan_6a_teacher].name == "Lệ"

    ppw = repo.get_periods_per_week(conn)
    assert ppw[(subjects["Toán học"], classes["6A"], "C")] == 4

    assert teachers["Giang"].is_gvcn is True
    assert teachers["Giang"].role == "GVCN"

    reductions = repo.get_role_reduction(conn)
    assert reductions["GVCN"] == 4
    assert reductions["Tổ trưởng"] == 3
    assert reductions["Tổ phó"] == 1
    assert reductions["Tổng phụ trách"] == 8


def test_reimport_same_workbook_does_not_duplicate_classes_or_subjects(conn):
    import_xlsm(conn, FIXTURE)
    report = import_xlsm(conn, FIXTURE)  # must not raise UNIQUE constraint failed

    assert report.counts["classes"] == 9
    assert report.counts["subjects"] == 16
    assert len(repo.list_classes(conn)) == 9
    assert len(repo.list_subjects(conn)) == 16
    assert len(repo.list_teachers(conn)) == 19


def test_import_infers_frame_template_from_real_khung_pattern(conn):
    import_xlsm(conn, FIXTURE)
    classes = {c.name: c.class_id for c in repo.list_classes(conn)}
    morning, afternoon, study_sunday, _allow_saturday, short_wd, short_m, short_a = \
        repo.get_frame_template(conn, classes["6A"])
    # the real workbook's Khung sheet currently marks only the 5 morning rows active,
    # uniformly across all weekdays (no ngày lệch tiết in this fixture)
    assert morning == 5
    assert afternoon == 0
    assert short_wd is None
    assert short_m is None
    assert short_a is None


def teachers_by_id(conn):
    return {t.teacher_id: t for t in repo.list_teachers(conn)}
