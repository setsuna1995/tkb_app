import pandas as pd
import streamlit as st

from data import repository as repo
from ui_common import get_conn, require_auth, require_school, sidebar_backup_export, sidebar_school_switcher

require_auth()
school_slug = require_school()
conn = get_conn(school_slug)

st.title("Giáo viên bận / Không xếp tiết (GV_Bận)")
st.caption(
    "Đánh dấu các tiết học không được xếp thời khóa biểu cho giáo viên. "
    "Bạn có thể tích chọn trực tiếp trên lưới tiết học, dùng công cụ chọn nhanh, hoặc chỉnh sửa bảng quy tắc."
)

teachers = repo.list_teachers(conn)
if not teachers:
    st.info("Chưa có giáo viên. Vào trang **Khai báo** trước.")
    st.stop()

name_by_id = {t.teacher_id: t.name for t in teachers}
id_by_name = {t.name: t.teacher_id for t in teachers}
teacher_obj_by_name = {t.name: t for t in teachers}

tab_grid, tab_overview, tab_list = st.tabs([
    "🗓️ Tích chọn theo Giáo viên",
    "👥 Ma trận bận toàn trường",
    "📋 Bảng quy tắc chi tiết",
])

# ---------------------------------------------------------------------------
# TAB 1: Visual Checkbox Grid per Teacher
# ---------------------------------------------------------------------------
with tab_grid:
    col_sel, col_info = st.columns([2, 3])
    with col_sel:
        selected_teacher_name = st.selectbox(
            "Chọn giáo viên cần thiết lập:",
            options=[t.name for t in teachers],
            key="gvban_selected_teacher",
        )
    
    sel_teacher = teacher_obj_by_name[selected_teacher_name]
    sel_tid = sel_teacher.teacher_id
    busy_cells = repo.get_teacher_busy_cells(conn, sel_tid)
    
    with col_info:
        role_label = sel_teacher.role if sel_teacher.role else "Giáo viên bộ môn"
        gvcn_str = " (GVCN)" if sel_teacher.is_gvcn else ""
        t2_str = " | Đi chào cờ T2" if sel_teacher.must_monday else ""
        st.markdown(
            f"**Chức vụ:** `{role_label}{gvcn_str}{t2_str}` &nbsp;|&nbsp; "
            f"**Đang bận:** `{len(busy_cells)}` tiết"
        )
        if busy_cells:
            summary_items = []
            for wd in range(2, 8):
                wd_cells = sorted([f"{sess}{p}" for (w, sess, p) in busy_cells if w == wd])
                if wd_cells:
                    summary_items.append(f"T{wd}: {', '.join(wd_cells)}")
            st.caption("Các tiết đang khoá: " + " • ".join(summary_items))

    # --- Quick Presets Bar ---
    with st.expander("⚡ Công cụ chọn nhanh (Quick Presets)", expanded=False):
        st.markdown("**Áp dụng nhanh các mẫu phổ biến cho giáo viên này:**")
        pcol1, pcol2, pcol3 = st.columns(3)
        with pcol1:
            if st.button("🌅 Không đi Tiết 1 (Thứ 3 & 5)", use_container_width=True, help="Ví dụ: Thầy Khu"):
                new_cells = set(busy_cells)
                new_cells.add((3, "S", 1))
                new_cells.add((5, "S", 1))
                repo.set_teacher_busy_cells(conn, sel_tid, new_cells)
                st.success(f"Đã cập nhật: {selected_teacher_name} không đi Tiết 1 Thứ 3 & Thứ 5!")
                st.rerun()
                
            if st.button("🌅 Không đi Tiết 1 (Thứ 3, 4, 5)", use_container_width=True, help="Ví dụ: Cô Huyền Ly"):
                new_cells = set(busy_cells)
                for w in (3, 4, 5):
                    new_cells.add((w, "S", 1))
                repo.set_teacher_busy_cells(conn, sel_tid, new_cells)
                st.success(f"Đã cập nhật: {selected_teacher_name} không đi Tiết 1 Thứ 3, 4, 5!")
                st.rerun()

        with pcol2:
            if st.button("🌅 Không đi Tiết 1 (Thứ 3, 4, 6)", use_container_width=True, help="Ví dụ: Cô Nguyễn Ly"):
                new_cells = set(busy_cells)
                for w in (3, 4, 6):
                    new_cells.add((w, "S", 1))
                repo.set_teacher_busy_cells(conn, sel_tid, new_cells)
                st.success(f"Đã cập nhật: {selected_teacher_name} không đi Tiết 1 Thứ 3, 4, 6!")
                st.rerun()

            if st.button("🌅 Không đi Tiết 1 (Thứ 3, 5, 6)", use_container_width=True, help="Ví dụ: Thầy Sơn"):
                new_cells = set(busy_cells)
                for w in (3, 5, 6):
                    new_cells.add((w, "S", 1))
                repo.set_teacher_busy_cells(conn, sel_tid, new_cells)
                st.success(f"Đã cập nhật: {selected_teacher_name} không đi Tiết 1 Thứ 3, 5, 6!")
                st.rerun()

        with pcol3:
            if st.button("⛔ Bận S4 & C1 cả tuần", use_container_width=True, help="Ví dụ: Thầy Hồng (GDTC)"):
                new_cells = set(busy_cells)
                for w in range(2, 8):
                    new_cells.add((w, "S", 4))
                    new_cells.add((w, "C", 1))
                repo.set_teacher_busy_cells(conn, sel_tid, new_cells)
                st.success(f"Đã cập nhật: {selected_teacher_name} bận S4 và C1 tất cả các ngày!")
                st.rerun()

            if st.button("🔄 Xóa sạch tất cả tiết bận", use_container_width=True):
                repo.clear_unavailability(conn, sel_tid)
                st.info(f"Đã xóa toàn bộ tiết bận của {selected_teacher_name}.")
                st.rerun()

        st.markdown("**Nghỉ trọn buổi / cả ngày:**")
        wd_pick = st.selectbox(
            "Thứ", options=list(range(2, 8)), format_func=lambda w: f"Thứ {w}",
            key="gvban_preset_weekday",
        )
        pcol4, pcol5, pcol6 = st.columns(3)
        with pcol4:
            if st.button(f"🌤️ Nghỉ trọn Sáng (Thứ {wd_pick})", use_container_width=True):
                new_cells = set(busy_cells)
                for p in range(1, 6):
                    new_cells.add((wd_pick, "S", p))
                repo.set_teacher_busy_cells(conn, sel_tid, new_cells)
                st.success(f"Đã cập nhật: {selected_teacher_name} nghỉ trọn buổi Sáng Thứ {wd_pick}!")
                st.rerun()
        with pcol5:
            if st.button(f"🌆 Nghỉ trọn Chiều (Thứ {wd_pick})", use_container_width=True):
                new_cells = set(busy_cells)
                for p in range(1, 6):
                    new_cells.add((wd_pick, "C", p))
                repo.set_teacher_busy_cells(conn, sel_tid, new_cells)
                st.success(f"Đã cập nhật: {selected_teacher_name} nghỉ trọn buổi Chiều Thứ {wd_pick}!")
                st.rerun()
        with pcol6:
            if st.button(f"🌑 Nghỉ trọn cả ngày (Thứ {wd_pick})", use_container_width=True):
                new_cells = set(busy_cells)
                for p in range(1, 6):
                    new_cells.add((wd_pick, "S", p))
                    new_cells.add((wd_pick, "C", p))
                repo.set_teacher_busy_cells(conn, sel_tid, new_cells)
                st.success(f"Đã cập nhật: {selected_teacher_name} nghỉ trọn cả ngày Thứ {wd_pick}!")
                st.rerun()

    st.write("---")
    st.subheader(f"Lưới tích chọn tiết bận: {selected_teacher_name}")
    st.caption("☑️ **Tích chọn ô** = Giáo viên bận (KHÔNG xếp tiết). ☐ **Bỏ tích** = Giáo viên rảnh (CÓ THỂ xếp tiết).")

    # Build DataFrame for 10 periods (S1..S5, C1..C5)
    grid_rows = []
    for sess, sess_label in [("S", "Sáng"), ("C", "Chiều")]:
        for p in range(1, 6):
            row_data = {
                "Buổi": sess_label,
                "Tiết": f"Tiết {p}",
            }
            for wd in range(2, 8):
                col_name = f"Thứ {wd}"
                row_data[col_name] = (wd, sess, p) in busy_cells
            grid_rows.append(row_data)

    df_grid = pd.DataFrame(grid_rows)

    column_config = {
        "Buổi": st.column_config.TextColumn("Buổi", disabled=True, width="small"),
        "Tiết": st.column_config.TextColumn("Tiết", disabled=True, width="small"),
    }
    for wd in range(2, 8):
        column_config[f"Thứ {wd}"] = st.column_config.CheckboxColumn(
            f"Thứ {wd}",
            help=f"Tích để cấm xếp tiết vào Thứ {wd}",
            default=False,
        )

    edited_grid = st.data_editor(
        df_grid,
        hide_index=True,
        use_container_width=True,
        key=f"editor_gvban_grid_{sel_tid}",
        column_config=column_config,
    )

    btn_col1, btn_col2 = st.columns([2, 4])
    with btn_col1:
        if st.button("💾 Lưu tiết bận cho giáo viên này", type="primary", use_container_width=True):
            new_busy_cells = set()
            for _, r in edited_grid.iterrows():
                sess_code = "S" if r["Buổi"] == "Sáng" else "C"
                p_code = int(str(r["Tiết"]).replace("Tiết ", "").strip())
                for wd in range(2, 8):
                    if bool(r.get(f"Thứ {wd}")):
                        new_busy_cells.add((wd, sess_code, p_code))
            repo.set_teacher_busy_cells(conn, sel_tid, new_busy_cells)
            st.success(f"✅ Đã lưu {len(new_busy_cells)} tiết bận cho giáo viên **{selected_teacher_name}**!")
            st.rerun()

# ---------------------------------------------------------------------------
# TAB 2: School Overview Grid
# ---------------------------------------------------------------------------
with tab_overview:
    st.subheader("Tổng hợp lịch bận của tất cả giáo viên")
    st.caption("Quan sát tổng quan ai bận vào những buổi/tiết nào trong tuần.")

    overview_rows = []
    total_busy_count = 0
    teachers_with_bans = 0

    for t in teachers:
        t_busy = repo.get_teacher_busy_cells(conn, t.teacher_id)
        if t_busy:
            teachers_with_bans += 1
            total_busy_count += len(t_busy)

        row_item = {
            "Giáo viên": t.name,
            "Chức vụ": t.role if t.role else "GV",
            "Tổng tiết bận": len(t_busy),
        }
        for wd in range(2, 8):
            s_busy = [str(p) for (w, s, p) in t_busy if w == wd and s == "S"]
            c_busy = [str(p) for (w, s, p) in t_busy if w == wd and s == "C"]
            parts = []
            if s_busy:
                parts.append("S:" + ",".join(sorted(s_busy)))
            if c_busy:
                parts.append("C:" + ",".join(sorted(c_busy)))
            row_item[f"Thứ {wd}"] = " | ".join(parts) if parts else "—"
        overview_rows.append(row_item)

    col_m1, col_m2 = st.columns(2)
    col_m1.metric("Số GV có tiết bận", f"{teachers_with_bans} / {len(teachers)}")
    col_m2.metric("Tổng số lượt tiết bận", total_busy_count)

    df_overview = pd.DataFrame(overview_rows)
    st.dataframe(df_overview, hide_index=True, use_container_width=True)

# ---------------------------------------------------------------------------
# TAB 3: Raw Rule List Editor
# ---------------------------------------------------------------------------
with tab_list:
    st.subheader("Bảng danh sách quy tắc chi tiết (Dạng thô)")
    st.caption("Chỉnh sửa hoặc thêm các quy tắc tổng quát có ký tự đại diện `*` (ví dụ `*` cả tuần, `*` cả buổi).")

    rows = repo.list_unavailability(conn)
    df_raw = pd.DataFrame([{
        "Giáo viên": name_by_id.get(r["teacher_id"], ""),
        "Thứ": r["weekday"],
        "Buổi": r["session"],
        "Tiết": r["period"],
    } for r in rows])
    if df_raw.empty:
        df_raw = pd.DataFrame(columns=["Giáo viên", "Thứ", "Buổi", "Tiết"])

    edited_raw = st.data_editor(
        df_raw,
        num_rows="dynamic",
        hide_index=True,
        key="editor_gvban_raw_list",
        use_container_width=True,
        column_config={
            "Giáo viên": st.column_config.SelectboxColumn(options=list(id_by_name)),
            "Thứ": st.column_config.SelectboxColumn(options=["*", "2", "3", "4", "5", "6", "7", "CN"]),
            "Buổi": st.column_config.SelectboxColumn(options=["*", "S", "C"]),
            "Tiết": st.column_config.SelectboxColumn(options=["*", "1", "2", "3", "4", "5"]),
        },
    )

    if st.button("💾 Lưu bảng quy tắc chi tiết", type="primary"):
        repo.clear_unavailability(conn)
        saved_count = 0
        for _, row in edited_raw.iterrows():
            name = str(row["Giáo viên"] or "").strip()
            tid = id_by_name.get(name)
            if not tid:
                continue
            repo.add_unavailability(
                conn, tid,
                str(row["Thứ"] or "*"), str(row["Buổi"] or "*"), str(row["Tiết"] or "*"),
            )
            saved_count += 1
        st.success(f"Đã lưu {saved_count} quy tắc GV bận.")
        st.rerun()

sidebar_backup_export(conn)
sidebar_school_switcher()
