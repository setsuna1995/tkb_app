import streamlit as st

from core import frame as frame_mod
from core.models import (
    ROLE_GDTC, ROLE_HDTN, ROLE_KEP, ROLE_NANG, ROLE_NANG_KEP, ROLE_THUONG,
    SchedulingConfig, WEEKDAY_NAMES, WEEKDAYS,
)
from data import repository as repo
from ui_common import (
    get_conn, require_auth, require_school, sidebar_backup_export,
    sidebar_fixed_rules, sidebar_school_switcher,
)

require_auth()
school_slug = require_school()
conn = get_conn(school_slug)
st.title("⚙️ Cấu hình xếp Thời khóa biểu")
st.caption(
    "Tuỳ biến toàn diện các ràng buộc sư phạm, tiêu chuẩn Hội đồng Sư phạm (HĐSP), "
    "hiện diện giáo viên và thuật toán tối ưu hóa toàn cục CP-SAT."
)

config = repo.get_scheduling_config(conn)
max_p = frame_mod.MAX_PERIODS_PER_SESSION
all_subjects = repo.list_subjects(conn)
subject_names = {s.subject_id: s.name for s in all_subjects}
all_teachers = repo.list_teachers(conn)
teacher_names = {t.teacher_id: t.name for t in all_teachers}
teacher_ids = [t.teacher_id for t in all_teachers]

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🏛️ Khung thời gian & Tiết ghim",
    "👨‍🏫 Hiện diện & Nghỉ GV",
    "⚖️ Định mức & Môn học",
    "🎓 Tiêu chuẩn Sư phạm",
    "⚡ Bộ giải CP-SAT Solver",
])

# ── TAB 1: KHUNG THỜI GIAN & TIẾT GHIM ──
with tab1:
    st.subheader("🏛️ Tiết ghim toàn trường & Khung Thể dục (GDTC)")
    st.caption("Các mốc thời gian cố định áp dụng cho toàn bộ học sinh và giáo viên trong trường.")
    
    col_cc1, col_cc2 = st.columns(2)
    chao_co_weekday = col_cc1.selectbox(
        "Chào cờ - Thứ", WEEKDAYS, index=WEEKDAYS.index(config.chao_co_weekday),
        format_func=lambda w: WEEKDAY_NAMES[w],
        help="Mặc định: Thứ 2. Tiết chào cờ đầu tuần.",
    )
    col_cc2.number_input(
        "Chào cờ - Tiết (buổi sáng)", 1, 1, 1, disabled=True,
        help="Cố định ở Tiết 1 sáng — toàn trường tập trung.",
    )
    chao_co_period = 1
    gdtc_avoid_period = config.gdtc_avoid_period

    st.markdown("---")
    st.markdown("**Khung giờ môn Giáo dục thể chất (Thể dục):**")
    c_gdtc1, c_gdtc2 = st.columns(2)
    gdtc_morning_allowed = c_gdtc1.multiselect(
        "GDTC: Các tiết được phép xếp buổi Sáng",
        options=list(range(1, max_p + 1)),
        default=[p for p in config.gdtc_morning_allowed_periods if p <= max_p],
        help="Mặc định: Tiết 1, 2, 3, 4 (tránh tiết 5 trưa muộn trời nắng).",
    )
    gdtc_afternoon_allowed = c_gdtc2.multiselect(
        "GDTC: Các tiết được phép xếp buổi Chiều",
        options=list(range(1, max_p + 1)),
        default=[p for p in config.gdtc_afternoon_allowed_periods if p <= max_p],
        help="Mặc định: Tiết 2, 3 (tránh tiết 1 đầu chiều trời nắng gắt).",
    )

    st.markdown("---")
    st.markdown("**Buổi cấm nghỉ & Buổi chiều trống:**")
    forbidden_selection = st.multiselect(
        "Buổi cấm chọn làm buổi nghỉ của GV",
        options=[(wd, s) for wd in WEEKDAYS for s in ("S", "C")],
        default=sorted(config.forbidden_off_cells),
        format_func=lambda cell: f"{WEEKDAY_NAMES[cell[0]]} {'Sáng' if cell[1] == 'S' else 'Chiều'}",
        help="Giáo viên không được phân buổi nghỉ vào các buổi này (mặc định: Sáng T2, T5, T6 và Chiều T5, T6).",
    )

    reserved_weekdays_selection = st.multiselect(
        "Các thứ có buổi chiều luôn để trống toàn trường (dành sinh hoạt chuyên môn / bồi dưỡng ngoài TKB):",
        options=list(WEEKDAYS),
        default=list(config.reserved_off_weekdays_chieu),
        format_func=lambda w: WEEKDAY_NAMES[w],
        help="Mặc định: Thứ 5, Thứ 6 (toàn trường nghỉ chiều để sinh hoạt chuyên môn và bồi dưỡng học sinh).",
    )

# ── TAB 2: HIỆN DIỆN & NGHỈ CỦA GIÁO VIÊN ──
with tab2:
    st.subheader("👨‍🏫 Quy định hiện diện & Buổi nghỉ của Giáo viên")
    st.caption("Đảm bảo công tác quản lý của nhà trường, chào cờ đầu tuần và sinh hoạt cuối tuần.")

    strict_morning_selection = st.multiselect(
        "Sáng mà MỌI giáo viên bắt buộc phải có tiết dạy (bắt buộc toàn trường):",
        options=list(WEEKDAYS),
        default=list(getattr(config, "strict_morning_weekdays", (2, 6)) or (2, 6)),
        format_func=lambda w: f"{WEEKDAY_NAMES[w]} Sáng",
        help="Mặc định: Thứ 2 (Chào cờ) và Thứ 6 (Sinh hoạt lớp/Tổng kết). "
             "Mọi giáo viên bắt buộc có tiết dạy. Ngoại lệ duy nhất: Ban Giám hiệu (Hiệu trưởng / Phó hiệu trưởng) "
             "được miễn trừ do phụ trách điều hành quản lý chung và số tiết định mức ít (2-4 tiết/tuần).",
    )

    col_m1, col_m2 = st.columns(2)
    mandatory_morning_selection = col_m1.multiselect(
        "Buổi sáng bắt buộc GV có mặt / đi làm (xét theo ngưỡng tải):",
        options=list(WEEKDAYS),
        default=list(getattr(config, "mandatory_morning_weekdays", (2, 5, 6))),
        format_func=lambda w: f"{WEEKDAY_NAMES[w]} Sáng",
        help="Mặc định: Thứ 2, Thứ 5, Thứ 6. Áp dụng cho các GV có tải giảng dạy đạt ngưỡng bên phải.",
    )
    min_weekly_periods_for_mandatory_morning = col_m2.number_input(
        "Ngưỡng tiết/tuần áp dụng cho sáng có mặt ở trên:",
        0, 30, getattr(config, "min_weekly_periods_for_mandatory_morning", 10),
        help="GV có tổng số tiết/tuần dưới ngưỡng này được miễn, không bắt buộc có mặt (mặc định 10 tiết).",
    )

    teacher_off_sessions_per_week = st.number_input(
        "Số buổi nghỉ tối đa cho mỗi giáo viên trong tuần (buổi):",
        0, 3, config.teacher_off_sessions_per_week,
        help="Mặc định: 1 buổi nghỉ/tuần (thường là 1 buổi chiều hoặc sáng không bị cấm).",
    )

    st.markdown("---")
    st.markdown("**Miễn trừ & Ưu tiên cá nhân:**")
    lone_exempt_selection = st.multiselect(
        "Giáo viên được MIỄN TRỪ luật 'tránh dạy 1 tiết/buổi' (chọn theo tên):",
        options=teacher_ids,
        default=[t for t in getattr(config, "lone_session_exempt_teacher_ids", frozenset()) if t in teacher_names],
        format_func=lambda t: teacher_names.get(t, str(t)),
        help="Dành cho giáo viên đã có mặt thường xuyên ở trường (phụ trách thiết bị, phòng máy, thư viện...). "
             "Những GV này dạy 1 tiết/buổi không bị coi là vi phạm.",
    )

    compact_sched_selection = st.multiselect(
        "Giáo viên ƯU TIÊN gom tiết để được nghỉ trọn nhiều buổi:",
        options=teacher_ids,
        default=[t for t in getattr(config, "compact_schedule_teacher_ids", frozenset()) if t in teacher_names],
        format_func=lambda t: teacher_names.get(t, str(t)),
        help="Thuật toán sẽ ưu tiên dồn tiết của những giáo viên này vào ít buổi nhất để họ được nghỉ trọn nhiều buổi (ví dụ: GV Thể dục).",
    )

# ── TAB 3: ĐỊNH MỨC & PHÂN BỔ MÔN HỌC ──
with tab3:
    st.subheader("⚖️ Giới hạn tiết học & Phân bổ môn học")
    st.caption("Kiểm soát mật độ học tập, tránh quá tải cho học sinh và giáo viên.")

    col_ld1, col_ld2 = st.columns(2)
    max_periods_per_session = col_ld1.number_input(
        "Mỗi giáo viên: tối đa mấy tiết/buổi", 1, max_p, config.max_periods_per_session,
        help="Mặc định: 4 tiết/buổi.",
    )
    max_teacher_periods_per_day = col_ld2.number_input(
        "Mỗi giáo viên: tối đa mấy tiết/ngày (cả ngày sáng+chiều)", 1, 10,
        getattr(config, "max_teacher_periods_per_day", 5),
        help="Tiêu chí II.2: Đảm bảo không quá 5 tiết/ngày cho mỗi giáo viên.",
    )

    col_hv1, col_hv2 = st.columns(2)
    max_heavy_consecutive = col_hv1.number_input(
        "Môn nặng: tối đa mấy tiết liên tiếp trong buổi", 1, max_p, config.max_heavy_consecutive,
        help="Toán, Văn, KHTN... không được xếp quá số tiết này liên tiếp cho 1 lớp (mặc định 3).",
    )
    max_heavy_per_session = col_hv2.number_input(
        "Tối đa mấy tiết môn Nặng/buổi cho 1 lớp", 1, max_p,
        getattr(config, "max_heavy_per_session", 3),
        help="Tiêu chí II.13: Tránh quá tải các môn nặng trong cùng một buổi học (mặc định 3).",
    )

    heavy_subject_priority_periods = st.number_input(
        "Môn Nặng: ưu tiên mấy tiết đầu buổi sáng (0 = tắt)", 0, max_p,
        config.heavy_subject_priority_periods,
        help="Tiêu chí II.5: Ưu tiên xếp môn nặng vào 4 tiết đầu buổi sáng khi học sinh minh mẫn nhất.",
    )

    st.markdown("---")
    st.markdown("**Phân luồng Môn Sáng / Chiều:**")
    heavy_subjects_morning_only = st.checkbox(
        "Môn Nặng: bắt buộc xếp buổi sáng (cấm xếp buổi chiều)",
        config.heavy_subjects_morning_only,
        help="Ràng buộc CỨNG: Các môn vai trò Nặng (Toán, KHTN...) chỉ được xếp buổi sáng.",
    )

    saved_morning_only_ids = getattr(config, "morning_only_subject_ids", frozenset())
    morning_only_selection = st.multiselect(
        "Môn bắt buộc xếp buổi sáng (cấm chiều) — chọn từng môn cụ thể:",
        options=[s.subject_id for s in all_subjects],
        default=[sid for sid in saved_morning_only_ids if sid in subject_names],
        format_func=lambda sid: subject_names.get(sid, str(sid)),
        help="Các môn được chọn ở đây sẽ không bao giờ bị xếp vào buổi chiều.",
    )

    afternoon_preferred_selection = st.multiselect(
        "Môn ưu tiên buổi chiều (gợi ý mềm cho bộ giải):",
        options=[s.subject_id for s in all_subjects],
        default=[sid for sid in config.afternoon_preferred_subject_ids if sid in subject_names],
        format_func=lambda sid: subject_names.get(sid, str(sid)),
        help="Gợi ý mềm xếp các môn thực hành, nghệ thuật, thể chất vào buổi chiều.",
    )

    st.markdown("---")
    st.markdown("**Quy cách phân bố tiết môn học:**")
    gdtc_ids = [s.subject_id for s in all_subjects if s.role_code == ROLE_GDTC]
    default_non_consec = [sid for sid in config.non_consecutive_subject_ids if sid in subject_names]
    if not config.non_consecutive_subject_ids and gdtc_ids:
        default_non_consec = gdtc_ids

    non_consecutive_selection = st.multiselect(
        "Môn không xếp liền ngày (cách nhật):",
        options=[s.subject_id for s in all_subjects],
        default=default_non_consec,
        format_func=lambda sid: subject_names.get(sid, str(sid)),
        help="Ví dụ: Thể dục (GDTC) không xếp vào 2 ngày liên tiếp cho cùng 1 lớp.",
    )

    single_pair_selection = st.multiselect(
        "Môn xếp 1 cặp liền tiết (còn lại xếp tiết lẻ):",
        options=[s.subject_id for s in all_subjects],
        default=[sid for sid in config.single_pair_subject_ids if sid in subject_names],
        format_func=lambda sid: subject_names.get(sid, str(sid)),
        help="Thường áp dụng cho môn Ngữ văn: có đúng 1 cặp 2 tiết liền nhau trong tuần, các tiết còn lại xếp đơn lẻ.",
    )

# ── TAB 4: TIÊU CHUẨN SƯ PHẠM ──
with tab4:
    st.subheader("🎓 Tiêu chuẩn Sư phạm & Tiêu chí Hội đồng Sư phạm")
    st.caption("Các tiêu chí chuẩn hóa chất lượng lịch giảng dạy của giáo viên và thời khóa biểu của học sinh.")

    col_sp1, col_sp2 = st.columns(2)
    avoid_teacher_gaps = col_sp1.checkbox(
        "Tránh tiết trống / lủng của GV trong buổi",
        value=getattr(config, "avoid_teacher_gaps", True),
        help="Tránh việc GV dạy tiết 1, nghỉ tiết 2-3 rồi mới dạy tiết 4. Các tiết trong buổi được xếp liền mạch.",
    )
    avoid_teacher_lone_periods = col_sp2.checkbox(
        "Tránh GV đi dạy chỉ 1 tiết/ngày hoặc sáng 1 + chiều 1",
        value=getattr(config, "avoid_teacher_lone_periods", True),
        help="Hạn chế việc GV đến trường chỉ dạy đúng 1 tiết đơn lẻ hoặc phân tán 1 tiết sáng + 1 tiết chiều.",
    )

    col_sp3, col_sp4 = st.columns(2)
    balance_afternoon_teachers = col_sp3.checkbox(
        "Cân đối tiết buổi chiều cho GV",
        value=getattr(config, "balance_afternoon_teachers", True),
        help="Phân bổ tiết chiều hợp lý cho GV dạy các lớp có học chiều, tránh để GV nghỉ toàn bộ chiều.",
    )
    avoid_gdtc_consecutive = col_sp4.checkbox(
        "GDTC (Thể dục) không xếp vào 2 ngày liên tiếp",
        value=getattr(config, "avoid_gdtc_consecutive_days", True),
        help="Đảm bảo học sinh có thời gian hồi phục thể lực, không học thể dục 2 ngày liền.",
    )

    col_sp5, col_sp6 = st.columns(2)
    hdtn_period2_afternoon = col_sp5.checkbox(
        "Tiết 2 HĐTN (chủ đề) xếp vào buổi chiều",
        value=getattr(config, "hdtn_period2_afternoon", True),
        help="Tiêu chí II.6: Tiết 1 sáng T2 (Chào cờ), Tiết 3 chiều T6 (SHL), Tiết 2 xếp buổi chiều.",
    )
    avoid_heavy_afternoon_period3 = col_sp6.checkbox(
        "Hạn chế môn Nặng vào tiết 3 buổi chiều",
        value=getattr(config, "avoid_heavy_afternoon_period3", True),
        help="Tiêu chí II.15: Tiết cuối chiều học sinh mệt mỏi, hạn chế các môn tư duy trừu tượng cao.",
    )

    col_sp7, col_sp8 = st.columns(2)
    avoid_teacher_4_consecutive_morning = col_sp7.checkbox(
        "Hạn chế GV dạy 4 tiết sáng liên tục (nếu tải <= 20)",
        value=getattr(config, "avoid_teacher_4_consecutive_morning", True),
        help="Tiêu chí II.14: Giảm tải áp lực cho giáo viên giảng dạy.",
    )
    min_weekly_periods_for_lone_penalty = col_sp8.number_input(
        "Ngưỡng tiết/tuần phạt lẻ tiết GV (miễn trừ GV ít tiết):",
        0, 30, getattr(config, "min_weekly_periods_for_lone_penalty", 8),
        help="Tiêu chí II.4: GV có tổng tải dưới ngưỡng này (mặc định 8) được miễn trừ phạt tiết đơn lẻ.",
    )

# ── TAB 5: BỘ GIẢI CP-SAT ──
with tab5:
    st.subheader("⚡ Cấu hình Bộ giải Tối ưu hóa Toàn cục CP-SAT (Google OR-Tools)")
    st.caption(
        "Bộ giải CP-SAT mô hình hóa toàn bộ thời khóa biểu thành bài toán quy hoạch thỏa mãn ràng buộc (Constraint Programming) "
        "giúp tìm ra phương án tối ưu toàn cục chỉ trong vài chục giây."
    )

    col_cp1, col_cp2 = st.columns(2)
    use_cpsat = col_cp1.checkbox(
        "Kích hoạt bộ giải tối ưu toàn cục CP-SAT (Khuyên dùng)",
        value=getattr(config, "use_cpsat", True),
        help="Bật để giải tự động tối ưu hóa toàn bộ TKB. Nếu quá giờ hoặc không tìm được, hệ thống sẽ tự động fallback sang thuật toán dự phòng.",
    )
    cpsat_time_limit_seconds = col_cp2.number_input(
        "Giới hạn thời gian giải cho CP-SAT (giây):",
        min_value=5, max_value=300,
        value=int(getattr(config, "cpsat_time_limit_seconds", 45)),
        help="Thời gian tối đa bộ giải được phép chạy (mặc định 45s). Thường bộ giải tìm ra nghiệm tối ưu chỉ sau 15-25 giây.",
    )

    col_cp3, col_cp4 = st.columns(2)
    worker_options = {
        0: "🤖 Tự động nhận diện (Cloud: 2 workers, PC: 4 workers)",
        1: "1 worker (Đơn luồng, tiết kiệm CPU tối đa)",
        2: "2 workers (Khuyên dùng cho Streamlit Cloud)",
        4: "4 workers (Tốc độ cao trên PC/Laptop 4+ cores)",
        8: "8 workers (Cực nhanh trên máy trạm đa luồng)",
    }
    current_workers = int(getattr(config, "cpsat_workers", 0))
    worker_keys = list(worker_options.keys())
    worker_idx = worker_keys.index(current_workers) if current_workers in worker_keys else 0
    chosen_workers = col_cp3.selectbox(
        "Số luồng CPU (Workers) cho CP-SAT:",
        options=worker_keys,
        index=worker_idx,
        format_func=lambda k: worker_options[k],
        help="Tự động nhận diện: Khi chạy trên Streamlit Cloud giới hạn tài nguyên sẽ dùng 2 luồng nhẹ nhàng; trên PC cục bộ dùng 4 luồng mượt mà.",
    )

    cpsat_minimize_changes = col_cp4.checkbox(
        "Ưu tiên giữ nguyên tối đa ô TKB cũ",
        value=getattr(config, "cpsat_minimize_changes", False),
        help="Khi bật, bộ giải sẽ cố gắng giữ nguyên tối đa các tiết của TKB hiện có, hạn chế tối đa xáo trộn thời khóa biểu cũ khi xếp tuần mới.",
    )

st.write("---")

# --- Kiểm tra cảnh báo xung đột cấu hình ---
effective_morning_only = set(morning_only_selection)
if heavy_subjects_morning_only:
    effective_morning_only |= {s.subject_id for s in all_subjects if s.role_code in (1, 3)}

conflict_afternoon_morning = effective_morning_only & set(afternoon_preferred_selection)
if conflict_afternoon_morning:
    c_names = [subject_names.get(sid, str(sid)) for sid in conflict_afternoon_morning]
    st.warning(f"⚠️ **Xung đột cấu hình:** Môn **{', '.join(c_names)}** vừa được đặt \"Bắt buộc sáng (cấm chiều)\" vừa được chọn \"Ưu tiên buổi chiều\". Hãy bỏ chọn ở một trong hai mục.")

if st.button("💾 Lưu toàn bộ cấu hình xếp lịch", type="primary"):
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
        cpsat_minimize_changes=bool(cpsat_minimize_changes),
        cpsat_workers=int(chosen_workers),
    )
    repo.set_scheduling_config(conn, new_config)
    st.success("✅ Đã lưu toàn bộ cấu hình xếp lịch thành công!")
    st.rerun()

# ── KHỐI PHỤ: RÀNG BUỘC RIÊNG MÔN/LỚP ──
with st.expander("📋 Ràng buộc môn / lớp theo buổi cụ thể (tuỳ chọn nâng cao)", expanded=False):
    st.caption(
        "Ví dụ: 1 môn ở một số lớp CHỈ được xếp vào đúng các (thứ, buổi) đã chọn -- "
        "ràng buộc CỨNG, có thể khiến thuật toán không tìm được lời giải nếu quá chặt."
    )
    all_classes = repo.list_classes(conn)
    rule_subjects = [s for s in all_subjects if s.role_code != ROLE_HDTN]
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
