# Thiết Kế Lại Giao Diện Streamlit — Chuẩn UI/UX Pro Max

- **Dự án**: `tkb_app` (Hệ thống Xếp Thời Khóa Biểu Tự Động THCS/THPT)
- **Ngày**: 2026-09-07
- **Tác giả**: Antigravity & User
- **Tiêu chuẩn áp dụng**: `ui-ux-pro-max` (Modern Clean SaaS / Academic Dashboard)

---

## 1. Mục Tiêu & Bối Cảnh (Goals & Context)

Hệ thống `tkb_app` hiện sử dụng giao diện mặc định của Streamlit với các widget thô sơ, chưa có hệ thống màu nhận diện thương hiệu, font chữ chưa tối ưu cho tiếng Việt, và thiếu sự phân cấp thị giác (visual hierarchy) giữa các khối chức năng.

Mục tiêu của đợt tái thiết kế này:
1. **Trải nghiệm người dùng cao cấp (Modern Academic Dashboard)**: Mang lại diện mạo chuyên nghiệp, tinh tế, thoáng đãng với gam màu xanh học thuật (`#2563EB`), nền sáng chống mỏi mắt (`#F8FAFC`), và font chữ **Plus Jakarta Sans**.
2. **Loại bỏ rào cản đăng nhập**: Gỡ bỏ hoàn toàn màn hình mật khẩu đăng nhập (`require_auth`), cho phép người dùng vào thẳng ứng dụng và tự động tải dữ liệu trường mặc định.
3. **Tối ưu hóa luồng thao tác (Workflow Optimization)**: Tích hợp trực tiếp công cụ **Xuất Excel Thời Khóa Biểu theo tuần** ngay tại trang trung tâm `06_Xep_TKB.py`. Tách biệt trang `09_Import_Export.py` làm khu vực chuyên quản lý sao lưu toàn hệ thống và nhập/xuất dữ liệu thiết lập.
4. **Bảo tồn 100% logic thuật toán**: Giữ nguyên vẹn động cơ tối ưu Google OR-Tools CP-SAT, bộ kiểm tra 18 tiêu chí (Validation), và toàn bộ các hàm lưu trữ SQLite.
5. **Nâng cấp đồng bộ 11 trang**: Thiết kế lại toàn bộ hệ thống trang theo kiến trúc thẻ card (Bento grid) và hệ thống token nhất quán.

---

## 2. Kiến Trúc Token & Giao Diện Dùng Chung (Design System Foundation)

### 2.1. Cấu hình Theme Gốc (`.streamlit/config.toml`)
```toml
[server]
headless = true

[theme]
base = "light"
primaryColor = "#2563EB"              # Xanh Trust Blue (Chủ đạo)
backgroundColor = "#F8FAFC"           # Slate-50: Nền tổng thể sáng dịu mắt
secondaryBackgroundColor = "#FFFFFF"  # Nền card, container & sidebar
textColor = "#0F172A"                 # Slate-900: Đảm bảo tương phản văn bản >= 7:1
font = "sans serif"
```

### 2.2. Module Quản lý Giao diện Tập trung (`ui_theme.py`)
Tạo mới file `ui_theme.py` cung cấp CSS biến (CSS Variables) và các hàm helper HTML/CSS. Module này được tự động kích hoạt thông qua `ui_common.py`.

#### CSS Tokens & Font
- **Google Font**: `Plus Jakarta Sans` (400, 500, 600, 700, 800) nhúng trực tiếp qua `@import`.
- **Màu sắc**:
  - Primary: `#2563EB` | Primary Hover: `#1D4ED8` | Primary Light: `#EFF6FF`
  - Secondary: `#3B82F6` | Accent: `#EA580C`
  - Success: `#10B981` | Success Light: `#ECFDF5`
  - Warning: `#F59E0B` | Warning Light: `#FFFBEB`
  - Danger: `#EF4444` | Danger Light: `#FEF2F2`
  - Surface: `#FFFFFF` | Border: `#E2E8F0` | Border Hover: `#CBD5E1`
  - Text Primary: `#0F172A` | Text Muted: `#64748B`
- **Hiệu ứng & Bo góc**:
  - Radius Card: `12px` | Radius Button: `8px` | Radius Badge: `9999px`
  - Shadow Card: `0 1px 3px 0 rgb(0 0 0 / 0.06), 0 1px 2px -1px rgb(0 0 0 / 0.04)`
  - Shadow Card Hover: `0 10px 15px -3px rgb(0 0 0 / 0.08), 0 4px 6px -4px rgb(0 0 0 / 0.03)`

#### CSS Overrides cho Widget Streamlit:
- **Sidebar**: Nền trắng sáng, viền phải mảnh `#E2E8F0`, header thương hiệu có icon trường học sắc nét, các mục menu phân cấp với khoảng cách chuẩn `8px`.
- **Tabs (`st.tabs`)**: Kiểu dáng pill capsule hiện đại với trạng thái active bo tròn nền xanh nhạt, chữ xanh đậm.
- **Buttons (`st.button`)**: Phân biệt rõ nút chính (Primary - xanh đậm nổi bật) và nút phụ (Secondary - viền mảnh sạch sẽ).
- **Dataframes (`st.dataframe`)**: Bo góc `10px`, viền mềm, dòng sọc xen kẽ nhẹ, tiêu đề cột nổi bật.
- **Expanders (`st.expander`)**: Nền thẻ trắng tinh, viền `#E2E8F0`, icon mũi tên mượt mà.

### 2.3. Bộ Helper Components Trực Quan Trong `ui_theme.py`
1. `render_page_header(title: str, subtitle: str = None, badge: str = None, icon: str = None)`
2. `render_kpi_card(title: str, value: Any, subtitle: str = "", icon: str = "", variant: str = "primary")`
3. `render_status_badge(label: str, status: str = "info") -> str`
4. `render_stepper_flow(steps: list[tuple[str, bool, str]])`
5. `render_card(title: str, content_html: str, badge: str = None)`
6. `render_callout(message: str, level: str = "info", title: str = None)`

---

## 3. Loại Bỏ Màn Hình Mật Khẩu & Xử Lý Xác Thực (`ui_common.py`)

- **Loại bỏ mật khẩu**: Cập nhật hàm `require_auth()` trong `ui_common.py` thành pass-through (không yêu cầu mật khẩu `app_password`, không dừng bằng `st.stop()`).
- **Tự động chọn trường**: Trong `require_school()`, nếu đã có danh sách trường (như `truong-thcs`), hệ thống tự động thiết lập trường mặc định và chuyển tiếp người dùng vào Dashboard ngay lập tức.
- Nút **"🏫 Đổi trường"** trên Sidebar được làm mới với giao diện dạng card tinh tế, cho phép quản trị viên đổi trường bất cứ khi nào cần.

---

## 4. Chi Tiết Thiết Kế Lại Toàn Bộ 11 Trang

### Nhóm 1: Tổng Quan (Dashboard)
1. **`pages/00_Trang_chu.py`**:
   - Header trường học hiện đại với thông tin học kỳ và tuần.
   - Hàng 4 KPI Cards: **Số Lớp**, **Số Môn**, **Số Giáo Viên**, **Tuần Đang Xếp**.
   - Bảng tiến độ thiết lập dữ liệu (5 bước) dạng bảng thẻ card có badge trạng thái xanh/cam và nút chuyển trang trực tiếp.
   - Thẻ tóm tắt **"Thời khóa biểu gần nhất"** hiển thị chi tiết thời gian tạo, seed và tổng số ô xếp.
   - Khối cảnh báo định mức GV (vượt trần / thiếu sàn) đóng khung chuyên nghiệp.
2. **`pages/11_Huong_Dan.py`**:
   - Bố cục dạng **Tabs hiện đại**: *Quy trình 5 bước*, *Các quy tắc cốt lõi (18 tiêu chí)*, *Mẹo xử lý bài toán khó*, *Hỏi đáp (FAQ)*.
   - Typography phân cấp rõ ràng, các bước có huy hiệu số thứ tự tròn, codeblock và mẹo có khung highlight riêng.

### Nhóm 2: Thiết Lập Dữ Liệu (Setup Flow)
3. **`pages/01_Khai_bao.py`**:
   - Chia 3 tabs lớn: Lớp, Môn, Giáo viên.
   - Form khai báo gọn gàng đặt trong thẻ Card bên cạnh bảng danh sách.
   - Đánh dấu rõ các thuộc tính môn nặng, tiết kép, môn GDTC/Chào cờ.
4. **`pages/02_PhanCong.py`**:
   - Bộ lọc tiện lợi theo Khối và Lớp.
   - Ma trận phân công hiển thị tổng số tiết/tuần rõ ràng trên tiêu đề cột.
5. **`pages/03_DinhMuc.py`**:
   - Bổ sung thanh tiến độ (% tải) cho từng giáo viên, đánh dấu màu trực quan: Xanh lá (chuẩn định mức), Vàng (sát trần hoặc thiếu nhẹ), Đỏ (vượt trần).
6. **`pages/04_GV_Ban.py`**:
   - Ma trận báo bận thiết kế theo dạng lưới lịch trực quan (Thứ 2 ➔ Thứ 7 x Tiết 1 ➔ Tiết 5), các ô bận có màu nổi bật, dễ quan sát bao quát toàn trường.
7. **`pages/05_Khung_tiet.py`**:
   - Bảng cấu hình khung tiết từng lớp với bảng tóm tắt tổng số tiết sáng/chiều và các nút gạt cấu hình Thứ 7.
8. **`pages/10_Cau_hinh_Xep_lich.py`**:
   - Phân cụm các tham số thành từng Card chủ đề: *Môn nặng*, *Thể dục & Chào cờ*, *Buổi nghỉ giáo viên*, *Tối ưu tránh tiết lủng/tiết lẻ*.

### Nhóm 3: Xếp & Sửa Thời Khóa Biểu
9. **`pages/06_Xep_TKB.py`** *(Trang trọng tâm)*:
   - **Bảng điều khiển (Control Console)**: Nút "🚀 Bắt đầu xếp TKB" kích thước lớn, hàng tham số thời gian giải và seed gọn gàng.
   - **Thanh trạng thái giải thuật (Solver Monitor)**: Hiển thị trực quan Pass 1 (Chẩn đoán khả thi) và Pass 2 (Tối ưu điểm phạt), biểu đồ thu hẹp điểm phạt khi tìm thấy nghiệm mới.
   - **Tính năng Xuất Excel TKB trực tiếp ngay tại trang**:
     - Khu vực **"📥 Xuất Thời Khóa Biểu"** chuyên dụng ngay bên cạnh ma trận TKB.
     - Cho phép chọn tuần cần xuất và chọn phạm vi: *TKB Toàn trường*, *TKB theo Lớp*, *TKB theo Giáo viên*.
     - Nút tải trực tiếp file `.xlsx` định dạng chuẩn Bộ GD&ĐT không cần chuyển trang.
   - **Ma trận TKB trực quan**: Đổ màu sắc nhận diện thông minh cho các môn học.
   - **Bảng thẩm định 18 tiêu chí (Validation Audit)**: Hiển thị dạng danh sách checklist có đếm số vi phạm, nhấn vào xem chi tiết từng dòng.
10. **`pages/08_Lich_su_Tuan.py`**:
    - Danh sách các tuần đã lưu dạng Timeline Cards, hiển thị rõ số tiết, ngày tạo và nút kích hoạt tuần.

### Nhóm 4: Dữ Liệu & Sao Lưu
11. **`pages/09_Import_Export.py`**:
    - Tái cấu trúc thành **"Quản lý Dữ liệu & Sao lưu Hệ thống"**:
      - Cột trái: Nhập file Excel/XLSM cấu hình mẫu (Lớp, Môn, GV, Phân công).
      - Cột phải: Xuất file sao lưu cơ sở dữ liệu và sao lưu toàn diện.
      - Banner chỉ dẫn: Nếu muốn xuất TKB đã xếp, có nút liên kết nhanh chuyển sang `06_Xep_TKB.py`.

---

## 5. Kế Hoạch Kiểm Tra & Đảm Bảo Tính Toàn Vẹn (Verification)

1. **Automated Tests**: Chạy toàn bộ test suite (`pytest`) đảm bảo 100% test case hiện hành (solver, validation, repositories) không bị ảnh hưởng.
2. **Visual Inspection**: Kiểm tra hiển thị của font `Plus Jakarta Sans`, các thẻ KPI card, bảng tiến độ và responsive trên trình duyệt.
3. **Workflow Check**:
   - Mở app -> Vào thẳng Trang chủ (không hỏi mật khẩu).
   - Vào `06_Xep_TKB.py` -> Chạy xếp TKB -> Xuất Excel TKB theo tuần ngay tại trang -> Kiểm tra file tải về.
   - Kiểm tra các trang Khai báo, Phân công, Định mức, Báo bận hoạt động bình thường.
