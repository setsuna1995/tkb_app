# Trang Hướng dẫn sử dụng Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a single in-app "Hướng dẫn sử dụng" page that walks a new user through the whole app, in the order they'd actually use it — no such page exists today (confirmed absent in the spec's exploration).

**Architecture:** A static Streamlit page (`pages/11_Huong_Dan.py`), no DB reads beyond what the shared page boilerplate already needs for the sidebar. Content is grouped into `st.expander` sections, one per real workflow step, matching the app's actual page order in `app.py`. Registered as its own entry in the existing "Tổng quan" nav group, next to "Trang chủ".

**Tech Stack:** Python 3, Streamlit.

**Spec:** `docs/superpowers/specs/2026-08-29-rang-buoc-xep-lich-v2-design.md` (mục "Kiến trúc" → "4. Trang Hướng dẫn sử dụng")

## Global Constraints

- This plan should be applied **last**, after the companion "rang-buoc-mem-mon-buoi" (Plan A), "gv-nghi-rieng" (Plan B), and "luat-mon-lop-buoi" (Plan C) plans, so the guide's "Cấu hình xếp lịch" and "Khai báo" sections can describe the final field set accurately instead of a moving target.
- Purely additive — no existing file's *behavior* changes (only `app.py`'s `pages` dict gains one new entry).
- No placeholder sections ("TBD", "coming soon", etc.) — every expander must have real, complete content for the page it describes.
- Content stays consistent with terminology already used in the app's own UI labels (e.g. "Vai trò", "Đi T2", "GVCN", "buổi/tiết", "Sáng/Chiều") rather than inventing new terms.

---

## Task 1: Create the guide page and register it in navigation

**Files:**
- Create: `pages/11_Huong_Dan.py`
- Modify: `app.py:9-12` (register the new page in the "Tổng quan" group)

**Interfaces:**
- Consumes: `ui_common.get_conn`/`require_auth`/`require_school`/`sidebar_backup_export`/`sidebar_fixed_rules`/`sidebar_school_switcher` (existing, same boilerplate every other page uses)

No automated test — this is a static-content Streamlit page, matching this repo's existing convention (pages have no dedicated test files). Verify manually in Step 3.

- [ ] **Step 1: Create the page**

Create `pages/11_Huong_Dan.py`:

```python
import streamlit as st

from ui_common import get_conn, require_auth, require_school, sidebar_backup_export, sidebar_fixed_rules, \
    sidebar_school_switcher

require_auth()
school_slug = require_school()
conn = get_conn(school_slug)

st.title("Hướng dẫn sử dụng")
st.caption(
    "Thứ tự dưới đây đúng theo luồng làm việc thực tế: khai báo dữ liệu trước, "
    "cấu hình quy tắc xếp lịch, rồi mới xếp thời khóa biểu (TKB)."
)

with st.expander("🗺️ Tổng quan luồng làm việc", expanded=True):
    st.markdown(
        "1. **Khai báo Lớp / Môn / Giáo viên** -- nhập danh sách lớp, môn học, giáo viên.\n"
        "2. **Phân công chuyên môn** -- gán mỗi (môn, lớp) cho 1 giáo viên dạy.\n"
        "3. **Định mức tiết / tuần** -- số tiết/tuần mỗi (môn, lớp) cần xếp, và bảng giảm trừ "
        "tiết dạy theo chức vụ (GVCN, Tổ trưởng...).\n"
        "4. **Giáo viên bận** -- khai báo khung giờ 1 giáo viên KHÔNG thể dạy (bận việc khác).\n"
        "5. **Khung tiết** -- số tiết sáng/chiều mỗi lớp học trong tuần.\n"
        "6. **Cấu hình xếp lịch** -- các quy tắc \"lựa chọn của trường\" (né tiết, số buổi nghỉ GV, "
        "môn ưu tiên buổi nào...).\n"
        "7. **Xếp TKB tự động** -- chạy thuật toán, tạo thời khóa biểu cho cả trường.\n"
        "8. **Cân bằng tải giáo viên** -- kiểm tra/điều chỉnh số tiết mỗi GV sau khi xếp.\n"
        "9. **Lịch sử tuần** -- xem lại các tuần TKB đã xếp trước đó.\n"
        "10. **Nhập / Xuất Excel** -- nhập dữ liệu từ file Excel cũ, hoặc xuất TKB ra Excel."
    )

with st.expander("🏫 Khai báo Lớp / Môn / Giáo viên"):
    st.markdown(
        "Trang này có 3 tab:\n\n"
        "**Tab Lớp học** -- tên lớp và thứ tự hiển thị. Xoá 1 dòng = xoá lớp đó khỏi hệ thống "
        "(chỉ nên làm khi lớp không còn dữ liệu phân công/TKB liên quan).\n\n"
        "**Tab Môn học** -- tên môn và **Vai trò**, quyết định cách thuật toán xử lý môn đó:\n"
        "- *Thường*: không có ràng buộc đặc biệt.\n"
        "- *Nặng*: môn kiến thức nặng (Toán, Lý, Hoá...) -- bị giới hạn số tiết liên tiếp trong "
        "1 buổi (cấu hình ở trang Cấu hình xếp lịch), và có thể được ưu tiên (không bắt buộc) "
        "vào các tiết đầu buổi sáng nếu trường bật tính năng đó.\n"
        "- *Kép*: môn cần xếp 2 tiết liền nhau cùng buổi (VD Ngữ văn, Toán 2 tiết liên tiếp).\n"
        "- *Nặng+Kép*: vừa nặng vừa kép.\n"
        "- *GDTC*: đúng 1 môn (Thể dục) -- có thể né 1 tiết cụ thể mỗi buổi (cấu hình riêng).\n"
        "- *HDTN*: đúng 1 môn (Hoạt động trải nghiệm) -- **bắt buộc phải có**, vì tiết chào cờ "
        "Thứ 2 và sinh hoạt lớp cuối tuần đều dùng môn này.\n\n"
        "**Tab Giáo viên** -- tên, chức vụ, và các cờ:\n"
        "- *Đi T2*: giáo viên bắt buộc có mặt chiều Thứ 2 (không được chọn làm buổi nghỉ).\n"
        "- *GVCN*: giáo viên chủ nhiệm -- tiết sinh hoạt lớp của đúng lớp họ chủ nhiệm sẽ không "
        "bị chọn làm buổi nghỉ.\n"
        "- *Nghỉ mấy buổi/tuần*: để trống = dùng mặc định chung của trường (cấu hình ở trang "
        "Cấu hình xếp lịch); điền số riêng nếu giáo viên này cần nghỉ nhiều/ít hơn mức chung "
        "(VD giáo viên đang ốm cần nghỉ nhiều buổi hơn).\n"
        "- *Nghỉ trọn ngày - Thứ*: ghim CẢ NGÀY (sáng + chiều) của 1 thứ cụ thể làm buổi nghỉ "
        "cố định cho giáo viên này -- đây là trường hợp đặc biệt duy nhất được nghỉ trọn ngày, "
        "còn lại quy tắc chung là mỗi buổi nghỉ rơi vào 1 ngày khác nhau.\n"
        "- *Nghỉ chiều cố định - Thứ*: ghim 1 buổi CHIỀU cụ thể làm buổi nghỉ cố định (dùng kèm "
        "hoặc độc lập với ghim nghỉ trọn ngày ở trên).\n\n"
        "Nếu chọn ghim vào 1 thứ đã bị cấm ở \"Buổi cấm chọn làm buổi nghỉ GV\" (trang Cấu hình "
        "xếp lịch), hoặc trùng với \"Đi T2\", hệ thống sẽ báo lỗi và không lưu."
    )

with st.expander("📋 Phân công chuyên môn"):
    st.markdown(
        "Gán mỗi (môn, lớp) cho đúng 1 giáo viên dạy. Đây là dữ liệu bắt buộc để thuật toán biết "
        "ai dạy môn nào ở lớp nào -- (môn, lớp) chưa gán giáo viên vẫn xếp được (hệ thống tự tạo "
        "một giáo viên \"ảo\" riêng cho ô đó), nhưng nên gán đầy đủ trước khi xếp TKB thật."
    )

with st.expander("📊 Định mức tiết / tuần"):
    st.markdown(
        "Nhập số tiết/tuần mỗi (môn, lớp) cần xếp -- theo tuần **chẵn** và **lẻ** riêng (một số "
        "môn có số tiết khác nhau giữa 2 loại tuần). Trang này cũng có bảng \"giảm trừ theo chức "
        "vụ\" -- số tiết dạy được giảm cho GVCN, Tổ trưởng, Tổ phó... để tính đúng định mức còn "
        "lại (tải dạy) của từng giáo viên."
    )

with st.expander("🚫 Giáo viên bận"):
    st.markdown(
        "Khai báo khung giờ 1 giáo viên KHÔNG thể dạy (bận việc riêng, dạy trường khác...), theo "
        "(thứ, buổi, tiết) -- mỗi phần có thể để `*` nghĩa là \"mọi giá trị\" (VD: bận mọi tiết "
        "Thứ 3 buổi sáng). Đây là ràng buộc CỨNG -- thuật toán sẽ không bao giờ xếp giáo viên đó "
        "dạy vào các ô đã khai bận."
    )

with st.expander("🗓️ Khung tiết"):
    st.markdown(
        "Cấu hình số tiết buổi sáng/buổi chiều mỗi lớp học trong tuần (khung tiết khác nhau giữa "
        "các lớp là bình thường, VD lớp học 2 buổi/ngày vs lớp chỉ học buổi sáng). Trang này cũng "
        "hiển thị các buổi chiều bị khoá cứng toàn trường (cấu hình ở trang Cấu hình xếp lịch) và "
        "kiểm tra khung tiết có đủ chỗ so với tổng số tiết cần xếp hay không."
    )

with st.expander("⚙️ Cấu hình xếp lịch"):
    st.markdown(
        "Các ràng buộc \"lựa chọn của trường\" -- trường khác có thể cấu hình khác, không phải "
        "hằng số cố định của thuật toán.\n\n"
        "**Vị trí cố định**\n"
        "- *GDTC né tiết*: Thể dục sẽ không bao giờ được xếp vào tiết này.\n"
        "- *Chào cờ - Thứ / Tiết*: ô cố định xếp môn HDTN (chào cờ) mỗi tuần.\n\n"
        "**Ngưỡng số lượng**\n"
        "- *Môn nặng: tối đa mấy tiết liên tiếp*: giới hạn số tiết môn \"Nặng\" liên tiếp trong "
        "1 buổi.\n"
        "- *Mỗi giáo viên: tối đa mấy tiết/buổi*: trần số tiết 1 giáo viên dạy trong 1 buổi.\n"
        "- *Mỗi giáo viên: nghỉ mấy buổi/tuần*: mức nghỉ MẶC ĐỊNH áp dụng cho mọi giáo viên -- "
        "xem trang Khai báo để đặt riêng cho 1 giáo viên cụ thể.\n"
        "- *Môn nặng: ưu tiên mấy tiết đầu buổi sáng*: ràng buộc MỀM (không bắt buộc) -- 0 = tắt. "
        "Khi bật, môn \"Nặng\" được ưu tiên (không cấm tuyệt đối môn khác) xếp vào N tiết đầu "
        "buổi sáng.\n\n"
        "**Buổi/ngày khoá cứng**\n"
        "- *Buổi cấm chọn làm buổi nghỉ GV*: các (thứ, buổi) không bao giờ được chọn làm buổi "
        "nghỉ của bất kỳ giáo viên nào (kể cả giáo viên có ghim nghỉ riêng ở trang Khai báo -- "
        "một ghim trùng ô cấm sẽ bị bỏ qua).\n"
        "- *Thứ có buổi chiều luôn trống*: các thứ mà buổi chiều luôn để trống toàn trường (dành "
        "ôn bồi dưỡng/phụ đạo ngoài TKB, không phải buổi nghỉ giáo viên được chọn).\n\n"
        "**Ưu tiên buổi (mềm, không bắt buộc)**\n"
        "- Chọn các môn được ưu tiên (không cấm tuyệt đối môn khác) xếp vào buổi chiều -- để "
        "trống = tắt tính năng này.\n\n"
        "**Ràng buộc môn/lớp theo buổi cụ thể (tuỳ chọn)**\n"
        "- Ràng buộc CỨNG, tổng quát: chọn 1 môn (trừ HDTN, vì môn này đã có vị trí ghim cố định "
        "riêng), 1 số lớp áp dụng, và tập (thứ, buổi) môn đó CHỈ được xếp vào cho các lớp này. "
        "VD: \"Nhạc, các lớp khối 6 và 9, chỉ chiều Thứ 3 và chiều Thứ 5\" -- dùng khi có chỉ đạo "
        "hành chính cụ thể (VD cần buổi sáng trống cho họp/khách). Vì đây là ràng buộc CỨNG, tạo "
        "luật quá chặt so với số tiết/tuần cần xếp có thể khiến \"Xếp TKB tự động\" không tìm "
        "được lời giải -- xem thêm nguyên nhân (4) ở mục Xếp TKB tự động bên dưới."
    )

with st.expander("🚀 Xếp TKB tự động"):
    st.markdown(
        "Chạy thuật toán xếp thời khóa biểu cho cả trường theo dữ liệu đã khai báo và các quy "
        "tắc đã cấu hình. Thuật toán thử nhiều phương án ngẫu nhiên, giữ lại phương án ít thay "
        "đổi nhất so với TKB tuần trước (nếu có).\n\n"
        "Nếu báo **\"Không xếp được\"**, nguyên nhân hay gặp:\n"
        "1. GV HDTN (GVCN) trùng nhau giữa 2 lớp -- chào cờ và sinh hoạt lớp diễn ra đồng thời "
        "nên mỗi lớp cần một giáo viên chủ nhiệm HDTN riêng.\n"
        "2. Giáo viên bận cấm quá nhiều giờ của một giáo viên tải nặng.\n"
        "3. Định mức số tiết vượt khả năng khung tiết (quá nhiều tiết cần xếp so với số ô trống "
        "trong tuần).\n"
        "4. Luật gán môn/lớp theo buổi (trang Cấu hình xếp lịch) quá chặt so với số tiết/tuần "
        "cần xếp cho môn/lớp đó.\n\n"
        "Thử giảm bớt ràng buộc (nới lỏng luật môn/lớp, giảm số buổi bận, hoặc tăng khung tiết) "
        "rồi chạy lại."
    )

with st.expander("⚖️ Cân bằng tải giáo viên"):
    st.markdown(
        "Sau khi xếp TKB, dùng trang này để kiểm tra số tiết thực tế mỗi giáo viên đang dạy so "
        "với định mức, và điều chỉnh nếu có chênh lệch lớn giữa các giáo viên."
    )

with st.expander("🕘 Lịch sử tuần"):
    st.markdown(
        "Xem lại các tuần TKB đã xếp trước đó (seed dùng để xếp, tuần chẵn/lẻ, số ô thay đổi so "
        "với tuần trước) -- hữu ích khi cần đối chiếu hoặc xếp lại một tuần cũ."
    )

with st.expander("📁 Nhập / Xuất Excel"):
    st.markdown(
        "**Nhập**: đọc dữ liệu từ file Excel theo đúng cấu trúc workbook gốc (lớp, môn, giáo "
        "viên, phân công, định mức...) để không phải khai báo lại từ đầu.\n\n"
        "**Xuất**: xuất TKB hiện tại (hoặc sao lưu toàn bộ dữ liệu trường) ra file Excel."
    )

sidebar_backup_export(conn)
sidebar_fixed_rules(conn)
sidebar_school_switcher()
```

- [ ] **Step 2: Register the page in navigation**

In `app.py`, add the new page to the end of the `"Tổng quan"` list (currently lines 10-12):

```python
    "Tổng quan": [
        st.Page("pages/00_Trang_chu.py", title="Trang chủ", icon="🏠", default=True),
        st.Page("pages/11_Huong_Dan.py", title="Hướng dẫn sử dụng", icon="📖"),
    ],
```

- [ ] **Step 3: Manually verify**

Run: `streamlit run app.py`

- Log in, select/create a school, confirm "Hướng dẫn sử dụng" appears in the "Tổng quan" nav group with a 📖 icon.
- Open the page — confirm the "🗺️ Tổng quan luồng làm việc" section is expanded by default and every other section is collapsed.
- Expand every section one by one — confirm no crash, no leftover placeholder text, and that the "Cấu hình xếp lịch" section's field list matches what's actually on that page (re-check after Plans A/B/C have landed, since this section names fields those plans introduce).
- Confirm the sidebar (backup/export, "📐 Quy tắc xếp lịch", school switcher) renders normally, same as any other page.

- [ ] **Step 4: Run the full test suite one final time**

Run: `python -m pytest -v`
Expected: PASS — entire suite (this task touches no function any test calls directly).

- [ ] **Step 5: Commit**

```bash
git add pages/11_Huong_Dan.py app.py
git commit -m "feat: add Hướng dẫn sử dụng page covering the full app workflow"
```

---

## Self-Review Notes

- **Spec coverage:** Spec section "4. Trang Hướng dẫn sử dụng" is fully covered — every listed topic (tổng quan luồng, Khai báo including the 3 new teacher fields, Phân công/Định mức/GV bận/Khung tiết, Cấu hình xếp lịch including every old and new field plus the subject/class rule engine, Xếp TKB tự động including the 4th failure cause, Cân bằng tải/Lịch sử tuần/Import-Export) has a corresponding expander with real content, not a placeholder.
- **Placeholder scan:** No "TBD"/"coming soon" text anywhere in the page content; every expander has complete, specific Vietnamese prose.
- **Type consistency:** N/A — this plan introduces no new functions, classes, or shared data shapes; it only adds a Streamlit page and one `app.py` nav entry, both verified against the actual current file contents (`app.py:9-12` read directly, boilerplate pattern matched against `pages/00_Trang_chu.py:1-12`).
