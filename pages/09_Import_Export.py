import os
import tempfile
from datetime import datetime

import streamlit as st

from data import repository as repo
from io_excel.exporter import export_xlsx, export_xlsx_both_parities
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
    except Exception as e:
        st.error(f"Lỗi khi nhập: {e}")
    finally:
        os.remove(tmp_path)

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

st.divider()
st.subheader("Xuất cả 2 tuần (Chẵn + Lẻ)")
st.caption("Gộp lần chấp nhận gần nhất của mỗi tuần vào 1 file .xlsx (8 sheet, hậu tố _Chan/_Le).")
try:
    data_both, both_warnings = export_xlsx_both_parities(conn)
except ValueError as e:
    st.info(str(e))
else:
    for w in both_warnings:
        st.warning(w)
    if st.download_button(
        "📤 Xuất cả 2 tuần (.xlsx)", data=data_both, file_name="TKB_ca_2_tuan.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="export_both",
    ):
        repo.set_meta(conn, "last_exported_at", datetime.now().strftime("%d/%m/%Y %H:%M"))
        st.success("Đã xuất file.")

sidebar_backup_export(conn)
sidebar_school_switcher()
