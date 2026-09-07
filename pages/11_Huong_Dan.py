import streamlit as st

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
    title="Cẩm Nang Hướng Dẫn Sử Dụng",
    subtitle="Quy trình làm việc, tiêu chuẩn nghiệp vụ sư phạm và cẩm nang xử lý bài toán xếp lịch",
    badge="Tài liệu chuẩn",
    icon="📖",
)

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🗺️ Quy trình làm việc",
    "📋 Chuẩn bị dữ liệu",
    "⚙️ Cấu hình xếp lịch",
    "🚀 Xếp TKB & Xuất Excel",
    "💡 Xử lý sự cố thường gặp",
])

with tab1:
    st.markdown("### 🗺️ Trình tự 5 bước chuẩn bị & xếp thời khóa biểu")
    render_callout(
        "Thứ tự dưới đây được thiết kế theo đúng quy chuẩn nghiệp vụ: Khai báo đầy đủ danh mục, "
        "gán phân công và định mức trước, sau đó cấu hình các quy tắc ràng buộc của trường, rồi mới tiến hành chạy xếp TKB tự động.",
        level="info",
        title="Nguyên tắc cốt lõi",
    )
    st.markdown(
        """
        1. **Bước 1: Khai báo Lớp / Môn / Giáo viên** — Nhập danh mục lớp học, danh mục môn học (phân loại vai trò Nặng, Kép, GDTC, HDTN), và danh sách giáo viên.
        2. **Bước 2: Phân công chuyên môn** — Phân công từng cặp (Môn, Lớp) cho giáo viên giảng dạy cụ thể.
        3. **Bước 3: Định mức tiết / tuần** — Thiết lập số tiết/tuần cho từng môn học theo 35 tuần năm học và định mức chuẩn theo chức vụ.
        4. **Bước 4: Giáo viên bận & Khung tiết** — Khai báo các buổi/tiết giáo viên bận việc riêng và cấu hình số tiết sáng/chiều của từng lớp.
        5. **Bước 5: Cấu hình quy tắc & Xếp TKB** — Tùy chỉnh các ràng buộc sư phạm đặc thù của trường, chạy thuật toán OR-Tools CP-SAT và xuất kết quả Excel.
        """
    )

with tab2:
    st.markdown("### 📋 Chi tiết các bước chuẩn bị dữ liệu")
    
    with st.expander("🏫 1. Khai báo Lớp / Môn / Giáo viên", expanded=True):
        st.markdown(
            "**Tab Lớp học** — Quản lý danh sách lớp và thứ tự hiển thị trên bảng thời khóa biểu.\n\n"
            "**Tab Môn học** — Quản lý vai trò chuyên môn quyết định thuật toán xử lý:\n"
            "- **Thường**: Môn không có ràng buộc khối tiết đặc thù.\n"
            "- **Nặng** (Toán, Lý, Hóa...): Giới hạn số tiết liên tiếp trong buổi, ưu tiên tiết đầu buổi sáng.\n"
            "- **Kép** (Văn, Toán...): Ràng buộc CỨNG buộc phải ghép 2 tiết liền kề cùng buổi.\n"
            "- **Nặng+Kép**: Vừa là môn nặng, vừa phải ghép cặp 2 tiết liền nhau.\n"
            "- **GDTC**: Môn Giáo dục thể chất, tự động tránh tiết 5 sáng và tiết 1 chiều.\n"
            "- **HDTN**: Hoạt động trải nghiệm (Chào cờ đầu tuần và Sinh hoạt lớp cuối tuần).\n\n"
            "**Tab Giáo viên** — Khai báo chức vụ, quy định số buổi nghỉ/tuần riêng, và ghim ngày nghỉ cố định."
        )

    with st.expander("📋 2. Phân công chuyên môn"):
        st.markdown(
            "Gán mỗi cặp (Môn, Lớp) cho một giáo viên phụ trách. Bạn có thể chọn giáo viên có sẵn "
            "hoặc gõ tên giáo viên mới trực tiếp trên bảng phân công để hệ thống tự động khởi tạo."
        )

    with st.expander("📊 3. Định mức tiết / tuần"):
        st.markdown(
            "Nhập số tiết giảng dạy từng môn cho từng tuần trong **35 tuần năm học** (Học kỳ I: 1–18, Học kỳ II: 19–35). "
            "Hệ thống tự động tính toán tổng tải, đối chiếu với khung sàn chuẩn (16 tiết) và trần chuẩn (19 tiết) "
            "kết hợp các mức giảm trừ giờ dạy theo chức danh."
        )

    with st.expander("🚫 4. Giáo viên bận & Khung tiết"):
        st.markdown(
            "**Giáo viên bận**: Tích chọn trên lưới lịch 10 tiết/ngày (Sáng/Chiều x Tiết 1-5) để cấm xếp tiết khi giáo viên bận việc khác. "
            "Đây là ràng buộc CỨNG mà thuật toán tuyệt đối không bao giờ vi phạm.\n\n"
            "**Khung tiết**: Quy định số tiết học sáng và chiều của từng lớp, tự động đối soát tổng số ô học khả dụng."
        )

with tab3:
    st.markdown("### ⚙️ Các quy tắc cấu hình xếp lịch của trường")
    st.markdown(
        """
        Trang **Cấu hình xếp lịch** cho phép hiệu chỉnh các quy tắc quản lý riêng của từng trường:
        - **Khung tiết GDTC (Thể dục)**: Mặc định xếp vào Tiết 1-4 sáng và Tiết 2-3 chiều; cấm xếp 2 ngày liên tiếp.
        - **Chào cờ**: Mặc định xếp Tiết 1 sáng Thứ 2 (có thể đổi sang thứ khác).
        - **Giới hạn môn nặng**: Khống chế tối đa số tiết môn nặng liên tiếp trong một buổi.
        - **Buổi nghỉ giáo viên**: Mặc định số buổi nghỉ/tuần (thường là 1-2 buổi), cấm nghỉ vào các buổi họp hội đồng.
        - **Tránh tiết lủng**: Tối ưu không để giáo viên bị trống tiết giữa buổi.
        - **Tránh dạy 1 tiết lẻ**: Hạn chế giáo viên đến trường chỉ để dạy đúng 1 tiết/ngày.
        - **Buổi sáng bắt buộc**: Toàn thể giáo viên có mặt vào các buổi sáng quy định (Thứ 2, Thứ 5, Thứ 6).
        """
    )

with tab4:
    st.markdown("### 🚀 Xếp Thời khóa biểu tự động & Xuất Excel")
    st.markdown(
        """
        - **Chọn tuần xếp lịch**: Chọn tuần cụ thể từ 1 đến 35 để nạp đúng định mức của tuần đó.
        - **Chuyên đề HDTN**: Tùy chọn dồn 3 tiết HDTN thành 1 khối tập trung cho toàn trường khi tổ chức sự kiện.
        - **Bộ giải Google OR-Tools CP-SAT**:
          - **Pass 1**: Chẩn đoán tính khả thi (Pure Feasibility) và phát hiện các xung đột toán học.
          - **Pass 2**: Tối ưu hóa đa mục tiêu với cơ chế Early Stopping để tìm phương án có điểm chất lượng tốt nhất.
        - **Xuất Excel TKB trực tiếp**: Bạn có thể tải ngay file Excel TKB Toàn trường, TKB theo Lớp, hoặc TKB theo Giáo viên "
          ngay tại trang **Xếp TKB tự động** mà không cần chuyển qua trang khác.
        """
    )

with tab5:
    st.markdown("### 💡 Xử lý sự cố khi hệ thống báo \"Không thể xếp lịch\"")
    render_callout(
        "Khi bộ giải CP-SAT báo không tìm thấy phương án (Infeasible), nguyên nhân luôn xuất phát từ "
        "các ràng buộc cứng mâu thuẫn lẫn nhau trong dữ liệu đầu vào. Hãy rà soát theo danh sách dưới đây:",
        level="warning",
        title="Hướng dẫn chẩn đoán",
    )
    st.markdown(
        """
        1. **Trùng GVCN (HDTN)**: Một giáo viên làm chủ nhiệm 2 lớp khác nhau. Do tiết Chào cờ và Sinh hoạt lớp diễn ra đồng thời, GV không thể có mặt ở cả 2 phòng.
        2. **Giáo viên báo bận quá dày**: Giáo viên có số tiết dạy lớn nhưng lại báo bận hầu hết các buổi trống trong tuần.
        3. **Khung tiết không đủ chỗ**: Tổng số tiết cần học của một lớp vượt quá tổng số tiết khả dụng trong tuần.
        4. **Ghim nghỉ quá chặt**: Giáo viên vừa có số buổi nghỉ cao, vừa ghim ngày nghỉ cố định, dẫn tới không đủ buổi để xếp các môn Kép hoặc môn nhiều tiết.
        5. **Ép môn nặng học 100% buổi sáng**: Khi bật ràng buộc này mà số tiết môn nặng của trường quá lớn, buổi sáng sẽ bị nghẽn phòng/tiết.
        """
    )

sidebar_backup_export(conn)
sidebar_fixed_rules(conn)
sidebar_school_switcher()
