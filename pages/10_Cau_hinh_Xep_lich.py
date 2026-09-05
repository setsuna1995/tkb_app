import streamlit as st

from core import frame as frame_mod
from core.models import (
    ROLE_GDTC, ROLE_HDTN, ROLE_KEP, ROLE_NANG, ROLE_NANG_KEP, ROLE_THUONG,
    SchedulingConfig, WEEKDAY_NAMES, WEEKDAYS,
)
from data import repository as repo
from ui_common import get_conn, require_auth, require_school, sidebar_backup_export, sidebar_fixed_rules, \
    sidebar_school_switcher

require_auth()
school_slug = require_school()
conn = get_conn(school_slug)
st.title("Cấu hình xếp lịch")
st.caption(
    "Các ràng buộc dưới đây là lựa chọn của từng trường, khác trường có thể cấu hình khác. "
    "Giá trị mặc định đúng bằng hành vi trước khi có trang này."
)

config = repo.get_scheduling_config(conn)
max_p = frame_mod.MAX_PERIODS_PER_SESSION

st.subheader("Vị trí cố định & Khung tiết GDTC (Thể dục)")
c1, c2 = st.columns(2)
gdtc_morning_allowed = c1.multiselect(
    "GDTC: Các tiết được phép xếp buổi Sáng",
    options=list(range(1, max_p + 1)),
    default=[p for p in config.gdtc_morning_allowed_periods if p <= max_p],
    help="Mặc định: Tiết 1, 2, 3, 4 (tránh tiết 5 trưa muộn trời nắng).",
)
gdtc_afternoon_allowed = c2.multiselect(
    "GDTC: Các tiết được phép xếp buổi Chiều",
    options=list(range(1, max_p + 1)),
    default=[p for p in config.gdtc_afternoon_allowed_periods if p <= max_p],
    help="Mặc định: Tiết 2, 3 (tránh tiết đầu chiều trời nắng gắt).",
)
c_cc1, c_cc2 = st.columns(2)
chao_co_weekday = c_cc1.selectbox(
    "Chào cờ - Thứ", WEEKDAYS, index=WEEKDAYS.index(config.chao_co_weekday),
    format_func=lambda w: WEEKDAY_NAMES[w],
)
c_cc2.number_input(
    "Chào cờ - Tiết (buổi sáng)", 1, 1, 1, disabled=True,
    help="Cố định ở Tiết 1 -- cơ chế ghim tiết hiện tại chỉ hoạt động đúng ở tiết đầu buổi sáng.",
)
chao_co_period = 1
gdtc_avoid_period = config.gdtc_avoid_period

st.subheader("Ngưỡng số lượng")
c3, c4, c5 = st.columns(3)
max_heavy_consecutive = c3.number_input(
    "Môn nặng: tối đa mấy tiết liên tiếp", 1, max_p, config.max_heavy_consecutive,
    help="Toán/Lý/Hoá (và các môn đánh dấu \"Nặng\") không được xếp quá số tiết này liên tiếp trong 1 buổi.",
)
max_periods_per_session = c4.number_input(
    "Mỗi giáo viên: tối đa mấy tiết/buổi", 1, max_p, config.max_periods_per_session,
)
teacher_off_sessions_per_week = c5.number_input(
    "Mỗi giáo viên: nghỉ mấy buổi/tuần", 0, 3, config.teacher_off_sessions_per_week,
)

heavy_subject_priority_periods = st.number_input(
    "Môn nặng: ưu tiên (không bắt buộc) mấy tiết đầu buổi sáng (0 = tắt)", 0, max_p,
    config.heavy_subject_priority_periods,
    help="Chỉ là gợi ý cho thuật toán -- không cấm tuyệt đối, không làm hỏng khả năng tìm lời giải.",
)
st.caption(
    "Ưu tiên mềm này thể hiện rõ nhất khi xếp TKB tự động trên tuần TRỐNG (chưa có dữ liệu cũ). "
    "Khi xếp lại đè lên TKB đã có sẵn, cơ chế \"giữ nguyên tiết cũ\" luôn được ưu tiên hơn nên hiệu ứng sẽ khó thấy."
)
heavy_subjects_morning_only = st.checkbox(
    "Môn Nặng: bắt buộc xếp buổi sáng (không được xếp chiều)",
    config.heavy_subjects_morning_only,
    help="Ràng buộc CỨNG (khác ô ưu tiên phía trên) -- môn không Nặng KHÔNG bị cấm xếp sáng, "
         "chỉ môn Nặng bị cấm xếp chiều. Có thể khiến thuật toán khó/không tìm được lời giải nếu "
         "khối tiết sáng/chiều của trường quá chật.",
)

all_subjects_for_morning = repo.list_subjects(conn)
morning_only_subject_names = {s.subject_id: s.name for s in all_subjects_for_morning}
saved_morning_only_ids = getattr(config, "morning_only_subject_ids", frozenset())
morning_only_selection = st.multiselect(
    "Môn bắt buộc xếp buổi sáng (cấm chiều) — chọn từng môn cụ thể",
    options=[s.subject_id for s in all_subjects_for_morning],
    default=[sid for sid in saved_morning_only_ids if sid in morning_only_subject_names],
    format_func=lambda sid: morning_only_subject_names.get(sid, str(sid)),
    help="Ràng buộc CỨNG -- các môn được chọn sẽ KHÔNG BAO GIỜ xếp vào buổi chiều, "
         "bất kể vai trò (Nặng/Kép/Thường). Có thể khiến thuật toán khó tìm lời giải "
         "nếu quá nhiều môn bị cấm chiều.",
)

st.subheader("Buổi/ngày khoá cứng")
st.caption("Buổi không được chọn làm buổi nghỉ của giáo viên:")
forbidden_selection = st.multiselect(
    "Buổi cấm chọn làm buổi nghỉ GV",
    options=[(wd, s) for wd in WEEKDAYS for s in ("S", "C")],
    default=sorted(config.forbidden_off_cells),
    format_func=lambda cell: f"{WEEKDAY_NAMES[cell[0]]} {'Sáng' if cell[1] == 'S' else 'Chiều'}",
    label_visibility="collapsed",
)
st.caption("Buổi chiều luôn để trống toàn trường (dành ôn bồi dưỡng/phụ đạo, ngoài TKB):")
reserved_weekdays_selection = st.multiselect(
    "Thứ có buổi chiều luôn trống",
    options=list(WEEKDAYS),
    default=list(config.reserved_off_weekdays_chieu),
    format_func=lambda w: WEEKDAY_NAMES[w],
    label_visibility="collapsed",
)

st.subheader("Ưu tiên buổi (mềm, không bắt buộc)")
st.caption(
    "Các môn dưới đây được ưu tiên xếp vào buổi chiều (không cấm tuyệt đối môn khác, "
    "chỉ là gợi ý cho thuật toán). Để trống = tắt tính năng này."
)
all_subjects = repo.list_subjects(conn)
subject_names = {s.subject_id: s.name for s in all_subjects}
afternoon_preferred_selection = st.multiselect(
    "Môn ưu tiên buổi chiều",
    options=[s.subject_id for s in all_subjects],
    default=[sid for sid in config.afternoon_preferred_subject_ids if sid in subject_names],
    format_func=lambda sid: subject_names.get(sid, str(sid)),
    label_visibility="collapsed",
)

st.subheader("Môn không xếp liền ngày")
st.caption(
    "Các môn học không được xếp vào các ngày liên tiếp cho cùng 1 lớp (ví dụ: Thể dục, nếu xếp vào Thứ 2 thì không được xếp vào Thứ 3)."
)
gdtc_ids = [s.subject_id for s in all_subjects if s.role_code == ROLE_GDTC]
default_non_consec = [sid for sid in config.non_consecutive_subject_ids if sid in subject_names]
if not config.non_consecutive_subject_ids and gdtc_ids:
    default_non_consec = gdtc_ids

non_consecutive_selection = st.multiselect(
    "Môn không xếp liền ngày",
    options=[s.subject_id for s in all_subjects],
    default=default_non_consec,
    format_func=lambda sid: subject_names.get(sid, str(sid)),
    help="Các môn học không được xếp vào các ngày liên tiếp cho cùng 1 lớp (mặc định Thể dục / GDTC). Có thể thêm bớt môn tùy ý.",
    label_visibility="collapsed",
)

st.subheader("Môn xếp 1 cặp liền tiết (còn lại lẻ)")
st.caption(
    "Các môn học bắt buộc phải có đúng 1 cặp 2 tiết liền nhau trong tuần, các tiết còn lại (nếu có) sẽ xếp đơn lẻ. (Thường áp dụng cho môn Ngữ văn)."
)
single_pair_selection = st.multiselect(
    "Môn xếp 1 cặp liền tiết",
    options=[s.subject_id for s in all_subjects],
    default=[sid for sid in config.single_pair_subject_ids if sid in subject_names],
    format_func=lambda sid: subject_names.get(sid, str(sid)),
    label_visibility="collapsed",
)

st.subheader("Chất lượng lịch giáo viên")
st.caption(
    "Các quy tắc tối ưu hóa chất lượng lịch dạy cho giáo viên, tránh các bất tiện trong phân công giảng dạy."
)
c_tg1, c_tg2 = st.columns(2)
avoid_teacher_gaps = c_tg1.checkbox(
    "Tránh tiết trống / lủng của GV trong buổi",
    value=getattr(config, "avoid_teacher_gaps", True),
    help="Tránh trường hợp GV dạy tiết 1, nghỉ tiết 2-3 rồi mới dạy tiết 4. Các tiết dạy trong buổi sẽ được gom liền mạch.",
)
avoid_teacher_lone_periods = c_tg2.checkbox(
    "Tránh GV đi dạy 1 tiết/ngày hoặc sáng 1 + chiều 1",
    value=getattr(config, "avoid_teacher_lone_periods", True),
    help="Tránh việc GV phải đến trường cả ngày chỉ để dạy 1 tiết lẻ, hoặc bị phân tán sáng 1 tiết chiều 1 tiết.",
)
balance_afternoon_teachers = st.checkbox(
    "Cân đối tiết buổi chiều cho GV (tránh để GV nghỉ full chiều)",
    value=getattr(config, "balance_afternoon_teachers", True),
    help="Phân bổ tiết chiều công bằng cho các giáo viên dạy các lớp có học buổi chiều, tránh để GV nghỉ toàn bộ các buổi chiều.",
)
mandatory_morning_selection = st.multiselect(
    "Buổi sáng bắt buộc toàn thể GV đi làm / có mặt",
    options=list(WEEKDAYS),
    default=list(getattr(config, "mandatory_morning_weekdays", (2, 5, 6))),
    format_func=lambda w: f"{WEEKDAY_NAMES[w]} Sáng",
    help="Các buổi sáng này (mặc định Thứ 2, Thứ 5, Thứ 6) toàn thể GV bắt buộc có mặt, cấm chọn làm buổi nghỉ và ưu tiên xếp tiết dạy.",
)
strict_morning_selection = st.multiselect(
    "Sáng mà MỌI giáo viên đều phải có tiết dạy",
    options=list(WEEKDAYS),
    default=list(getattr(config, "strict_morning_weekdays", ()) or ()),
    format_func=lambda w: f"{WEEKDAY_NAMES[w]} Sáng",
    help="Các sáng này áp dụng cho TOÀN BỘ giáo viên, KHÔNG xét ngưỡng tải bên dưới — "
         "vi phạm sẽ chặn nút Lưu. Ngoại lệ duy nhất: Hiệu trưởng / Phó hiệu trưởng "
         "(nhận diện theo chức vụ ghi trong hồ sơ GV), vì tải của họ quá ít để trải "
         "đủ các sáng. Để trống = tắt.",
)
min_weekly_periods_for_mandatory_morning = st.number_input(
    "Sáng bắt buộc: chỉ áp dụng cho GV có tải từ mấy tiết/tuần trở lên",
    0, 30, getattr(config, "min_weekly_periods_for_mandatory_morning", 10),
    help="GV có tải DƯỚI ngưỡng này được miễn, không bắt buộc phải có mặt các sáng ở trên. "
         "Đặt 0 = áp dụng cho mọi GV. Lưu ý: ngưỡng càng cao thì càng nhiều GV vắng mặt "
         "mà không bị báo vi phạm — đo trên dữ liệu thật với ngưỡng 10 cho thấy vẫn có "
         "khoảng 4 GV vắng sáng Thứ 5 vì tải dưới ngưỡng.",
)
avoid_gdtc_consecutive = st.checkbox(
    "GDTC (Thể dục) không xếp vào 2 ngày liên tiếp",
    value=getattr(config, "avoid_gdtc_consecutive_days", True),
    help="Ràng buộc CỨNG: GDTC của 1 lớp không bao giờ được xếp vào 2 ngày liền kề trong tuần.",
)

_all_teachers = repo.list_teachers(conn)
_teacher_names = {t.teacher_id: t.name for t in _all_teachers}
_teacher_ids = [t.teacher_id for t in _all_teachers]

lone_exempt_selection = st.multiselect(
    "GV được miễn luật 'không dạy 1 tiết/buổi'",
    options=_teacher_ids,
    default=[t for t in getattr(config, "lone_session_exempt_teacher_ids", frozenset()) if t in _teacher_names],
    format_func=lambda t: _teacher_names.get(t, str(t)),
    help="Dành cho GV vốn đã có mặt ở trường vì nhiệm vụ khác (phụ trách thiết bị, thư viện, văn phòng...). "
         "Với những GV này, một buổi chỉ có 1 tiết KHÔNG bị tính là vi phạm, vì họ không phải đi lại thêm. "
         "Khác với ngưỡng tải bên dưới: đây là miễn trừ theo TỪNG NGƯỜI, không theo số tiết.",
)
compact_sched_selection = st.multiselect(
    "GV ưu tiên được nghỉ trọn nhiều buổi",
    options=_teacher_ids,
    default=[t for t in getattr(config, "compact_schedule_teacher_ids", frozenset()) if t in _teacher_names],
    format_func=lambda t: _teacher_names.get(t, str(t)),
    help="Thuật toán sẽ cố gom tiết của những GV này vào ÍT BUỔI NHẤT có thể, để họ được nghỉ trọn "
         "nhiều buổi trong tuần (sáng hay chiều đều tính) — ví dụ GV Thể dục muốn nghỉ 2 buổi bất kỳ. "
         "Đây là ƯU TIÊN MỀM: nếu không còn chỗ thì vẫn xếp bình thường, không làm hỏng các tiêu chí khác.",
)

st.subheader("Tiêu chuẩn BGD & Tiêu chí HĐSP Nhà Trường")
st.caption(
    "Các ràng buộc sư phạm chuẩn GDPT 2018 và 15 tiêu chí của Hội đồng Sư phạm nhằm đảm bảo sức khỏe học sinh và tối ưu lịch công tác giáo viên."
)
c_hdsp1, c_hdsp2 = st.columns(2)
max_teacher_periods_per_day = c_hdsp1.number_input(
    "Mỗi GV: tối đa mấy tiết/ngày (cả ngày sáng+chiều)", 1, 10,
    getattr(config, "max_teacher_periods_per_day", 5),
    help="Tiêu chí II.2: Đảm bảo mỗi GV không bị quá tải vượt quá số tiết này trong một ngày.",
)
max_heavy_per_session = c_hdsp2.number_input(
    "Tối đa mấy tiết môn Nặng/buổi cho 1 lớp", 1, max_p,
    getattr(config, "max_heavy_per_session", 3),
    help="Tiêu chuẩn I.2 & Tiêu chí II.13: Tránh dồn dập các môn nặng (Toán, Văn, KHTN...) quá tải trong 1 buổi học.",
)

c_hdsp3, c_hdsp4 = st.columns(2)
hdtn_period2_afternoon = c_hdsp3.checkbox(
    "Tiết 2 HĐTN (chủ đề) xếp vào buổi chiều",
    value=getattr(config, "hdtn_period2_afternoon", True),
    help="Tiêu chí II.6: HĐTN có 3 tiết: Tiết 1 sáng T2 (Chào cờ), Tiết 3 cuối T6 (SHL), Tiết 2 xếp vào buổi chiều cho các lớp có học chiều.",
)
avoid_heavy_afternoon_period3 = c_hdsp4.checkbox(
    "Hạn chế / cấm môn Nặng vào tiết 3 buổi chiều",
    value=getattr(config, "avoid_heavy_afternoon_period3", True),
    help="Tiêu chí II.15: Tiết cuối buổi chiều học sinh mệt mỏi khó tiếp thu kiến thức tư duy cao.",
)

c_hdsp5, c_hdsp6 = st.columns(2)
avoid_teacher_4_consecutive_morning = c_hdsp5.checkbox(
    "Hạn chế GV dạy 4 tiết sáng liên tục (nếu tải <= 20 tiết/tuần)",
    value=getattr(config, "avoid_teacher_4_consecutive_morning", True),
    help="Tiêu chí II.14: Giảm tải áp lực cho GV, trừ những GV có số tiết thực dạy > 20 tiết/tuần.",
)
min_weekly_periods_for_lone_penalty = c_hdsp6.number_input(
    "Ngưỡng tiết/tuần áp dụng phạt lẻ tiết GV (0 = phạt toàn bộ, 15 = miễn trừ GV <15 tiết)",
    0, 30, getattr(config, "min_weekly_periods_for_lone_penalty", 8),
    help="Tiêu chí II.4: Hạn chế tối đa GV dạy 1 tiết/buổi hoặc 1 tiết/ngày, nhưng miễn trừ cho GV ít tiết (< 15 tiết/tuần).",
)

st.subheader("Bộ giải thuật toán")
c_solver1, c_solver2 = st.columns(2)
use_cpsat = c_solver1.checkbox(
    "Dùng bộ giải tối ưu toàn cục CP-SAT (Khuyên dùng)",
    value=getattr(config, "use_cpsat", True),
    help="Bật lên thì TKB được tối ưu hóa toàn cục bằng ràng buộc toán học (CP-SAT) thay vì thuật toán dò tìm ngẫu nhiên. "
         "Nếu bộ giải không tìm được lời giải hoặc quá giờ, hệ thống sẽ tự động chuyển sang bộ giải dự phòng."
)
cpsat_time_limit_seconds = c_solver2.number_input(
    "Giới hạn thời gian giải cho CP-SAT (giây)",
    min_value=5, max_value=300,
    value=int(getattr(config, "cpsat_time_limit_seconds", 30)),
    help="Thời gian tối đa bộ giải CP-SAT được phép chạy trước khi tự động fallback sang engine cũ."
)

# --- Kiểm tra cảnh báo xung đột cấu hình ---
effective_morning_only = set(morning_only_selection)
if heavy_subjects_morning_only:
    effective_morning_only |= {s.subject_id for s in all_subjects if s.role_code in (1, 3)}

conflict_afternoon_morning = effective_morning_only & set(afternoon_preferred_selection)
if conflict_afternoon_morning:
    c_names = [subject_names.get(sid, str(sid)) for sid in conflict_afternoon_morning]
    st.warning(f"⚠️ **Xung đột cấu hình:** Môn **{', '.join(c_names)}** vừa được đặt \"Bắt buộc sáng (cấm chiều)\" vừa được chọn \"Ưu tiên buổi chiều\". Hãy bỏ chọn ở một trong hai mục.")

if st.button("💾 Lưu cấu hình", type="primary"):
    new_config = SchedulingConfig(
        gdtc_avoid_period=int(gdtc_avoid_period),
        gdtc_morning_allowed_periods=tuple(sorted(gdtc_morning_allowed)),
        gdtc_afternoon_allowed_periods=tuple(sorted(gdtc_afternoon_allowed)),
        chao_co_weekday=int(chao_co_weekday),
        chao_co_period=int(chao_co_period),
        max_heavy_consecutive=int(max_heavy_consecutive),
        max_periods_per_session=int(max_periods_per_session),
        teacher_off_sessions_per_week=int(teacher_off_sessions_per_week),
        forbidden_off_cells=frozenset(forbidden_selection),
        reserved_off_weekdays_chieu=tuple(sorted(reserved_weekdays_selection)),
        heavy_subject_priority_periods=int(heavy_subject_priority_periods),
        afternoon_preferred_subject_ids=frozenset(afternoon_preferred_selection),
        heavy_subjects_morning_only=bool(heavy_subjects_morning_only),
        morning_only_subject_ids=frozenset(morning_only_selection),
        non_consecutive_subject_ids=frozenset(non_consecutive_selection),
        single_pair_subject_ids=frozenset(single_pair_selection),
        avoid_teacher_gaps=bool(avoid_teacher_gaps),
        avoid_teacher_lone_periods=bool(avoid_teacher_lone_periods),
        balance_afternoon_teachers=bool(balance_afternoon_teachers),
        strict_morning_weekdays=tuple(sorted(strict_morning_selection)),
        min_weekly_periods_for_mandatory_morning=int(min_weekly_periods_for_mandatory_morning),
        lone_session_exempt_teacher_ids=frozenset(lone_exempt_selection),
        compact_schedule_teacher_ids=frozenset(compact_sched_selection),
        mandatory_morning_weekdays=tuple(sorted(mandatory_morning_selection)),
        avoid_gdtc_consecutive_days=bool(avoid_gdtc_consecutive),
        max_teacher_periods_per_day=int(max_teacher_periods_per_day),
        max_heavy_per_session=int(max_heavy_per_session),
        hdtn_period2_afternoon=bool(hdtn_period2_afternoon),
        avoid_heavy_afternoon_period3=bool(avoid_heavy_afternoon_period3),
        avoid_teacher_4_consecutive_morning=bool(avoid_teacher_4_consecutive_morning),
        min_weekly_periods_for_lone_penalty=int(min_weekly_periods_for_lone_penalty),
        use_cpsat=bool(use_cpsat),
        cpsat_time_limit_seconds=int(cpsat_time_limit_seconds),
    )
    repo.set_scheduling_config(conn, new_config)
    st.success("Đã lưu cấu hình xếp lịch.")
    st.rerun()


st.subheader("Ràng buộc môn/lớp theo buổi cụ thể (tuỳ chọn)")
st.caption(
    "Ví dụ: 1 môn ở một số lớp CHỈ được xếp vào đúng các (thứ, buổi) đã chọn -- "
    "ràng buộc CỨNG, có thể khiến thuật toán không tìm được lời giải nếu quá chặt."
)
all_classes = repo.list_classes(conn)
all_subjects_for_rules = repo.list_subjects(conn)
rule_subjects = [s for s in all_subjects_for_rules if s.role_code != ROLE_HDTN]
if not rule_subjects or not all_classes:
    st.info("Cần khai báo ít nhất 1 môn (khác HDTN) và 1 lớp trước khi tạo luật.")
else:
    with st.form("add_subject_class_rule", clear_on_submit=True):
        rule_subject_id = st.selectbox(
            "Môn", options=[s.subject_id for s in rule_subjects],
            format_func=lambda sid: next(s.name for s in rule_subjects if s.subject_id == sid),
        )
        rule_class_ids = st.multiselect(
            "Lớp áp dụng", options=[c.class_id for c in all_classes],
            format_func=lambda cid: next(c.name for c in all_classes if c.class_id == cid),
        )
        rule_cells = st.multiselect(
            "Chỉ được xếp vào các (Thứ, Buổi) này",
            options=[(wd, s) for wd in WEEKDAYS for s in ("S", "C")],
            format_func=lambda cell: f"{WEEKDAY_NAMES[cell[0]]} {'Sáng' if cell[1] == 'S' else 'Chiều'}",
        )
        if st.form_submit_button("➕ Thêm luật"):
            is_morning_only = rule_subject_id in getattr(config, "morning_only_subject_ids", frozenset())
            rule_subj_obj = next((s for s in rule_subjects if s.subject_id == rule_subject_id), None)
            if getattr(config, "heavy_subjects_morning_only", False) and rule_subj_obj and rule_subj_obj.role_code in (1, 3):
                is_morning_only = True
            if is_morning_only and rule_cells and all(s == "C" for _wd, s in rule_cells):
                st.error("Môn này đang bị cấm xếp buổi chiều theo cấu hình chung, không thể tạo luật chỉ cho phép xếp buổi chiều!")
            elif rule_class_ids and rule_cells:
                repo.upsert_subject_class_rule(conn, rule_subject_id, rule_class_ids, rule_cells)
                st.success("Đã thêm luật.")
                st.rerun()
            else:
                st.error("Cần chọn ít nhất 1 lớp và 1 (thứ, buổi).")

existing_rules = repo.list_subject_class_rules(conn)
if existing_rules:
    st.caption("Luật hiện có:")
    subject_names = {s.subject_id: s.name for s in all_subjects_for_rules}
    class_names = {c.class_id: c.name for c in all_classes}
    for rule in existing_rules:
        subj_name = subject_names.get(rule["subject_id"], str(rule["subject_id"]))
        cls_names = ", ".join(class_names.get(cid, str(cid)) for cid in rule["class_ids"])
        cell_names = ", ".join(
            f"{WEEKDAY_NAMES[wd]} {'Sáng' if s == 'S' else 'Chiều'}" for wd, s in sorted(rule["cells"])
        )
        col1, col2 = st.columns([5, 1])
        col1.markdown(f"- **{subj_name}** ({cls_names}) chỉ xếp vào: {cell_names}")
        if col2.button("🗑️", key=f"del_rule_{rule['rule_id']}"):
            repo.delete_subject_class_rule(conn, rule["rule_id"])
            st.rerun()

sidebar_backup_export(conn)
sidebar_fixed_rules(conn)
sidebar_school_switcher()
