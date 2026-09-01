import pandas as pd
import streamlit as st

from data import repository as repo
from ui_common import get_conn, require_auth, require_school, sidebar_backup_export, sidebar_fixed_rules, \
    sidebar_school_switcher

require_auth()
school_slug = require_school()
conn = get_conn(school_slug)
st.title("Định mức tiết/tuần & Định mức giáo viên")

classes = repo.list_classes(conn)
subjects = repo.list_subjects(conn)

if not classes or not subjects:
    st.info("Chưa có lớp/môn. Vào trang Khai báo hoặc Nhập/Xuất Excel trước.")
    st.stop()

tab_sotiet, tab_gv = st.tabs(["📊 Số tiết/tuần (SoTiet)", "👩‍🏫 Định mức giáo viên (DinhMuc_GV)"])

with tab_sotiet:
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
        column_config=col_config, use_container_width=True,
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
        _, cur_parity = repo.get_tuan_config(conn)
        base_cap = repo.get_base_cap(conn)
        min_floor = repo.get_min_floor(conn)
        view = repo.get_teacher_quota_view(conn, cur_parity)

        gv_rows = []
        for v in view:
            gv_rows.append({
                "teacher_id": v["teacher_id"],
                "Giáo viên": v["name"],
                "Chức vụ / Kiêm nhiệm": v["role"] or "",
                "Giảm trừ (tiết)": int(v["reduction"]),
                "Trần định mức": int(v["cap"]),
                "Tải tuần " + ("Chẵn" if cur_parity == "C" else "Lẻ"): int(v["load"]),
                "Tải TB 2 tuần": round(float(v["load_avg"]), 1),
                "Vượt trần": round(float(v["over"]), 1),
                "Dưới sàn": round(float(v["under"]), 1),
            })
        gv_df = pd.DataFrame(gv_rows)

        st.markdown("**Bảng phân bổ định mức & giảm trừ theo từng Giáo viên**")
        st.caption(
            "Bạn có thể **chỉnh sửa trực tiếp** cột *Chức vụ / Kiêm nhiệm* và *Giảm trừ (tiết)* cho từng GV, "
            "sau đó bấm nút **💾 Lưu định mức & giảm trừ GV** phía dưới."
        )

        gv_editor_config = {
            "teacher_id": None,  # hidden
            "Giáo viên": st.column_config.TextColumn(disabled=True),
            "Chức vụ / Kiêm nhiệm": st.column_config.TextColumn(
                help="Ghi chú chức vụ hoặc kiêm nhiệm (ví dụ: GVCN, Tổ trưởng, Thư ký HĐ (2) + QL KHTN (1), TPT (4) + QL CLB (1)...)"
            ),
            "Giảm trừ (tiết)": st.column_config.NumberColumn(
                min_value=0, max_value=30, step=1, format="%d",
                help="Tổng số tiết giảm trừ trực tiếp của GV (Trần định mức = Trần chuẩn − Giảm trừ)"
            ),
            "Trần định mức": st.column_config.NumberColumn(disabled=True, format="%d"),
            "Tải tuần " + ("Chẵn" if cur_parity == "C" else "Lẻ"): st.column_config.NumberColumn(disabled=True, format="%d"),
            "Tải TB 2 tuần": st.column_config.NumberColumn(disabled=True, format="%.1f"),
            "Vượt trần": st.column_config.NumberColumn(disabled=True, format="%.1f"),
            "Dưới sàn": st.column_config.NumberColumn(disabled=True, format="%.1f"),
        }

        edited_gv = st.data_editor(
            gv_df, hide_index=True, key="editor_teacher_quotas",
            column_config=gv_editor_config, use_container_width=True,
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
            f"Trần định mức = {base_cap} − Giảm trừ. Tải = tổng tiết đã phân công (PhanCong × SoTiet). "
            "Vượt trần / Dưới sàn được xét theo TRUNG BÌNH tải 2 tuần Chẵn và Lẻ. "
            f"Sàn tối thiểu: (Tải TB + Giảm trừ) phải ≥ {min_floor}."
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

