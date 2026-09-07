import pandas as pd
import streamlit as st

from core.models import WEEKDAY_NAMES, WEEKDAYS
from data import repository as repo
from ui_common import (
    ROLE_CODE_LABELS,
    ROLE_LABEL_TO_CODE,
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
config = repo.get_scheduling_config(conn)

classes = repo.list_classes(conn)
subjects = repo.list_subjects(conn)
teachers = repo.list_teachers(conn)

render_page_header(
    title="Khai Báo Lớp / Môn / Giáo Viên",
    subtitle="Thiết lập danh mục cơ sở dữ liệu nền tảng và các phân loại nghiệp vụ sư phạm",
    badge=f"{len(classes)} lớp • {len(subjects)} môn • {len(teachers)} GV",
    icon="🏫",
)

tab_classes, tab_subjects, tab_teachers = st.tabs(["🏫 Lớp học", "📚 Môn học", "👨‍🏫 Giáo viên"])

with tab_classes:
    st.markdown("#### 🏫 Danh sách Lớp học")
    st.caption("Thêm mới, đổi tên hoặc điều chỉnh thứ tự hiển thị của các lớp trong toàn trường.")
    df_classes = pd.DataFrame([{"class_id": c.class_id, "Tên lớp": c.name, "Thứ tự": c.sort_order} for c in classes])
    edited_classes = st.data_editor(
        df_classes, num_rows="dynamic", key="editor_classes", hide_index=True,
        use_container_width=True,
        column_config={"class_id": None},
    )
    if st.button("💾 Lưu danh sách lớp", type="primary", key="btn_save_classes"):
        existing_ids = {c.class_id for c in classes}
        kept_ids = set()
        for _, row in edited_classes.iterrows():
            name = str(row["Tên lớp"] or "").strip()
            if not name:
                continue
            cid = row.get("class_id")
            cid = int(cid) if pd.notna(cid) else None
            new_id = repo.upsert_class(conn, name, int(row.get("Thứ tự") or 0), class_id=cid)
            kept_ids.add(new_id)
        for cid in existing_ids - kept_ids:
            repo.delete_class(conn, cid)
        st.success("✅ Đã lưu danh sách lớp học thành công.")
        st.rerun()

with tab_subjects:
    st.markdown("#### 📚 Danh mục Môn học & Phân loại Sư phạm")
    st.caption("Vai trò quyết định thuật toán: Thường, Nặng (Toán/Lý/Hóa), Kép (xếp 2 tiết liền), Nặng+Kép, GDTC (Thể dục), HDTN (Chào cờ/SHL).")
    df_subjects = pd.DataFrame([{
        "subject_id": s.subject_id, "Tên môn": s.name,
        "Vai trò": ROLE_CODE_LABELS.get(s.role_code, "Thường"), "Thứ tự": s.sort_order,
    } for s in subjects])
    edited_subjects = st.data_editor(
        df_subjects, num_rows="dynamic", key="editor_subjects", hide_index=True,
        use_container_width=True,
        column_config={
            "subject_id": None,
            "Vai trò": st.column_config.SelectboxColumn(options=list(ROLE_CODE_LABELS.values())),
        },
    )
    if st.button("💾 Lưu danh sách môn", type="primary", key="btn_save_subjects"):
        existing_ids = {s.subject_id for s in subjects}
        kept_ids = set()
        for _, row in edited_subjects.iterrows():
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
        st.success("✅ Đã lưu danh sách môn học thành công.")
        st.rerun()

with tab_teachers:
    st.markdown("#### 👨‍🏫 Danh sách Giáo viên & Ngoại lệ Xếp lịch")
    st.caption("Cấu hình số buổi nghỉ riêng, ghim ngày nghỉ cố định hoặc nhiệm vụ đi dạy bắt buộc.")
    role_options = ["", "GVCN", "Tổ trưởng", "Tổ phó", "Phó hiệu trưởng", "Tổng phụ trách"]
    weekday_pin_options = [""] + [WEEKDAY_NAMES[wd] for wd in WEEKDAYS]
    df_teachers = pd.DataFrame([{
        "teacher_id": t.teacher_id, "Tên GV": t.name, "Chức vụ": t.role,
        "Đi T2": t.must_monday, "GVCN": t.is_gvcn,
        "Nghỉ mấy buổi/tuần": t.off_sessions_override,
        "Nghỉ trọn ngày - Thứ": WEEKDAY_NAMES.get(t.pinned_full_day_off, ""),
        "Nghỉ chiều cố định - Thứ": WEEKDAY_NAMES.get(t.pinned_afternoon_off, ""),
    } for t in teachers])
    edited_teachers = st.data_editor(
        df_teachers, num_rows="dynamic", key="editor_teachers", hide_index=True,
        use_container_width=True,
        column_config={
            "teacher_id": None,
            "Chức vụ": st.column_config.TextColumn(help="Nhập chức vụ / nhiệm vụ (ví dụ: GVCN, Tổ trưởng, Thư ký, TPT...)"),
            "Nghỉ mấy buổi/tuần": st.column_config.NumberColumn(
                min_value=0, max_value=3, step=1, help="Bỏ trống = dùng mặc định chung của trường",
            ),
            "Nghỉ trọn ngày - Thứ": st.column_config.SelectboxColumn(
                options=weekday_pin_options,
                help="Ghim nghỉ CẢ NGÀY -- ngoại lệ so với quy tắc chung",
            ),
            "Nghỉ chiều cố định - Thứ": st.column_config.SelectboxColumn(options=weekday_pin_options),
        },
    )
    if st.button("💾 Lưu danh sách giáo viên", type="primary", key="btn_save_teachers"):
        weekday_name_to_num = {WEEKDAY_NAMES[wd]: wd for wd in WEEKDAYS}
        errors = []
        to_save = []
        for _, row in edited_teachers.iterrows():
            name = str(row["Tên GV"] or "").strip()
            if not name:
                continue
            tid = row.get("teacher_id")
            tid = int(tid) if pd.notna(tid) else None
            must_monday = bool(row["Đi T2"])
            is_gvcn = bool(row["GVCN"])
            off_override = row.get("Nghỉ mấy buổi/tuần")
            off_override = int(off_override) if pd.notna(off_override) else None
            full_day_name = str(row.get("Nghỉ trọn ngày - Thứ") or "").strip()
            afternoon_name = str(row.get("Nghỉ chiều cố định - Thứ") or "").strip()
            pinned_full_day_off = weekday_name_to_num.get(full_day_name)
            pinned_afternoon_off = weekday_name_to_num.get(afternoon_name)

            if must_monday and pinned_full_day_off == 2:
                errors.append(f"{name}: đã chọn 'Đi T2' nên không thể ghim nghỉ trọn ngày Thứ 2.")
            if must_monday and pinned_afternoon_off == 2:
                errors.append(f"{name}: đã chọn 'Đi T2' nên không thể ghim nghỉ chiều Thứ 2.")
            mand_morns = getattr(config, "mandatory_morning_weekdays", (2, 5, 6))
            if pinned_full_day_off is not None and (
                (pinned_full_day_off, "S") in config.forbidden_off_cells
                or (pinned_full_day_off, "C") in config.forbidden_off_cells
                or pinned_full_day_off in mand_morns
            ):
                errors.append(f"{name}: Thứ ghim nghỉ trọn ngày (Thứ {pinned_full_day_off}) nằm trong buổi cấm nghỉ hoặc sáng bắt buộc toàn thể GV đi làm.")
            if pinned_afternoon_off is not None and (pinned_afternoon_off, "C") in config.forbidden_off_cells:
                errors.append(f"{name}: Buổi chiều ghim nghỉ nằm trong 'Buổi cấm chọn làm buổi nghỉ GV'.")

            to_save.append((tid, name, str(row["Chức vụ"] or ""), must_monday, is_gvcn,
                             off_override, pinned_full_day_off, pinned_afternoon_off))

        if errors:
            for e in errors:
                render_callout(e, level="danger", title="Lỗi cấu hình giáo viên")
        else:
            existing_ids = {t.teacher_id for t in teachers}
            kept_ids = set()
            for tid, name, role, must_monday, is_gvcn, off_override, full_day_off, afternoon_off in to_save:
                new_id = repo.upsert_teacher(
                    conn, name, role, must_monday, is_gvcn, teacher_id=tid,
                    off_sessions_override=off_override,
                    pinned_full_day_off=full_day_off,
                    pinned_afternoon_off=afternoon_off,
                )
                kept_ids.add(new_id)
            for tid in existing_ids - kept_ids:
                repo.delete_teacher(conn, tid)
            st.success("✅ Đã lưu danh sách giáo viên thành công.")
            st.rerun()

sidebar_backup_export(conn)
sidebar_fixed_rules(conn)
sidebar_school_switcher()
