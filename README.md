# Xếp Thời Khóa Biểu

Ứng dụng web (Streamlit) xếp thời khóa biểu tự động cho trường THCS, port lại
toàn bộ logic từ bộ công cụ Excel/VBA gốc (`XepTKB.bas`, `ModCanBangTai.bas`,
`ModKhung.bas`, `ModSeed.bas`) sang Python — giữ nguyên mọi ràng buộc sư phạm,
thêm giao diện web, lưu dữ liệu bằng SQLite, và xuất kết quả ra file Excel.

## Tính năng

- **Xếp TKB tự động**: thuật toán greedy + swap-repair + thử lại nhiều lần,
  giữ tối đa lịch tuần trước. Đầy đủ ràng buộc: không trùng GV, môn nặng
  (Toán/Lý/Hoá) tối đa 3 tiết liên tiếp, tiết kép Ngữ văn liền nhau cùng buổi,
  Thể dục né tiết 5, chào cờ thứ 2 tiết 1 + sinh hoạt lớp thứ 7, mỗi GV được
  xếp đúng 1 buổi nghỉ/tuần, không xếp buổi nghỉ vào sáng thứ 2/5/6 (GVCN bắt
  buộc có mặt thứ 2 và thứ 7), chiều thứ 5 và thứ 6 luôn để trống trong TKB
  toàn trường (dành riêng cho ôn bồi dưỡng/phụ đạo, diễn ra ngoài TKB), không
  buổi nào bị xếp đúng 1 tiết lẻ, GV bận theo khai báo riêng, cảnh báo
  khi GV vượt định mức tiết.
- **Cân bằng tải**: đề xuất chuyển tiết từ GV quá tải sang GV cùng chuyên môn
  còn dư định mức (chỉ đề xuất, không tự sửa Phân công).
- **Khung tiết tùy chỉnh**: chọn mẫu buổi sáng/chiều có sẵn hoặc tự nhập số
  tiết mỗi buổi cho từng lớp.
- **Lịch sử tuần / seed**: sinh tuần mới (đảo định mức Chẵn/Lẻ), tái tạo lại
  đúng thời khóa biểu của một tuần cũ theo seed đã lưu.
- **Import/Export Excel**: nhập dữ liệu từ file `.xlsm` hiện có (PhanCong,
  SoTiet, DinhMuc_GV, GV_Bận, TKB_Nhap, Khung, TuanConfig), xuất thời khóa
  biểu ra `.xlsx` với các sheet TKB, TKB_GV, KiemTra.

## Chạy ở máy local

```bash
pip install -r requirements.txt
streamlit run app.py
```

Mở trình duyệt tại `http://localhost:8501`.

### Mật khẩu đăng nhập

App có 1 cổng mật khẩu chung (không có tài khoản riêng từng người). Mật khẩu
đọc từ `.streamlit/secrets.toml` (file này **không** commit lên git — đã có
trong `.gitignore`, chỉ tồn tại trên máy bạn):

```toml
app_password = "mật-khẩu-của-bạn"
```

Đổi mật khẩu: sửa giá trị `app_password` trong file đó rồi chạy lại app.
Có file mẫu `.streamlit/secrets.toml.example` để tham khảo cấu trúc.

## Dữ liệu lưu ở đâu

App hỗ trợ nhiều trường (multi-tenant): mỗi trường có 1 file SQLite riêng
trong thư mục `schools/<mã-trường>.db` (tự tạo khi chọn/tạo trường lần đầu,
không commit lên git). Trường được chọn ở đầu phiên làm việc và có thể đổi
qua nút chuyển trường ở thanh bên. Nếu máy bạn từng dùng bản cũ (1 file
`tkb_app_data.db` duy nhất ở gốc project), app tự động di chuyển dữ liệu đó
thành trường đầu tiên khi khởi động lần đầu sau khi cập nhật.

Mỗi file DB chứa toàn bộ dữ liệu của 1 trường (lớp, môn, GV, phân công, định
mức, GV bận, khung tiết, thời khóa biểu, lịch sử tuần). Sao lưu dữ liệu bằng
nút "Xuất Excel (sao lưu)" ở thanh bên — nên bấm thường xuyên, đặc biệt khi
host trên nền tảng free (xem phần Triển khai bên dưới).

## Chạy test

```bash
pip install -r requirements-dev.txt
python -m pytest
```

Bộ test gồm: kiểm tra từng ràng buộc riêng lẻ của thuật toán xếp (core/scheduler),
kiểm tra import đúng dữ liệu từ file Excel mẫu thật (`tests/fixtures/TKB_9lop_moi.xlsm`),
và kiểm tra xếp TKB thành công + đúng ràng buộc trên chính dữ liệu thật đó.

## Triển khai lên Streamlit Community Cloud (miễn phí)

1. Push project này lên một repo GitHub (private cũng được).
2. Vào [share.streamlit.io](https://share.streamlit.io) → New app → chọn repo,
   branch, và đường dẫn file chính là `app.py`.
3. Vào phần **Secrets** của app trên Streamlit Cloud, dán:
   ```toml
   app_password = "mật-khẩu-của-bạn"
   ```
4. Deploy.

**Lưu ý quan trọng**: ổ đĩa của Streamlit Community Cloud là tạm thời — dữ
liệu SQLite có thể mất khi app khởi động lại hoặc "ngủ" do không có người
dùng một thời gian. Với một công cụ nội bộ quy mô nhỏ như thế này, cách đơn
giản nhất là chấp nhận giới hạn đó và luôn xuất Excel sau mỗi lần chỉnh sửa
quan trọng — nếu app bị reset, chỉ cần nhập lại đúng file Excel đó ở trang
Import/Export là khôi phục lại toàn bộ dữ liệu.

## Cấu trúc thư mục

```
app.py                  # điểm vào, trang chủ/dashboard
ui_common.py            # cổng mật khẩu, kết nối DB dùng chung, nút sao lưu
pages/                  # 9 trang chức năng (Streamlit tự nhận theo tên file)
core/                   # thuật toán xếp TKB thuần Python, không phụ thuộc Streamlit
data/                   # schema SQLite + hàm CRUD/truy vấn
io_excel/               # import file .xlsm, export file .xlsx kết quả
tests/                  # test tự động, gồm cả dữ liệu Excel thật làm fixture
```
