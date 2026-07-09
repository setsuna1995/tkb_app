import streamlit as st

from data import repository as repo
from ui_common import get_conn, require_auth, require_school, sidebar_backup_export, sidebar_school_switcher

require_auth()
school_slug = require_school()
conn = get_conn(school_slug)

st.title("Xếp Thời Khóa Biểu")

seed, parity = repo.get_tuan_config(conn)
classes = repo.list_classes(conn)
subjects = repo.list_subjects(conn)
teachers = repo.list_teachers(conn)
latest_run = repo.get_latest_run(conn)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Số lớp", len(classes))
col2.metric("Số môn", len(subjects))
col3.metric("Số giáo viên", len(teachers))
col4.metric("Tuần hiện tại", "Chẵn" if parity == "C" else "Lẻ")

if len(classes) == 0:
    st.info(
        "Chưa có dữ liệu. Vào trang **Nhập / Xuất Excel** để nhập từ file .xlsm hiện có, "
        "hoặc trang **Khai báo** để nhập tay từ đầu."
    )

if latest_run:
    st.subheader("Lần xếp gần nhất")
    status = "✅ Thành công" if latest_run["succeeded"] else "❌ Thất bại"
    st.write(
        f"{status} — Tuần {latest_run['week_no']}, seed {latest_run['seed']}, "
        f"thay đổi {latest_run['cells_changed']}/{latest_run['cells_total']} ô "
        f"— lúc {latest_run['created_at']}"
    )
else:
    st.info("Chưa có lần xếp thời khóa biểu nào.")

if teachers:
    quota_view = repo.get_teacher_quota_view(conn, parity)
    over = [q for q in quota_view if q["cap"] > 0 and q["over"] > 0]
    under = [q for q in quota_view if q["under"] > 0]
    if over:
        st.warning(
            "Có giáo viên vượt định mức: "
            + ", ".join(f"{q['name']} (+{q['over']})" for q in over)
        )
    if under:
        min_floor = repo.get_min_floor(conn)
        st.warning(
            f"Có giáo viên dưới sàn tối thiểu (Tải TB 2 tuần + Giảm trừ ≥ {min_floor}): "
            + ", ".join(f"{q['name']} (thiếu {q['under']})" for q in under)
        )

st.markdown(
    """
Dùng thanh điều hướng bên trái để:
1. **Thiết lập dữ liệu** — khai báo lớp / môn / giáo viên, phân công, định mức, GV bận, khung tiết
2. **Xếp & sửa thời khóa biểu** — chạy xếp tự động, sửa tay, cân bằng tải, xem lịch sử tuần
3. **Dữ liệu** — nhập / xuất Excel

**Sắp có**: tra cứu TKB theo từng giáo viên, phân công dạy thay khi GV nghỉ đột xuất
(xem `reports/tkb-app-review-2026-07-09.md` — mục #12, #13).
"""
)

sidebar_backup_export(conn)
sidebar_school_switcher()
