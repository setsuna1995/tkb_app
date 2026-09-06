# Xếp Thời Khóa Biểu — Trường THCS (2026–2027)

Ứng dụng web (Streamlit) xếp thời khóa biểu tự động thông minh cho trường THCS, sử dụng động cơ giải tối ưu hóa toàn cục **Google OR-Tools CP-SAT** kết hợp thuật toán Greedy & Swap-repair. Ứng dụng đáp ứng 100% các quy chế hoạt động sư phạm trường học Việt Nam, tích hợp sẵn toàn bộ dữ liệu mẫu chuẩn năm học **2026–2027**, cung cấp thang đo **Đánh giá Sức khỏe TKB (100 điểm)** và hỗ trợ xuất/nhập Excel đa năng.

---

## 🌟 Tính năng nổi bật

- **Động cơ giải CP-SAT thông minh**:
  - Tối ưu hóa toàn cục hàng nghìn biến số đồng thời trong 15–35 giây.
  - Phân tầng chẩn đoán và tự động thích ứng theo tài nguyên máy (tối ưu mượt mà cả trên máy chủ Cloud 2 vCPU).
  - Tự động lưu phương án tốt nhất khi đạt điểm plateau (sớm hơn giới hạn thời gian).
- **Tuân thủ tuyệt đối quy chế HĐSP**:
  - **Sáng bắt buộc (II.3)**: 100% giáo viên cơ hữu (tải $\ge 8$ tiết/tuần) có mặt dạy vào **sáng Thứ 2** (Chào cờ/SHDC) và **sáng Thứ 6** (Sinh hoạt tổng kết tuần).
  - **Không lẻ tiết (II.4)**: Tuyệt đối tránh giáo viên đi dạy đúng 1 tiết/buổi hoặc 1 tiết/ngày.
  - **Không ngày chia lẻ (II.8)**: Chặn tình trạng giáo viên dạy 1 tiết sáng + 1 tiết chiều trong cùng một ngày.
  - **Môn kép & Môn nặng**: Ghép đôi liền kề cho tiết kép (Ngữ văn, KHTN...); môn nặng (Toán, Lý, Hóa, Ngoại ngữ) tối đa 3 tiết/buổi, né tiết 3 chiều.
  - **Khung thể dục & Chuyên đề**: Thể dục chỉ xếp các tiết hợp lý; chiều Thứ 5 và Thứ 6 để trống toàn trường phục vụ ôn bồi dưỡng/phụ đạo.
- **Bảng Đánh Giá Sức Khỏe TKB (Thang 100 điểm)**:
  - 📚 **Sư phạm học sinh (40%)**: Độ phân bổ môn học, nhịp độ học tập, giãn cách môn 2–3 tiết/tuần.
  - 👩‍🏫 **Tiện nghi & Công bằng GV (35%)**: Hạn chế tiết trống (lủng lịch), tránh nhảy ca gắt (chiều muộn $\to$ sáng sớm hôm sau), cân đối số buổi dạy.
  - ⚖️ **Tuân thủ HĐSP & Kế hoạch (25%)**: Không trùng lịch, không vi phạm giờ bận, đảm bảo ngày công lễ tiết.
- **Dữ liệu chuẩn tích hợp sẵn**:
  - Nạp sẵn toàn bộ dữ liệu thực tế **Trường THCS (2026–2027)**: 8 lớp (Khối 6, 7, 8, 9), 16 môn, 17 giáo viên, 236 tiết học/tuần và khung định lượng 35 tuần cả năm học.
  - Vào thẳng trường mẫu ngay khi mở app, không mất công thiết lập ban đầu.

---

## 🚀 Hướng dẫn chạy ứng dụng ở máy Local

### 1. Cài đặt thư viện

Mở PowerShell tại thư mục dự án (`c:\Users\Kien\tkb_app`):

```powershell
pip install -r requirements.txt
```

*(Khuyến khích tạo môi trường ảo Python trước khi cài đặt: `python -m venv .venv` và kích hoạt bằng `.\.venv\Scripts\Activate.ps1`)*

### 2. Thiết lập mật khẩu đăng nhập

App có cổng đăng nhập bảo mật chung. Hãy tạo file `.streamlit/secrets.toml` (nếu chưa có):

```toml
app_password = "mat-khau-cua-ban"
```

*(File này đã nằm trong `.gitignore` nên an toàn, không bị đẩy lên GitHub).*

### 3. Khởi chạy ứng dụng

> ⚠️ **LƯU Ý QUAN TRỌNG TRÊN WINDOWS POWERSHELL:**
> - **CÁCH CHẠY ĐÚNG**:
>   ```powershell
>   python -m streamlit run app.py
>   ```
>   *(hoặc nếu đã kích hoạt `.venv`: `streamlit run app.py`)*
>
> - **LỖI THƯỜNG GẶP**:
>   1. Gõ `python streamlit run app.py`:
>      ❌ Báo lỗi: `can't open file '...streamlit': [Errno 2] No such file or directory` (do Python tìm file `streamlit.py` thay vì chạy module `streamlit`). **Khắc phục: thêm cờ `-m`**.
>   2. Gõ `streamlit run app.py` khi chưa kích hoạt virtualenv:
>      ❌ Báo lỗi: `The term 'streamlit' is not recognized...` (do thư mục Scripts chưa nằm trong biến môi trường PATH). **Khắc phục: dùng `python -m streamlit run app.py`**.

Sau khi chạy lệnh, trình duyệt sẽ tự động mở tại địa chỉ: `http://localhost:8501`.

---

## ☁️ Triển khai lên Streamlit Community Cloud (Miễn phí)

1. **Đẩy mã nguồn lên GitHub**:
   - Dữ liệu chuẩn của trường (`schools/truong-thcs.db` và bản sao dự phòng `data/sample_truong_thcs.db`) đã được cấu hình lưu trong Git. Khi đẩy lên GitHub, máy chủ Cloud sẽ có sẵn toàn bộ dữ liệu 2026–2027.
2. **Tạo App trên Streamlit Cloud**:
   - Truy cập [share.streamlit.io](https://share.streamlit.io) $\to$ Chọn **New app**.
   - Chọn Repository, Branch `main`, và Main file path là `app.py`.
3. **Cấu hình Secret**:
   - Nhấp vào **Advanced Settings** $\to$ mục **Secrets**, điền mật khẩu đăng nhập của bạn:
     ```toml
     app_password = "mat-khau-cua-ban"
     ```
4. **Bấm Deploy**:
   - Ứng dụng sẽ tự động khởi tạo trên môi trường Cloud (2 vCPU / 2 Search Workers). Động cơ CP-SAT sẽ tự động áp dụng chiến lược giải phân tầng tối ưu cho cấu hình 2 CPU, đảm bảo **100% giáo viên có mặt sáng Thứ 2, Thứ 6** và **không bị lẻ tiết**.

---

## 📊 Cấu trúc dữ liệu & Quản lý trường học

- **Hỗ trợ đa trường (Multi-tenant)**: Mỗi trường học là một file SQLite độc lập trong thư mục `schools/<mã-trường>.db`.
- **Trường mẫu mặc định**: `Trường THCS (2026-2027)` (`schools/truong-thcs.db`) được nạp tự động khi khởi động.
- **Đổi trường hoặc Tạo trường mới**: Có thể chuyển đổi bất cứ lúc nào qua nút **🏫 Đổi trường** ở thanh bên (Sidebar).
- **Sao lưu & Phục hồi**:
  - Nút **📥 Xuất Excel (sao lưu)** ở thanh bên hỗ trợ tải trọn vẹn toàn bộ dữ liệu cấu hình, giáo viên, định mức và thời khóa biểu ra file `.xlsx`.
  - Có thể nhập lại file sao lưu bất cứ lúc nào ở trang **09. Nhập / Xuất Excel**.

---

## 🧪 Chạy kiểm thử tự động (Test Suite)

Dự án có bộ test toàn diện gồm 310 test cases bao phủ toàn bộ thuật toán, ràng buộc sư phạm, động cơ CP-SAT và điểm sức khỏe TKB:

```powershell
pip install -r requirements-dev.txt
python -m pytest -n auto tests/
```

---

## 📁 Cấu trúc thư mục chính

```
tkb_app/
├── app.py                      # Điểm khởi động chính, cấu hình menu điều hướng
├── ui_common.py                # Xác thực, quản lý kết nối DB đa trường, thanh bên
├── pages/                      # 12 trang chức năng của ứng dụng:
│   ├── 00_Trang_chu.py         # Tổng quan tiến độ thiết lập và thống kê trường
│   ├── 01_Khai_bao.py          # Khai báo Lớp, Môn học, Giáo viên
│   ├── 02_PhanCong.py          # Phân công chuyên môn
│   ├── 03_DinhMuc.py           # Định mức số tiết theo tuần
│   ├── 04_GV_Ban.py            # Khai báo giờ bận của giáo viên
│   ├── 05_Khung_tiet.py        # Cấu hình khung tiết theo lớp
│   ├── 06_Xep_TKB.py           # Bảng điều khiển xếp TKB CP-SAT & Sức khỏe TKB
│   ├── 07_Can_Bang_Tai.py      # Đề xuất cân bằng tải chuyên môn
│   ├── 08_Lich_su_Tuan.py      # Quản lý lịch sử và tuần học (Chẵn/Lẻ)
│   ├── 09_Import_Export.py     # Nhập/Xuất Excel (gồm định lượng 35 tuần)
│   ├── 10_Cau_hinh_Xep_lich.py # Cấu hình nâng cao ràng buộc sư phạm
│   └── 11_Huong_Dan.py         # Hướng dẫn sử dụng chi tiết
├── core/                       # Động cơ cốt lõi (Core Engine):
│   ├── scheduler/cpsat/        # Bộ giải CP-SAT: mô hình, hàm mục tiêu, chẩn đoán
│   ├── validation.py           # Bộ kiểm tra ràng buộc & Bảng điểm Sức khỏe TKB
│   ├── frame.py                # Xử lý khung thời gian học tập
│   └── models.py               # Data models và hằng số sư phạm
├── data/                       # Quản trị cơ sở dữ liệu SQLite & Repository
│   ├── sample_truong_thcs.db   # Bản sao dữ liệu mẫu chuẩn năm học 2026-2027
│   └── repository.py           # Các hàm CRUD dữ liệu trường học
├── schools/                    # Thư mục lưu trữ CSDL các trường học (.db)
│   └── truong-thcs.db          # Dữ liệu chính thức Trường THCS (2026-2027)
└── tests/                      # Bộ kiểm thử tự động (310 test cases)
```
