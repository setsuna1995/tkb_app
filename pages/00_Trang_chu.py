import pandas as pd
import streamlit as st

from core import frame as frame_mod
from core import setup_status
from data import repository as repo
from ui_common import (
    get_conn,
    require_auth,
    require_school,
    sidebar_backup_export,
    sidebar_fixed_rules,
    sidebar_school_switcher,
)
from ui_theme import (
    render_callout,
    render_kpi_row,
    render_page_header,
    render_status_badge,
)

require_auth()
school_slug = require_school()
conn = get_conn(school_slug)

seed, parity = repo.get_tuan_config(conn)
classes = repo.list_classes(conn)
subjects = repo.list_subjects(conn)
teachers = repo.list_teachers(conn)
config = repo.get_scheduling_config(conn)
saved_weeks = repo.list_saved_weeks(conn)
current_week = saved_weeks[0] if saved_weeks else 1

render_page_header(
    title="Trung Tâm Điều Hành Thời Khóa Biểu",
    subtitle="Hệ thống xếp lịch tự động & kiểm soát 18 tiêu chí chuyên môn THCS / THPT",
    badge=f"Tuần {current_week}",
    icon="🏫",
)

assignments = repo.get_assignments(conn)
ppw = repo.get_periods_per_week(conn)

class_totals = {}
class_quota_by_parity = {}
for c in classes:
    m, a, ss, allow_sat, short_wd, short_m, short_a = repo.get_frame_template(conn, c.class_id)
    class_totals[c.class_id] = frame_mod.total_cells_per_class(
        m, a, bool(ss), bool(allow_sat), short_wd, short_m, short_a,
        reserved_off_weekdays_chieu=config.reserved_off_weekdays_chieu,
    )
    class_quota_by_parity[c.class_id] = {
        par: sum(v for (_s, cid, p), v in ppw.items() if cid == c.class_id and p == par)
        for par in ("C", "L")
    }

num_teachers_with_busy = sum(1 for t in teachers if repo.get_teacher_busy_cells(conn, t.teacher_id))

render_kpi_row([
    {"title": "Số lớp học", "value": len(classes), "subtitle": "Đã thiết lập khung tiết", "icon": "👥", "variant": "primary"},
    {"title": "Số môn học", "value": len(subjects), "subtitle": "Phân loại chuyên môn", "icon": "📚", "variant": "info"},
    {"title": "Số giáo viên", "value": len(teachers), "subtitle": f"{num_teachers_with_busy} GV báo bận", "icon": "👨‍🏫", "variant": "warning"},
    {"title": "Tuần xếp lịch", "value": f"Tuần {current_week}", "subtitle": f"Seed: {seed}", "icon": "🗓️", "variant": "success"},
])

st.markdown("### 📋 Tiến độ chuẩn bị dữ liệu")

setup_steps = [
    ("Khai báo", setup_status.check_khai_bao(len(classes), len(subjects), len(teachers)), "01_Khai_bao"),
    ("Phân công", setup_status.check_phan_cong(ppw, assignments), "02_PhanCong"),
    ("Định mức", setup_status.check_dinh_muc(repo.get_teacher_quota_view(conn, week_no=current_week)), "03_DinhMuc"),
    ("Khung tiết", setup_status.check_khung_tiet(class_totals, class_quota_by_parity), "05_Khung_tiet"),
    ("GV bận", setup_status.check_gv_ban(len(teachers), num_teachers_with_busy), "04_GV_Ban"),
]

status_df = pd.DataFrame([
    {"Bước": label, "Trạng thái": "✅ Đạt chuẩn" if status.ok else "⚠️ Cần chú ý", "Ghi chú": status.detail}
    for label, status, _page in setup_steps
])
st.dataframe(status_df, hide_index=True, use_container_width=True)

link_cols = st.columns(len(setup_steps))
for col, (label, _status, page) in zip(link_cols, setup_steps):
    col.page_link(f"pages/{page}.py", label=f"Đi đến {label} →", use_container_width=True)

if len(classes) == 0:
    render_callout(
        "Chưa có dữ liệu trường học. Vào trang **Nhập / Xuất Excel** để nhập file .xlsm mẫu, "
        "hoặc vào trang **Khai báo** để nhập dữ liệu Lớp / Môn / Giáo viên từ đầu.",
        level="info",
        title="Dữ liệu ban đầu",
    )

st.markdown("### 🕘 Thời khóa biểu gần nhất")
latest_run = repo.get_latest_run(conn)
if latest_run:
    render_callout(
        f"Lần xếp gần nhất vào lúc **{latest_run['created_at']}** (Tuần {latest_run.get('week_no') or '1'}, "
        f"Seed = {latest_run['seed']}, tổng cộng **{latest_run['cells_total']}** ô tiết học đã được phân bổ thành công).",
        level="success",
        title="Trạng thái Thời khóa biểu",
    )
else:
    render_callout(
        "Chưa có lượt xếp thời khóa biểu nào. Hãy vào trang **Xếp TKB tự động** để bắt đầu xếp lịch.",
        level="info",
        title="Chưa có dữ liệu TKB",
    )

if teachers:
    quota_view = repo.get_teacher_quota_view(conn, week_no=current_week)
    over = [q for q in quota_view if q["cap"] > 0 and q["over"] > 0]
    under = [q for q in quota_view if q["under"] > 0]
    if over:
        render_callout(
            "Phát hiện giáo viên vượt trần định mức (> trần chuẩn): "
            + ", ".join(f"**{q['name']}** (+{round(q['over'], 1):g}t)" for q in over),
            level="warning",
            title="Cảnh báo định mức vượt trần",
        )
    if under:
        min_floor = repo.get_min_floor(conn)
        render_callout(
            f"Phát hiện giáo viên dưới sàn định mức tối thiểu (< sàn chuẩn {min_floor}t): "
            + ", ".join(f"**{q['name']}** (thiếu {round(q['under'], 1):g}t)" for q in under),
            level="warning",
            title="Cảnh báo định mức thiếu sàn",
        )

sidebar_backup_export(conn)
sidebar_fixed_rules(conn)
sidebar_school_switcher()
