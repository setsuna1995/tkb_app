import pandas as pd
import streamlit as st

from data import repository as repo
from ui_common import get_conn, require_auth, require_school, sidebar_backup_export, sidebar_school_switcher

require_auth()
school_slug = require_school()
conn = get_conn(school_slug)
st.title("Định mức tiết/tuần & Định mức giáo viên")

classes = repo.list_classes(conn)
subjects = repo.list_subjects(conn)

if not classes or not subjects:
    st.info("Chưa có lớp/môn. Vào trang Khai báo hoặc Nhập/Xuất Excel trước.")
    st.stop()

tab_sotiet, tab_gv = st.tabs(["Số tiết/tuần (SoTiet)", "Định mức giáo viên (DinhMuc_GV)"])

with tab_sotiet:
    parity_label = st.radio("Tuần", ["Chẵn", "Lẻ"], horizontal=True, key="sotiet_parity")
    parity = "C" if parity_label == "Chẵn" else "L"
    ppw = repo.get_periods_per_week(conn)
    data = {"Môn": [s.name for s in subjects]}
    for c in classes:
        data[c.name] = [ppw.get((s.subject_id, c.class_id, parity), 0) for s in subjects]
    df = pd.DataFrame(data)
    edited = st.data_editor(df, hide_index=True, key=f"editor_sotiet_{parity}", disabled=["Môn"],
                             use_container_width=True)
    if st.button("Lưu số tiết", key=f"save_sotiet_{parity}"):
        for i, s in enumerate(subjects):
            for c in classes:
                val = int(edited.loc[i, c.name] or 0)
                repo.set_periods_per_week(conn, s.subject_id, c.class_id, parity, val)
        st.success("Đã lưu số tiết.")
        st.rerun()
    totals = {c.name: sum(int(edited.loc[i, c.name] or 0) for i in range(len(subjects))) for c in classes}
    st.caption("Tổng tiết/lớp: " + ", ".join(f"{name}={total}" for name, total in totals.items()))

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
    with st.expander("⚙️ Trần chuẩn & Sàn tối thiểu", expanded=False):
        c1, c2, c3 = st.columns([1, 1, 1])
        new_base_cap = c1.number_input("Trần chuẩn (tiết/tuần)", 1, 30, repo.get_base_cap(conn))
        new_min_floor = c2.number_input("Sàn tối thiểu (tiết/tuần)", 0, 30, repo.get_min_floor(conn))
        c3.write("")
        if c3.button("Lưu trần / sàn"):
            repo.set_base_cap(conn, int(new_base_cap))
            repo.set_min_floor(conn, int(new_min_floor))
            st.success("Đã lưu.")
            st.rerun()

    teachers = repo.list_teachers(conn)
    if not teachers:
        st.info("Chưa có giáo viên.")
    else:
        _, cur_parity = repo.get_tuan_config(conn)
        base_cap = repo.get_base_cap(conn)
        min_floor = repo.get_min_floor(conn)
        view = repo.get_teacher_quota_view(conn, cur_parity)
        gv_df = pd.DataFrame(view)[["name", "role", "reduction", "cap", "load", "load_avg", "over", "under"]]
        gv_df.columns = ["Giáo viên", "Chức vụ", "Giảm trừ", "Trần", "Tải (tuần " +
                          ("Chẵn" if cur_parity == "C" else "Lẻ") + ")", "Tải TB 2 tuần", "Vượt", "Dưới sàn"]

        def highlight_row(row):
            over, under = row.iloc[-2], row.iloc[-1]
            if over > 0:
                return ["background-color: #ffc7ce" for _ in row]
            if under > 0:
                return ["background-color: #ffe0b2" for _ in row]
            return ["" for _ in row]

        st.dataframe(gv_df.style.apply(highlight_row, axis=1), hide_index=True, use_container_width=True)
        st.caption(
            f"Trần = {base_cap} − Giảm trừ (theo chức vụ). Tải = tổng tiết đã phân công (PhanCong × SoTiet) "
            "của đúng tuần đang xem. Vượt trần / Dưới sàn được xét theo TRUNG BÌNH tải 2 tuần Chẵn và Lẻ "
            "(cột \"Tải TB 2 tuần\") — một GV lệch tải giữa 2 tuần nhưng trung bình đã đúng định mức thì "
            f"không bị cảnh báo. Sàn tối thiểu: (Tải TB + Giảm trừ) phải ≥ {min_floor} — \"Dưới sàn\" > 0 là "
            "thiếu bấy nhiêu tiết (tô cam), chỉ cảnh báo, không chặn thao tác."
        )

    with st.expander("Bảng giảm trừ theo chức vụ"):
        rr = repo.get_role_reduction(conn)
        rr_df = pd.DataFrame([{"Chức vụ": k, "Giảm trừ": v} for k, v in rr.items()])
        rr_edited = st.data_editor(rr_df, hide_index=True, num_rows="dynamic", key="editor_role_reduction")
        if st.button("Lưu giảm trừ"):
            for _, row in rr_edited.iterrows():
                name = str(row["Chức vụ"] or "").strip()
                if name:
                    repo.set_role_reduction(conn, name, int(row["Giảm trừ"] or 0))
            st.success("Đã lưu.")
            st.rerun()

sidebar_backup_export(conn)
sidebar_school_switcher()
