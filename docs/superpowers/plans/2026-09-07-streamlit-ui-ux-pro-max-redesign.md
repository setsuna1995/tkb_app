# Kế Hoạch Triển Khai: Thiết Kế Lại Giao Diện Streamlit Chuẩn UI/UX Pro Max

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Chuyển đổi toàn diện giao diện Streamlit của `tkb_app` sang chuẩn Modern Academic Dashboard (UI/UX Pro Max), loại bỏ mật khẩu đăng nhập, tích hợp xuất Excel TKB trực tiếp tại trang `06_Xep_TKB.py`, và nâng cấp đồng bộ 11 trang mà không làm ảnh hưởng đến thuật toán xếp lịch và cơ sở dữ liệu.

**Architecture:** Tạo module giao diện tập trung `ui_theme.py` (font Plus Jakarta Sans, CSS tokens, component helpers) được tự động nhúng qua `ui_common.py`. Cập nhật `.streamlit/config.toml` đồng bộ theme. Chuẩn hóa bố cục thẻ card (Bento grid) và nâng cấp tuần tự 4 nhóm trang.

**Tech Stack:** Python 3.13, Streamlit 1.40+, HTML5/CSS3 (Google Fonts `Plus Jakarta Sans`), Pandas, Openpyxl, Pytest.

**Spec:** `docs/superpowers/specs/2026-09-07-streamlit-ui-ux-pro-max-redesign.md`

## Global Constraints

- **Primary Color**: `#2563EB` (Trust Blue)
- **Background**: `#F8FAFC` (Slate-50)
- **Card Surface**: `#FFFFFF` | Border: `#E2E8F0` | Text: `#0F172A`
- **Font**: `Plus Jakarta Sans` (sans-serif fallback)
- **No breaking changes**: Giữ nguyên 100% logic solver CP-SAT (`core/scheduler/*`), validation (`core/validation/*`), và SQLite DB (`data/*`).
- **No login barrier**: `require_auth()` là pass-through không yêu cầu mật khẩu.
- **Direct Export**: Tính năng xuất Excel TKB theo tuần được tích hợp trực tiếp trên `pages/06_Xep_TKB.py`.

---

### Task 1: Nền Tảng Design System & Module `ui_theme.py`

**Files:**
- Create: `ui_theme.py`
- Modify: `.streamlit/config.toml`
- Test: `tests/test_ui_theme.py`

**Interfaces:**
- Produces:
  - `inject_theme() -> None`
  - `render_page_header(title: str, subtitle: str = None, badge: str = None, icon: str = None) -> None`
  - `render_kpi_card(title: str, value: Any, subtitle: str = "", icon: str = "", variant: str = "primary") -> str`
  - `render_status_badge(label: str, status: str = "info") -> str`
  - `render_callout(message: str, level: str = "info", title: str = None) -> None`

- [ ] **Step 1: Viết test cho `ui_theme.py`**

Tạo file `tests/test_ui_theme.py`:
```python
import pytest
from ui_theme import render_kpi_card, render_status_badge, render_callout_html

def test_render_kpi_card():
    html = render_kpi_card("Số lớp", 12, subtitle="Khối 6-9", icon="🏫", variant="primary")
    assert "Số lớp" in html
    assert "12" in html
    assert "tkb-kpi-card" in html

def test_render_status_badge():
    badge = render_status_badge("Đạt chuẩn", status="success")
    assert "Đạt chuẩn" in badge
    assert "tkb-badge-success" in badge

def test_render_callout_html():
    callout = render_callout_html("Cảnh báo định mức", level="warning", title="Chú ý")
    assert "Cảnh báo định mức" in callout
    assert "tkb-callout-warning" in callout
```

- [ ] **Step 2: Chạy test để xác nhận fail**

Chạy: `pytest tests/test_ui_theme.py -v`
Kỳ vọng: FAIL vì chưa có file `ui_theme.py`.

- [ ] **Step 3: Cập nhật `.streamlit/config.toml` và viết `ui_theme.py`**

Cập nhật `.streamlit/config.toml`:
```toml
[server]
headless = true

[theme]
base = "light"
primaryColor = "#2563EB"
backgroundColor = "#F8FAFC"
secondaryBackgroundColor = "#FFFFFF"
textColor = "#0F172A"
font = "sans serif"
```

Viết `ui_theme.py` với font Plus Jakarta Sans, CSS Tokens, Custom CSS Overrides cho Streamlit widgets, và các helper functions: `inject_theme`, `render_page_header`, `render_kpi_card`, `render_status_badge`, `render_callout_html`, `render_callout`.

- [ ] **Step 4: Chạy test để xác nhận pass**

Chạy: `pytest tests/test_ui_theme.py -v`
Kỳ vọng: PASS.

- [ ] **Step 5: Commit**

```bash
git add .streamlit/config.toml ui_theme.py tests/test_ui_theme.py
git commit -m "feat(ui): add ui_theme design system and modern streamlit config"
```

---

### Task 2: Loại Bỏ Đăng Nhập & Nâng Cấp Bootstrap `ui_common.py`

**Files:**
- Modify: `ui_common.py`
- Test: `tests/test_ui_common.py`

**Interfaces:**
- Consumes: `ui_theme.inject_theme()`
- Produces: `require_auth() -> None`, `require_school() -> str`, `sidebar_school_switcher() -> None`, `sidebar_fixed_rules(conn) -> None`, `sidebar_backup_export(conn) -> None`

- [ ] **Step 1: Viết test cho `require_auth` trong `tests/test_ui_common.py`**

```python
import streamlit as st
from ui_common import require_auth

def test_require_auth_does_not_block():
    # Không ném ngoại lệ hay dừng st.stop()
    require_auth()
    assert True
```

- [ ] **Step 2: Run test để kiểm tra hiện trạng**

Chạy: `pytest tests/test_ui_common.py -v`

- [ ] **Step 3: Sửa `ui_common.py`**
  - Chuyển `require_auth()` thành hàm pass-through (`pass`).
  - Trong `require_school()`, tự động chọn trường mặc định nếu chưa chọn mà có danh sách trường, không chặn.
  - Tự động gọi `ui_theme.inject_theme()` trong `ui_common.py`.
  - Nâng cấp giao diện `sidebar_school_switcher`, `sidebar_fixed_rules`, `sidebar_backup_export` với CSS card và icon sắc nét.

- [ ] **Step 4: Run test để xác nhận pass**

Chạy: `pytest tests/test_ui_common.py -v`
Kỳ vọng: PASS.

- [ ] **Step 5: Commit**

```bash
git add ui_common.py tests/test_ui_common.py
git commit -m "feat(ui): remove login auth barrier and inject modern theme via ui_common"
```

---

### Task 3: Thiết Kế Lại Nhóm 1 — Tổng Quan (`00_Trang_chu.py` & `11_Huong_Dan.py`)

**Files:**
- Modify: `pages/00_Trang_chu.py`
- Modify: `pages/11_Huong_Dan.py`

**Interfaces:**
- Consumes: `ui_theme.render_page_header`, `ui_theme.render_kpi_card`, `ui_theme.render_status_badge`, `ui_theme.render_callout`

- [ ] **Step 1: Cập nhật `pages/00_Trang_chu.py`**
  - Thay tiêu đề `st.title` bằng `render_page_header("Trung Tâm Điều Hành Thời Khóa Biểu", "Hệ thống xếp lịch tự động & thẩm định 18 tiêu chí chuyên môn", badge=f"Tuần {current_week}", icon="🏫")`.
  - Thay `st.columns(4)` metric bằng hàng 4 `render_kpi_card` (Số Lớp, Số Môn, Số Giáo Viên, Tuần Đang Xếp).
  - Nâng cấp bảng Tiến độ thiết lập với badge trạng thái pill và button điều hướng nhanh.
  - Đóng gói Thời khóa biểu gần nhất vào Card thông tin nổi bật.
  - Hiển thị cảnh báo vượt trần / thiếu sàn định mức qua `render_callout`.

- [ ] **Step 2: Cập nhật `pages/11_Huong_Dan.py`**
  - Thêm `render_page_header("Hướng Dẫn Sử Dụng Hệ Thống", "Quy trình 5 bước, bộ 18 tiêu chí sư phạm và kinh nghiệm xếp lịch", icon="📖")`.
  - Phân chia tài liệu thành 4 tabs lớn: *Quy trình 5 bước*, *18 Tiêu chí ràng buộc*, *Mẹo giải bài toán khó*, *Câu hỏi thường gặp (FAQ)*.
  - Định dạng thẻ card cho từng tiêu chí và quy tắc.

- [ ] **Step 3: Kiểm tra cú pháp và chạy test**

Chạy: `pytest -k "not integration" tests/`
Kỳ vọng: PASS.

- [ ] **Step 4: Commit**

```bash
git add pages/00_Trang_chu.py pages/11_Huong_Dan.py
git commit -m "feat(ui): redesign dashboard and user guide pages with modern layout"
```

---

### Task 4: Thiết Kế Lại Nhóm 2 — Thiết Lập Dữ Liệu (6 Trang)

**Files:**
- Modify: `pages/01_Khai_bao.py`
- Modify: `pages/02_PhanCong.py`
- Modify: `pages/03_DinhMuc.py`
- Modify: `pages/04_GV_Ban.py`
- Modify: `pages/05_Khung_tiet.py`
- Modify: `pages/10_Cau_hinh_Xep_lich.py`

- [ ] **Step 1: Cập nhật `pages/01_Khai_bao.py`**
  - Thêm `render_page_header`.
  - Chuẩn hóa 3 tabs Lớp, Môn học, Giáo viên với các form nhập liệu trong card và badge phân loại (Môn nặng, GDTC, Chào cờ).
- [ ] **Step 2: Cập nhật `pages/02_PhanCong.py`**
  - Thêm `render_page_header`, bộ lọc nhanh theo khối/lớp, bảng phân công có tổng tiết rõ ràng.
- [ ] **Step 3: Cập nhật `pages/03_DinhMuc.py`**
  - Thêm `render_page_header`, thanh progress bar hiển thị tải định mức giáo viên, bảng màu trực quan (xanh, vàng, đỏ).
- [ ] **Step 4: Cập nhật `pages/04_GV_Ban.py`**
  - Thêm `render_page_header`, lưới ma trận báo bận Thứ 2 - Thứ 7 x Tiết 1 - 5 rõ ràng, trực quan.
- [ ] **Step 5: Cập nhật `pages/05_Khung_tiet.py`**
  - Thêm `render_page_header`, bảng khung tiết với các toggle Thứ 7 và ngày ngắn gọn gàng.
- [ ] **Step 6: Cập nhật `pages/10_Cau_hinh_Xep_lich.py`**
  - Thêm `render_page_header`, nhóm các tham số xếp lịch thành các Card chủ đề: *Môn nặng*, *GDTC & Chào cờ*, *Buổi nghỉ GV*, *Tiết lủng / Tiết lẻ*.
- [ ] **Step 7: Kiểm tra test suite**

Chạy: `pytest -k "not integration" tests/`
Kỳ vọng: PASS.

- [ ] **Step 8: Commit**

```bash
git add pages/01_Khai_bao.py pages/02_PhanCong.py pages/03_DinhMuc.py pages/04_GV_Ban.py pages/05_Khung_tiet.py pages/10_Cau_hinh_Xep_lich.py
git commit -m "feat(ui): redesign data setup pages with bento card layout"
```

---

### Task 5: Thiết Kế Lại Nhóm 3 — Xếp TKB & Xuất Excel Theo Tuần Tại Trang (`06_Xep_TKB.py` & `08_Lich_su_Tuan.py`)

**Files:**
- Modify: `pages/06_Xep_TKB.py`
- Modify: `pages/08_Lich_su_Tuan.py`

- [ ] **Step 1: Cập nhật `pages/06_Xep_TKB.py`**
  - Thêm `render_page_header("Xếp Thời Khóa Biểu Tự Động", "Tối ưu hóa toàn trường bằng bộ giải Google OR-Tools CP-SAT", badge="Trọng tâm", icon="🚀")`.
  - Console điều khiển: Nút chạy xếp lịch nổi bật, tham số thời gian và seed gọn gàng.
  - Solver progress monitor hiển thị trạng thái 2 Pass rõ ràng.
  - **Tích hợp khu vực Xuất Excel TKB trực tiếp**:
    - Chọn tuần xuất TKB (mặc định là tuần đang hiển thị).
    - Lựa chọn định dạng xuất: Toàn trường / Theo Lớp / Theo Giáo viên.
    - Nút `st.download_button` tải ngay file `.xlsx` chuẩn mà không cần qua trang khác.
  - Bảng TKB ma trận với màu sắc phân loại môn học đẹp mắt.
  - Bảng checklist thẩm định 18 tiêu chí (Validation checklist).
- [ ] **Step 2: Cập nhật `pages/08_Lich_su_Tuan.py`**
  - Thêm `render_page_header`, danh sách tuần đã lưu dạng timeline cards.
- [ ] **Step 3: Kiểm tra test**

Chạy: `pytest tests/`
Kỳ vọng: PASS.

- [ ] **Step 4: Commit**

```bash
git add pages/06_Xep_TKB.py pages/08_Lich_su_Tuan.py
git commit -m "feat(ui): redesign timetable solver page with direct weekly excel export"
```

---

### Task 6: Tái Cấu Trúc Trang Nhóm 4 — Quản Lý Dữ Liệu & Sao Lưu (`09_Import_Export.py`)

**Files:**
- Modify: `pages/09_Import_Export.py`

- [ ] **Step 1: Cập nhật `pages/09_Import_Export.py`**
  - Thêm `render_page_header("Quản Lý Dữ Liệu & Sao Lưu", "Nhập danh mục thiết lập ban đầu và sao lưu toàn diện cơ sở dữ liệu", icon="📁")`.
  - Thêm Banner Callout chỉ dẫn: "💡 Bạn muốn xuất Thời khóa biểu đã xếp? Hãy xuất trực tiếp tại trang **Xếp TKB tự động**." kèm nút link sang `pages/06_Xep_TKB.py`.
  - Bố cục 2 cột: Cột Trái (Nhập dữ liệu Excel/XLSM) | Cột Phải (Xuất dữ liệu cấu hình & Sao lưu DB).
- [ ] **Step 2: Kiểm tra test**

Chạy: `pytest tests/`
Kỳ vọng: PASS.

- [ ] **Step 3: Commit**

```bash
git add pages/09_Import_Export.py
git commit -m "feat(ui): reorient import/export page to system backup and config management"
```

---

### Task 7: Kiểm Thử Toàn Diện Hệ Thống (End-to-End Verification)

**Files:**
- Test: Toàn bộ test suite trong `tests/`
- Verification commands

- [ ] **Step 1: Chạy toàn bộ pytest suite**

Chạy: `pytest`
Kỳ vọng: Toàn bộ 40+ tests PASS, không có lỗi regression.

- [ ] **Step 2: Khởi chạy ứng dụng Streamlit và kiểm tra thực tế**

Chạy: `streamlit run app.py` (chạy thử nghiệm cục bộ)
Kiểm tra:
- Trang chủ mở ngay lập tức, không yêu cầu mật khẩu.
- Font Plus Jakarta Sans hiển thị sắc nét, các thẻ KPI hiển thị chuẩn.
- Vào trang `06_Xep_TKB.py`, kiểm tra nút xuất TKB theo tuần hoạt động trơn tru.
- Tất cả các trang hiển thị mượt mà không có lỗi runtime.
