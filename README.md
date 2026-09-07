# Xếp Thời Khóa Biểu — Trường THCS & THPT (2026–2027)

Ứng dụng web (Streamlit) xếp thời khóa biểu tự động thông minh cho trường học, sử dụng động cơ giải tối ưu hóa toàn cục **Google OR-Tools CP-SAT**. Giao diện được nâng cấp toàn diện theo chuẩn **UI/UX Pro Max (Modern Academic Dashboard)** với font chữ Plus Jakarta Sans, hệ thống thẻ card bento sang trọng và trực quan.

Ứng dụng đáp ứng 100% các quy chế hoạt động sư phạm trường học Việt Nam, tích hợp sẵn toàn bộ dữ liệu mẫu chuẩn năm học **2026–2027**, cung cấp thang đo **Đánh giá Sức khỏe TKB (100 điểm)** và hỗ trợ xuất/nhập Excel đa năng.

---

## 🌟 Tính năng nổi bật

- **Giao diện Modern Academic Dashboard (Chuẩn UI/UX Pro Max)**:
  - Bảng màu xanh nhận diện thương hiệu `Trust Blue (#2563EB)`, nền sáng dịu mắt `Slate-50 (#F8FAFC)` chống lóa khi làm việc ban ngày.
  - Phông chữ cao cấp **Plus Jakarta Sans** hiển thị tiếng Việt sắc nét.
  - Thẻ KPI bento cards trực quan, tabs phong cách pill capsule hiện đại, viền mờ bo tròn thanh lịch.
  - **Không rào cản**: Đã loại bỏ màn hình mật khẩu đăng nhập, truy cập thẳng vào trường học mặc định ngay khi khởi động.
- **Xuất Excel TKB trực tiếp theo tuần**:
  - Tích hợp trực tiếp công cụ tải Excel tại trang trọng tâm **`06_Xep_TKB.py`** — chọn tuần (1–35) và tải ngay TKB Toàn trường, TKB theo Lớp, hoặc TKB theo Giáo viên mà không cần chuyển trang.
- **Động cơ giải CP-SAT thông minh**:
  - Tối ưu hóa toàn cục hàng nghìn biến số đồng thời trong 15–35 giây.
  - Hai pha giải: **Pass 1** (Chẩn đoán tính khả thi) và **Pass 2** (Tối ưu hóa đa mục tiêu với Early Stopping).
- **Tuân thủ tuyệt đối quy chế HĐSP**:
  - **Sáng bắt buộc (II.3)**: 100% giáo viên cơ hữu (tải $\ge 8$ tiết/tuần) có mặt dạy vào **sáng Thứ 2** (Chào cờ/SHDC) và **sáng Thứ 6** (Sinh hoạt tổng kết tuần).
  - **Không lẻ tiết (II.4)**: Tuyệt đối tránh giáo viên đi dạy đúng 1 tiết/buổi hoặc 1 tiết/ngày.
  - **Không ngày chia lẻ (II.8)**: Chặn tình trạng giáo viên dạy 1 tiết sáng + 1 tiết chiều trong cùng một ngày.
  - **Môn kép & Môn nặng**: Ghép đôi liền kề cho tiết kép (Ngữ văn, KHTN...); môn nặng (Toán, Lý, Hóa, Ngoại ngữ) tối đa 3 tiết/buổi.
  - **Khung thể dục & Chuyên đề**: Thể dục tự động tránh tiết 5 sáng và tiết 1 chiều; hỗ trợ tuần chuyên đề dồn tiết HDTN toàn trường.
- **Dữ liệu chuẩn tích hợp sẵn**:
  - Nạp sẵn toàn bộ dữ liệu thực tế **Trường THCS (2026–2027)**: 8 lớp (Khối 6, 7, 8, 9), 16 môn, 17 giáo viên, 236 tiết học/tuần và khung định lượng 35 tuần cả năm học.

---

## 🚀 Hướng dẫn chạy ứng dụng ở máy Local

### 1. Cài đặt thư viện

Mở PowerShell tại thư mục dự án (`c:\Users\kiennt9\tkb_app`):

```powershell
pip install -r requirements.txt
```

*(Khuyến khích tạo môi trường ảo Python trước khi cài đặt: `python -m venv .venv` và kích hoạt bằng `.\.venv\Scripts\Activate.ps1`)*

### 2. Khởi chạy ứng dụng

Chạy một trong các lệnh sau trên terminal PowerShell:

```powershell
python -m streamlit run app.py
```

hoặc (nếu đã kích hoạt môi trường ảo `.venv` hoặc streamlit đã nằm trong PATH):

```powershell
streamlit run app.py
```

> 💡 **Mẹo:** Trình duyệt web sẽ tự động mở trang web tại địa chỉ: **`http://localhost:8501`**. Ứng dụng sẽ vào thẳng màn hình làm việc mà không yêu cầu nhập mật khẩu.

---

## ☁️ Triển khai lên Streamlit Community Cloud (Miễn phí)

1. **Đẩy mã nguồn lên GitHub**:
   - Repository chứa sẵn cơ sở dữ liệu mẫu (`schools/truong-thcs.db` và `data/sample_truong_thcs.db`).
2. **Tạo App trên Streamlit Cloud**:
   - Truy cập [share.streamlit.io](https://share.streamlit.io) $\to$ Chọn **New app**.
   - Chọn Repository, Branch `main`, và Main file path là `app.py`.
3. **Bấm Deploy**:
   - Ứng dụng sẽ tự động khởi tạo trên môi trường Cloud với giao diện UI/UX Pro Max đồng bộ.

---

## 📊 Cấu trúc dữ liệu & Quản lý trường học

- **Hỗ trợ đa trường (Multi-tenant)**: Mỗi trường học là một file SQLite độc lập trong thư mục `schools/<mã-trường>.db`.
- **Trường mẫu mặc định**: `Trường THCS (2026-2027)` (`schools/truong-thcs.db`) được nạp tự động khi khởi động.
- **Đổi trường hoặc Tạo trường mới**: Có thể chuyển đổi bất cứ lúc nào qua nút **🏫 Đổi trường** ở thanh bên (Sidebar).
- **Sao lưu & Phục hồi**:
  - Nút **📥 Xuất Excel (sao lưu)** ở thanh bên hỗ trợ tải trọn vẹn toàn bộ dữ liệu cấu hình, giáo viên, định mức và thời khóa biểu ra file `.xlsx`.
  - Quản lý nạp định lượng 35 tuần và nhập file cấu hình tại trang **09. Quản Lý Dữ Liệu & Sao Lưu**.

---

## 🧪 Chạy kiểm thử tự động (Test Suite)

Dự án có bộ test toàn diện gồm **326 test cases** bao phủ toàn bộ thuật toán, ràng buộc sư phạm, động cơ CP-SAT, giao diện `ui_theme`, `ui_common` và xuất/nhập Excel:

```powershell
pip install -r requirements-dev.txt
pytest -v
```

---

## 📁 Cấu trúc thư mục chính

```
tkb_app/
├── app.py                      # Điểm khởi động chính, cấu hình menu điều hướng st.navigation
├── ui_theme.py                 # Module Design System: Google Font Plus Jakarta Sans, CSS Tokens & Helpers
├── ui_common.py                # Quản lý kết nối DB đa trường, theme bootstrap, thanh bên Sidebar
├── .streamlit/
│   └── config.toml             # Cấu hình theme màu Modern Academic Dashboard
├── pages/                      # 11 trang chức năng của ứng dụng:
│   ├── 00_Trang_chu.py         # Dashboard điều hành, KPI cards, tiến độ chuẩn bị dữ liệu
│   ├── 01_Khai_bao.py          # Khai báo Lớp, Môn học, Giáo viên (3 tabs bento)
│   ├── 02_PhanCong.py          # Phân công chuyên môn (Ma trận môn x lớp)
│   ├── 03_DinhMuc.py           # Định mức số tiết theo 35 tuần năm học & định mức GV
│   ├── 04_GV_Ban.py            # Khai báo giờ bận của giáo viên (Lưới 10 tiết/ngày)
│   ├── 05_Khung_tiet.py        # Cấu hình khung tiết theo lớp
│   ├── 06_Xep_TKB.py           # Lõi xếp TKB tự động Google CP-SAT & Xuất Excel TKB trực tiếp theo tuần
│   ├── 08_Lich_su_Tuan.py      # Quản lý lịch sử và tuần học (Chẵn/Lẻ), tái lập bằng Seed
│   ├── 09_Import_Export.py     # Quản lý dữ liệu, nạp định lượng 35 tuần & sao lưu hệ thống
│   ├── 10_Cau_hinh_Xep_lich.py # Cấu hình 18 tiêu chí chuyên môn và tham số CP-SAT
│   └── 11_Huong_Dan.py         # Cẩm nang hướng dẫn sử dụng 5 bước chi tiết
├── core/                       # Động cơ cốt lõi (Core Engine):
│   ├── scheduler/              # Bộ giải Google OR-Tools CP-SAT: mô hình, hàm mục tiêu, chẩn đoán
│   ├── validation.py           # Bộ thẩm định 18 tiêu chí sư phạm & Bảng điểm Sức khỏe TKB
│   ├── frame.py                # Xử lý khung thời gian học tập
│   └── models.py               # Data models và hằng số sư phạm
├── data/                       # Quản trị cơ sở dữ liệu SQLite & Repository
│   ├── sample_truong_thcs.db   # Bản sao dữ liệu mẫu chuẩn năm học 2026-2027
│   └── repository.py           # Các hàm CRUD dữ liệu trường học
├── io_excel/                   # Bộ đọc và xuất biểu mẫu Excel chuẩn Bộ GD&ĐT
├── schools/                    # Thư mục lưu trữ CSDL các trường học (.db)
│   └── truong-thcs.db          # Dữ liệu chính thức Trường THCS (2026-2027)
└── tests/                      # Bộ kiểm thử tự động (326 test cases đạt 100% pass)
```
