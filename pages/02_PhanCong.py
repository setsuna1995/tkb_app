import pandas as pd
import streamlit as st

from data import repository as repo
from ui_common import (
    get_conn,
    require_auth,
    require_school,
    sidebar_backup_export,
    sidebar_fixed_rules,
    sidebar_school_switcher,
)
from ui_theme import render_callout, render_page_header

require_auth()
school_slug = require_school()
conn = get_conn(school_slug)

classes = repo.list_classes(conn)
subjects = repo.list_subjects(conn)

render_page_header(
    title="Phân Công Chuyên Môn",
    subtitle="Ma trận phân bổ giáo viên giảng dạy từng Môn học theo từng Lớp học",
    badge=f"{len(classes)} lớp • {len(subjects)} môn",
    icon="📋",
)

if not classes or not subjects:
    render_callout(
        "Chưa có dữ liệu Lớp học hoặc Môn học. Hãy vào trang **Khai báo** hoặc **Nhập / Xuất Excel** để chuẩn bị dữ liệu trước.",
        level="warning",
        title="Thiếu dữ liệu nền tảng",
    )
    sidebar_backup_export(conn)
    sidebar_fixed_rules(conn)
    sidebar_school_switcher()
    st.stop()

assignments = repo.get_assignments(conn)
teacher_names = {t.teacher_id: t.name for t in repo.list_teachers(conn)}

data = {"Môn": [s.name for s in subjects]}
for c in classes:
    data[c.name] = [teacher_names.get(assignments.get((s.subject_id, c.class_id)), "") for s in subjects]
df = pd.DataFrame(data)

assigned_count = sum(1 for v in assignments.values() if v is not None)
total_slots = len(classes) * len(subjects)

render_callout(
    f"Đã phân công: **{assigned_count}/{total_slots}** vị trí (môn × lớp). "
    "Bạn có thể gõ tên giáo viên có sẵn hoặc gõ tên mới trực tiếp vào ô tương ứng để hệ thống tự động khởi tạo giáo viên.",
    level="info",
    title="Hướng dẫn phân công",
)

edited = st.data_editor(
    df,
    hide_index=True,
    key="editor_phancong",
    disabled=["Môn"],
    use_container_width=True,
)

if st.button("💾 Lưu phân công chuyên môn", type="primary", key="btn_save_phancong"):
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
    st.success("✅ Đã lưu bảng phân công chuyên môn thành công.")
    st.rerun()

sidebar_backup_export(conn)
sidebar_fixed_rules(conn)
sidebar_school_switcher()
