import os
import pandas as pd
import streamlit as st

from data import repository as repo
from io_excel.weekly_importer import import_weekly_curriculum_from_excel
from ui_common import (
    get_conn, require_auth, require_school, sidebar_backup_export,
    sidebar_fixed_rules, sidebar_school_switcher,
)

require_auth()
school_slug = require_school()
conn = get_conn(school_slug)
st.title("Định mức tiết/tuần & Định mức giáo viên")

classes = repo.list_classes(conn)
subjects = repo.list_subjects(conn)

if not classes or not subjects:
    st.info("Chưa có lớp/môn. Vào trang Khai báo hoặc Nhập/Xuất Excel trước.")
    st.stop()

# ── Khối Nạp nhanh dữ liệu Định lượng cả năm ──
with st.expander("📥 Nạp định lượng số tiết 35 tuần từ file Excel", expanded=False):
    st.caption(
        "Hệ thống hỗ trợ nạp trực tiếp toàn bộ 35 tuần năm học (Học kỳ I: 1-18, Học kỳ II: 19-35) "
        "với đầy đủ các phân môn KHTN (Lý, Hóa, Sinh), LS&ĐL (Sử, Địa), Nghệ thuật (Âm nhạc, Mỹ thuật), GD địa phương, HĐTN..."
    )
    col_imp1, col_imp2 = st.columns([1, 1])
    
    default_excel_file = "Định lượng số tiết theo tuần năm học 2026_2027.xlsx"
    has_default_file = os.path.exists(default_excel_file)
    
    if col_imp1.button("🚀 Nạp tự động từ file mẫu chuẩn (2026_2027)", disabled=not has_default_file, type="primary"):
        with st.spinner("Đang phân tích và nạp dữ liệu 35 tuần từ Excel..."):
            try:
                rep = import_weekly_curriculum_from_excel(conn, default_excel_file)
                st.success(
                    f"✅ Đã nạp thành công **{rep['records_imported']}** dòng dữ liệu cho **{rep['weeks_count']}** tuần "
                    f"({', '.join(rep['classes_updated'])})."
                )
            except Exception as e:
                st.error(f"Lỗi khi nạp file: {e}")
                
    uploaded_file = col_imp2.file_uploader("Hoặc tải lên file Excel định lượng khác (.xlsx)", type=["xlsx", "xlsm"])
    if uploaded_file is not None:
        if col_imp2.button("📥 Nạp từ file tải lên", key="btn_upload_weekly"):
            with st.spinner("Đang đọc file..."):
                try:
                    rep = import_weekly_curriculum_from_excel(conn, uploaded_file.getvalue())
                    st.success(
                        f"✅ Đã nạp thành công **{rep['records_imported']}** dòng dữ liệu cho **{rep['weeks_count']}** tuần."
                    )
                except Exception as e:
                    st.error(f"Lỗi khi nạp: {e}")

tab_sotiet, tab_gv = st.tabs(["📊 Số tiết/tuần (SoTiet)", "👩‍🏫 Định mức giáo viên (DinhMuc_GV)"])

with tab_sotiet:
    view_mode = st.radio(
        "Chế độ định mức",
        ["📅 Định lượng 35 tuần cả năm", "⚖️ Định mức Chẵn / Lẻ"],
        horizontal=True,
        key="sotiet_view_mode",
    )

    if view_mode == "📅 Định lượng 35 tuần cả năm":
        c_hk, c_wk = st.columns([1, 2])
        hk_choice = c_hk.selectbox("Học kỳ", ["Học kỳ I (Tuần 1 - 18)", "Học kỳ II (Tuần 19 - 35)", "Tất cả các tuần (1 - 35)"])
        
        if "I (Tuần 1 - 18)" in hk_choice:
            week_options = list(range(1, 19))
        elif "II (Tuần 19 - 35)" in hk_choice:
            week_options = list(range(19, 36))
        else:
            week_options = list(range(1, 36))

        selected_week = c_wk.select_slider(
            "Chọn tuần cần xem & chỉnh sửa:",
            options=week_options,
            value=week_options[0],
            format_func=lambda w: f"Tuần {w} ({'Chẵn' if w % 2 == 0 else 'Lẻ'})",
            key="slider_selected_week",
        )

        effective_par = "C" if selected_week % 2 == 0 else "L"
        week_periods = repo.get_periods_for_week(conn, week_no=selected_week, parity=effective_par)
        
        st.write(f"Đang hiển thị: **Tuần {selected_week}** (Tuần {'Chẵn' if effective_par == 'C' else 'Lẻ'})")

        data = {"Môn": [s.name for s in subjects]}
        for c in classes:
            data[c.name] = [int(week_periods.get((s.subject_id, c.class_id), 0)) for s in subjects]
        df = pd.DataFrame(data)

        col_config = {
            "Môn": st.column_config.TextColumn(disabled=True),
        }
        for c in classes:
            col_config[c.name] = st.column_config.NumberColumn(
                min_value=0, max_value=20, step=1, format="%d", help=f"Số tiết môn học cho lớp {c.name}"
            )

        edited = st.data_editor(
            df, hide_index=True, key=f"editor_week_{selected_week}",
            column_config=col_config, width="stretch",
        )

        c_save, c_copy = st.columns([1, 1])
        if c_save.button(f"💾 Lưu định mức Tuần {selected_week}", key=f"save_week_{selected_week}", type="primary"):
            entries = []
            for i, s in enumerate(subjects):
                for c in classes:
                    raw_val = edited.loc[i, c.name]
                    val = int(float(raw_val)) if pd.notna(raw_val) and str(raw_val).strip() != "" else 0
                    entries.append((s.subject_id, c.class_id, selected_week, val))
            repo.bulk_set_weekly_curriculum(conn, entries)
            st.success(f"Đã lưu thành công định mức cho Tuần {selected_week}.")
            st.rerun()

        with c_copy.expander(f"📋 Sao chép định lượng Tuần {selected_week} sang các tuần khác"):
            target_weeks = st.multiselect(
                "Chọn các tuần đích nhận định mức:",
                options=[w for w in range(1, 36) if w != selected_week],
                key=f"target_weeks_{selected_week}",
            )
            if st.button("Áp dụng sao chép", key=f"btn_apply_copy_{selected_week}"):
                if target_weeks:
                    copy_entries = []
                    for i, s in enumerate(subjects):
                        for c in classes:
                            raw_val = edited.loc[i, c.name]
                            val = int(float(raw_val)) if pd.notna(raw_val) and str(raw_val).strip() != "" else 0
                            for tw in target_weeks:
                                copy_entries.append((s.subject_id, c.class_id, tw, val))
                    repo.bulk_set_weekly_curriculum(conn, copy_entries)
                    st.success(f"Đã sao chép thành công định lượng sang các tuần: {', '.join(str(w) for w in target_weeks)}.")
                    st.rerun()

        totals = {}
        for c in classes:
            t = 0
            for i in range(len(subjects)):
                v = edited.loc[i, c.name]
                t += int(float(v)) if pd.notna(v) and str(v).strip() != "" else 0
            totals[c.name] = t
        st.caption("Tổng tiết/lớp trong tuần này: " + ", ".join(f"**{name}**: {total}" for name, total in totals.items()))

        with st.expander("📈 Ma trận tổng tiết 35 tuần của tất cả các lớp", expanded=False):
            matrix_data = {"Lớp": [c.name for c in classes]}
            configured_weeks = repo.list_configured_weeks(conn)
            all_week_data = repo.get_weekly_curriculum(conn)
            for w in range(1, 36):
                col_totals = []
                for c in classes:
                    t = sum(all_week_data.get((s.subject_id, c.class_id, w), 0) for s in subjects)
                    if t == 0:
                        # Fallback
                        par = "C" if w % 2 == 0 else "L"
                        ppw = repo.get_periods_per_week(conn)
                        t = sum(ppw.get((s.subject_id, c.class_id, par), 0) for s in subjects)
                    col_totals.append(t)
                matrix_data[f"T{w}"] = col_totals
            st.dataframe(pd.DataFrame(matrix_data), hide_index=True, width="stretch")

    else:
        # Chế độ Chẵn / Lẻ
        parity_label = st.radio("Tuần", ["Chẵn", "Lẻ"], horizontal=True, key="sotiet_parity")
        parity = "C" if parity_label == "Chẵn" else "L"
        ppw = repo.get_periods_per_week(conn)
        data = {"Môn": [s.name for s in subjects]}
        for c in classes:
            data[c.name] = [int(ppw.get((s.subject_id, c.class_id, parity), 0)) for s in subjects]
        df = pd.DataFrame(data)

        col_config = {
            "Môn": st.column_config.TextColumn(disabled=True),
        }
        for c in classes:
            col_config[c.name] = st.column_config.NumberColumn(
                min_value=0, max_value=20, step=1, format="%d", help=f"Số tiết môn học cho lớp {c.name}"
            )

        edited = st.data_editor(
            df, hide_index=True, key=f"editor_sotiet_{parity}",
            column_config=col_config, width="stretch",
        )

        if st.button(f"💾 Lưu số tiết tuần {'Chẵn' if parity == 'C' else 'Lẻ'}", key=f"save_sotiet_{parity}", type="primary"):
            for i, s in enumerate(subjects):
                for c in classes:
                    raw_val = edited.loc[i, c.name]
                    val = int(float(raw_val)) if pd.notna(raw_val) and str(raw_val).strip() != "" else 0
                    repo.set_periods_per_week(conn, s.subject_id, c.class_id, parity, val)
            st.success(f"Đã lưu thành công số tiết tuần {'Chẵn' if parity == 'C' else 'Lẻ'}.")
            st.rerun()

        totals = {}
        for c in classes:
            t = 0
            for i in range(len(subjects)):
                v = edited.loc[i, c.name]
                t += int(float(v)) if pd.notna(v) and str(v).strip() != "" else 0
            totals[c.name] = t
        st.caption("Tổng tiết/lớp: " + ", ".join(f"**{name}**: {total}" for name, total in totals.items()))

        st.divider()
        st.subheader("Cân bằng Chẵn/Lẻ theo lớp")
        st.caption(
            "Môn có số tiết khác nhau giữa tuần Chẵn và tuần Lẻ (ví dụ 2 tiết tuần này, 1 tiết tuần kia) "
            "để đạt trung bình lẻ như 1.5 tiết/tuần. Nếu các môn lệch không cân bằng nhau giữa 2 tuần, "
            "tổng tiết/tuần của lớp sẽ khác nhau giữa Chẵn và Lẻ -- một trong 2 tuần có thể không đủ chỗ "
            "xếp TKB dù tuần kia vừa khít. Chọn lại tuần nào \"nặng\" hơn cho từng môn để cân bằng."
        )
        ppw_full = repo.get_periods_per_week(conn)
        for cls in classes:
            alt_subjects = []
            total_c = total_l = 0
            for s in subjects:
                c_val = ppw_full.get((s.subject_id, cls.class_id, "C"), 0)
                l_val = ppw_full.get((s.subject_id, cls.class_id, "L"), 0)
                total_c += c_val
                total_l += l_val
                if c_val != l_val:
                    alt_subjects.append((s, c_val, l_val))
            if not alt_subjects:
                continue
            label = f"{cls.name}: tổng Chẵn={total_c}, Lẻ={total_l}"
            label += f" -- LỆCH {abs(total_c - total_l)} tiết" if total_c != total_l else " (đã cân bằng)"
            with st.expander(label):
                for s, c_val, l_val in alt_subjects:
                    heavier = "Chẵn" if c_val > l_val else "Lẻ"
                    choice = st.radio(
                        f"{s.name} (chẵn={c_val}, lẻ={l_val}) -- tuần nào nặng hơn?", ["Chẵn", "Lẻ"],
                        index=0 if heavier == "Chẵn" else 1, horizontal=True,
                        key=f"parity_swap_{cls.class_id}_{s.subject_id}",
                    )
                    if choice != heavier:
                        repo.set_periods_per_week(conn, s.subject_id, cls.class_id, "C", l_val)
                        repo.set_periods_per_week(conn, s.subject_id, cls.class_id, "L", c_val)
                        st.rerun()

with tab_gv:
    with st.expander("⚙️ Thiết lập Trần chuẩn & Sàn tối thiểu toàn trường", expanded=False):
        c1, c2, c3 = st.columns([1, 1, 1])
        new_base_cap = c1.number_input("Trần chuẩn (tiết/tuần)", 1, 30, repo.get_base_cap(conn),
                                       help="Định mức cơ bản cho GV THCS (mặc định 19 tiết/tuần theo Thông tư 28/2009/TT-BGDĐT)")
        new_min_floor = c2.number_input("Sàn tối thiểu (tiết/tuần)", 0, 30, repo.get_min_floor(conn),
                                         help="Ngưỡng cảnh báo khi tổng tiết giảng dạy + giảm trừ của GV quá thấp (mặc định 16)")
        c3.write("")
        c3.write("")
        if c3.button("Lưu trần / sàn", type="primary"):
            repo.set_base_cap(conn, int(new_base_cap))
            repo.set_min_floor(conn, int(new_min_floor))
            st.success("Đã lưu trần chuẩn và sàn tối thiểu.")
            st.rerun()

    teachers = repo.list_teachers(conn)
    if not teachers:
        st.info("Chưa có giáo viên. Vào trang Khai báo để thêm GV.")
    else:
        c_mode, c_val = st.columns([1, 2])
        gv_view_filter = c_mode.radio(
            "Chế độ xem định mức",
            ["📅 Theo tuần cụ thể (1-35)", "📈 Tổng quan toàn năm học (35 tuần)", "⚖️ Theo Chẵn / Lẻ"],
            horizontal=True, key="gv_view_filter"
        )
        
        base_cap = repo.get_base_cap(conn)
        min_floor = repo.get_min_floor(conn)

        if gv_view_filter == "📅 Theo tuần cụ thể (1-35)":
            chosen_gv_week = c_val.slider(
                "Chọn tuần:", 1, 35, 1,
                format="Tuần %d",
                key="gv_week_slider",
            )
            cur_par = "C" if chosen_gv_week % 2 == 0 else "L"
            view = repo.get_teacher_quota_view(conn, parity=cur_par, week_no=chosen_gv_week)
            load_col_name = f"Tải Tuần {chosen_gv_week}"
            st.caption(
                f"Đang hiển thị tải giảng dạy của **Tuần {chosen_gv_week}** "
                f"({'Học kỳ I' if chosen_gv_week <= 18 else 'Học kỳ II'} — Tuần {'Chẵn' if cur_par == 'C' else 'Lẻ'})."
            )

            # Metrics
            n_over = sum(1 for v in view if v["cap"] > 0 and v["over_current"] > 0)
            n_under = sum(1 for v in view if v["cap"] > 0 and v["under_current"] > 0)
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Tổng số GV", len(view))
            m2.metric("Trần chuẩn", f"{base_cap} tiết/tuần")
            m3.metric(f"GV vượt trần Tuần {chosen_gv_week}", n_over, delta=f"+{n_over}" if n_over else "0", delta_color="inverse" if n_over else "normal")
            m4.metric(f"GV dưới sàn Tuần {chosen_gv_week}", n_under, delta=f"-{n_under}" if n_under else "0", delta_color="inverse" if n_under else "normal")

            gv_rows = []
            for v in view:
                curr_over = round(float(v["over_current"]), 1)
                gv_rows.append({
                    "teacher_id": v["teacher_id"],
                    "Giáo viên": v["name"],
                    "Chức vụ / Kiêm nhiệm": v["role"] or "",
                    "Giảm trừ (tiết)": int(v["reduction"]),
                    "Trần định mức": int(v["cap"]),
                    load_col_name: int(v["load"]),
                    "Lệch tuần này": f"{'+' if curr_over > 0 else ''}{curr_over}" if curr_over != 0 else "0",
                    "Tải TB cả năm": round(float(v.get("load_full_year_avg", v["load_avg"])), 1),
                    "Tải TB HK1": round(float(v.get("load_hk1_avg", v["load_avg"])), 1),
                    "Tải TB HK2": round(float(v.get("load_hk2_avg", v["load_avg"])), 1),
                })
            gv_df = pd.DataFrame(gv_rows)

            gv_editor_config = {
                "teacher_id": None,
                "Giáo viên": st.column_config.TextColumn(disabled=True),
                "Chức vụ / Kiêm nhiệm": st.column_config.TextColumn(
                    help="Ghi chú chức vụ hoặc kiêm nhiệm"
                ),
                "Giảm trừ (tiết)": st.column_config.NumberColumn(
                    min_value=0, max_value=30, step=1, format="%d",
                    help="Tổng số tiết giảm trừ trực tiếp của GV (Trần = Trần chuẩn − Giảm trừ)"
                ),
                "Trần định mức": st.column_config.NumberColumn(disabled=True, format="%d"),
                load_col_name: st.column_config.NumberColumn(disabled=True, format="%d"),
                "Lệch tuần này": st.column_config.TextColumn(disabled=True, help="Số tiết thừa (+) hoặc thiếu (−) so với định mức trần"),
                "Tải TB cả năm": st.column_config.NumberColumn(disabled=True, format="%.1f"),
                "Tải TB HK1": st.column_config.NumberColumn(disabled=True, format="%.1f"),
                "Tải TB HK2": st.column_config.NumberColumn(disabled=True, format="%.1f"),
            }

        elif gv_view_filter == "📈 Tổng quan toàn năm học (35 tuần)":
            view = repo.get_teacher_quota_view(conn, week_no=1)
            load_col_name = "Tải TB cả năm"
            st.caption(
                "Tổng quan tải định mức toàn năm học: hiển thị trung bình cả năm, trung bình Học kỳ I (tuần 1-18), "
                "Học kỳ II (tuần 19-35) và các tuần cao điểm / thấp điểm."
            )

            # Metrics
            n_over_year = sum(1 for v in view if v["cap"] > 0 and v["over_year"] > 0)
            n_under_year = sum(1 for v in view if v["cap"] > 0 and v["under_year"] > 0)
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Tổng số GV", len(view))
            m2.metric("Trần chuẩn", f"{base_cap} tiết/tuần")
            m3.metric("GV vượt trần TB cả năm", n_over_year, delta=f"+{n_over_year}" if n_over_year else "0", delta_color="inverse" if n_over_year else "normal")
            m4.metric("GV dưới sàn TB cả năm", n_under_year, delta=f"-{n_under_year}" if n_under_year else "0", delta_color="inverse" if n_under_year else "normal")

            gv_rows = []
            for v in view:
                year_over = round(float(v["over_year"]), 1)
                gv_rows.append({
                    "teacher_id": v["teacher_id"],
                    "Giáo viên": v["name"],
                    "Chức vụ / Kiêm nhiệm": v["role"] or "",
                    "Giảm trừ (tiết)": int(v["reduction"]),
                    "Trần định mức": int(v["cap"]),
                    "Tải TB cả năm": round(float(v["load_full_year_avg"]), 1),
                    "Lệch TB cả năm": f"{'+' if year_over > 0 else ''}{year_over}" if year_over != 0 else "0",
                    "Tải TB HK1": round(float(v["load_hk1_avg"]), 1),
                    "Tải TB HK2": round(float(v["load_hk2_avg"]), 1),
                    "Tuần cao nhất": f"T{v['max_week']} ({v['max_load']} tiết)",
                    "Tuần thấp nhất": f"T{v['min_week']} ({v['min_load']} tiết)",
                })
            gv_df = pd.DataFrame(gv_rows)

            gv_editor_config = {
                "teacher_id": None,
                "Giáo viên": st.column_config.TextColumn(disabled=True),
                "Chức vụ / Kiêm nhiệm": st.column_config.TextColumn(help="Ghi chú chức vụ hoặc kiêm nhiệm"),
                "Giảm trừ (tiết)": st.column_config.NumberColumn(
                    min_value=0, max_value=30, step=1, format="%d",
                    help="Tổng số tiết giảm trừ trực tiếp của GV (Trần = Trần chuẩn − Giảm trừ)"
                ),
                "Trần định mức": st.column_config.NumberColumn(disabled=True, format="%d"),
                "Tải TB cả năm": st.column_config.NumberColumn(disabled=True, format="%.1f"),
                "Lệch TB cả năm": st.column_config.TextColumn(disabled=True),
                "Tải TB HK1": st.column_config.NumberColumn(disabled=True, format="%.1f"),
                "Tải TB HK2": st.column_config.NumberColumn(disabled=True, format="%.1f"),
                "Tuần cao nhất": st.column_config.TextColumn(disabled=True),
                "Tuần thấp nhất": st.column_config.TextColumn(disabled=True),
            }

        else:
            # Chẵn / Lẻ
            _, cur_par = repo.get_tuan_config(conn)
            chosen_par = c_val.radio("Chọn loại tuần:", ["Chẵn", "Lẻ"], index=0 if cur_par == "C" else 1, horizontal=True, key="gv_par_radio")
            cur_par = "C" if chosen_par == "Chẵn" else "L"
            view = repo.get_teacher_quota_view(conn, parity=cur_par)
            load_col_name = f"Tải tuần {'Chẵn' if cur_par == 'C' else 'Lẻ'}"

            gv_rows = []
            for v in view:
                c_over = round(float(v["load_chan"] - v["cap"]), 1)
                l_over = round(float(v["load_le"] - v["cap"]), 1)
                avg_over = round(float(v["over"]), 1)
                curr_over = round(float(v["over_current"]), 1)
                gv_rows.append({
                    "teacher_id": v["teacher_id"],
                    "Giáo viên": v["name"],
                    "Chức vụ / Kiêm nhiệm": v["role"] or "",
                    "Giảm trừ (tiết)": int(v["reduction"]),
                    "Trần định mức": int(v["cap"]),
                    load_col_name: int(v["load"]),
                    "Tải TB cả năm": round(float(v["load_avg"]), 1),
                    "Lệch so với trần": f"{'+' if curr_over > 0 else ''}{curr_over}" if curr_over != 0 else "0",
                    "Tải tuần Chẵn": int(v["load_chan"]),
                    "Tải tuần Lẻ": int(v["load_le"]),
                })
            gv_df = pd.DataFrame(gv_rows)

            gv_editor_config = {
                "teacher_id": None,
                "Giáo viên": st.column_config.TextColumn(disabled=True),
                "Chức vụ / Kiêm nhiệm": st.column_config.TextColumn(help="Ghi chú chức vụ hoặc kiêm nhiệm"),
                "Giảm trừ (tiết)": st.column_config.NumberColumn(
                    min_value=0, max_value=30, step=1, format="%d",
                    help="Tổng số tiết giảm trừ trực tiếp của GV"
                ),
                "Trần định mức": st.column_config.NumberColumn(disabled=True, format="%d"),
                load_col_name: st.column_config.NumberColumn(disabled=True, format="%d"),
                "Tải TB cả năm": st.column_config.NumberColumn(disabled=True, format="%.1f"),
                "Lệch so với trần": st.column_config.TextColumn(disabled=True),
                "Tải tuần Chẵn": st.column_config.NumberColumn(disabled=True, format="%d"),
                "Tải tuần Lẻ": st.column_config.NumberColumn(disabled=True, format="%d"),
            }

        st.markdown("**Bảng phân bổ định mức & tải giảng dạy của Giáo viên**")
        st.caption(
            "Bạn có thể **chỉnh sửa trực tiếp** cột *Chức vụ / Kiêm nhiệm* và *Giảm trừ (tiết)* rồi bấm **💾 Lưu định mức & giảm trừ GV**."
        )

        edited_gv = st.data_editor(
            gv_df, hide_index=True, key="editor_teacher_quotas",
            column_config=gv_editor_config, width="stretch",
        )

        if st.button("💾 Lưu định mức & giảm trừ GV", key="btn_save_teacher_quotas", type="primary"):
            for _, row in edited_gv.iterrows():
                tid = int(row["teacher_id"])
                tname = str(row["Giáo viên"]).strip()
                trole = str(row.get("Chức vụ / Kiêm nhiệm") or "").strip()
                raw_red = row.get("Giảm trừ (tiết)")
                red_val = int(float(raw_red)) if pd.notna(raw_red) and str(raw_red).strip() != "" else 0
                repo.upsert_teacher(
                    conn,
                    name=tname,
                    role=trole,
                    reduction_override=red_val,
                    teacher_id=tid,
                )
            st.success("Đã cập nhật định mức & giảm trừ cho giáo viên thành công!")
            st.rerun()

        st.caption(
            f"Trần định mức = {base_cap} − Giảm trừ. Tải = tổng số tiết dạy thực tế theo tuần đã chọn (Phân công × Số tiết tuần). "
            f"Sàn tối thiểu cảnh báo: (Tải TB + Giảm trừ) phải ≥ {min_floor}."
        )

        # ── Ma trận Tải 35 tuần của toàn bộ Giáo viên ──
        with st.expander("📊 Ma trận tải 35 tuần của toàn bộ Giáo viên (35 tuần × GV)", expanded=False):
            st.caption(
                "Bảng theo dõi tải giảng dạy thực tế của tất cả giáo viên qua từng tuần trong năm học. "
                "Các ô có màu đỏ nhạt là các tuần giáo viên dạy vượt trần định mức."
            )
            matrix_gv_rows = []
            for v in view:
                r_dict = {
                    "Giáo viên": v["name"],
                    "Trần": v["cap"],
                    "TB Năm": round(float(v["load_full_year_avg"]), 1),
                }
                w_loads = v.get("weekly_loads", {})
                for w in range(1, 36):
                    r_dict[f"T{w}"] = w_loads.get(w, 0)
                matrix_gv_rows.append(r_dict)

            df_matrix_gv = pd.DataFrame(matrix_gv_rows)

            def _highlight_over_cap(row):
                cap_val = row["Trần"]
                styles = [""] * len(row)
                for i, col in enumerate(row.index):
                    if col.startswith("T") and col[1:].isdigit():
                        w_val = row[col]
                        if cap_val > 0 and w_val > cap_val:
                            styles[i] = "background-color: #ffc7ce; font-weight: bold; color: #9c0006"
                return styles

            st.dataframe(
                df_matrix_gv.style.apply(_highlight_over_cap, axis=1),
                hide_index=True, width="stretch",
            )

        with st.expander("🔬 Chi tiết phân công môn & số tiết theo tuần của từng Giáo viên (KHTN, LS&ĐL, Toán, Văn...)", expanded=False):
            teacher_choices = [v["name"] for v in view if v.get("assignments")]
            if not teacher_choices:
                st.info("Chưa có giáo viên nào được phân công giảng dạy.")
            else:
                chosen_t_name = st.selectbox("Chọn Giáo viên để xem chi tiết:", teacher_choices, key="detail_t_select")
                chosen_v = next((v for v in view if v["name"] == chosen_t_name), None)
                if chosen_v and chosen_v.get("assignments"):
                    detail_rows = []
                    for a in chosen_v["assignments"]:
                        w_map = a.get("weekly_periods", {})
                        hk1_avg = sum(w_map.get(w, 0) for w in range(1, 19)) / 18.0 if w_map else a["periods_chan"]
                        hk2_avg = sum(w_map.get(w, 0) for w in range(19, 36)) / 17.0 if w_map else a["periods_le"]
                        detail_rows.append({
                            "Lớp": a["class_name"],
                            "Môn học": a["subject_name"],
                            "Tiết tuần đang chọn": a.get("periods_week", 0),
                            "Tiết TB HK1": round(hk1_avg, 1),
                            "Tiết TB HK2": round(hk2_avg, 1),
                            "Tiết TB Cả năm": round(sum(w_map.values()) / 35.0, 1) if w_map else (a["periods_chan"] + a["periods_le"]) / 2,
                        })
                    st.dataframe(pd.DataFrame(detail_rows), hide_index=True, width="stretch")
                    st.caption(
                        f"👉 **Tổng kết {chosen_t_name}**: Dạy **{chosen_v['load']}** tiết (tuần đang chọn) — "
                        f"Trung bình HK1: **{chosen_v['load_hk1_avg']:.1f}** tiết/tuần, "
                        f"Trung bình HK2: **{chosen_v['load_hk2_avg']:.1f}** tiết/tuần, "
                        f"Trung bình Cả năm: **{chosen_v['load_full_year_avg']:.1f}** tiết/tuần. "
                        f"Định mức trần: **{chosen_v['cap']}** tiết."
                    )

    with st.expander("Mức giảm trừ mặc định theo tên chức vụ", expanded=False):
        st.caption("Các mức giảm trừ tham chiếu chung cho toàn trường:")
        rr = repo.get_role_reduction(conn)
        rr_df = pd.DataFrame([{"Chức vụ": k, "Giảm trừ": v} for k, v in rr.items()])
        rr_edited = st.data_editor(rr_df, hide_index=True, num_rows="dynamic", key="editor_role_reduction")
        if st.button("Lưu bảng giảm trừ mẫu"):
            for _, row in rr_edited.iterrows():
                name = str(row["Chức vụ"] or "").strip()
                if name:
                    repo.set_role_reduction(conn, name, int(row["Giảm trừ"] or 0))
            st.success("Đã lưu bảng giảm trừ mẫu.")
            st.rerun()

sidebar_backup_export(conn)
sidebar_fixed_rules(conn)
sidebar_school_switcher()
