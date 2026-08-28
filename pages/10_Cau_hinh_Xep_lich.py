import streamlit as st

from core import frame as frame_mod
from core.models import SchedulingConfig, WEEKDAY_NAMES, WEEKDAYS
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
    )
    repo.set_scheduling_config(conn, new_config)
    st.success("Đã lưu cấu hình xếp lịch.")
    st.rerun()

sidebar_backup_export(conn)
sidebar_fixed_rules(conn)
sidebar_school_switcher()
