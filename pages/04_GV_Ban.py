import pandas as pd
import streamlit as st

from data import repository as repo
from ui_common import get_conn, require_auth, require_school, sidebar_backup_export, sidebar_school_switcher

require_auth()
school_slug = require_school()
conn = get_conn(school_slug)
st.title("Giáo viên bận / xin nghỉ (GV_Bận)")
st.caption(
    "Ví dụ: Giang | 5 | * | * → nghỉ cả Thứ 5. Hồng | 3 | S | * → bận sáng Thứ 3. "
    "Xoá dòng khi GV dạy lại rồi lưu lại."
)

teachers = repo.list_teachers(conn)
if not teachers:
    st.info("Chưa có giáo viên. Vào trang Khai báo trước.")
    st.stop()

name_by_id = {t.teacher_id: t.name for t in teachers}
id_by_name = {t.name: t.teacher_id for t in teachers}

rows = repo.list_unavailability(conn)
df = pd.DataFrame([{
    "Giáo viên": name_by_id.get(r["teacher_id"], ""),
    "Thứ": r["weekday"], "Buổi": r["session"], "Tiết": r["period"],
} for r in rows])
if df.empty:
    df = pd.DataFrame(columns=["Giáo viên", "Thứ", "Buổi", "Tiết"])

edited = st.data_editor(
    df, num_rows="dynamic", hide_index=True, key="editor_gvban", use_container_width=True,
    column_config={
        "Giáo viên": st.column_config.SelectboxColumn(options=list(id_by_name)),
        "Thứ": st.column_config.SelectboxColumn(options=["*", "2", "3", "4", "5", "6", "7", "CN"]),
        "Buổi": st.column_config.SelectboxColumn(options=["*", "S", "C"]),
        "Tiết": st.column_config.SelectboxColumn(options=["*", "1", "2", "3", "4", "5"]),
    },
)

if st.button("Lưu GV bận"):
    for r in rows:
        repo.delete_unavailability(conn, r["row_id"])
    for _, row in edited.iterrows():
        name = str(row["Giáo viên"] or "").strip()
        tid = id_by_name.get(name)
        if not tid:
            continue
        repo.add_unavailability(
            conn, tid,
            str(row["Thứ"] or "*"), str(row["Buổi"] or "*"), str(row["Tiết"] or "*"),
        )
    st.success("Đã lưu GV bận.")
    st.rerun()

sidebar_backup_export(conn)
sidebar_school_switcher()
