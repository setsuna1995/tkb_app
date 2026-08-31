import streamlit as st

from core import frame as frame_mod
from core.models import ROLE_HDTN, SchedulingConfig, WEEKDAY_NAMES, WEEKDAYS
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

st.subheader("Vị trí cố định")
c1, c2 = st.columns(2)
gdtc_avoid_period = c1.number_input(
    "GDTC né tiết", 1, max_p, config.gdtc_avoid_period,
    help="Thể dục sẽ không bao giờ được xếp vào tiết này.",
)
chao_co_weekday = c2.selectbox(
    "Chào cờ - Thứ", WEEKDAYS, index=WEEKDAYS.index(config.chao_co_weekday),
    format_func=lambda w: WEEKDAY_NAMES[w],
)
c1.number_input(
    "Chào cờ - Tiết (buổi sáng)", 1, 1, 1, disabled=True,
    help="Cố định ở Tiết 1 -- cơ chế ghim tiết hiện tại chỉ hoạt động đúng ở tiết đầu buổi sáng.",
)
chao_co_period = 1

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
non_consecutive_selection = st.multiselect(
    "Môn không xếp liền ngày",
    options=[s.subject_id for s in all_subjects],
    default=[sid for sid in config.non_consecutive_subject_ids if sid in subject_names],
    format_func=lambda sid: subject_names.get(sid, str(sid)),
    label_visibility="collapsed",
)

if st.button("💾 Lưu cấu hình", type="primary"):
    new_config = SchedulingConfig(
        gdtc_avoid_period=int(gdtc_avoid_period),
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
            if rule_class_ids and rule_cells:
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
