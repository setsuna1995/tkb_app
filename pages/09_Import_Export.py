import os
import tempfile
from datetime import datetime

import streamlit as st

from data import repository as repo
from io_excel.exporter import export_xlsx
from io_excel.importer import import_xlsm
from ui_common import get_conn, require_auth, require_school, sidebar_backup_export, sidebar_school_switcher

require_auth()
school_slug = require_school()
conn = get_conn(school_slug)
st.title("Nhập / Xuất Excel")

st.subheader("Nhập từ file .xlsm hiện có")
st.caption(
    "Đọc PhanCong, SoTiet, DinhMuc_GV, GV_Bận, TKB_Nhap, Khung, TuanConfig từ file Excel gốc "
    "và ghi vào cơ sở dữ liệu của app. Có thể chạy lại nhiều lần (sẽ cập nhật đè lên dữ liệu cũ)."
)
uploaded = st.file_uploader("Chọn file .xlsm / .xlsx", type=["xlsm", "xlsx"])
if uploaded is not None and st.button("Nhập dữ liệu"):
    fd, tmp_path = tempfile.mkstemp(suffix=".xlsm")
    os.close(fd)
    try:
        with open(tmp_path, "wb") as f:
            f.write(uploaded.getvalue())
        report = import_xlsm(conn, tmp_path)
        st.success(
            f"Đã nhập: {report.counts['classes']} lớp, {report.counts['subjects']} môn, "
            f"{report.counts['teachers']} giáo viên, {report.counts['tkb_nhap_cells']} ô TKB, "
            f"{report.counts['unavailability_rows']} dòng GV bận, "
            f"{report.counts['seed_history_rows']} dòng lịch sử tuần."
        )
        if report.warnings:
            st.warning("\n".join(report.warnings))
    finally:
        os.remove(tmp_path)

st.divider()
st.subheader("📥 Nhập Định lượng số tiết 35 tuần năm học")
st.caption(
    "Nhập trực tiếp file định lượng số tiết cả năm (như `Định lượng số tiết theo tuần năm học 2026_2027.xlsx`) "
    "gồm các sheet K6, K7, K8, K9 cho cả Học kỳ I và Học kỳ II."
)
c_w1, c_w2 = st.columns([1, 1])
default_excel_file = "Định lượng số tiết theo tuần năm học 2026_2027.xlsx"
has_default_file = os.path.exists(default_excel_file)
if c_w1.button("🚀 Nạp tự động từ file mẫu chuẩn 2026-2027", disabled=not has_default_file):
    from io_excel.weekly_importer import import_weekly_curriculum_from_excel
    with st.spinner("Đang nạp dữ liệu..."):
        try:
            rep = import_weekly_curriculum_from_excel(conn, default_excel_file)
            st.success(f"Đã nạp thành công {rep['records_imported']} dòng định mức cho {rep['weeks_count']} tuần ({', '.join(rep['classes_updated'])}).")
        except Exception as e:
            st.error(f"Lỗi: {e}")

uploaded_weekly = c_w2.file_uploader("Hoặc tải file định lượng .xlsx", type=["xlsx", "xlsm"], key="upload_weekly_curriculum")
if uploaded_weekly is not None and c_w2.button("Nạp file định lượng"):
    from io_excel.weekly_importer import import_weekly_curriculum_from_excel
    with st.spinner("Đang nạp file..."):
        try:
            rep = import_weekly_curriculum_from_excel(conn, uploaded_weekly.getvalue())
            st.success(f"Đã nạp thành công {rep['records_imported']} dòng định mức cho {rep['weeks_count']} tuần.")
        except Exception as e:
            st.error(f"Lỗi: {e}")

st.divider()
st.subheader("📤 Xuất kết quả ra Excel theo tuần")
st.caption(
    "Xuất thời khóa biểu chính thức của từng tuần theo đúng định lượng số tiết của tuần đó. "
    "File Excel tải về giữ nguyên mẫu biểu chuẩn của trường gồm 3 sheet: TKB_Mon, TKB (lớp) và TKB_GV."
)

saved_weeks = repo.list_saved_weeks(conn)

tab_export_week, tab_export_other = st.tabs([
    "📅 Xuất theo Tuần (1 - 35)",
    "📑 Xuất Bản Nháp / Gộp Chẵn Lẻ",
])

with tab_export_week:
    c_hk, c_w = st.columns([1, 2])
    hk_choice = c_hk.selectbox(
        "Lọc theo học kỳ:",
        ["Tất cả các tuần (1 - 35)", "Học kỳ I (Tuần 1 - 18)", "Học kỳ II (Tuần 19 - 35)"],
        key="exp_hk_pick",
    )
    if "Học kỳ I" in hk_choice:
        available_weeks = list(range(1, 19))
    elif "Học kỳ II" in hk_choice:
        available_weeks = list(range(19, 36))
    else:
        available_weeks = list(range(1, 36))

    default_idx = 0
    if saved_weeks:
        first_saved_in_range = next((i for i, w in enumerate(available_weeks) if w in saved_weeks), 0)
        default_idx = first_saved_in_range

    chosen_export_week = c_w.selectbox(
        "Chọn tuần muốn xuất Excel:",
        options=available_weeks,
        index=default_idx,
        format_func=lambda w: f"Tuần {w}{' — ✅ Đã lưu' if w in saved_weeks else ' (chưa có TKB)'}",
        key="exp_week_select",
    )

    run_for_week = repo.get_latest_run_by_week(conn, chosen_export_week)
    if run_for_week:
        st.success(
            f"✅ **Thời khóa biểu Tuần {chosen_export_week}** — "
            f"Đã lưu lúc: **{run_for_week['created_at']}** | "
            f"Seed: **{run_for_week['seed']}** | "
            f"Tổng số tiết đã xếp: **{run_for_week['cells_total']}**"
        )
        try:
            week_data = export_xlsx(conn, run_id=run_for_week["run_id"])
            st.download_button(
                f"📥 Tải file Excel Tuần {chosen_export_week} (.xlsx)",
                data=week_data,
                file_name=f"TKB_Tuan_{chosen_export_week}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"btn_export_week_{chosen_export_week}",
                type="primary",
            )
        except Exception as e:
            st.error(f"Không thể xuất file Excel Tuần {chosen_export_week}: {e}")
    else:
        st.warning(
            f"Tuần {chosen_export_week} chưa có thời khóa biểu chính thức được lưu trong cơ sở dữ liệu. "
            f"Vui lòng vào trang **Xếp TKB** để tạo và lưu thời khóa biểu cho tuần này trước."
        )
        if saved_weeks:
            st.caption(f"Các tuần đã có TKB chính thức: **{', '.join(f'Tuần {w}' for w in saved_weeks)}**")

with tab_export_other:
    st.markdown("##### 1. Xuất theo bản TKB Nháp hiện tại")
    st.caption("Xuất toàn bộ ô dữ liệu đang có trong bảng TKB_Nhap hiện thời.")
    try:
        data_nhap = export_xlsx(conn, run_id=None)
        st.download_button(
            "📤 Tải TKB Nháp hiện tại (.xlsx)",
            data=data_nhap,
            file_name="TKB_Nhap_hien_tai.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="btn_export_nhap",
        )
    except Exception as e:
        st.error(f"Lỗi xuất TKB Nháp: {e}")

    st.markdown("---")
    st.markdown("##### 2. Xuất gộp 2 tuần Chẵn & Lẻ (6 sheets)")
    st.caption("Gộp lần chấp nhận gần nhất của cả tuần Chẵn và tuần Lẻ vào 1 file Excel duy nhất gồm 6 sheet.")
    try:
        from io_excel.exporter import export_xlsx_both_parities
        data_both, warnings = export_xlsx_both_parities(conn)
        if warnings:
            for w in warnings:
                st.warning(w)
        st.download_button(
            "📤 Tải TKB Gộp Chẵn - Lẻ (.xlsx)",
            data=data_both,
            file_name="TKB_Chan_Le_Gop.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="btn_export_both_parities",
        )
    except Exception as e:
        st.caption(f"Xuất gộp chẵn lẻ: {e}")

sidebar_backup_export(conn)
sidebar_school_switcher()
