import sqlite3
import pytest
from data.repositories.constraints import set_inter_school_teacher_config, get_teacher_busy_cells
from data.repositories.entities import list_teachers


def create_mock_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE teachers (
            teacher_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            role TEXT DEFAULT '',
            must_monday INTEGER DEFAULT 0,
            is_gvcn INTEGER DEFAULT 0,
            off_sessions_override INTEGER,
            pinned_full_day_off INTEGER,
            pinned_afternoon_off INTEGER,
            min_afternoon_off INTEGER,
            reduction_override INTEGER
        );
        CREATE TABLE teacher_unavailability (
            row_id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER NOT NULL,
            weekday TEXT DEFAULT '*',
            session TEXT DEFAULT '*',
            period TEXT DEFAULT '*'
        );
        INSERT INTO teachers (teacher_id, name, off_sessions_override) VALUES
            (14, 'Cô Hoà', NULL),
            (15, 'Cô Trang', NULL);
    """)
    return conn


def test_inter_school_teacher_config_auto_mode():
    conn = create_mock_db()
    # 1. Cấu hình tự do cho Cô Hoà (3 buổi nghỉ)
    set_inter_school_teacher_config(conn, teacher_id=14, off_sessions_override=3, mode="auto")
    
    t_hoa = [t for t in list_teachers(conn) if t.teacher_id == 14][0]
    assert t_hoa.off_sessions_override == 3
    busy = get_teacher_busy_cells(conn, 14)
    assert len(busy) == 0  # Không có ô bận cưỡng bức


def test_inter_school_teacher_config_fixed_mode():
    conn = create_mock_db()
    # 2. Cấu hình cố định cho Cô Trang (2 buổi nghỉ: Chiều T3 và Sáng T5)
    fixed = [(3, "C"), (5, "S")]
    set_inter_school_teacher_config(
        conn, teacher_id=15, off_sessions_override=2, mode="fixed", fixed_sessions=fixed, max_periods=4
    )
    
    t_trang = [t for t in list_teachers(conn) if t.teacher_id == 15][0]
    assert t_trang.off_sessions_override == 2
    busy = get_teacher_busy_cells(conn, 15)
    assert len(busy) == 8  # 2 buổi * 4 tiết/buổi = 8 ô bận
    assert (3, "C", 1) in busy
    assert (5, "S", 4) in busy

    # 3. Chuyển lại về chế độ Tự do: phải dọn dẹp các ô bận cũ
    set_inter_school_teacher_config(conn, teacher_id=15, off_sessions_override=2, mode="auto")
    busy_after = get_teacher_busy_cells(conn, 15)
    assert len(busy_after) == 0
