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
st.subheader("Xuất kết quả ra Excel")
latest_run = repo.get_latest_run(conn)
run_id = latest_run["run_id"] if latest_run and latest_run["succeeded"] else None
if run_id:
    st.caption(f"Xuất theo lần xếp gần nhất đã chấp nhận (run #{run_id}).")
else:
    st.caption("Chưa có lần xếp nào được chấp nhận — xuất theo lịch hiện tại (TKB_Nhap).")

try:
    data = export_xlsx(conn, run_id=run_id)
    if st.download_button(
        "📤 Xuất file .xlsx", data=data, file_name="TKB_xuat.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ):
        repo.set_meta(conn, "last_exported_at", datetime.now().strftime("%d/%m/%Y %H:%M"))
        st.success("Đã xuất file.")
except Exception as e:
    st.error(f"Không thể xuất: {e}")

sidebar_backup_export(conn)
sidebar_school_switcher()
