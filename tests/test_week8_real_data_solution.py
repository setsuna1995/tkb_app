import sqlite3
import dataclasses
from collections import Counter
import pytest

from core.models import SchedulingConfig
from core.scheduler import cpsat_model
from data import repository as repo


def test_week8_real_data_solution_cap_and_inter_school():
    """Kiểm thử nghiệm thực tế Tuần 8 từ database trường học:
    1. Thầy Khu (13 tiết) với cấu hình off=1: Dạy ít nhất 7 buổi trong 8 buổi học,
       có mặt rải đều cuối tuần (không bị trống cả sáng T5 lẫn sáng T6).
    2. Cô Hoà (7 tiết, off_sessions_override=3):
       Được nghỉ ít nhất 3 buổi trong 8 buổi học, các buổi dạy đều >= 2 tiết (KHÔNG có 1 tiết lẻ).
    3. Cô Trang (16 tiết, off_sessions_override=2):
       Được nghỉ ít nhất 2 buổi trong 8 buổi học.
    4. Pass 1 FEASIBLE ngay lập tức (không bị nới lỏng II.4 hay bất kỳ luật sư phạm nào).
    """
    conn = sqlite3.connect("schools/truong-thcs-2-buoi.db")
    conn.row_factory = sqlite3.Row

    # Cập nhật cấu hình GV liên trường trên DB cho bài test
    conn.execute("UPDATE teachers SET off_sessions_override = 3 WHERE teacher_id = 14")  # Cô Hoà
    conn.execute("UPDATE teachers SET off_sessions_override = 2 WHERE teacher_id = 15")  # Cô Trang
    conn.execute("DELETE FROM teacher_unavailability WHERE teacher_id = 14")             # Xoá lock tuần 6 cũ

    inp = repo.build_scheduling_input(conn, parity="all", week_no=8)

    # Đảm bảo cấu hình chung: 1 buổi nghỉ, mode hard, Toán/Văn sáng 100%
    cfg = dataclasses.replace(
        inp.config,
        teacher_off_sessions_per_week=1,
        teacher_off_sessions_mode="hard",
        morning_only_subject_ids=frozenset({1, 2}),
    )
    inp_test = dataclasses.replace(inp, config=cfg)

    built = cpsat_model.build_model(inp_test)
    res = cpsat_model.solve_to_result(built, time_limit_s=60.0, workers=8)

    assert res is not None and res.success is True
    assert res.diagnostics.get("pass1_status") == "FEASIBLE", "Pass 1 phải FEASIBLE!"
    assert not any(r["rule_id"] == "II.4" for r in res.relaxed_rules), "Không được nới lỏng luật buổi lẻ II.4!"

    all_sessions = sorted({(ts.weekday, ts.session) for ts in inp_test.timeslots})

    # 1. Thầy Khu (teacher_id=13)
    khu_slots = [
        s for s in inp_test.slots
        if inp_test.assigned_teacher.get((res.assignment.get(s.slot_id), s.class_id)) == 13
    ]
    khu_sessions = {(s.ts.weekday, s.ts.session) for s in khu_slots}
    assert len(khu_sessions) >= 7, f"Thầy Khu bị nghỉ quá nhiều: chỉ dạy {len(khu_sessions)} buổi!"
    assert (5, "S") in khu_sessions or (6, "S") in khu_sessions, "Thầy Khu bị trống cả sáng T5 lẫn sáng T6!"

    # 2. Cô Hoà (teacher_id=14, 7 tiết)
    hoa_slots = [
        s for s in inp_test.slots
        if inp_test.assigned_teacher.get((res.assignment.get(s.slot_id), s.class_id)) == 14
    ]
    hoa_sess_counts = Counter((s.ts.weekday, s.ts.session) for s in hoa_slots)
    hoa_off_sessions = set(all_sessions) - set(hoa_sess_counts.keys())
    assert len(hoa_off_sessions) >= 3, f"Cô Hoà phải được nghỉ >= 3 buổi, thực tế: {len(hoa_off_sessions)}"
    for sess, count in hoa_sess_counts.items():
        assert count >= 2, f"Cô Hoà bị dính buổi lẻ 1 tiết tại {sess} ({count} tiết)!"

    # 3. Cô Trang (teacher_id=15, 16 tiết)
    trang_slots = [
        s for s in inp_test.slots
        if inp_test.assigned_teacher.get((res.assignment.get(s.slot_id), s.class_id)) == 15
    ]
    trang_sessions = {(s.ts.weekday, s.ts.session) for s in trang_slots}
    trang_off_sessions = set(all_sessions) - trang_sessions
    assert len(trang_off_sessions) >= 2, f"Cô Trang phải được nghỉ >= 2 buổi, thực tế: {len(trang_off_sessions)}"
