import pandas as pd
import streamlit as st

from data import repository as repo
from ui_common import get_conn, require_auth, require_school, sidebar_backup_export, sidebar_school_switcher

require_auth()
school_slug = require_school()
conn = get_conn(school_slug)
st.title("Phân công chuyên môn (PhanCong)")

classes = repo.list_classes(conn)
subjects = repo.list_subjects(conn)

if not classes or not subjects:
    st.info("Chưa có lớp/môn. Vào trang Khai báo hoặc Nhập/Xuất Excel trước.")
    st.stop()

assignments = repo.get_assignments(conn)
teacher_names = {t.teacher_id: t.name for t in repo.list_teachers(conn)}

data = {"Môn": [s.name for s in subjects]}
for c in classes:
    data[c.name] = [teacher_names.get(assignments.get((s.subject_id, c.class_id)), "") for s in subjects]
df = pd.DataFrame(data)

st.caption("Điền tên giáo viên vào ô tương ứng (môn × lớp). Để trống nếu chưa phân công.")
edited = st.data_editor(df, hide_index=True, key="editor_phancong", disabled=["Môn"], use_container_width=True)

if st.button("Lưu phân công"):
    def get_or_create_teacher(name: str):
        name = name.strip()
        if not name:
            return None
        tid = repo.get_teacher_by_name(conn, name)
        return tid if tid is not None else repo.upsert_teacher(conn, name)

    for i, s in enumerate(subjects):
        for c in classes:
            teacher_name = str(edited.loc[i, c.name] or "")
            tid = get_or_create_teacher(teacher_name)
            repo.set_assignment(conn, s.subject_id, c.class_id, tid)
    st.success("Đã lưu phân công.")
    st.rerun()

sidebar_backup_export(conn)
sidebar_school_switcher()
