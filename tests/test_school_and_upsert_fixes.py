import sqlite3
import pytest
from pathlib import Path
from data import db, repository as repo
import ui_common


@pytest.fixture()
def conn(tmp_path):
    connection = db.get_connection(str(tmp_path / "test.db"))
    db.init_db(connection)
    yield connection
    connection.close()



def test_upsert_class_idempotent_on_duplicate_name(conn):
    id1 = repo.upsert_class(conn, "6A1", sort_order=1)
    id2 = repo.upsert_class(conn, "6A1", sort_order=2)
    assert id1 == id2
    classes = repo.list_classes(conn)
    assert len(classes) == 1
    assert classes[0].name == "6A1"
    assert classes[0].sort_order == 2


def test_upsert_subject_idempotent_on_duplicate_name(conn):
    id1 = repo.upsert_subject(conn, "Toán", role_code=1, sort_order=1)
    id2 = repo.upsert_subject(conn, "Toán", role_code=2, sort_order=2)
    assert id1 == id2
    subjects = repo.list_subjects(conn)
    assert len(subjects) == 1
    assert subjects[0].name == "Toán"
    assert subjects[0].role_code == 2


def test_upsert_teacher_idempotent_on_duplicate_name(conn):
    id1 = repo.upsert_teacher(conn, "Nguyễn Văn A", role="GV")
    id2 = repo.upsert_teacher(conn, "Nguyễn Văn A", role="Tổ trưởng")
    assert id1 == id2
    teachers = repo.list_teachers(conn)
    assert len(teachers) == 1
    assert teachers[0].name == "Nguyễn Văn A"
    assert teachers[0].role == "Tổ trưởng"


def test_list_schools_closes_connections(tmp_path, monkeypatch):
    monkeypatch.setattr(ui_common, "SCHOOLS_DIR", tmp_path)
    monkeypatch.setattr(ui_common, "LEGACY_DB_PATH", str(tmp_path / "legacy.db"))

    # Create two school databases
    s1_path = tmp_path / "truong-a.db"
    conn1 = db.get_connection(str(s1_path))
    db.init_db(conn1)
    repo.set_meta(conn1, "school_name", "Trường A")
    conn1.close()

    s2_path = tmp_path / "truong-b.db"
    conn2 = db.get_connection(str(s2_path))
    db.init_db(conn2)
    repo.set_meta(conn2, "school_name", "Trường B")
    conn2.close()

    schools = ui_common.list_schools()
    assert len(schools) == 2
    assert {s["name"] for s in schools} == {"Trường A", "Trường B"}
