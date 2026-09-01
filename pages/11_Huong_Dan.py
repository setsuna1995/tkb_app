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
        "- *Kép*: môn cần xếp 2 tiết liền nhau cùng buổi (VD Ngữ văn, Toán 2 tiết liên tiếp). Đây "
        "là ràng buộc CỨNG (không phải chỉ ưu tiên) -- thuật toán buộc phải ghép đủ thành khối 2 "
        "tiết liền kề (trừ đúng 1 tiết dư mỗi tuần nếu số tiết là số lẻ), và có thể không tìm được "
        "lời giải nếu dữ liệu (số tiết/tuần, khung tiết, giáo viên) quá chật để ghép hết -- xem "
        "thêm nguyên nhân (6) ở mục Xếp TKB tự động bên dưới.\n"
        "- *Nặng+Kép*: vừa nặng vừa kép.\n"
        "- *GDTC*: đúng 1 môn (Thể dục) -- có thể né 1 tiết cụ thể mỗi buổi (cấu hình riêng).\n"
        "- *HDTN*: đúng 1 môn (Hoạt động trải nghiệm) -- **bắt buộc phải có**, vì tiết chào cờ "
        "đầu tuần (mặc định Thứ 2, đổi được ở trang Cấu hình xếp lịch) và sinh hoạt lớp cuối "
        "tuần đều dùng môn này.\n\n"
        "**Tab Giáo viên** -- tên, chức vụ, và các cờ:\n"
        "- *Đi T2*: giáo viên bắt buộc có mặt chiều Thứ 2 (không được chọn làm buổi nghỉ).\n"
        "- *GVCN*: giáo viên chủ nhiệm -- cả buổi (thứ + sáng/chiều, không chỉ riêng 1 tiết) chứa "
        "tiết sinh hoạt lớp của đúng lớp họ chủ nhiệm sẽ không được chọn làm buổi nghỉ.\n"
        "- *Nghỉ mấy buổi/tuần*: để trống = dùng mặc định chung của trường (cấu hình ở trang "
        "Cấu hình xếp lịch, mục \"Mỗi giáo viên: nghỉ mấy buổi/tuần\"); điền số riêng (0-3) nếu "
        "giáo viên này cần nghỉ nhiều/ít hơn mức chung (VD giáo viên đang ốm cần nghỉ nhiều buổi "
        "hơn).\n"
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
        "Gán mỗi (môn, lớp) cho đúng 1 giáo viên dạy. Khuyến nghị gán đầy đủ trước khi xếp TKB "
        "thật, dù (môn, lớp) chưa gán vẫn xếp được nhờ \"giáo viên ảo\" tạm thời riêng cho ô đó "
        "(thuật toán vẫn chạy được, nhưng TKB ra sẽ thiếu tên giáo viên thật ở ô đó).\n\n"
        "Điền vào ô: gõ tên 1 giáo viên đã khai báo để gán, hoặc gõ thẳng 1 tên hoàn toàn mới -- "
        "khi bấm \"Lưu phân công\", hệ thống tự tạo luôn giáo viên mới với tên đó, không cần "
        "quay lại trang Khai báo tạo trước."
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
        "Trang này có 3 tab. Tab mặc định khi mở trang, **\"🗓️ Tích chọn theo Giáo viên\"**, cho "
        "tích chọn trực tiếp trên lưới 10 ô (Sáng/Chiều × Tiết 1-5) của TỪNG giáo viên, kèm vài "
        "mẫu chọn nhanh (VD nghỉ trọn 1 buổi/1 ngày). Tab **\"👥 Ma trận bận toàn trường\"** xem "
        "tổng hợp ai bận vào buổi/tiết nào trong tuần, toàn trường. Tab **\"📋 Bảng quy tắc chi "
        "tiết\"** (dạng thô) sửa trực tiếp danh sách quy tắc theo (thứ, buổi, tiết) -- mỗi phần "
        "có thể để `*` nghĩa là \"mọi giá trị\" (VD: bận mọi tiết Thứ 3 buổi sáng), tiện khi cần "
        "khai nhanh 1 quy tắc tổng quát mà lưới tích chọn không diễn đạt được. Dù khai ở tab nào, "
        "đây đều là ràng buộc CỨNG -- thuật toán sẽ không bao giờ xếp giáo viên đó dạy vào các ô "
        "đã khai bận."
    )

with st.expander("🗓️ Khung tiết"):
    st.markdown(
        "Cấu hình số tiết buổi sáng/buổi chiều mỗi lớp học trong tuần (khung tiết khác nhau giữa "
        "các lớp là bình thường, VD lớp học 2 buổi/ngày vs lớp chỉ học buổi sáng). Trang này tự "
        "động trừ các buổi chiều bị khoá cứng toàn trường (cấu hình ở trang Cấu hình xếp lịch) "
        "khỏi cột \"Tổng ô/tuần\" -- danh sách đầy đủ các buổi đó xem ở khung \"📐 Quy tắc xếp "
        "lịch\" trong thanh bên, không phải ở đây. Trang cũng kiểm tra khung tiết có đủ chỗ so "
        "với tổng số tiết cần xếp hay không."
    )

with st.expander("⚙️ Cấu hình xếp lịch"):
    st.markdown(
        "Các ràng buộc \"lựa chọn của trường\" -- trường khác có thể cấu hình khác, không phải "
        "hằng số cố định của thuật toán. Giá trị mặc định đúng bằng hành vi trước khi có trang "
        "này.\n\n"
        "**Vị trí cố định & Khung tiết GDTC (Thể dục)**\n"
        "- *GDTC - Khung tiết cho phép*: Mặc định Thể dục chỉ được xếp vào **Tiết 1, 2, 3, 4 buổi sáng** (tránh tiết 5 trưa nắng) "
        "và **Tiết 2, 3 buổi chiều** (tránh tiết đầu chiều nắng gắt).\n"
        "- *GDTC không xếp 2 ngày liên tiếp*: GDTC của mỗi lớp luôn được xếp cách ngày (không bao giờ rơi vào 2 ngày liền kề).\n"
        "- *Chào cờ - Thứ*: chọn thứ nào trong tuần xếp môn HDTN (chào cờ). *Chào cờ - Tiết*: "
        "luôn cố định ở Tiết 1 buổi sáng, không chỉnh được (cơ chế ghim tiết hiện tại chỉ hoạt "
        "động đúng ở tiết đầu buổi sáng).\n\n"
        "**Ngưỡng số lượng**\n"
        "- *Môn nặng: tối đa mấy tiết liên tiếp*: giới hạn số tiết môn \"Nặng\" liên tiếp trong "
        "1 buổi.\n"
        "- *Mỗi giáo viên: tối đa mấy tiết/buổi*: trần số tiết 1 giáo viên dạy trong 1 buổi.\n"
        "- *Mỗi giáo viên: nghỉ mấy buổi/tuần*: mức nghỉ MẶC ĐỊNH áp dụng cho mọi giáo viên -- "
        "xem trang Khai báo để đặt riêng cho 1 giáo viên cụ thể.\n"
        "- *Môn nặng: ưu tiên (không bắt buộc) mấy tiết đầu buổi sáng (0 = tắt)*: ràng buộc MỀM "
        "-- khi bật (N > 0), môn \"Nặng\" được ưu tiên (không cấm tuyệt đối môn khác) xếp vào N "
        "tiết đầu buổi sáng. Ưu tiên mềm này thể hiện rõ nhất khi xếp TKB tự động trên tuần TRỐNG "
        "(chưa có dữ liệu cũ); khi xếp lại đè lên TKB đã có sẵn, cơ chế \"giữ nguyên tiết cũ\" "
        "luôn được ưu tiên hơn nên hiệu ứng sẽ khó thấy.\n"
        "- *Môn Nặng: bắt buộc xếp buổi sáng (không được xếp chiều)*: khác với ô ưu tiên MỀM ở "
        "trên, đây là ràng buộc CỨNG -- khi bật, môn \"Nặng\" (và \"Nặng+Kép\") sẽ KHÔNG BAO GIỜ "
        "được xếp vào buổi chiều (môn không Nặng không bị ảnh hưởng). Trường chỉ học 1 buổi/ngày "
        "không bị tác động. Ràng buộc này khá chặt, đặc biệt khi kết hợp với yêu cầu ghép khối môn "
        "Kép ở trên -- có thể khiến \"Xếp TKB tự động\" khó/không tìm được lời giải nếu khối tiết "
        "sáng/chiều của trường quá chật -- xem thêm nguyên nhân (7) ở mục Xếp TKB tự động bên "
        "dưới.\n\n"
        "**Buổi/ngày khoá cứng**\n"
        "- *Buổi cấm chọn làm buổi nghỉ GV*: các (thứ, buổi) không bao giờ được chọn làm buổi "
        "nghỉ của bất kỳ giáo viên nào (kể cả giáo viên có ghim nghỉ riêng ở trang Khai báo -- "
        "một ghim trùng ô cấm sẽ bị bỏ qua).\n"
        "- *Thứ có buổi chiều luôn trống*: các thứ mà buổi chiều luôn để trống toàn trường (dành "
        "ôn bồi dưỡng/phụ đạo ngoài TKB, không phải buổi nghỉ giáo viên được chọn).\n\n"
        "**Ưu tiên buổi (mềm, không bắt buộc)**\n"
        "- *Môn ưu tiên buổi chiều*: chọn các môn được ưu tiên (không cấm tuyệt đối môn khác) "
        "xếp vào buổi chiều -- để trống = tắt tính năng này.\n\n"
        "**Chất lượng lịch giáo viên**\n"
        "- *Tránh tiết trống / lủng của GV trong buổi*: không để GV dạy tiết 1 nghỉ 2-3 rồi mới dạy tiết 4. "
        "Thuật toán ưu tiên xếp các tiết của GV liền mạch nhau trong cùng buổi.\n"
        "- *Tránh GV đi dạy 1 tiết/ngày hoặc sáng 1 + chiều 1*: tránh để GV đến trường chỉ dạy 1 tiết lẻ cả ngày, "
        "hoặc bị xé lẻ sáng 1 tiết và chiều 1 tiết đi lại vất vả. Khuyến khích gom từ 2 tiết trở lên trong cùng 1 buổi.\n"
        "- *Cân đối tiết buổi chiều cho GV*: tránh để một số GV được nghỉ 100% các buổi chiều trong khi dạy lớp 2 buổi/ngày.\n"
        "- *Buổi sáng bắt buộc toàn thể GV đi làm / có mặt*: các buổi sáng (mặc định Thứ 2, Thứ 5, Thứ 6) toàn thể GV có mặt, "
        "cấm chọn làm buổi nghỉ và ưu tiên xếp lịch dạy.\n\n"
        "**Ràng buộc môn/lớp theo buổi cụ thể (tuỳ chọn)**\n"
        "- Ràng buộc CỨNG, tổng quát: chọn 1 **Môn** (trừ HDTN, vì môn này đã có vị trí ghim cố "
        "định riêng), 1 số **Lớp áp dụng**, và tập **\"Chỉ được xếp vào các (Thứ, Buổi) này\"** "
        "cho các lớp này. VD: \"Nhạc, các lớp khối 6 và 9, chỉ chiều Thứ 3 và chiều Thứ 5\" -- dùng "
        "khi có chỉ đạo hành chính cụ thể (VD cần buổi sáng trống cho họp/khách). Vì đây là ràng "
        "buộc CỨNG, tạo luật quá chặt so với số tiết/tuần cần xếp có thể khiến \"Xếp TKB tự "
        "động\" không tìm được lời giải -- xem thêm nguyên nhân (5) ở mục Xếp TKB tự động bên "
        "dưới."
    )

with st.expander("🚀 Xếp TKB tự động"):
    st.markdown(
        "Trước khi chạy: chọn **Tuần** (Chẵn/Lẻ) ở đầu trang -- quyết định dùng bộ định mức "
        "tiết/tuần nào (chẵn hay lẻ) cho lần xếp này.\n\n"
        "**Tuần này tổ chức chuyên đề**: tick nếu tuần này HDTN không chạy theo lịch thường (chào "
        "cờ đầu tuần + sinh hoạt lớp cuối tuần), mà dồn cả 3 tiết HDTN thành 1 khối liền kề (giống "
        "cơ chế Kép nhưng 3 tiết thay vì 2), áp dụng cho TOÀN TRƯỜNG, và bỏ ghim cố định chào cờ/"
        "SHL trong lần xếp này. Chỉ áp dụng cho lần chạy xếp TKB này, không đổi vĩnh viễn cách xếp "
        "HDTN các tuần sau.\n\n"
        "Chạy thuật toán xếp thời khóa biểu cho cả trường theo dữ liệu đã khai báo và các quy "
        "tắc đã cấu hình. Thuật toán thử nhiều phương án ngẫu nhiên, giữ lại phương án ít thay "
        "đổi nhất so với TKB tuần trước (nếu có).\n\n"
        "Sau khi xếp xong, trang hiển thị bảng **\"Kiểm tra định mức (thực tế − định mức, kỳ "
        "vọng 0)\"** -- mỗi ô là (thực tế − định mức) của 1 (môn, lớp), ô khác 0 được tô đỏ và nên "
        "xem lại (0 nghĩa là đúng như kỳ vọng).\n\n"
        "**Quan trọng**: kết quả xếp CHƯA được lưu, chỉ là bản xem trước. Phải bấm nút **\"✅ "
        "Chấp nhận và lưu làm lịch chính thức\"** thì TKB mới thực sự được ghi vào hệ thống -- "
        "rời trang mà chưa bấm nút này sẽ mất toàn bộ kết quả vừa xếp.\n\n"
        "Nếu báo **\"Không xếp được\"**, nguyên nhân hay gặp:\n"
        "1. GV HDTN (GVCN) trùng nhau giữa 2 lớp -- chào cờ và sinh hoạt lớp diễn ra đồng thời "
        "nên mỗi lớp cần một giáo viên chủ nhiệm HDTN riêng.\n"
        "2. Giáo viên bận cấm quá nhiều giờ của một giáo viên tải nặng.\n"
        "3. Định mức số tiết vượt khả năng khung tiết (quá nhiều tiết cần xếp so với số ô trống "
        "trong tuần).\n"
        "4. Cấu hình nghỉ riêng của 1 giáo viên quá chặt -- đặt \"Nghỉ mấy buổi/tuần\" cao kết "
        "hợp ghim buổi/ngày nghỉ cố định (trang Khai báo) khiến các lớp giáo viên đó dạy không "
        "còn đủ ô trống để xếp đủ số tiết.\n"
        "5. Luật gán môn/lớp theo buổi (trang Cấu hình xếp lịch) quá chặt so với số tiết/tuần "
        "cần xếp cho môn/lớp đó.\n"
        "6. Môn Kép (hoặc \"Nặng+Kép\") bắt buộc ghép đủ thành khối 2 tiết liền kề (chỉ được dư "
        "đúng 1 tiết lẻ/tuần nếu số tiết là số lẻ) -- dữ liệu quá chật (số tiết/tuần, khung tiết, "
        "giáo viên) khiến thuật toán không ghép được hết dù đã thử lại nhiều lần.\n"
        "7. Bật \"Môn Nặng: bắt buộc xếp buổi sáng\" (trang Cấu hình xếp lịch) khiến buổi sáng quá "
        "tải, nhất là khi kết hợp với yêu cầu ghép khối môn Kép ở (6).\n\n"
        "Thử giảm bớt ràng buộc (nới lỏng luật môn/lớp, giảm số buổi nghỉ riêng/bận, tăng khung "
        "tiết, hoặc tắt bớt \"Môn Nặng: bắt buộc xếp buổi sáng\") rồi chạy lại."
    )

with st.expander("⚖️ Cân bằng tải giáo viên"):
    st.markdown(
        "Đây là công cụ **Đề xuất và Tự động Điều chỉnh Phân công** dựa trên định mức tiết/tuần:\n\n"
        "1. **Nguyên tắc trọn gói theo Lớp**: Mọi điều chỉnh đều chuyển nguyên vẹn từng **Lớp cho Môn học đó** "
        "(toàn bộ số tiết cả tuần Chẵn và tuần Lẻ), tuyệt đối không chia cắt lẻ từng tiết nhằm đảm bảo tính đồng bộ hoàn hảo.\n"
        "2. **Hình thức cân bằng linh hoạt**:\n"
        "   - **Chuyển 1 lớp (Transfer)**: Chuyển trọn gói 1 lớp từ GV vượt trần sang GV còn dư địa (ưu tiên GV dưới sàn).\n"
        "   - **Đổi chéo 2 lớp (Class Swap)**: Hoán đổi 2 lớp cùng môn giữa 2 GV khi chênh lệch tải nhỏ (1–2 tiết) mà chuyển 1 lớp nguyên vẹn không khả thi.\n"
        "3. **Áp dụng 1-click vào Phân công**: Bạn có thể chọn các đề xuất phù hợp và bấm **\"Áp dụng các đề xuất đã chọn\"** "
        "hoặc **\"Áp dụng TẤT CẢ đề xuất\"** để hệ thống tự động lưu trực tiếp vào cơ sở dữ liệu Phân công chuyên môn mà không cần phải đi sửa tay từng ô."
    )

with st.expander("🕘 Lịch sử tuần"):
    st.markdown(
        "Xem lại các tuần TKB đã xếp trước đó: số thứ tự tuần, seed dùng để xếp, tuần chẵn/lẻ, "
        "và thời điểm tạo -- hữu ích khi cần đối chiếu hoặc xếp lại một tuần cũ (chọn tuần rồi "
        "\"Nạp seed của tuần đã chọn\", sang trang Xếp TKB tự động để chạy lại). Số ô thay đổi so "
        "với lần xếp gần nhất KHÔNG nằm ở trang này -- xem ở mục \"Lần xếp gần nhất\" trên trang "
        "**Trang chủ**."
    )

with st.expander("📁 Nhập / Xuất Excel"):
    st.markdown(
        "**Nhập**: đọc dữ liệu từ file Excel theo đúng cấu trúc workbook gốc (lớp, môn, giáo "
        "viên, phân công, định mức...) để không phải khai báo lại từ đầu.\n\n"
        "**Xuất TKB**: trên trang này, xuất TKB hiện tại (hoặc theo lần xếp gần nhất đã chấp "
        "nhận) ra file Excel để in/chia sẻ -- không phải bản sao lưu đầy đủ.\n\n"
        "**Xuất sao lưu**: nút **\"📥 Xuất Excel (sao lưu)\"** nằm ở THANH BÊN (sidebar), hiển thị "
        "trên MỌI trang của app (kể cả trang Hướng dẫn này) -- không phải một nút trên trang Nhập "
        "/ Xuất Excel. Bấm bất cứ lúc nào, từ bất kỳ trang nào, để tải file sao lưu mới nhất.\n\n"
        "File sao lưu ghi lại: lớp, môn, giáo viên, phân công chuyên môn, định mức tiết/tuần, "
        "bảng giảm trừ theo chức vụ (kèm 2 cờ Đi T2/GVCN), giáo viên bận, khung tiết, TKB nháp "
        "hiện tại, và lịch sử tuần (seed + tuần chẵn/lẻ). File sao lưu **KHÔNG** gồm: toàn bộ cấu "
        "hình ở trang **Cấu hình xếp lịch** (né tiết, ngưỡng số lượng, buổi/ngày khoá cứng, ưu "
        "tiên buổi, và các luật ràng buộc môn/lớp theo buổi cụ thể), lẫn 3 lựa chọn nghỉ riêng "
        "của từng giáo viên ở trang Khai báo (nghỉ mấy buổi/tuần riêng, ghim nghỉ trọn ngày, ghim "
        "nghỉ chiều cố định). Sau khi khôi phục từ file sao lưu, phải tự cấu hình lại 3 phần này "
        "bằng tay."
    )

sidebar_backup_export(conn)
sidebar_fixed_rules(conn)
sidebar_school_switcher()
