import pandas as pd
import streamlit as st

from data import repository as repo
from ui_common import ROLE_CODE_LABELS, ROLE_LABEL_TO_CODE, get_conn, require_auth, require_school, \
    sidebar_backup_export, sidebar_school_switcher

require_auth()
school_slug = require_school()
conn = get_conn(school_slug)
st.title("Khai báo Lớp / Môn / Giáo viên")

tab_classes, tab_subjects, tab_teachers = st.tabs(["Lớp học", "Môn học", "Giáo viên"])

with tab_classes:
    classes = repo.list_classes(conn)
    df = pd.DataFrame([{"class_id": c.class_id, "Tên lớp": c.name, "Thứ tự": c.sort_order} for c in classes])
    edited = st.data_editor(
        df, num_rows="dynamic", key="editor_classes", hide_index=True,
        column_config={"class_id": None},
    )
    if st.button("Lưu danh sách lớp"):
        existing_ids = {c.class_id for c in classes}
        kept_ids = set()
        for _, row in edited.iterrows():
            name = str(row["Tên lớp"] or "").strip()
            if not name:
                continue
            cid = row.get("class_id")
            cid = int(cid) if pd.notna(cid) else None
            new_id = repo.upsert_class(conn, name, int(row.get("Thứ tự") or 0), class_id=cid)
            kept_ids.add(new_id)
        for cid in existing_ids - kept_ids:
            repo.delete_class(conn, cid)
        st.success("Đã lưu danh sách lớp.")
        st.rerun()

with tab_subjects:
    subjects = repo.list_subjects(conn)
    df = pd.DataFrame([{
        "subject_id": s.subject_id, "Tên môn": s.name,
        "Vai trò": ROLE_CODE_LABELS.get(s.role_code, "Thường"), "Thứ tự": s.sort_order,
    } for s in subjects])
    edited = st.data_editor(
        df, num_rows="dynamic", key="editor_subjects", hide_index=True,
        column_config={
            "subject_id": None,
            "Vai trò": st.column_config.SelectboxColumn(options=list(ROLE_CODE_LABELS.values())),
        },
    )
    if st.button("Lưu danh sách môn"):
        existing_ids = {s.subject_id for s in subjects}
        kept_ids = set()
        for _, row in edited.iterrows():
            name = str(row["Tên môn"] or "").strip()
            if not name:
                continue
            sid = row.get("subject_id")
            sid = int(sid) if pd.notna(sid) else None
            role_code = ROLE_LABEL_TO_CODE.get(str(row["Vai trò"]), 0)
            new_id = repo.upsert_subject(conn, name, role_code, int(row.get("Thứ tự") or 0), subject_id=sid)
            kept_ids.add(new_id)
        for sid in existing_ids - kept_ids:
            repo.delete_subject(conn, sid)
        st.success("Đã lưu danh sách môn.")
        st.rerun()

with tab_teachers:
    teachers = repo.list_teachers(conn)
    role_options = ["", "GVCN", "Tổ trưởng", "Tổ phó", "Tổng phụ trách"]
    df = pd.DataFrame([{
        "teacher_id": t.teacher_id, "Tên GV": t.name, "Chức vụ": t.role,
        "Đi T2": t.must_monday, "GVCN": t.is_gvcn,
    } for t in teachers])
    edited = st.data_editor(
        df, num_rows="dynamic", key="editor_teachers", hide_index=True,
        column_config={
            "teacher_id": None,
            "Chức vụ": st.column_config.SelectboxColumn(options=role_options),
        },
    )
    if st.button("Lưu danh sách giáo viên"):
        existing_ids = {t.teacher_id for t in teachers}
        kept_ids = set()
        for _, row in edited.iterrows():
            name = str(row["Tên GV"] or "").strip()
            if not name:
                continue
            tid = row.get("teacher_id")
            tid = int(tid) if pd.notna(tid) else None
            new_id = repo.upsert_teacher(
                conn, name, str(row["Chức vụ"] or ""), bool(row["Đi T2"]), bool(row["GVCN"]), teacher_id=tid,
            )
            kept_ids.add(new_id)
        for tid in existing_ids - kept_ids:
            repo.delete_teacher(conn, tid)
        st.success("Đã lưu danh sách giáo viên.")
        st.rerun()

sidebar_backup_export(conn)
sidebar_school_switcher()
