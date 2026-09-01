import pandas as pd
import streamlit as st

from core import load_balance
from data import repository as repo
from ui_common import get_conn, require_auth, require_school, sidebar_backup_export, sidebar_school_switcher

require_auth()
school_slug = require_school()
conn = get_conn(school_slug)
base_cap = repo.get_base_cap(conn)
min_floor = repo.get_min_floor(conn)
floor_margin = base_cap - min_floor

st.title("⚖️ Cân bằng tải giáo viên (đề xuất)")
st.info(
    "💡 **Nguyên tắc đồng bộ trọn gói theo Lớp**: Phân công giảng dạy được tính toán và điều chỉnh "
    "theo từng **Lớp cho Môn học đó**, chuyển đồng thời toàn bộ số tiết cả tuần Chẵn và tuần Lẻ sang "
    "giáo viên mới. Tuyệt đối không chia cắt lẻ số tiết trong cùng một lớp để giữ vững tính toàn vẹn của TKB.\n\n"
    "Hệ thống hỗ trợ cả **Chuyển 1 lớp nguyên vẹn** và **Hoán đổi chéo 2 lớp cùng môn** giữa 2 GV khi chênh lệch tải nhỏ (1-2 tiết). "
    "Bạn có thể chọn đề xuất và bấm **Áp dụng vào Phân công** để tự động cập nhật ngay lập tức vào cơ sở dữ liệu."
)

teachers = repo.list_teachers(conn)
if not teachers:
    st.info("Chưa có giáo viên. Vào trang Khai báo trước.")
    st.stop()

classes = repo.list_classes(conn)
subjects = repo.list_subjects(conn)
if not classes or not subjects:
    st.info("Chưa có danh mục Lớp hoặc Môn học. Vào trang Khai báo trước.")
    st.stop()

_, parity = repo.get_tuan_config(conn)
assignments = repo.get_assignments(conn)
periods_per_week = repo.get_periods_per_week(conn)
caps = repo.get_teacher_caps(conn)
reductions = repo.get_role_reduction(conn)

name_by_id = {t.teacher_id: t.name for t in teachers}
subj_name_by_id = {s.subject_id: s.name for s in subjects}
class_name_by_id = {c.class_id: c.name for c in classes}

allow_swap = st.toggle("Cho phép đề xuất Hoán đổi chéo 2 lớp (Class Swap)", value=True,
                       help="Khi độ chênh lệch tải nhỏ (1-2 tiết), hệ thống sẽ tìm phương án đổi chéo 2 lớp cùng môn giữa 2 GV để cân bằng hoàn hảo.")

# Tính tải giáo viên hiện tại
load_c = load_balance.compute_teacher_loads(assignments, periods_per_week, "C")
load_l = load_balance.compute_teacher_loads(assignments, periods_per_week, "L")
teacher_classes: dict[int, list[str]] = {}
for (s_id, c_id), t_id in assignments.items():
    if t_id is not None:
        c_p = periods_per_week.get((s_id, c_id, "C"), 0)
        l_p = periods_per_week.get((s_id, c_id, "L"), 0)
        avg_p = (c_p + l_p) / 2
        p_str = f"{avg_p:g}t" if c_p == l_p else f"C{c_p}/L{l_p}t"
        teacher_classes.setdefault(t_id, []).append(f"{class_name_by_id.get(c_id, '')} ({subj_name_by_id.get(s_id, '')}: {p_str})")

# Tính đề xuất
suggestions, unresolved_over, unresolved_under = load_balance.suggest_rebalance(
    assignments, periods_per_week, parity, caps, floor_margin=floor_margin, allow_swap=allow_swap
)

# 1. Bảng Tổng Hợp Tải Giáo Viên
with st.expander("📊 Bảng Tổng Hợp Tải Giáo Viên Hiện Tại", expanded=True):
    summary_rows = []
    for t in teachers:
        tid = t.teacher_id
        lc = load_c.get(tid, 0)
        ll = load_l.get(tid, 0)
        lavg = (lc + ll) / 2
        reduction = t.reduction_override if t.reduction_override is not None else reductions.get(t.role, 0)
        cap = caps.get(tid, base_cap)
        floor = cap - floor_margin if cap else 0

        if cap and lavg > cap:
            status = f"🔴 Vượt trần (+{lavg - cap:g}t)"
        elif cap and lavg < floor:
            status = f"🟡 Dưới sàn (-{floor - lavg:g}t)"
        else:
            status = "🟢 Cân bằng"

        summary_rows.append({
            "Mã": tid,
            "Giáo viên": t.name,
            "Chức vụ": t.role or "Giáo viên",
            "Giảm trừ": reduction,
            "Trần (Cap)": cap,
            "Sàn (Floor)": floor,
            "Tuần C": lc,
            "Tuần L": ll,
            "Trung bình": lavg,
            "Trạng thái": status,
            "Lớp phụ trách": ", ".join(teacher_classes.get(tid, [])) or "(chưa có)",
        })

    df_summary = pd.DataFrame(summary_rows)
    st.dataframe(df_summary, hide_index=True, use_container_width=True)

# 2. Bảng Đề Xuất Phân Công
if not suggestions and not unresolved_over and not unresolved_under:
    st.success("🎉 Tất cả giáo viên đều nằm trong khung định mức (từ sàn đến trần) — tải đã hoàn toàn cân bằng!")
else:
    if suggestions:
        st.subheader("💡 Danh Sách Đề Xuất Điều Chỉnh Phân Công Lớp")
        st.caption("Chọn các phương án muốn áp dụng vào bảng Phân công, sau đó bấm nút **Áp dụng** bên dưới.")

        sug_display_data = []
        for idx, s in enumerate(suggestions):
            over_name = name_by_id.get(s.over_teacher_id, f"GV #{s.over_teacher_id}")
            to_name = name_by_id.get(s.to_teacher_id, f"GV #{s.to_teacher_id}")
            s_name = subj_name_by_id.get(s.subject_id, f"Môn #{s.subject_id}")
            c_name = class_name_by_id.get(s.class_id, f"Lớp #{s.class_id}")
            class_info = f"{s_name} - {c_name} (C: {s.periods_c}t, L: {s.periods_l}t → TB {s.periods:g}t)"

            if s.action_type == "swap":
                swap_s_name = subj_name_by_id.get(s.swap_subject_id, f"Môn #{s.swap_subject_id}")
                swap_c_name = class_name_by_id.get(s.swap_class_id, f"Lớp #{s.swap_class_id}")
                swap_info = f"{swap_s_name} - {swap_c_name} (C: {s.swap_periods_c}t, L: {s.swap_periods_l}t → TB {s.swap_periods:g}t)"
                action_label = "🔁 Đổi chéo 2 lớp"
            else:
                swap_info = "—"
                action_label = "➡️ Chuyển 1 lớp"

            reason_label = "🔴 Giảm quá tải" if s.reason == "vuot_tran" else "🟡 Bù thiếu tải"

            from_cap = caps.get(s.over_teacher_id, base_cap)
            to_cap = caps.get(s.to_teacher_id, base_cap)

            from_load_old = s.from_teacher_new_load + (s.periods if s.action_type == "transfer" else (s.periods - s.swap_periods))
            from_load_info = f"{over_name} ({from_load_old:g}t → {s.from_teacher_new_load:g}t / Trần {from_cap})"
            to_load_info = f"{to_name} ({s.to_teacher_load:g}t → {s.to_teacher_new_load:g}t / Trần {to_cap})"

            sug_display_data.append({
                "Áp dụng": True,
                "Hình thức": action_label,
                "Mục đích": reason_label,
                "Lớp chuyển đi": class_info,
                "GV chuyển đi (Tải cũ → mới)": from_load_info,
                "GV nhận (Tải cũ → mới)": to_load_info,
                "Lớp hoán đổi (nếu có)": swap_info,
                "_sug_index": idx,
            })

        df_sug = pd.DataFrame(sug_display_data)
        edited_sug = st.data_editor(
            df_sug,
            hide_index=True,
            column_config={
                "Áp dụng": st.column_config.CheckboxColumn("Áp dụng", default=True),
                "_sug_index": None,
            },
            disabled=["Hình thức", "Mục đích", "Lớp chuyển đi", "GV chuyển đi (Tải cũ → mới)", "GV nhận (Tải cũ → mới)", "Lớp hoán đổi (nếu có)"],
            use_container_width=True,
            key="editor_suggestions",
        )

        col_btn1, col_btn2, _ = st.columns([3, 3, 4])
        with col_btn1:
            if st.button("⚡ Áp dụng các đề xuất đã chọn", type="primary", use_container_width=True):
                selected_indices = [
                    int(row["_sug_index"])
                    for _, row in edited_sug.iterrows()
                    if row["Áp dụng"]
                ]
                if not selected_indices:
                    st.warning("Bạn chưa chọn đề xuất nào.")
                else:
                    applied_count = 0
                    for idx in selected_indices:
                        s = suggestions[idx]
                        if s.action_type == "transfer":
                            repo.set_assignment(conn, s.subject_id, s.class_id, s.to_teacher_id)
                            applied_count += 1
                        elif s.action_type == "swap":
                            repo.set_assignment(conn, s.subject_id, s.class_id, s.to_teacher_id)
                            if s.swap_subject_id is not None and s.swap_class_id is not None:
                                repo.set_assignment(conn, s.swap_subject_id, s.swap_class_id, s.over_teacher_id)
                            applied_count += 1
                    st.success(f"✅ Đã áp dụng thành công {applied_count} điều chỉnh vào cơ sở dữ liệu Phân công!")
                    st.rerun()

        with col_btn2:
            if st.button("⚡ Áp dụng TẤT CẢ đề xuất", use_container_width=True):
                applied_count = 0
                for s in suggestions:
                    if s.action_type == "transfer":
                        repo.set_assignment(conn, s.subject_id, s.class_id, s.to_teacher_id)
                        applied_count += 1
                    elif s.action_type == "swap":
                        repo.set_assignment(conn, s.subject_id, s.class_id, s.to_teacher_id)
                        if s.swap_subject_id is not None and s.swap_class_id is not None:
                            repo.set_assignment(conn, s.swap_subject_id, s.swap_class_id, s.over_teacher_id)
                        applied_count += 1
                st.success(f"✅ Đã áp dụng toàn bộ {applied_count} điều chỉnh vào cơ sở dữ liệu Phân công!")
                st.rerun()

    if unresolved_over:
        st.warning(
            "⚠️ **Chưa tìm được phương án nhận lớp phù hợp cho giáo viên vượt trần:**\n"
            + "\n".join(
                f"- **{name_by_id.get(u.over_teacher_id, '')}**: còn vượt trần {u.remaining_over:g} tiết (các GV cùng bộ môn không còn đủ dư địa nhận thêm lớp)."
                for u in unresolved_over
            )
        )
    if unresolved_under:
        st.warning(
            "⚠️ **Chưa tìm được phương án nhượng lớp phù hợp để bù cho giáo viên dưới sàn:**\n"
            + "\n".join(
                f"- **{name_by_id.get(u.under_teacher_id, '')}**: còn thiếu {u.remaining_under:g} tiết để đạt sàn tối thiểu (các GV khác cùng bộ môn nếu nhượng lớp sẽ bị tụt dưới sàn của chính họ)."
                for u in unresolved_under
            )
        )

sidebar_backup_export(conn)
sidebar_school_switcher()
