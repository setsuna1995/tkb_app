import streamlit as st

st.set_page_config(page_title="Xếp Thời Khóa Biểu", layout="wide")

# st.navigation phải được gọi vô điều kiện ở MỌI lần chạy (kể cả khi chưa đăng
# nhập) để Streamlit dùng đúng cấu trúc menu 2 cấp này thay vì rơi về chế độ tự
# dò trang cũ (phẳng, không dấu). Xác thực (require_auth/require_school) nằm
# bên trong từng trang con, giống như trước đây.
pages = {
    "Tổng quan": [
        st.Page("pages/00_Trang_chu.py", title="Trang chủ", icon="🏠", default=True),
    ],
    "Thiết lập dữ liệu": [
        st.Page("pages/01_Khai_bao.py", title="Khai báo Lớp / Môn / Giáo viên", icon="🏫"),
        st.Page("pages/02_PhanCong.py", title="Phân công chuyên môn", icon="📋"),
        st.Page("pages/03_DinhMuc.py", title="Định mức tiết / tuần", icon="📊"),
        st.Page("pages/04_GV_Ban.py", title="Giáo viên bận", icon="🚫"),
        st.Page("pages/05_Khung_tiet.py", title="Khung tiết", icon="🗓️"),
    ],
    "Xếp & sửa thời khóa biểu": [
        st.Page("pages/06_Xep_TKB.py", title="Xếp TKB tự động", icon="🚀"),
        st.Page("pages/07_Can_Bang_Tai.py", title="Cân bằng tải giáo viên", icon="⚖️"),
        st.Page("pages/08_Lich_su_Tuan.py", title="Lịch sử tuần", icon="🕘"),
    ],
    "Dữ liệu": [
        st.Page("pages/09_Import_Export.py", title="Nhập / Xuất Excel", icon="📁"),
    ],
}

st.navigation(pages).run()
