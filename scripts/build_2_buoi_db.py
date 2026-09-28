"""Build default 2-shift (2 buổi) databases:
- schools/truong-thcs-2-buoi.db
- data/sample_truong_thcs_2_buoi.db
Based on 'TKB_sao_luu (1) copy.xlsx' and 'Định lượng số tiết theo tuần năm học 2026_2027.xlsx'.
"""
from __future__ import annotations

import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data import db, repository as repo
from io_excel.importer import import_xlsm
from io_excel.weekly_importer import import_weekly_curriculum_from_excel

SOURCE_EXCEL = "TKB_sao_luu (1) copy.xlsx"
WEEKLY_EXCEL = "Định lượng số tiết theo tuần năm học 2026_2027.xlsx"
SCHOOL_NAME = "Trường THCS - Học 2 buổi (2026-2027)"

TARGET_PATHS = [
    os.path.join(os.path.dirname(__file__), "..", "schools", "truong-thcs-2-buoi.db"),
    os.path.join(os.path.dirname(__file__), "..", "data", "sample_truong_thcs_2_buoi.db"),
]


def build_database(db_path: str):
    if os.path.exists(db_path):
        os.remove(db_path)

    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = db.get_connection(db_path)
    try:
        db.init_db(conn)
        rep_import = import_xlsm(conn, SOURCE_EXCEL)
        print(f"[{os.path.basename(db_path)}] import_xlsm: {rep_import.counts}")

        rep_weekly = import_weekly_curriculum_from_excel(conn, WEEKLY_EXCEL)
        print(f"[{os.path.basename(db_path)}] import_weekly: {rep_weekly['records_imported']} records across {rep_weekly['weeks_count']} weeks")

        repo.set_meta(conn, "school_name", SCHOOL_NAME)
        repo.set_meta(conn, "base_cap", "19")
        repo.set_meta(conn, "min_floor", "16")

        # Verify
        classes = repo.list_classes(conn)
        subjects = repo.list_subjects(conn)
        teachers = repo.list_teachers(conn)
        frames = repo.get_all_frame_templates(conn)
        print(f"[{os.path.basename(db_path)}] Verification: {len(classes)} classes, {len(subjects)} subjects, {len(teachers)} teachers, {len(frames)} frames")
    finally:
        conn.close()


def main():
    for p in TARGET_PATHS:
        build_database(p)
    print("All 2-shift databases created successfully!")


if __name__ == "__main__":
    main()
