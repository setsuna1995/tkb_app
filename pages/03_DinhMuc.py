import os
import pandas as pd
import streamlit as st

from data import db
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
        format_func=lambda w: f"Tuần {w} ({'Học kỳ I' if w <= 18 else 'Học kỳ II'})",
        key="slider_selected_week",
    )

    week_periods = repo.get_periods_for_week(conn, week_no=selected_week)
    
    st.write(f"Đang hiển thị: **Tuần {selected_week}** ({'Học kỳ I' if selected_week <= 18 else 'Học kỳ II'})")

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

with tab_gv:
    with st.expander("⚙️ Thiết lập Khung Định mức (Sàn 16 - Trần 19 tiết/tuần) & Giảm trừ toàn trường", expanded=False):
        c1, c2, c3 = st.columns([1, 1, 1])
        new_min_floor = c1.number_input("Sàn định mức tối thiểu (tiết/tuần)", 0, 30, repo.get_min_floor(conn),
                                         help="Sàn chuẩn theo quy định (mặc định 16 tiết/tuần)")
        new_base_cap = c2.number_input("Trần định mức tối đa (tiết/tuần)", 1, 30, repo.get_base_cap(conn),
                                       help="Trần chuẩn theo quy định (mặc định 19 tiết/tuần theo Thông tư 28/2009/TT-BGDĐT)")
        c3.write("")
        c3.write("")
        if c3.button("Lưu khung định mức (16-19t)", type="primary"):
            repo.set_base_cap(conn, int(new_base_cap))
            repo.set_min_floor(conn, int(new_min_floor))
            st.success("Đã lưu khung định mức chuẩn thành công.")
            st.rerun()

    def _format_quota_status(load_val: float, floor_val: int, cap_val: int) -> str:
        l = round(load_val, 1)
        if cap_val > 0 and l > cap_val:
            diff = round(l - cap_val, 1)
            return f"⚠️ Vượt trần (+{diff:g}t)"
        elif l < floor_val:
            diff = round(floor_val - l, 1)
            return f"⚠️ Dưới sàn (-{diff:g}t)"
        else:
            return f"✅ Đạt chuẩn ({l:g}t)"

    def _format_quota_range(floor_val: int, cap_val: int) -> str:
        if floor_val == cap_val:
            return f"{cap_val}"
        return f"{floor_val} – {cap_val}"

    teachers = repo.list_teachers(conn)
    if not teachers:
        st.info("Chưa có giáo viên. Vào trang Khai báo để thêm GV.")
    else:
        c_mode, c_val = st.columns([1, 2])
        gv_view_filter = c_mode.radio(
            "Chế độ xem định mức",
            ["📅 Theo tuần cụ thể (1-35)", "📈 Tổng quan toàn năm học (35 tuần)"],
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
            view = repo.get_teacher_quota_view(conn, week_no=chosen_gv_week)
            load_col_name = f"Tải Tuần {chosen_gv_week}"
            st.caption(
                f"Đang hiển thị tải giảng dạy của **Tuần {chosen_gv_week}** "
                f"({'Học kỳ I' if chosen_gv_week <= 18 else 'Học kỳ II'})."
            )

            # Metrics
            n_in_norm = sum(1 for v in view if v["floor"] <= v["load"] <= v["cap"])
            n_over = sum(1 for v in view if v["cap"] > 0 and v["load"] > v["cap"])
            n_under = sum(1 for v in view if v["load"] < v["floor"])

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Tổng số GV", len(view))
            m2.metric("Trong định mức (16–19t)", n_in_norm)
            m3.metric("Dạy vượt trần (> 19t)", n_over, delta=f"+{n_over}" if n_over else "0", delta_color="normal")
            m4.metric("Dưới sàn (< 16t)", n_under, delta=f"-{n_under}" if n_under else "0", delta_color="inverse" if n_under else "normal")

            gv_rows = []
            for v in view:
                status_str = _format_quota_status(v["load"], v["floor"], v["cap"])
                quota_range_str = _format_quota_range(v["floor"], v["cap"])
                gv_rows.append({
                    "teacher_id": v["teacher_id"],
                    "Giáo viên": v["name"],
                    "Chức vụ / Kiêm nhiệm": v["role"] or "",
                    "Giảm trừ (tiết)": int(v["reduction"]),
                    "Định mức chuẩn": quota_range_str,
                    load_col_name: int(v["load"]),
                    "Tình trạng tuần này": status_str,
                    "Tải TB cả năm": round(float(v.get("load_full_year_avg", v["load_avg"])), 1),
                    "Tải TB HK1": round(float(v.get("load_hk1_avg", v["load_avg"])), 1),
                    "Tải TB HK2": round(float(v.get("load_hk2_avg", v["load_avg"])), 1),
                })
            gv_df = pd.DataFrame(gv_rows)

            gv_editor_config = {
                "teacher_id": None,
                "Giáo viên": st.column_config.TextColumn(disabled=True),
                "Chức vụ / Kiêm nhiệm": st.column_config.TextColumn(
                    help="Ghi chú chức vụ hoặc kiêm nhiệm (Hiệu trưởng: 2t, Phó hiệu trưởng: 4t, GVCN: -4t, Tổ trưởng: -3t...)"
                ),
                "Giảm trừ (tiết)": st.column_config.NumberColumn(
                    min_value=0, max_value=30, step=1, format="%d",
                    help="Tổng số tiết giảm trừ trực tiếp của GV (Khung = Sàn chuẩn − Giảm trừ đến Trần chuẩn − Giảm trừ)"
                ),
                "Định mức chuẩn": st.column_config.TextColumn(
                    disabled=True,
                    help="Khoảng định mức tiết dạy hợp lệ (Ví dụ: 16 - 19 tiết cho GV, 12 - 15 tiết cho GVCN)"
                ),
                load_col_name: st.column_config.NumberColumn(disabled=True, format="%d"),
                "Tình trạng tuần này": st.column_config.TextColumn(
                    disabled=True,
                    help="Đánh giá tải: Đạt chuẩn (trong khoảng 16-19t), Vượt trần (>19t) hoặc Dưới sàn (<16t)"
                ),
                "Tải TB cả năm": st.column_config.NumberColumn(disabled=True, format="%.1f"),
                "Tải TB HK1": st.column_config.NumberColumn(disabled=True, format="%.1f"),
                "Tải TB HK2": st.column_config.NumberColumn(disabled=True, format="%.1f"),
            }

        else:
            view = repo.get_teacher_quota_view(conn, week_no=1)
            load_col_name = "Tải TB cả năm"
            st.caption(
                "Tổng quan tải định mức toàn năm học: hiển thị trung bình cả năm, trung bình Học kỳ I (tuần 1-18), "
                "Học kỳ II (tuần 19-35) và các tuần cao điểm / thấp điểm."
            )

            # Metrics
            n_in_norm_year = sum(1 for v in view if v["floor"] <= round(v["load_full_year_avg"], 1) <= v["cap"])
            n_over_year = sum(1 for v in view if v["cap"] > 0 and round(v["load_full_year_avg"], 1) > v["cap"])
            n_under_year = sum(1 for v in view if round(v["load_full_year_avg"], 1) < v["floor"])

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Tổng số GV", len(view))
            m2.metric("Trong định mức TB cả năm", n_in_norm_year)
            m3.metric("Vượt trần TB cả năm (>19t)", n_over_year, delta=f"+{n_over_year}" if n_over_year else "0", delta_color="normal")
            m4.metric("Dưới sàn TB cả năm (<16t)", n_under_year, delta=f"-{n_under_year}" if n_under_year else "0", delta_color="inverse" if n_under_year else "normal")

            gv_rows = []
            for v in view:
                status_year = _format_quota_status(v["load_full_year_avg"], v["floor"], v["cap"])
                quota_range_str = _format_quota_range(v["floor"], v["cap"])
                gv_rows.append({
                    "teacher_id": v["teacher_id"],
                    "Giáo viên": v["name"],
                    "Chức vụ / Kiêm nhiệm": v["role"] or "",
                    "Giảm trừ (tiết)": int(v["reduction"]),
                    "Định mức chuẩn": quota_range_str,
                    "Tải TB cả năm": round(float(v["load_full_year_avg"]), 1),
                    "Tình trạng cả năm": status_year,
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
                    help="Tổng số tiết giảm trừ trực tiếp của GV"
                ),
                "Định mức chuẩn": st.column_config.TextColumn(
                    disabled=True,
                    help="Khoảng định mức tiết dạy hợp lệ (Ví dụ: 16 - 19 tiết cho GV, 12 - 15 tiết cho GVCN)"
                ),
                "Tải TB cả năm": st.column_config.NumberColumn(disabled=True, format="%.1f"),
                "Tình trạng cả năm": st.column_config.TextColumn(disabled=True),
                "Tải TB HK1": st.column_config.NumberColumn(disabled=True, format="%.1f"),
                "Tải TB HK2": st.column_config.NumberColumn(disabled=True, format="%.1f"),
                "Tuần cao nhất": st.column_config.TextColumn(disabled=True),
                "Tuần thấp nhất": st.column_config.TextColumn(disabled=True),
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
            f"💡 **Quy định khung định mức:** Tiết dạy chuẩn giáo viên THCS nằm trong khoảng **{min_floor} – {base_cap} tiết/tuần** (theo TT 28/2009/TT-BGDĐT). "
            f"Khoảng định mức cá nhân = (Sàn {min_floor} − Giảm trừ) đến (Trần {base_cap} − Giảm trừ). "
            f"Giáo viên dạy trong khoảng này là **Đạt chuẩn**, chỉ cảnh báo khi **Vượt trần** (> trần) hoặc **Dưới sàn** (< sàn)."
        )

        # ── Ma trận Tải 35 tuần của toàn bộ Giáo viên ──
        with st.expander("📊 Ma trận tải 35 tuần của toàn bộ Giáo viên (35 tuần × GV)", expanded=False):
            st.caption(
                "Bảng theo dõi tải giảng dạy thực tế của tất cả giáo viên qua từng tuần trong năm học. "
                "Ô màu đỏ: Tuần vượt trần (> trần) | Ô màu vàng: Tuần dưới sàn (< sàn)."
            )
            matrix_gv_rows = []
            for v in view:
                r_dict = {
                    "Giáo viên": v["name"],
                    "Khung chuẩn": _format_quota_range(v["floor"], v["cap"]),
                    "TB Năm": round(float(v["load_full_year_avg"]), 1),
                    "_floor": v["floor"],
                    "_cap": v["cap"],
                }
                w_loads = v.get("weekly_loads", {})
                for w in range(1, 36):
                    r_dict[f"T{w}"] = w_loads.get(w, 0)
                matrix_gv_rows.append(r_dict)

            df_matrix_gv = pd.DataFrame(matrix_gv_rows)

            def _highlight_quota(row):
                floor_val = row["_floor"]
                cap_val = row["_cap"]
                styles = [""] * len(row)
                for i, col in enumerate(row.index):
                    if col.startswith("T") and col[1:].isdigit():
                        w_val = row[col]
                        if cap_val > 0 and w_val > cap_val:
                            styles[i] = "background-color: #ffc7ce; font-weight: bold; color: #9c0006"
                        elif floor_val > 0 and w_val < floor_val:
                            styles[i] = "background-color: #fff3cd; font-weight: bold; color: #856404"
                return styles

            st.dataframe(
                df_matrix_gv.style.apply(_highlight_quota, axis=1),
                hide_index=True, width="stretch",
                column_config={"_floor": None, "_cap": None},
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
                        f"Khung định mức chuẩn: **{_format_quota_range(chosen_v['floor'], chosen_v['cap'])}** tiết/tuần."
                    )

    with st.expander("⚖️ Mức giảm trừ định mức theo chức vụ & chuẩn Bộ GD&ĐT (Thông tư 28/2009 & 15/2017)", expanded=False):
        st.markdown(
            """
            **Quy định chuẩn của Bộ GD&ĐT đối với giáo viên THCS (Khung chuẩn 16 – 19 tiết/tuần, trần tối đa 19 tiết/tuần):**
            - **Giáo viên THCS**: Khung chuẩn **16 – 19 tiết/tuần** (sàn 16, trần 19)
            - **Hiệu trưởng**: Định mức **2 tiết/tuần** (Sàn = Trần = 2)
            - **Phó hiệu trưởng**: Định mức **4 tiết/tuần** (Sàn = Trần = 4)
            - **Giáo viên chủ nhiệm (GVCN)**: Giảm **4 tiết/tuần** (Khung chuẩn **12 – 15 tiết/tuần**)
            - **Tổ trưởng chuyên môn**: Giảm **3 tiết/tuần** (Khung chuẩn **13 – 16 tiết/tuần**)
            - **Tổ phó chuyên môn**: Giảm **1 tiết/tuần** (Khung chuẩn **15 – 18 tiết/tuần**)
            - **Thư ký Hội đồng trường**: Giảm **2 tiết/tuần** (Khung chuẩn **14 – 17 tiết/tuần**)
            - **Tổng phụ trách Đội**: Giảm **8 tiết/tuần** (hoặc định mức riêng theo hạng trường)
            """
        )
        rr = repo.get_role_reduction(conn)
        rr_df = pd.DataFrame([{"Chức vụ": k, "Giảm trừ": v} for k, v in rr.items()])
        rr_edited = st.data_editor(rr_df, hide_index=True, num_rows="dynamic", key="editor_role_reduction")
        
        c_rr1, c_rr2 = st.columns([1, 1])
        if c_rr1.button("💾 Lưu bảng giảm trừ chức vụ", type="primary"):
            for _, row in rr_edited.iterrows():
                name = str(row["Chức vụ"] or "").strip()
                if name:
                    repo.set_role_reduction(conn, name, int(row["Giảm trừ"] or 0))
            st.success("Đã lưu bảng giảm trừ mẫu thành công.")
            st.rerun()

        if c_rr2.button("🔄 Nạp mẫu giảm trừ chuẩn Bộ GD&ĐT (TT 28/2009)"):
            for k, v in db.DEFAULT_ROLE_REDUCTION.items():
                repo.set_role_reduction(conn, k, v)
            st.success("Đã cập nhật bảng giảm trừ theo chuẩn Bộ GD&ĐT (TT 28/2009 & 15/2017).")
            st.rerun()

sidebar_backup_export(conn)
sidebar_fixed_rules(conn)
sidebar_school_switcher()
