import os

import pytest

from core.models import ROLE_HDTN, ROLE_THUONG
from data import db, repository as repo
from io_excel.exporter import export_full_backup_xlsx
from io_excel.importer import import_xlsm

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "TKB_9lop_moi.xlsm")


@pytest.fixture()
def conn(tmp_path):
    connection = db.get_connection(str(tmp_path / "source.db"))
    db.init_db(connection)
    yield connection
    connection.close()


@pytest.fixture()
def target_conn(tmp_path):
    connection = db.get_connection(str(tmp_path / "target.db"))
    db.init_db(connection)
    yield connection
    connection.close()


def _export_and_reimport(conn, target_conn, tmp_path):
    data = export_full_backup_xlsx(conn)
    backup_path = tmp_path / "backup.xlsx"
    backup_path.write_bytes(data)
    return import_xlsm(target_conn, str(backup_path))


def _snapshot(conn) -> dict:
    """Chụp toàn bộ dữ liệu setup, chuẩn hoá theo TÊN (không theo id) để so sánh giữa 2 DB
    khác nhau (id autoincrement khác nhau giữa DB nguồn và DB nhập lại)."""
    classes = {c.class_id: c.name for c in repo.list_classes(conn)}
    subjects = {s.subject_id: s.name for s in repo.list_subjects(conn)}
    teachers = {t.teacher_id: t.name for t in repo.list_teachers(conn)}

    assignments = {
        (subjects[s], classes[c]): teachers.get(t)
        for (s, c), t in repo.get_assignments(conn).items()
    }
    ppw = {
        (subjects[s], classes[c], p): n
        for (s, c, p), n in repo.get_periods_per_week(conn).items()
    }
    frames = {classes[cid]: frame for cid, frame in repo.get_all_frame_templates(conn).items()}
    unavailability = sorted(
        (teachers.get(u["teacher_id"]), u["weekday"], u["session"], u["period"])
        for u in repo.list_unavailability(conn)
    )
    return {
        "class_names": set(classes.values()),
        "subject_roles": {s.name: s.role_code for s in repo.list_subjects(conn)},
        "teacher_info": {t.name: (t.role, t.must_monday, t.is_gvcn) for t in repo.list_teachers(conn)},
        "assignments": assignments,
        "periods_per_week": ppw,
        "role_reduction": repo.get_role_reduction(conn),
        "frame_templates": frames,
        "unavailability": unavailability,
        "tuan_config": repo.get_tuan_config(conn),
        "base_cap": repo.get_base_cap(conn),
        "min_floor": repo.get_min_floor(conn),
    }


def _seed_history_tuples(conn) -> list:
    # created_at bị re-stamp ở thời điểm import (repo.add_seed_history tự sinh timestamp mới)
    # nên không so sánh created_at -- chỉ so week_no/seed/parity.
    return [(h["week_no"], h["seed"], h["parity"]) for h in repo.list_seed_history(conn)]


def test_full_backup_round_trips_real_fixture_data(conn, target_conn, tmp_path):
    import_xlsm(conn, FIXTURE)
    report = _export_and_reimport(conn, target_conn, tmp_path)

    assert report.counts["classes"] == 9
    assert report.counts["subjects"] == 16
    assert report.counts["teachers"] == 19
    assert _snapshot(conn) == _snapshot(target_conn)
    assert _seed_history_tuples(conn) == _seed_history_tuples(target_conn)


def test_full_backup_round_trips_ngay_lech_tiet(conn, target_conn, tmp_path):
    # Dữ liệu thật/fixture hiện KHÔNG có ví dụ ngày lệch tiết nào (đã xác nhận qua khảo sát) --
    # tạo DB tối giản bằng tay để test riêng ca dễ sai nhất: Thứ 7 chỉ 4 tiết sáng thay vì 5.
    cls_id = repo.upsert_class(conn, "6A")
    subj_thuong = repo.upsert_subject(conn, "Toan", role_code=ROLE_THUONG)
    subj_hdtn = repo.upsert_subject(conn, "HDTN", role_code=ROLE_HDTN)
    teacher_id = repo.upsert_teacher(conn, "GV A")
    repo.set_assignment(conn, subj_thuong, cls_id, teacher_id)
    repo.set_assignment(conn, subj_hdtn, cls_id, teacher_id)
    repo.set_periods_per_week(conn, subj_thuong, cls_id, "C", 26)
    repo.set_periods_per_week(conn, subj_hdtn, cls_id, "C", 3)
    repo.set_frame_template(conn, cls_id, 5, 0, short_weekday=7, short_morning_periods=4)

    _export_and_reimport(conn, target_conn, tmp_path)

    dst_classes = {c.name: c.class_id for c in repo.list_classes(target_conn)}
    morning, afternoon, _ss, _allow_sat, short_wd, short_m, short_a = \
        repo.get_frame_template(target_conn, dst_classes["6A"])
    assert (morning, afternoon) == (5, 0)
    assert (short_wd, short_m, short_a) == (7, 4, None)


def test_full_backup_round_trips_base_cap_and_min_floor(conn, target_conn, tmp_path):
    repo.upsert_class(conn, "6A")
    repo.upsert_subject(conn, "HDTN", role_code=ROLE_HDTN)
    repo.set_base_cap(conn, 21)
    repo.set_min_floor(conn, 14)

    _export_and_reimport(conn, target_conn, tmp_path)

    assert repo.get_base_cap(target_conn) == 21
    assert repo.get_min_floor(target_conn) == 14


def test_full_backup_reimport_does_not_duplicate_when_run_twice(conn, target_conn, tmp_path):
    import_xlsm(conn, FIXTURE)
    _export_and_reimport(conn, target_conn, tmp_path)
    _export_and_reimport(conn, target_conn, tmp_path)  # phải không lỗi UNIQUE constraint

    assert len(repo.list_classes(target_conn)) == 9
    assert len(repo.list_subjects(target_conn)) == 16
    assert len(repo.list_teachers(target_conn)) == 19
