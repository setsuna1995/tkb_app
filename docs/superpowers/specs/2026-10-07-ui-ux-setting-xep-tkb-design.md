# Thiết Kế Lại Giao Diện Trang Cấu Hình & Trang Xếp Thời Khóa Biểu — Chuẩn UI/UX Pro Max

- **Dự án**: `tkb_app` (Hệ thống Xếp Thời Khóa Biểu Tự Động THCS/THPT)
- **Tài liệu**: Design Specification
- **Ngày**: 2026-10-07
- **Tác giả**: Antigravity & User
- **Tiêu chuẩn áp dụng**: `ui-ux-pro-max` (Modern Academic Dashboard & SaaS Control System)
- **Phạm vi tác động**:
  - [`pages/10_Cau_hinh_Xep_lich.py`](../../../pages/10_Cau_hinh_Xep_lich.py) (Trang Cấu hình / Setting)
  - [`pages/06_Xep_TKB.py`](../../../pages/06_Xep_TKB.py) (Trang Xếp Thời khóa biểu & Studio khảo sát)
  - [`ui_theme.py`](../../../ui_theme.py) (Mở rộng CSS variables, components và color tokens)

---

## 1. Bối Cảnh & Mục Tiêu Cải Tiến (Context & Objectives)

### 1.1. Hiện trạng & Thách thức
Hệ thống `tkb_app` sở hữu bộ giải tối ưu hóa toàn cục Google OR-Tools CP-SAT rất mạnh mẽ và hệ thống 18 tiêu chuẩn sư phạm chi tiết. Tuy nhiên, qua quá trình sử dụng thực tế:
1. **Trang Cài đặt (`10_Cau_hinh_Xep_lich.py`)** có mật độ thông tin dày đặc, nhiều container lồng nhau, text giải thích dài dòng và cụm nút Lưu bị đẩy xuống tận đáy trang khiến người dùng thao tác rất bất tiện.
2. **Trang Xếp Thời khóa biểu (`06_Xep_TKB.py`)** bị quá tải nhận thức (Cognitive Overload). Người dùng phải xem quá nhiều khối rời rạc trước và sau khi chạy: panel chọn tuần cồng kềnh, cấu hình HĐTN tuần choán diện tích, chuỗi dài các bảng kết quả nối tiếp nhau (Bento Card, Expander tinh chỉnh sâu, Health Score, Studio 3 tab, Bảng lỗi vi phạm, Bảng định mức số tiết, Nút lưu).
3. **Khả năng quét mắt (Scanability) của bảng TKB còn thô sơ**: Dữ liệu lớp và giáo viên hiển thị dạng `st.dataframe` thuần với chuỗi `Môn (GV)` đơn điệu, chưa có nhận diện màu sắc theo vai trò môn học.

### 1.2. Mục tiêu cốt lõi
1. **Tổ chức thông tin theo nguyên tắc Tiết lộ Dần dần (Progressive Disclosure)**: Mặc định chỉ hiển thị các thông tin và luồng thao tác quan trọng nhất; các tùy chọn nâng cao chỉ hiển thị khi người dùng cần.
2. **Bố cục Phân cấp Rõ Ràng (Bento Card & 2-Column Grid)**: Tách biệt rõ ràng form nhập liệu và khối trực quan hóa/tóm tắt kết quả.
3. **Thanh Thao Tác Ưu Tiên (Prominent Action Bar)**: Đưa các nút Lưu, Xuất Excel, Khôi phục lên vị trí trực quan, dễ tiếp cận ở mọi trạng thái cuộn trang.
4. **Hệ Thống Nhận Diện Màu Sắc Môn Học (Subject Role Palette)**: Thổi sức sống vào lưới thời khóa biểu, giúp giáo viên và ban giám hiệu dễ dàng nhận biết môn Nặng, GDTC, HĐTN, Nghệ thuật.
5. **Bảo tồn 100% Logic & Dữ Liệu**: Giữ nguyên toàn bộ cấu trúc dữ liệu `SchedulingConfig`, cơ sở dữ liệu SQLite, bộ giải CP-SAT và luồng validation.

---

## 2. Nền Tảng Thiết Kế & Token Mở Rộng (`ui_theme.py`)

### 2.1. Bảng màu Nhận diện Vai trò Môn học (Subject Role Color Tokens)
Bổ sung các token màu có độ tương phản đạt chuẩn WCAG (tối thiểu 4.5:1 với chữ) cho các môn học:

| Nhóm môn | Vai trò | Màu nền Light | Màu viền Light | Màu chữ Light | Ý nghĩa trực quan |
|---|---|---|---|---|---|
| **Môn Nặng** (Toán, Văn, KHTN...) | `ROLE_NANG` / `ROLE_NANG_KEP` | `#EFF6FF` (Blue-50) | `#BFDBFE` | `#1E40AF` | Tập trung, học thuật |
| **Thể dục** (GDTC) | `ROLE_GDTC` | `#FFF7ED` (Orange-50) | `#FED7AA` | `#9A3412` | Năng động, vận động ngoài trời |
| **Trải nghiệm** (HĐTN, Chào cờ, SHL) | `ROLE_HDTN` | `#F0FDF4` (Green-50) | `#BBF7D0` | `#166534` | Tập thể, sinh hoạt |
| **Môn Kép / Nghệ thuật** (Âm nhạc, MT...) | `ROLE_KEP` / Năng khiếu | `#FAF5FF` (Purple-50) | `#E9D5FF` | `#6B21A8` | Sáng tạo, đặc thù |
| **Môn Thường** (Lịch sử, Địa lí, GDCD...) | `ROLE_THUONG` | `#F8FAFC` (Slate-50) | `#E2E8F0` | `#334155` | Trung tính, cân đối |
| **Ô Tiết Trống / Nghỉ** | `None` / `0` | `#FFFFFF` | `#F1F5F9` | `#94A3B8` | Thông thoáng, sạch sẽ |

### 2.2. Các Component Trực Quan Mới Trong `ui_theme.py`
1. `render_action_bar(primary_btn_text, secondary_actions, status_badge)`:
   - Thanh công cụ hành động hiển thị ở đầu trang, chứa nút hành động chính (màu xanh thương hiệu nổi bật) kèm các nút phụ và badge trạng thái.
2. `render_subject_pill(subject_name, teacher_name, role_code)`:
   - Badge hiển thị tên môn và giáo viên với màu sắc theo vai trò môn, hỗ trợ tooltip chi tiết.
3. `render_bento_section(title, subtitle, icon, content_html, badge)`:
   - Card container bento bo góc `12px`, bóng mờ êm dịu, phân cách rõ ràng từng cụm tính năng.
4. `render_status_summary_bar(items: list[dict])`:
   - Dải tóm tắt trạng thái (ví dụ: `18/18 Tiêu chuẩn đạt`, `0 Tiết trống lẻ`, `3 Lớp hai buổi`).

---

## 3. Thiết Kế Chi Tiết Trang Cài Đặt (`pages/10_Cau_hinh_Xep_lich.py`)

### 3.1. Cấu Trúc Bố Cục Trang
```
┌────────────────────────────────────────────────────────────────────────┐
│ HEADER: Cấu hình Ràng buộc & Tiêu chuẩn Sư phạm (Trường THCS Phú Thịnh) │
├────────────────────────────────────────────────────────────────────────┤
│ TOP ACTION BAR:                                                        │
│ [💾 Lưu Cấu Hình]  [📥 Xuất File Excel (.xlsx)]  [🔄 Mặc Định]        │
│ Trạng thái: ✅ Cấu hình hợp lệ • 18/18 tiêu chí đang hoạt động          │
├────────────────────────────────────────────────────────────────────────┤
│ TABS:                                                                  │
│ ┌─ Tab 1 ──────┬─ Tab 2 ──────┬─ Tab 3 ─────┬─ Tab 4 ─────┬─ Tab 5 ──┐ │
│ │ 🏛️ Khung giờ │ 👨‍🏫 Hiện diện │ ⚖️ Phân bổ   │ 🎓 Tiêu chuẩn│ ⚡ Solver│ │
│ └──────────────┴──────────────┴─────────────┴─────────────┴──────────┘ │
└────────────────────────────────────────────────────────────────────────┘
```

### 3.2. Chi Tiết Từng Tab

#### Tab 1: Khung Thời Gian & Tiết Ghim
- **Tổ chức 2 cột Bento Grid**:
  - **Cột Trái (Form Cấu hình HĐTN)**:
    - Segmented Radio chọn Phương án: `📅 Phân bổ 3 tiết chuẩn` vs `🎪 Dồn 3 tiết chuyên đề toàn trường`.
    - Khi chọn *Phân bổ*: Hiển thị 3 card con xếp dọc tinh gọn cho Tiết 1 (Chào cờ), Tiết 2 (Chủ đề - kèm toggle tự do/cố định), Tiết 3 (SHL - kèm toggle tự do/cố định).
    - Cắt bỏ các khung viền kép lồng nhau gây rối mắt.
  - **Cột Phải (Tiết chuyên biệt & Buổi cấm)**:
    - Card 1: *Ưu tiên GVCN tiết 2 Thứ 2* (checkbox bật/tắt + multiselect chọn lớp miễn trừ).
    - Card 2: *Khung giờ Thể dục (GDTC)* (chọn tiết sáng/chiều được phép).
    - Card 3: *Buổi cấm nghỉ & Buổi chiều trống toàn trường* (danh sách Thứ/Buổi chọn lọc).
    - Sơ đồ mini preview trực quan hoá tuần học (Mini Timetable Visualizer).

#### Tab 2: Hiện Diện & Buổi Nghỉ Của Giáo Viên
- Gom nhóm theo 3 Card chức năng:
  1. **Card 1 — Bắt Buộc Có Mặt Tại Trường**:
     - Cấu hình sáng Thứ 2 (Chào cờ toàn trường).
     - Cấu hình các buổi sáng bắt buộc có mặt theo ngưỡng tải (Thứ 2, 5, 6) + Ngưỡng tiết/tuần.
     - Toggle: Cho phép 1 tiết lẻ vào các buổi bắt buộc có mặt (đã được kiểm chứng trong `test_mandatory_morning_lone_session.py`).
  2. **Card 2 — Chế Độ Buổi Nghỉ Trong Tuần**:
     - Số buổi nghỉ mong muốn cho mỗi GV (0 - 3 buổi).
     - Mức độ áp dụng: *Không áp dụng* | *Ưu tiên cao (Mềm)* | *Bắt buộc tuyệt đối (Cứng)*.
  3. **Card 3 — Danh Sách Miễn Trừ & Ưu Tiên Cá Nhân**:
     - Giáo viên được miễn trừ luật tránh dạy 1 tiết/buổi (GV thiết bị, thư viện, tin học...).
     - Giáo viên ưu tiên gom tiết để nghỉ trọn nhiều buổi (GV Thể dục, Nhạc, Mỹ thuật...).

#### Tab 3: Định Mức & Phân Bổ Môn Học
- **Tích hợp tính năng**: Đưa khối *"Ràng buộc riêng Môn/Lớp"* (vốn bị giấu ở expander dưới đáy trang) vào làm một phân vùng rõ ràng trong Tab 3.
- **Card 1 — Giới Hạn Tải Giảng Dạy**:
  - Số tiết tối đa/buổi cho GV (mặc định 4).
  - Số tiết tối đa/ngày cho GV cả sáng + chiều (mặc định 5).
  - Giới hạn tiết môn Nặng liên tiếp & tối đa môn Nặng/buổi.
- **Card 2 — Phân Luồng Buổi Sáng / Buổi Chiều**:
  - Checkbox môn Nặng chỉ học buổi sáng.
  - Multiselect môn bắt buộc học sáng / ưu tiên học chiều.
- **Card 3 — Luật Phân Bố Môn Cách Nhật & Tiết Kép**:
  - Môn cách nhật (không xếp liền ngày — ví dụ GDTC).
  - Môn đúng 1 cặp kép (ví dụ Ngữ văn có 1 cặp 2 tiết liền).
- **Card 4 — Ràng Buộc Riêng Môn/Lớp Theo Buổi**:
  - Form thêm nhanh luật riêng + Bảng danh sách luật hiện có với nút xoá inline dạng icon thùng rác đỏ tinh tế.

#### Tab 4: Tiêu Chuẩn Sư Phạm (18 Tiêu Chí HĐSP)
- **Tái cấu trúc từ 8 checkbox rời rạc thành 2 phân khu chuẩn hóa**:
  1. **Phân khu A — Ràng Buộc Cốt Lõi (Core Pedagogy)**:
     - Badge màu đỏ/xanh: `[Bắt buộc/Mềm]`
     - Tránh tiết trống/lủng của GV trong buổi.
     - Tránh GV đi dạy chỉ 1 tiết/ngày hoặc phân tán sáng 1 + chiều 1.
     - Ngưỡng tiết/tuần phạt lẻ tiết GV.
     - Hạn chế GV dạy 4 tiết sáng liên tục.
  2. **Phân khu B — Tiện Nghi Học Sinh & Giáo Viên**:
     - Cân đối tiết buổi chiều cho GV.
     - Thể dục (GDTC) không xếp vào 2 ngày liên tiếp.
     - Hạn chế môn Nặng vào tiết 3 buổi chiều.

#### Tab 5: Bộ Giải Tối Ưu Hóa CP-SAT (Google OR-Tools)
- **Tái thiết kế thành Trung Tâm Điều Khiển Động Cơ**:
  - **Card 1 — Tham Số Bộ Giải**:
    - Thời gian chạy tối đa (Time Limit: 5s - 300s, slider kèm số).
    - Cờ `cpsat_minimize_changes`: Ưu tiên giữ nguyên ô TKB cũ khi xếp tuần mới.
    - Lựa chọn số luồng CPU (Workers) kèm giải thích phù hợp với Streamlit Cloud vs Máy trạm.
  - **Card 2 — Bảng Đánh Giá Hiệu Năng & Khuyến Nghị**:
    - Hiển thị cấu hình đề xuất dựa trên quy mô trường học (Số lớp, Số GV).
    - Hộp nạp file cấu hình Excel (`.xlsx`) để phục hồi nhanh toàn bộ thiết lập.

---

## 4. Thiết Kế Chi Tiết Trang Xếp Thời Khóa Biểu (`pages/06_Xep_TKB.py`)

### 4.1. Kiến Trúc Luồng 2 Bước (2-Step Execution Flow)
Người dùng được dẫn dắt theo luồng tự nhiên: **Khởi tạo & Chạy -> Đối sánh & Khảo sát Studio -> Lưu kết quả**.

```
┌────────────────────────────────────────────────────────────────────────┐
│ HEADER: Xếp Thời Khóa Biểu & Xuất Excel Theo Tuần                       │
├────────────────────────────────────────────────────────────────────────┤
│ BƯỚC 1: BẢNG ĐIỀU KHIỂN XẾP LỊCH (HERO RUN CONTROL)                    │
│ ┌────────────────────────────────────────────────────────────────────┐ │
│ │ Chọn Tuần: [Tuần 6 ▾]  Học Kỳ: [Học kỳ I ▾]                        │ │
│ │ Trạng thái tuần: ✅ Đã có TKB chính thức (lưu lúc 09:30 06/10)       │ │
│ │                                                                    │ │
│ │ [🚀 CHẠY XẾP TKB (3 PHƯƠNG ÁN)]        [⚡ XẾP NHANH 1 PHƯƠNG ÁN]   │ │
│ │                                                                    │ │
│ │ ▸ ⚙️ Tùy chỉnh riêng cho tuần này (Môn kép tạm thời, Mốc HĐTN)     │ │
│ └────────────────────────────────────────────────────────────────────┘ │
│                                                                        │
│ BƯỚC 2: KẾT QUẢ ĐỐI SÁNH & STUDIO ĐIỀU PHỐI (Khi có nghiệm)            │
│ ┌────────────────────────────────────────────────────────────────────┐ │
│ │ 3 BENTO CARDS ĐỐI SÁNH PHƯƠNG ÁN (Kèm Health Score tổng hợp)       │ │
│ │  • Phương án 1 (Triệt tiêu lẻ): 92/100 🏆                         │ │
│ │  • Phương án 2 (Kỷ luật sáng T2): 89/100 🚩                        │ │
│ │  • Phương án 3 (Cân bằng tối ưu): 94/100 🌟 [Đang chọn]           │ │
│ └────────────────────────────────────────────────────────────────────┘ │
│                                                                        │
│ ACTION BAR KẾT QUẢ:                                                    │
│ [✅ Chấp Nhận & Lưu Tuần 6]  [📤 Tải Excel Tuần]  [🛠️ Tinh Chỉnh Sâu] │
│                                                                        │
│ STUDIO KHẢO SÁT THỜI KHÓA BIỂU:                                        │
│  [🏫 Xem Lớp Học]   [👩‍🏫 Tra Cứu Giáo Viên]   [📊 Ma Trận Toàn Trường] │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ Lưới hiển thị trực quan có màu sắc môn học                       │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                        │
│ KIỂM ĐỊNH CHẤT LƯỢNG (Progressive Disclosure):                         │
│  • Báo cáo vi phạm HĐSP: Badge xanh nếu sạch, chỉ bung nếu có vi phạm  │
│  • Báo cáo định mức: Badge xanh nếu khớp 100%, chỉ bung bảng nếu lệch  │
└────────────────────────────────────────────────────────────────────────┘
```

### 4.2. Chi Tiết Các Phân Vùng

#### A. Hero Run Control (Trước Khi Chạy)
- Gom chọn Học kỳ, Chọn tuần vào 1 hàng ngang cân đối.
- Hiển thị ngay trạng thái tuần đã chọn: đã có TKB chính thức chưa, ngày lưu, nút tải nhanh Excel nếu tuần đã lưu.
- Khối cấu hình phụ (môn kép tuần, phương án HĐTN tuần) được thu gọn trong expander `⚙️ Tùy chỉnh riêng tuần này` với mặc định là áp dụng cấu hình chuẩn của trường.
- Hai nút chạy lớn, rõ ràng: **Nút chính (Primary)** tính toán 3 phương án; **Nút phụ (Secondary)** xếp nhanh 1 phương án.

#### B. Bento Card Đối Sánh Phương Án (Tích Hợp Health Score)
- Tích hợp điểm số sức khỏe TKB (Overall Score, Sư phạm, Tiện nghi GV, Tuân thủ) trực tiếp vào trong mỗi thẻ phương án thay vì để một khối riêng biệt dài dằng dặc phía dưới.
- Người dùng chỉ cần nhìn vào 3 thẻ là biết ngay:
  - Phương án nào điểm cao nhất.
  - Số buổi lẻ là bao nhiêu (0 buổi = badge xanh lá).
  - Có lủng tiết không (0 lủng = badge xanh lá).
  - Sáng Thứ 2 có mặt 100% không.
- Thao tác 1-Click để chuyển đổi giữa các phương án.

#### C. Timetable Studio (Khảo Sát Chi Tiết TKB)
- **Tab 1: Xem Theo Lớp Học**:
  - Bộ lọc chọn nhanh theo Khối (Khối 6, Khối 7, Khối 8, Khối 9).
  - Bảng TKB lớp hiển thị các ô tiết với màu nền dịu mắt theo vai trò môn:
    - Toán/Văn/KHTN: Nền xanh lam nhạt, chữ đậm.
    - GDTC: Nền cam nhạt.
    - HĐTN/Chào cờ/SHL: Nền xanh lá nhạt.
    - Nghệ thuật: Nền tím nhạt.
  - Tên GV hiển thị rõ nét bên dưới tên môn, không bị dính chùm chữ.
- **Tab 2: Tra Cứu Chuyên Sâu Từng Giáo Viên**:
  - Hàng nút chọn nhanh giáo viên có ràng buộc trọng điểm (GV Âm nhạc, GV GDTC, GVCN...).
  - Dải 5 KPI cá nhân thu gọn thành thanh trạng thái ngang thanh thoát: *Tổng tiết*, *Số buổi dạy*, *Nghỉ chiều (Đạt/Chưa)*, *Buổi lẻ 1 tiết (0 = Chuẩn)*, *Sáng Thứ 2 (Có mặt/Nghỉ)*.
  - Bảng lưới tuần của GV với highlight viền đỏ/cam nếu có buổi lẻ cần lưu ý.
- **Tab 3: Ma Trận Tải & Buổi Lẻ Toàn Trường**:
  - 4 KPI tổng quan toàn trường: *Số GV phân công*, *Tổng buổi lẻ*, *Chỉ tiêu nghỉ chiều*, *Tỷ lệ GV sạch buổi lẻ*.
  - Bộ lọc tức thì: Toggle *"Chỉ hiện GV có vấn đề"* + Ô tìm kiếm theo tên GV hoặc môn.
  - Bảng dữ liệu rõ ràng, tô màu cảnh báo tại cột vi phạm.

#### D. Thu Gọn Khối Kiểm Định (Vi Phạm & Định Mức)
- Áp dụng nguyên tắc **Management by Exception**:
  - Nếu kết quả đạt chuẩn 100% không vi phạm quy tắc bắt buộc: Hiển thị Callout xanh ngắn gọn: `✅ Thời khóa biểu tuân thủ 100% quy chuẩn sư phạm`.
  - Nếu định mức khớp 100%: Hiển thị Callout xanh: `✅ Khớp 100% định mức số tiết chuẩn của Tuần`.
  - Chỉ khi có trường hợp vi phạm hoặc lệch định mức thì mới bung bảng chi tiết và danh sách đối soát để người dùng xử lý.

#### E. Tinh Gọn Mã Nguồn & Tab Xem Lại Các Tuần
- Gỡ bỏ hoàn toàn đoạn mã xếp nhiều tuần (Batch Scheduling) đang tạm tắt không sử dụng để code tinh gọn, giảm kích thước file từ 124KB xuống mức tối ưu, giúp trang phản hồi mượt mà hơn.
- Tab Xem lại TKB các tuần (1 - 35) giữ luồng xem và xuất Excel rõ ràng theo tuần đã chọn.

---

## 5. Kế Hoạch Triển Khai (Implementation Strategy)

### Giai đoạn 1: Bổ Sung Nền Tảng UI (`ui_theme.py`)
- Định nghĩa các hằng số màu vai trò môn học và CSS class tương ứng.
- Cập nhật hàm `inject_theme()` với các CSS rule mới cho table, cards, và badges.
- Viết các helper component: `render_action_bar`, `render_subject_pill`, `render_bento_section`.

### Giai đoạn 2: Tái Thiết Kế Trang Cài Đặt (`pages/10_Cau_hinh_Xep_lich.py`)
- Tái cấu trúc theo 5 Tab với layout Bento 2 cột.
- Đưa Top Action Bar (Lưu, Xuất file, Reset) lên đầu trang.
- Tích hợp quản lý luật riêng môn/lớp vào Tab 3.
- Kiểm thử lưu cấu hình, nạp file Excel, khôi phục mặc định.

### Giai đoạn 3: Tái Thiết Kế Trang Xếp Thời Khóa Biểu (`pages/06_Xep_TKB.py`)
- Thiết kế Hero Run Control tinh gọn trước khi giải.
- Tích hợp Health Score vào 3 Bento Card đối sánh phương án.
- Tinh chỉnh Timetable Studio với màu sắc môn học và phân cấp rõ ràng.
- Rút gọn phần kiểm tra vi phạm/định mức theo nguyên tắc Progressive Disclosure.
- Loại bỏ code rác batch scheduling.

### Giai đoạn 4: Kiểm Thử Toàn Diện & Đảm Bảo Tính Toàn Vẹn
- Chạy toàn bộ test suite (`pytest tests/`) để xác nhận không có bất kỳ regression nào trong logic thuật toán hoặc xử lý dữ liệu.
- Kiểm tra tính tương thích Responsive (màn hình Laptop, PC lớn, hiển thị dark/light mode).
- Chạy GitNexus impact analysis và detect changes trước khi hoàn tất.

---

## 6. Đánh Giá Rủi Ro & Giải Pháp Phòng Ngừa (Risk Assessment)

| Rủi ro tiềm ẩn | Mức độ | Biện pháp phòng ngừa |
|---|---|---|
| **Thay đổi nhầm tham số cấu hình khi tái cấu trúc widget** | Trung bình | Giữ nguyên 100% tên trường `SchedulingConfig` và key `st.session_state` tương thích ngược. |
| **Ảnh hưởng đến hiệu năng render của Streamlit** | Thấp | Tối ưu hóa việc gọi CSS và HTML tĩnh, tránh lồng quá nhiều container không cần thiết. |
| **Xung đột bộ giải CP-SAT hoặc luồng nới lỏng** | Rất thấp | Giữ nguyên vẹn 100% các hàm gọi solver (`_run_single_solver`, `_run_multi_strategy_solver`, CP-SAT model). |
| **Lệch layout trên màn hình nhỏ** | Thấp | Sử dụng responsive grid tự co giãn và kiểm tra breakpoint theo chuẩn `ui-ux-pro-max`. |

---

## 7. Tiêu Chí Nghiệm Thu (Acceptance Criteria)

1. **Trang Cài đặt (`10_Cau_hinh_Xep_lich.py`)**:
   - [ ] Có thanh công cụ hành động phía trên, bấm Lưu / Xuất / Reset hoạt động chuẩn xác 100%.
   - [ ] 5 Tab được trình bày gọn gàng, không còn các khối container lồng nhau vụn vặt.
   - [ ] Phân loại rõ ràng tiêu chuẩn bắt buộc vs tiêu chuẩn khuyến nghị.
   - [ ] Mục luật riêng môn/lớp được tích hợp mượt mà vào Tab 3.

2. **Trang Xếp TKB (`06_Xep_TKB.py`)**:
   - [ ] Trước khi chạy: Màn hình khởi tạo gọn gàng, nút bấm nổi bật, không bị ngập trong cấu hình phụ.
   - [ ] Sau khi chạy: 3 Card phương án hiển thị trực quan kèm điểm số sức khỏe; Action Bar nằm ngay phía dưới để quyết định lưu/tải ngay.
   - [ ] Lưới TKB Lớp học và Giáo viên có màu sắc nhận diện vai trò môn học trực quan, dễ quét mắt.
   - [ ] Báo cáo vi phạm và định mức hiển thị gọn gàng, chỉ bung chi tiết khi có cảnh báo.

3. **Hệ thống & Kiểm thử**:
   - [ ] `pytest tests/` chạy pass 100% không có lỗi.
   - [ ] Không có lỗi lint hoặc import bất thường.
