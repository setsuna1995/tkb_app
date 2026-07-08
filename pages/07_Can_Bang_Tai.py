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

st.title("Cân bằng tải giáo viên (đề xuất)")
st.caption(
    "Đây chỉ là đề xuất — công cụ KHÔNG tự sửa Phân công. Hãy tự sửa tay ở trang Phân công "
    "rồi quay lại đây để kiểm tra lại. Gợi ý dựa trên tải thiếu/thừa TRUNG BÌNH 2 tuần Chẵn/Lẻ "
    f"(vượt trần {base_cap}-giảm trừ, hoặc dưới sàn tối thiểu {min_floor}), ưu tiên phương án đổi "
    "ít GV nhất — một lượt chuyển có thể giải quyết đồng thời cả GV vượt trần lẫn GV dưới sàn."
)

teachers = repo.list_teachers(conn)
if not teachers:
    st.info("Chưa có giáo viên. Vào trang Khai báo trước.")
    st.stop()

_, parity = repo.get_tuan_config(conn)
assignments = repo.get_assignments(conn)
periods_per_week = repo.get_periods_per_week(conn)
caps = repo.get_teacher_caps(conn)
name_by_id = {t.teacher_id: t.name for t in teachers}
subj_name_by_id = {s.subject_id: s.name for s in repo.list_subjects(conn)}
class_name_by_id = {c.class_id: c.name for c in repo.list_classes(conn)}

suggestions, unresolved_over, unresolved_under = load_balance.suggest_rebalance(
    assignments, periods_per_week, parity, caps, floor_margin=floor_margin
)

if not suggestions and not unresolved_over and not unresolved_under:
    st.success("Không có GV nào vượt trần hay dưới sàn — tải đã cân bằng!")
else:
    if suggestions:
        st.subheader("Đề xuất chuyển tiết (chỉ đánh dấu gợi ý, không tự áp dụng)")
        rows = [{
            "Lý do": "Vượt trần" if s.reason == "vuot_tran" else "Bù dưới sàn",
            "GV chuyển đi": name_by_id.get(s.over_teacher_id, ""),
            "Vượt (nếu có)": s.over_amount,
            "Môn": subj_name_by_id.get(s.subject_id, ""),
            "Lớp": class_name_by_id.get(s.class_id, ""),
            "Số tiết": s.periods,
            "-> Chuyển sang GV": name_by_id.get(s.to_teacher_id, ""),
            "Tải GV nhận": s.to_teacher_load,
            "Trần GV nhận": s.to_teacher_cap,
        } for s in suggestions]

        def highlight_reason(row):
            color = "#ffe0b2" if row["Lý do"] == "Bù dưới sàn" else "#ffc7ce"
            return [f"background-color: {color}" for _ in row]

        st.dataframe(
            pd.DataFrame(rows).style.apply(highlight_reason, axis=1),
            hide_index=True, use_container_width=True,
        )
    if unresolved_over:
        st.warning(
            "Không tìm được GV nhận phù hợp cho GV vượt trần:\n"
            + "\n".join(
                f"- {name_by_id.get(u.over_teacher_id, '')}: còn vượt {u.remaining_over} tiết"
                for u in unresolved_over
            )
        )
    if unresolved_under:
        st.warning(
            "Không tìm được GV nhượng tiết phù hợp để bù cho GV dưới sàn:\n"
            + "\n".join(
                f"- {name_by_id.get(u.under_teacher_id, '')}: còn thiếu {u.remaining_under} tiết"
                for u in unresolved_under
            )
        )

sidebar_backup_export(conn)
sidebar_school_switcher()
