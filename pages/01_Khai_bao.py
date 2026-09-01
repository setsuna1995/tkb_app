import pandas as pd
import streamlit as st

from core.models import WEEKDAY_NAMES, WEEKDAYS
from data import repository as repo
from ui_common import ROLE_CODE_LABELS, ROLE_LABEL_TO_CODE, get_conn, require_auth, require_school, \
    sidebar_backup_export, sidebar_fixed_rules, sidebar_school_switcher

require_auth()
school_slug = require_school()
conn = get_conn(school_slug)
config = repo.get_scheduling_config(conn)
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
    role_options = ["", "GVCN", "Tổ trưởng", "Tổ phó", "Phó hiệu trưởng", "Tổng phụ trách"]
    weekday_pin_options = [""] + [WEEKDAY_NAMES[wd] for wd in WEEKDAYS]
    df = pd.DataFrame([{
        "teacher_id": t.teacher_id, "Tên GV": t.name, "Chức vụ": t.role,
        "Đi T2": t.must_monday, "GVCN": t.is_gvcn,
        "Nghỉ mấy buổi/tuần": t.off_sessions_override,
        "Nghỉ trọn ngày - Thứ": WEEKDAY_NAMES.get(t.pinned_full_day_off, ""),
        "Nghỉ chiều cố định - Thứ": WEEKDAY_NAMES.get(t.pinned_afternoon_off, ""),
    } for t in teachers])
    edited = st.data_editor(
        df, num_rows="dynamic", key="editor_teachers", hide_index=True,
        column_config={
            "teacher_id": None,
            "Chức vụ": st.column_config.SelectboxColumn(options=role_options),
            "Nghỉ mấy buổi/tuần": st.column_config.NumberColumn(
                min_value=0, max_value=3, step=1, help="Bỏ trống = dùng mặc định chung của trường",
            ),
            "Nghỉ trọn ngày - Thứ": st.column_config.SelectboxColumn(
                options=weekday_pin_options,
                help="Ghim nghỉ CẢ NGÀY -- ngoại lệ so với quy tắc chung \"không nghỉ trọn ngày\"",
            ),
            "Nghỉ chiều cố định - Thứ": st.column_config.SelectboxColumn(options=weekday_pin_options),
        },
    )
    if st.button("Lưu danh sách giáo viên"):
        weekday_name_to_num = {WEEKDAY_NAMES[wd]: wd for wd in WEEKDAYS}
        errors = []
        to_save = []
        for _, row in edited.iterrows():
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
                errors.append(f"{name}: đã chọn \"Đi T2\" nên không thể ghim nghỉ trọn ngày Thứ 2.")
            if must_monday and pinned_afternoon_off == 2:
                errors.append(f"{name}: đã chọn \"Đi T2\" nên không thể ghim nghỉ chiều Thứ 2.")
            mand_morns = getattr(config, "mandatory_morning_weekdays", (2, 5, 6))
            if pinned_full_day_off is not None and (
                (pinned_full_day_off, "S") in config.forbidden_off_cells
                or (pinned_full_day_off, "C") in config.forbidden_off_cells
                or pinned_full_day_off in mand_morns
            ):
                errors.append(f"{name}: Thứ ghim nghỉ trọn ngày (Thứ {pinned_full_day_off}) nằm trong buổi cấm nghỉ hoặc sáng bắt buộc toàn thể GV đi làm.")
            if pinned_afternoon_off is not None and (pinned_afternoon_off, "C") in config.forbidden_off_cells:
                errors.append(f"{name}: buổi chiều ghim nghỉ nằm trong \"Buổi cấm chọn làm buổi nghỉ GV\".")

            to_save.append((tid, name, str(row["Chức vụ"] or ""), must_monday, is_gvcn,
                             off_override, pinned_full_day_off, pinned_afternoon_off))

        if errors:
            for e in errors:
                st.error(e)
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
            st.success("Đã lưu danh sách giáo viên.")
            st.rerun()

sidebar_backup_export(conn)
sidebar_fixed_rules(conn)
sidebar_school_switcher()
