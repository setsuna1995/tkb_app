import os
import tempfile
from datetime import datetime

import streamlit as st

from data import repository as repo
from io_excel.exporter import export_full_backup_xlsx, export_xlsx
from io_excel.importer import import_xlsm
from ui_common import (
    get_conn,
    require_auth,
    require_school,
    sidebar_backup_export,
    sidebar_fixed_rules,
    sidebar_school_switcher,
)
from ui_theme import render_callout, render_page_header

require_auth()
school_slug = require_school()
conn = get_conn(school_slug)

render_page_header(
    title="Quản Lý Dữ Liệu & Sao Lưu Hệ Thống",
    subtitle="Nhập danh mục thiết lập ban đầu (Lớp, Môn, Phân công, Định lượng) & xuất file sao lưu cơ sở dữ liệu",
    badge="Quản trị dữ liệu",
    icon="📁",
)

render_callout(
    "Bạn đang tìm nơi tải Thời khóa biểu theo tuần? "
    "Tính năng **Xuất Excel Thời khóa biểu chính thức** (cho toàn trường, từng lớp và giáo viên) "
    "hiện đã được tích hợp trực tiếp ngay tại trang **Xếp TKB tự động** (tab 'Xuất Excel & Xem Lại TKB Các Tuần') "
    "để tiện theo dõi và tải ngay sau khi xếp lịch.",
    level="info",
    title="💡 Gợi ý xuất Thời khóa biểu",
)

tab_import, tab_backup = st.tabs([
    "📥 Nhập dữ liệu ban đầu",
    "💾 Sao lưu hệ thống & Dữ liệu nháp",
])

with tab_import:
    st.markdown("### 1. Nhập từ file .xlsm chuẩn mẫu trường học")
    st.caption(
        "Đọc đồng bộ các sheet PhanCong, SoTiet, DinhMuc_GV, GV_Bận, TKB_Nhap, Khung, TuanConfig từ file Excel "
        "và ghi đè vào cơ sở dữ liệu của app."
    )
    c_f1, c_f2 = st.columns([3, 1])
    with c_f1:
        uploaded = st.file_uploader("Chọn file .xlsm / .xlsx cấu hình mẫu", type=["xlsm", "xlsx"], key="upload_main_xlsm")
    with c_f2:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        btn_import_main = st.button("🚀 Bắt đầu nạp dữ liệu", type="primary", disabled=uploaded is None, key="btn_import_main")

    if uploaded is not None and btn_import_main:
        fd, tmp_path = tempfile.mkstemp(suffix=".xlsm")
        os.close(fd)
        try:
            with open(tmp_path, "wb") as f:
                f.write(uploaded.getvalue())
            report = import_xlsm(conn, tmp_path)
            st.success(
                f"✅ Đã nạp thành công: {report.counts['classes']} lớp, {report.counts['subjects']} môn, "
                f"{report.counts['teachers']} giáo viên, {report.counts['tkb_nhap_cells']} ô TKB nháp, "
                f"{report.counts['unavailability_rows']} dòng GV bận, "
                f"{report.counts['seed_history_rows']} dòng lịch sử tuần."
            )
            if report.warnings:
                for w in report.warnings:
                    render_callout(w, level="warning", title="Cảnh báo nhập dữ liệu")
        except Exception as e:
            st.error(f"Lỗi khi xử lý file: {e}")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    st.markdown("---")
    st.markdown("### 2. Nạp định lượng số tiết 35 tuần năm học")
    st.caption(
        "Nhập file định lượng số tiết chi tiết theo tuần (gồm các sheet K6, K7, K8, K9 cho cả Học kỳ I và Học kỳ II)."
    )
    c_w1, c_w2 = st.columns([1, 1])
    default_excel_file = "Định lượng số tiết theo tuần năm học 2026_2027.xlsx"
    has_default_file = os.path.exists(default_excel_file)
    with c_w1:
        if st.button("🚀 Nạp tự động từ file mẫu chuẩn (2026-2027)", disabled=not has_default_file, type="primary"):
            from io_excel.weekly_importer import import_weekly_curriculum_from_excel
            with st.spinner("Đang nạp dữ liệu..."):
                try:
                    rep = import_weekly_curriculum_from_excel(conn, default_excel_file)
                    st.success(
                        f"✅ Đã nạp thành công {rep['records_imported']} dòng định mức cho {rep['weeks_count']} tuần "
                        f"({', '.join(rep['classes_updated'])})."
                    )
                except Exception as e:
                    st.error(f"Lỗi: {e}")

    with c_w2:
        uploaded_weekly = st.file_uploader("Hoặc tải file định lượng .xlsx khác", type=["xlsx", "xlsm"], key="upload_weekly_curriculum")
        if uploaded_weekly is not None and st.button("Nạp file định lượng tải lên"):
            from io_excel.weekly_importer import import_weekly_curriculum_from_excel
            with st.spinner("Đang nạp file..."):
                try:
                    rep = import_weekly_curriculum_from_excel(conn, uploaded_weekly.getvalue())
                    st.success(f"✅ Đã nạp thành công {rep['records_imported']} dòng định mức cho {rep['weeks_count']} tuần.")
                except Exception as e:
                    st.error(f"Lỗi: {e}")

with tab_backup:
    st.markdown("### 1. Xuất file Sao lưu Toàn Diện Hệ Thống")
    st.caption(
        "File sao lưu ghi lại đầy đủ: Lớp, Môn, Giáo viên, Phân công chuyên môn, Định mức tiết 35 tuần, "
        "Giáo viên bận, Khung tiết và kết quả xếp lịch. Bạn nên tải file sao lưu này định kỳ để lưu trữ an toàn."
    )
    try:
        backup_data = export_full_backup_xlsx(conn)
        st.download_button(
            "💾 Tải file Sao lưu Toàn trường (.xlsx)",
            data=backup_data,
            file_name=f"TKB_Sao_Luu_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            key="btn_download_full_backup",
        )
    except Exception as e:
        st.error(f"Không thể tạo file sao lưu: {e}")

    st.markdown("---")
    st.markdown("### 2. Xuất dữ liệu bảng TKB Nháp hiện thời")
    st.caption("Xuất các ô dữ liệu hiện đang lưu trong bảng nháp (TKB_Nhap) để đối chiếu tạm thời.")
    try:
        data_nhap = export_xlsx(conn, run_id=None)
        st.download_button(
            "📤 Tải bảng TKB Nháp hiện thời (.xlsx)",
            data=data_nhap,
            file_name="TKB_Nhap_hien_tai.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="btn_export_nhap",
        )
    except Exception as e:
        st.error(f"Lỗi xuất TKB Nháp: {e}")

sidebar_backup_export(conn)
sidebar_fixed_rules(conn)
sidebar_school_switcher()
