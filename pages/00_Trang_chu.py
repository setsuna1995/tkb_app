import pandas as pd
import streamlit as st

from core import frame as frame_mod
from core import setup_status
from data import repository as repo
from ui_common import get_conn, require_auth, require_school, sidebar_backup_export, sidebar_fixed_rules, \
    sidebar_school_switcher

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

st.subheader("Tiến độ thiết lập")

assignments = repo.get_assignments(conn)
ppw = repo.get_periods_per_week(conn)

class_totals = {}
class_quota_by_parity = {}
for c in classes:
    m, a, ss, allow_sat, short_wd, short_m, short_a = repo.get_frame_template(conn, c.class_id)
    class_totals[c.class_id] = frame_mod.total_cells_per_class(
        m, a, bool(ss), bool(allow_sat), short_wd, short_m, short_a,
    )
    class_quota_by_parity[c.class_id] = {
        par: sum(v for (_s, cid, p), v in ppw.items() if cid == c.class_id and p == par)
        for par in ("C", "L")
    }

num_teachers_with_busy = sum(1 for t in teachers if repo.get_teacher_busy_cells(conn, t.teacher_id))

setup_steps = [
    ("Khai báo", setup_status.check_khai_bao(len(classes), len(subjects), len(teachers)), "01_Khai_bao"),
    ("Phân công", setup_status.check_phan_cong(ppw, assignments), "02_PhanCong"),
    ("Định mức", setup_status.check_dinh_muc(repo.get_teacher_quota_view(conn, parity)), "03_DinhMuc"),
    ("Khung tiết", setup_status.check_khung_tiet(class_totals, class_quota_by_parity), "05_Khung_tiet"),
    ("GV bận", setup_status.check_gv_ban(len(teachers), num_teachers_with_busy), "04_GV_Ban"),
]
status_df = pd.DataFrame([
    {"Bước": label, "Trạng thái": "✅" if status.ok else "⚠️", "Ghi chú": status.detail}
    for label, status, _page in setup_steps
])
st.dataframe(status_df, hide_index=True, use_container_width=True)

link_cols = st.columns(len(setup_steps))
for col, (label, _status, page) in zip(link_cols, setup_steps):
    col.page_link(f"pages/{page}.py", label=f"→ {label}")

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
sidebar_fixed_rules()
sidebar_school_switcher()
