import dataclasses
import random
import pandas as pd
import streamlit as st

from core import scheduler as sched
from core.models import ROLE_HDTN, ROLE_KEP, WEEKDAY_NAMES, WEEKDAYS
from core.rules import RULES
from core.rules.detectors import find_teacher_single_gaps, run_detectors
from core.rules.params import resolve_effective_params
from core.rules.view import build_schedule_view
from core.rules.violations import BREACH, FORCED, SHORTFALL, classify, group_by_rule
from core.scheduler.bottleneck import analyze_bottlenecks, more_time_can_help, search_headroom
from core.scheduler.placement import _build_effective_assigned_teacher
from core.scheduler.refinement import compute_candidate_metrics, find_valid_swap_candidates, validate_and_swap_slots
from core.validation import compute_quota_diff, compute_tkb_health_score
from data import repository as repo
from io_excel.exporter import export_xlsx
from ui_common import get_conn, require_auth, require_school, sidebar_backup_export, sidebar_school_switcher
from ui_theme import render_callout, render_kpi_row, render_page_header, render_status_badge, role_cell_css


def _schedule_violations(inp, result) -> list:
    # getattr: a ScheduleResult kept in st.session_state across a code reload predates this field
    params = getattr(result, "effective_params", None) or resolve_effective_params(inp)
    return classify(run_detectors(build_schedule_view(inp, result.assignment), params), params)


def _write_details(violations: list) -> None:
    for violation in violations:
        st.write(f"- {violation.detail}")


def _render_rule_violations(violations: list, save_override_key: str, week_label: str = "", single_gaps: list = None) -> bool:
    """Show violations grouped by level. Returns True when saving is allowed."""
    blocking = group_by_rule(v for v in violations if v.level == BREACH and RULES[v.rule_id].blocks_save)
    other_breaches = group_by_rule(v for v in violations if v.level == BREACH and not RULES[v.rule_id].blocks_save)
    forced = group_by_rule(v for v in violations if v.level == FORCED)
    shortfalls = group_by_rule(v for v in violations if v.level == SHORTFALL)

    for rule_id, items in other_breaches.items():
        st.error(f"❌ {RULES[rule_id].title_vi}: {len(items)} trường hợp{week_label}.")
        with st.expander("Chi tiết", expanded=False):
            _write_details(items)

    if blocking:
        st.error(f"❌ Còn {len(blocking)} tiêu chí HĐSP bắt buộc chưa được thỏa mãn (chặn lưu){week_label}:")
        for rule_id, items in blocking.items():
            with st.expander(f"{rule_id}: {RULES[rule_id].title_vi} ({len(items)} trường hợp)", expanded=False):
                _write_details(items)

    for rule_id, items in forced.items():
        with st.expander(f"⚠️ {RULES[rule_id].title_vi}: {len(items)} trường hợp buộc phải chấp nhận "
                         f"(không chặn lưu){week_label}", expanded=False):
            for violation in items:
                st.write(f"- {violation.detail} — Lý do: {violation.evidence}")

    if shortfalls:
        total = sum(len(items) for items in shortfalls.values())
        with st.expander(f"⚠️ {total} trường hợp thuộc {len(shortfalls)} tiêu chí HĐSP mềm "
                         f"(không chặn lưu){week_label}", expanded=False):
            for rule_id, items in shortfalls.items():
                st.write(f"**{RULES[rule_id].title_vi}** ({len(items)} trường hợp)")
                _write_details(items)

    # Mục riêng: Thống kê tiết trống lẻ 1 tiết (giải lao giữa buổi)
    if single_gaps:
        with st.expander(f"☕ Mục riêng: Thống kê {len(single_gaps)} lượt nghỉ giải lao 1 tiết lẻ giữa buổi (Hợp lý sư phạm, không phải lỗi vi phạm){week_label}", expanded=False):
            st.markdown(
                "<div style='font-size: 13px; color: #475569; margin-bottom: 8px;'>"
                "💡 <i>Nghỉ 1 tiết đơn lẻ giữa buổi (ví dụ dạy tiết 1, nghỉ giải lao tiết 2, dạy tiết 3) giúp giáo viên có thời gian "
                "nghỉ ngơi, chuẩn bị bài giảng và hoàn toàn hợp lệ trong phân công chuyên môn.</i>"
                "</div>",
                unsafe_allow_html=True
            )
            for sg in single_gaps:
                st.write(f"- {sg['detail']}")

    if not blocking:
        return True
    return st.checkbox("Vẫn lưu dù còn vi phạm tiêu chí HĐSP bắt buộc ở trên (không khuyến khích)",
                       key=save_override_key)


def _render_interactive_timetable_studio(
    classes: list,
    subjects: list,
    teachers: list,
    cells: dict,
    assignments: dict,
    key_prefix: str = "",
    title: str = "Studio Khảo Sát Chi Tiết Thời Khóa Biểu",
    config=None,
):
    from collections import defaultdict
    from core.models import SchedulingConfig

    if config is None:
        try:
            school_slug = require_school()
            c_conn = get_conn(school_slug)
            config = repo.get_scheduling_config(c_conn)
        except Exception:
            config = SchedulingConfig()

    strict_morns = set(getattr(config, "strict_morning_weekdays", (2,)) if getattr(config, "strict_morning_weekdays", None) is not None else (2,))
    mand_morns = set(getattr(config, "mandatory_morning_weekdays", (2, 5, 6)) if getattr(config, "mandatory_morning_weekdays", None) is not None else (2, 5, 6))
    min_mand_load = getattr(config, "min_weekly_periods_for_mandatory_morning", 10)
    allow_lone_mand = getattr(config, "allow_lone_period_on_mandatory_mornings", True)

    teacher_busy_map = defaultdict(set)
    try:
        school_slug = require_school()
        c_conn = get_conn(school_slug)
        busy_rows = repo.list_unavailability(c_conn)
        for r in busy_rows:
            try:
                teacher_busy_map[int(r["teacher_id"])].add((int(r["weekday"]), str(r["session"]), int(r["period"])))
            except Exception:
                pass
    except Exception:
        pass

    def _get_required_mornings(t, load_p):
        role = getattr(t, "role", "") or ""
        is_bgh = any(k in role for k in ["Hiệu trưởng", "Phó hiệu trưởng"])
        req = set()
        if not is_bgh:
            req |= strict_morns
        if load_p >= min_mand_load:
            req |= mand_morns
        has_must_mon_flag = getattr(t, "must_monday", None)
        if has_must_mon_flag is True:
            req.add(2)
        elif has_must_mon_flag is False and any(getattr(tch, "must_monday", False) for tch in teachers):
            if load_p < min_mand_load:
                req.discard(2)
        pinned_off = getattr(t, "pinned_full_day_off", None)
        if pinned_off:
            req.discard(pinned_off)
        return req

    subj_map = {s.subject_id: s.name for s in subjects}
    role_of = {s.subject_id: getattr(s, "role_code", None) for s in subjects}
    teach_map = {t.teacher_id: t.name for t in teachers}
    class_map = {c.class_id: c.name for c in classes}
    classes_sorted = sorted(classes, key=lambda c: getattr(c, "sort_order", 0) or 0)
    teachers_sorted = sorted(teachers, key=lambda t: t.name)

    # Build teacher schedule lookup
    teacher_sched = defaultdict(lambda: defaultdict(list))
    for (cid, wd, sess, per), sid in cells.items():
        if sid is not None and sid > 0:
            tid = assignments.get((sid, cid))
            if tid and tid > 0:
                c_name = class_map.get(cid, f"Lớp #{cid}")
                s_name = subj_map.get(sid, f"Môn #{sid}")
                teacher_sched[tid][(wd, sess, per)].append((c_name, s_name))

    # Count periods per session for each teacher (lone-session detection)
    teacher_sess_counts = defaultdict(int)
    for tid in teacher_sched:
        for (wd, sess, per) in teacher_sched[tid]:
            teacher_sess_counts[(tid, wd, sess)] += 1

    # Map teacher -> taught subjects
    teacher_subjects = defaultdict(set)
    for (sid, cid), tid in assignments.items():
        if tid and tid > 0:
            s_name = subj_map.get(sid, "")
            if s_name:
                teacher_subjects[tid].add(s_name)
    teacher_subj_labels = {
        tid: ", ".join(sorted(list(subjs))[:2]) for tid, subjs in teacher_subjects.items()
    }

    # Summary metrics for whole school
    active_teachers = [t for t in teachers_sorted if sum(len(v) for v in teacher_sched[t.teacher_id].values()) > 0]
    total_lone_school = 0
    teachers_with_lone = []
    teachers_with_aft_shortfall = []

    for t in active_teachers:
        tid = t.teacher_id
        t_total_p = sum(len(v) for v in teacher_sched[tid].values())
        t_req_morns = _get_required_mornings(t, t_total_p)
        t_sessions = {(wd, sess) for (wd, sess, per) in teacher_sched[tid]}
        t_violating_lone = sum(
            1 for (wd, sess) in t_sessions
            if teacher_sess_counts.get((tid, wd, sess), 0) == 1
            and not (allow_lone_mand and sess == "S" and wd in t_req_morns)
        )
        if t_violating_lone > 0:
            total_lone_school += t_violating_lone
            teachers_with_lone.append(t)

        t_aft_teaching = sum(1 for (wd, sess) in t_sessions if sess == "C")
        t_aft_off = 6 - t_aft_teaching
        if getattr(t, "min_afternoon_off", None) and t.min_afternoon_off > 0:
            if t_aft_off < t.min_afternoon_off:
                teachers_with_aft_shortfall.append(t)

    # Studio Container
    st.markdown(f"#### 📅 {title}")
    st.caption("Khảo sát đa chiều: Theo Lớp học • Chuyên sâu Giáo viên • Ma trận & Kiểm định toàn trường")

    tab_cls, tab_teacher, tab_matrix = st.tabs([
        "🏫 Xem Theo Lớp Học",
        "👩‍🏫 Tra Cứu Chuyên Sâu Từng Giáo Viên",
        "👥 Ma Trận Tải & Buổi Lẻ Toàn Trường",
    ])

    # ─────────────────────────────────────────────────────────────────
    # TAB 1: XEM THEO LỚP HỌC
    # ─────────────────────────────────────────────────────────────────
    with tab_cls:
        # Detect grades
        grades_found = set()
        for c in classes_sorted:
            p = ""
            for ch in c.name:
                if ch.isdigit():
                    p += ch
                else:
                    break
            if p:
                grades_found.add(p)

        if len(grades_found) > 1:
            sorted_g = sorted(list(grades_found), key=lambda x: int(x) if x.isdigit() else 99)
            g_opts = ["Tất cả khối"] + [f"Khối {g}" for g in sorted_g]
            sel_g = st.radio("Lọc nhanh theo khối:", g_opts, horizontal=True, key=f"{key_prefix}g_filter")
            if sel_g != "Tất cả khối":
                target_g = sel_g.replace("Khối ", "")
                classes_in_view = [c for c in classes_sorted if c.name.startswith(target_g)]
            else:
                classes_in_view = classes_sorted
        else:
            classes_in_view = classes_sorted

        if not classes_in_view:
            classes_in_view = classes_sorted

        col_c_sel, col_c_info = st.columns([1.5, 3])
        with col_c_sel:
            chosen_cls = st.selectbox(
                "Chọn lớp học:",
                classes_in_view,
                format_func=lambda c: c.name,
                key=f"{key_prefix}cls_pick",
            )

        c_slots = {
            (wd, sess, per): sid
            for (cid, wd, sess, per), sid in cells.items()
            if cid == chosen_cls.class_id and sid is not None and sid > 0
        }
        m_count = sum(1 for (wd, sess, per) in c_slots if sess == "S")
        a_count = sum(1 for (wd, sess, per) in c_slots if sess == "C")
        total_c_periods = m_count + a_count

        with col_c_info:
            c_kpi1, c_kpi2, c_kpi3 = st.columns(3)
            c_kpi1.metric("Tổng số tiết", f"{total_c_periods} tiết/tuần")
            c_kpi2.metric("Sáng / Chiều", f"{m_count} Sáng • {a_count} Chiều")
            shift_label = "2 Buổi (Cả ngày)" if (m_count > 0 and a_count > 0) else ("Ca Sáng" if m_count > 0 else "Ca Chiều")
            c_kpi3.metric("Hình thức học", shift_label)

        has_afternoon_overall = any(k[2] == "C" for k in cells.keys()) or a_count > 0
        sessions_to_show = ["S", "C"] if has_afternoon_overall else ["S"]

        rows, styles = [], []
        for sess in sessions_to_show:
            sess_name = "Sáng" if sess == "S" else "Chiều"
            for per in range(1, 6):
                row = {"Buổi": sess_name, "Tiết": per}
                style_row = {"Buổi": "", "Tiết": ""}
                has_any = False
                for wd in WEEKDAYS:
                    sid = cells.get((chosen_cls.class_id, wd, sess, per))
                    if sid and sid > 0:
                        s_name = subj_map.get(sid, f"Môn #{sid}")
                        tid = assignments.get((sid, chosen_cls.class_id))
                        t_name = teach_map.get(tid, "")
                        row[WEEKDAY_NAMES[wd]] = f"{s_name} ({t_name})" if t_name else s_name
                        style_row[WEEKDAY_NAMES[wd]] = role_cell_css(role_of.get(sid))
                        has_any = True
                    else:
                        row[WEEKDAY_NAMES[wd]] = "—"
                        style_row[WEEKDAY_NAMES[wd]] = role_cell_css(None)
                if has_any or sess == "S" or a_count > 0:
                    rows.append(row)
                    styles.append(style_row)

        df_cls = pd.DataFrame(rows)
        css = pd.DataFrame(styles, index=df_cls.index, columns=df_cls.columns)
        st.dataframe(df_cls.style.apply(lambda _: css, axis=None), hide_index=True, width="stretch")
        st.caption("🟦 Môn nặng • 🟧 GDTC • 🟩 HĐTN/Chào cờ/SHL • 🟪 Môn kép/Nghệ thuật • ⬜ Môn thường")

    # ─────────────────────────────────────────────────────────────────
    # TAB 2: TRA CỨU CHUYÊN SÂU TỪNG GIÁO VIÊN
    # ─────────────────────────────────────────────────────────────────
    with tab_teacher:
        st.markdown("##### ⚡ Tra cứu nhanh giáo viên có ràng buộc trọng điểm:")
        ha_teacher = next((t for t in teachers_sorted if "Hà" in t.name or "Ha" in t.name), None)
        hong_teacher = next((t for t in teachers_sorted if "Hồng" in t.name or "Hong" in t.name), None)

        col_q1, col_q2, col_q3 = st.columns([1.3, 1.3, 2.4])
        with col_q1:
            if ha_teacher:
                if st.button(f"🎵 Cô {ha_teacher.name} (Âm nhạc)", key=f"{key_prefix}btn_ha", help="Kiểm tra mở Tiết 2-3 Thứ 3 & Thứ 4", use_container_width=True):
                    st.session_state[f"{key_prefix}target_teacher_name"] = ha_teacher.name
                    st.rerun()
        with col_q2:
            if hong_teacher:
                if st.button(f"🏃 Thầy {hong_teacher.name} (GDTC)", key=f"{key_prefix}btn_hong", help="Kiểm tra nghỉ 2 buổi chiều", use_container_width=True):
                    st.session_state[f"{key_prefix}target_teacher_name"] = hong_teacher.name
                    st.rerun()

        target_name = st.session_state.get(f"{key_prefix}target_teacher_name")
        def_idx = 0
        if target_name:
            for idx, t in enumerate(teachers_sorted):
                if t.name == target_name:
                    def_idx = idx
                    break

        chosen_t = st.selectbox(
            "Chọn giáo viên cần khảo sát:",
            teachers_sorted,
            index=def_idx,
            format_func=lambda t: f"{t.name} ({teacher_subj_labels.get(t.teacher_id, 'GV')} - {getattr(t, 'department', '') or 'Bộ môn'})",
            key=f"{key_prefix}teacher_picker_studio",
        )

        tid = chosen_t.teacher_id
        t_slots = teacher_sched[tid]
        total_p = sum(len(v) for v in t_slots.values())
        sessions_set = {(wd, sess) for (wd, sess, per) in t_slots}
        days_set = {wd for (wd, sess, per) in t_slots}

        aft_teaching = sum(1 for (wd, sess) in sessions_set if sess == "C")
        aft_off_count = 6 - aft_teaching

        req_morns_chosen = _get_required_mornings(chosen_t, total_p)
        violating_lones = []
        accepted_mand_lones = []
        for (wd, sess) in sorted(sessions_set):
            if teacher_sess_counts.get((tid, wd, sess), 0) == 1:
                if allow_lone_mand and sess == "S" and wd in req_morns_chosen:
                    accepted_mand_lones.append(wd)
                else:
                    violating_lones.append((wd, sess))

        lone_count = len(violating_lones)
        lone_details = [
            f"{WEEKDAY_NAMES[wd]} ({'Sáng' if sess == 'S' else 'Chiều'})"
            for (wd, sess) in violating_lones
        ]
        has_monday_morning = (2, "S") in sessions_set

        # KPI row
        kpi_t1, kpi_t2, kpi_t3, kpi_t4, kpi_t5 = st.columns(5)
        kpi_t1.metric("Tổng số tiết", f"{total_p} tiết/tuần", help="Tổng tải tiết dạy trong tuần")
        kpi_t2.metric("Số buổi dạy", f"{len(sessions_set)} buổi", f"{len(days_set)} ngày dạy")

        req_aft = getattr(chosen_t, "min_afternoon_off", None)
        if req_aft and req_aft > 0:
            is_aft_ok = aft_off_count >= req_aft
            kpi_t3.metric(
                "Nghỉ buổi chiều",
                f"{aft_off_count} / {req_aft} buổi",
                "✅ Đạt yêu cầu" if is_aft_ok else "⚠️ Chưa đạt",
                delta_color="normal" if is_aft_ok else "inverse"
            )
        else:
            kpi_t3.metric("Nghỉ buổi chiều", f"{aft_off_count} buổi", "Tự do")

        is_lone_clean = (lone_count == 0)
        if is_lone_clean:
            if accepted_mand_lones:
                mand_str = ", ".join(f"T{w}" for w in accepted_mand_lones)
                kpi_t4.metric(
                    "Buổi lẻ 1 tiết",
                    "0 buổi",
                    f"✅ Chuẩn SP ({mand_str} hợp lệ)",
                    delta_color="normal"
                )
            else:
                kpi_t4.metric(
                    "Buổi lẻ 1 tiết",
                    "0 buổi",
                    "✅ Chuẩn sư phạm",
                    delta_color="normal"
                )
        else:
            kpi_t4.metric(
                "Buổi lẻ 1 tiết",
                f"{lone_count} buổi",
                "⚠️ Có buổi lẻ",
                delta_color="inverse"
            )

        is_mon_pinned_off = (getattr(chosen_t, "pinned_full_day_off", None) == 2)
        mon_busy_periods = {p for p in range(1, 6) if (2, "S", p) in teacher_busy_map.get(chosen_t.teacher_id, set())}
        is_mon_all_busy = (len(mon_busy_periods) >= 4)
        is_mon_required = (2 in req_morns_chosen) and not is_mon_all_busy

        if is_mon_pinned_off:
            kpi_t5.metric(
                "Sáng Thứ 2",
                "Nghỉ sáng T2",
                "ℹ️ Được duyệt nghỉ",
                delta_color="off"
            )
        elif is_mon_all_busy:
            kpi_t5.metric(
                "Sáng Thứ 2",
                "Nghỉ sáng T2",
                "ℹ️ Bận theo lịch",
                delta_color="off"
            )
        elif is_mon_required:
            if has_monday_morning:
                mon_p_count = sum(1 for (wd, sess, per) in t_slots if wd == 2 and sess == "S")
                kpi_t5.metric(
                    "Sáng Thứ 2",
                    f"Có tiết dạy ({mon_p_count} tiết)",
                    "✅ Đúng quy định",
                    delta_color="normal"
                )
            else:
                kpi_t5.metric(
                    "Sáng Thứ 2",
                    "Nghỉ sáng T2",
                    "⚠️ Chưa đạt",
                    delta_color="inverse"
                )
        else:
            mon_p_count = sum(1 for (wd, sess, per) in t_slots if wd == 2 and sess == "S")
            kpi_t5.metric(
                "Sáng Thứ 2",
                f"Có tiết dạy ({mon_p_count} tiết)" if has_monday_morning else "Nghỉ sáng T2",
                "ℹ️ Tự do" if has_monday_morning else "ℹ️ Không bắt buộc",
                delta_color="off"
            )

        # Special Inspector Alerts
        if "Hà" in chosen_t.name or "Ha" in chosen_t.name:
            allowed = {(3, "S", 2), (3, "S", 3), (4, "S", 2), (4, "S", 3)}
            actual = set(t_slots.keys())
            if actual and actual.issubset(allowed):
                st.success("✨ **Kiểm tra chuyên sâu GV Hà:** Xuất sắc! Tất cả các tiết dạy rơi chính xác vào **Tiết 2-3 Sáng Thứ 3 & Sáng Thứ 4** theo đúng cấu hình.")
            elif not actual:
                st.info("ℹ️ GV Hà không có tiết phân công trong tuần này.")
            else:
                outside = actual - allowed
                st.warning(f"⚠️ GV Hà có tiết ngoài khung T3-T4 S2-3: {outside}")

        if req_aft and req_aft >= 2:
            if aft_off_count >= req_aft:
                off_days = [WEEKDAY_NAMES[wd] for wd in WEEKDAYS if (wd, "C") not in sessions_set]
                st.success(f"✨ **Kiểm tra chuyên sâu GV {chosen_t.name}:** Đạt chuẩn nghỉ {req_aft} buổi chiều! Các buổi chiều được nghỉ: **{', '.join(off_days)}**.")

        if is_mon_required and not has_monday_morning and not is_mon_all_busy:
            st.warning(f"⚠️ **Kiểm tra GV {chosen_t.name}:** Chưa có tiết dạy vào **Sáng Thứ 2** (buổi bắt buộc có mặt theo quy chế của trường)!")

        if lone_count > 0:
            st.warning(f"⚠️ Giáo viên đang có **{lone_count} buổi lẻ 1 tiết** cần tránh: {', '.join(lone_details)}.")
        if accepted_mand_lones:
            mand_names = [f"Sáng {WEEKDAY_NAMES[w]}" for w in accepted_mand_lones]
            st.info(f"💡 GV {chosen_t.name} có 1 tiết dạy vào **{', '.join(mand_names)}** để đảm bảo có mặt ở trường theo quy định (buổi bắt buộc có mặt, được chấp nhận).")

        # Teacher Weekly Grid
        rows_t = []
        for sess in ("S", "C"):
            sess_name = "Sáng" if sess == "S" else "Chiều"
            for per in range(1, 6):
                row = {"Buổi": sess_name, "Tiết": per}
                for wd in WEEKDAYS:
                    entries = t_slots.get((wd, sess, per), [])
                    row[WEEKDAY_NAMES[wd]] = ", ".join(f"{c} ({s})" for c, s in entries) if entries else "—"
                rows_t.append(row)

        df_t = pd.DataFrame(rows_t)

        def _highlight_teacher_cells(row):
            styles = [""] * len(row)
            sess_code = "S" if row["Buổi"] == "Sáng" else "C"
            for i, col in enumerate(row.index):
                if col in ("Buổi", "Tiết"):
                    continue
                wd_num = next((k for k, v in WEEKDAY_NAMES.items() if v == col), None)
                if wd_num and row[col] and row[col] != "—":
                    if teacher_sess_counts.get((tid, wd_num, sess_code), 0) == 1:
                        if allow_lone_mand and sess_code == "S" and wd_num in req_morns_chosen:
                            styles[i] = "background-color: #F0FDF4; color: #166534; font-weight: 600; border: 1px dashed #86EFAC;"
                        else:
                            styles[i] = "background-color: #FEF2F2; color: #DC2626; font-weight: 700; border: 1px solid #FCA5A5;"
                    else:
                        styles[i] = "background-color: #F0FDF4; color: #166534; font-weight: 500;"
            return styles

        st.dataframe(df_t.style.apply(_highlight_teacher_cells, axis=1), hide_index=True, width="stretch")

    # ─────────────────────────────────────────────────────────────────
    # TAB 3: MA TRẬN TẢI & BUỔI LẺ TOÀN TRƯỜNG
    # ─────────────────────────────────────────────────────────────────
    with tab_matrix:
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric("Giáo viên phân công", f"{len(active_teachers)} GV")
        col_m2.metric(
            "Tổng buổi lẻ toàn trường",
            f"{total_lone_school} buổi",
            "✅ Tuyệt đối không lẻ" if total_lone_school == 0 else f"{len(teachers_with_lone)} GV bị lẻ",
            delta_color="normal" if total_lone_school == 0 else "inverse"
        )
        total_with_aft = sum(1 for t in active_teachers if getattr(t, "min_afternoon_off", None) and t.min_afternoon_off > 0)
        aft_ok_count = total_with_aft - len(teachers_with_aft_shortfall)
        col_m3.metric(
            "Chỉ tiêu nghỉ chiều",
            f"{aft_ok_count}/{total_with_aft} GV đạt" if total_with_aft > 0 else "Không cài đặt",
            "✅ 100% đạt chuẩn" if len(teachers_with_aft_shortfall) == 0 else "⚠️ Có GV chưa đạt",
            delta_color="normal" if len(teachers_with_aft_shortfall) == 0 else "inverse"
        )
        compliance_pct = 100 if len(active_teachers) == 0 else round((len(active_teachers) - len(teachers_with_lone)) / len(active_teachers) * 100, 1)
        col_m4.metric("Tỷ lệ GV sạch buổi lẻ", f"{compliance_pct}%")

        col_f1, col_f2 = st.columns([1.2, 2.8])
        with col_f1:
            show_issues_only = st.checkbox("🔍 Chỉ hiện GV có vấn đề (Buổi lẻ / Thiếu nghỉ chiều)", value=False, key=f"{key_prefix}chk_issues_only")
        with col_f2:
            search_kw = st.text_input("Tìm kiếm theo tên GV hoặc môn:", placeholder="Nhập tên GV hoặc môn...", key=f"{key_prefix}txt_search_kw")

        matrix_rows = []
        for t in active_teachers:
            tid = t.teacher_id
            t_slots = teacher_sched[tid]
            total_p = sum(len(v) for v in t_slots.values())
            s_set = {(wd, sess) for (wd, sess, per) in t_slots}
            d_set = {wd for (wd, sess, per) in t_slots}
            t_req_morns = _get_required_mornings(t, total_p)

            t_violating_lones = [
                (wd, sess) for (wd, sess) in sorted(s_set)
                if teacher_sess_counts.get((tid, wd, sess), 0) == 1
                and not (allow_lone_mand and sess == "S" and wd in t_req_morns)
            ]
            t_lone = len(t_violating_lones)

            aft_t = sum(1 for (wd, sess) in s_set if sess == "C")
            aft_off = 6 - aft_t
            req_a = getattr(t, "min_afternoon_off", None)
            aft_label = f"{aft_off} (Định mức: {req_a})" if req_a else f"{aft_off}"

            lone_dt = [f"{WEEKDAY_NAMES[wd]} ({'S' if sess == 'S' else 'C'})" for (wd, sess) in t_violating_lones]
            has_morn = (2, "S") in s_set
            mon_p_count = sum(1 for (wd, sess, per) in t_slots if wd == 2 and sess == "S")

            is_mon_pinned = (getattr(t, "pinned_full_day_off", None) == 2)
            mon_busy_periods = {p for p in range(1, 6) if (2, "S", p) in teacher_busy_map.get(tid, set())}
            is_mon_all_busy = (len(mon_busy_periods) >= 4)
            is_mon_req = (2 in t_req_morns) and not is_mon_all_busy and not is_mon_pinned

            if has_morn:
                mon_status = f"Có mặt ({mon_p_count} tiết)"
            elif is_mon_pinned:
                mon_status = "Nghỉ (Được duyệt)"
            elif is_mon_all_busy:
                mon_status = "Nghỉ (Bận lịch)"
            elif not is_mon_req:
                mon_status = "Nghỉ (Không bắt buộc)"
            else:
                mon_status = "⚠️ Vắng mặt"

            has_problem = (t_lone > 0) or (req_a and aft_off < req_a) or (is_mon_req and not has_morn)
            if show_issues_only and not has_problem:
                continue

            s_label = teacher_subj_labels.get(tid, "")
            if search_kw:
                kw_lower = search_kw.lower().strip()
                if kw_lower not in t.name.lower() and kw_lower not in s_label.lower():
                    continue

            matrix_rows.append({
                "Giáo viên": t.name,
                "Bộ môn": s_label,
                "Tổng tiết": total_p,
                "Số ngày": len(d_set),
                "Số buổi": len(s_set),
                "Nghỉ chiều": aft_label,
                "Buổi lẻ 1 tiết": t_lone,
                "Chi tiết buổi lẻ": ", ".join(lone_dt) if lone_dt else "—",
                "Sáng Thứ 2": mon_status,
            })

        df_matrix = pd.DataFrame(matrix_rows)
        if not df_matrix.empty:
            def _highlight_matrix(row):
                styles = [""] * len(row)
                if row["Buổi lẻ 1 tiết"] > 0:
                    for i, col in enumerate(row.index):
                        if col == "Buổi lẻ 1 tiết":
                            styles[i] = "background-color: #FEF2F2; color: #DC2626; font-weight: bold;"
                if "⚠️" in str(row["Sáng Thứ 2"]):
                    for i, col in enumerate(row.index):
                        if col == "Sáng Thứ 2":
                            styles[i] = "background-color: #FEF2F2; color: #DC2626; font-weight: bold;"
                return styles
            st.dataframe(df_matrix.style.apply(_highlight_matrix, axis=1), hide_index=True, width="stretch")
        else:
            st.info("Không có giáo viên nào khớp với điều kiện lọc.")


def _render_saved_tkb(conn, cells: dict, classes: list, subjects: list, teachers: list, key_prefix: str = ""):
    assignments = repo.get_assignments(conn)
    cfg = repo.get_scheduling_config(conn)
    _render_interactive_timetable_studio(
        classes=classes,
        subjects=subjects,
        teachers=teachers,
        cells=cells,
        assignments=assignments,
        key_prefix=key_prefix,
        title="Studio Khảo Sát Thời Khóa Biểu",
        config=cfg,
    )

require_auth()
school_slug = require_school()
conn = get_conn(school_slug)

render_page_header(
    title="Xếp Thời Khóa Biểu & Xuất Excel Theo Tuần",
    subtitle="Tối ưu hóa toàn trường bằng bộ giải Google OR-Tools CP-SAT & Xuất bảng biểu chuẩn Bộ GD&ĐT",
    badge="Trung tâm xếp lịch",
    icon="🚀",
)

classes = repo.list_classes(conn)
subjects = repo.list_subjects(conn)
if not classes or not subjects:
    render_callout(
        "Chưa có dữ liệu Lớp học hoặc Môn học. Vào trang **Khai báo** hoặc **Nhập / Xuất Excel** trước.",
        level="warning",
        title="Thiếu dữ liệu nền tảng",
    )
    sidebar_backup_export(conn)
    sidebar_school_switcher()
    st.stop()

tab_schedule, tab_history = st.tabs([
    "🚀 Xếp Thời khóa biểu mới",
    "📥 Xuất Excel & Xem Lại TKB Các Tuần (1 - 35)",
])

with tab_schedule:
    seed, _ = repo.get_tuan_config(conn)
    c_hk, c_sel = st.columns([1, 2])
    hk_choice = c_hk.selectbox("Học kỳ", ["Học kỳ I (Tuần 1 - 18)", "Học kỳ II (Tuần 19 - 35)", "Tất cả các tuần (1 - 35)"], key="sched_hk_pick")
    if "I (Tuần 1 - 18)" in hk_choice:
        week_opts = list(range(1, 19))
    elif "II (Tuần 19 - 35)" in hk_choice:
        week_opts = list(range(19, 36))
    else:
        week_opts = list(range(1, 36))

    chosen_week = c_sel.selectbox(
        "Chọn tuần cần xếp:",
        options=week_opts,
        index=0,
        format_func=lambda w: f"Tuần {w} ({'Học kỳ I' if w <= 18 else 'Học kỳ II'})",
        key="sched_week_select",
    )
    parity = "C" if chosen_week % 2 == 0 else "L"

    # Hàng thông tin tuần & Nút xuất nhanh Excel nếu tuần này đã có kết quả
    run_now = repo.get_latest_run_by_week(conn, chosen_week)
    col_w_head1, col_w_head2 = st.columns([3, 2])
    with col_w_head1:
        st.markdown(
            f"Trạng thái Tuần {chosen_week}: "
            + (f"✅ **Đã có TKB chính thức** (lưu lúc {run_now['created_at']})" if run_now
               else "⏳ **Chưa có TKB chính thức**")
        )
        st.caption(f"🎯 **Định lượng:** Tự động áp dụng phân bổ số tiết định lượng theo chuẩn của **Tuần {chosen_week}**.")
    with col_w_head2:
        if run_now:
            try:
                instant_xlsx = export_xlsx(conn, run_id=run_now["run_id"])
                st.download_button(
                    f"📥 Xuất ngay Excel Tuần {chosen_week} (.xlsx)",
                    data=instant_xlsx,
                    file_name=f"TKB_Tuan_{chosen_week}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"btn_quick_export_top_{chosen_week}",
                    type="primary",
                    width="stretch",
                )
            except Exception:
                pass


    quota_view = repo.get_teacher_quota_view(conn, week_no=chosen_week)
    over = [q for q in quota_view if q["cap"] > 0 and q["load"] > q["cap"]]
    under = [q for q in quota_view if q["load"] < q["floor"]]
    if over or under:
        info_titles = []
        if over:
            info_titles.append(f"{len(over)} GV dạy vượt trần (> trần)")
        if under:
            info_titles.append(f"{len(under)} GV dưới sàn (< sàn)")
        with st.expander(f"ℹ️ Tải giảng dạy Tuần {chosen_week} (chuẩn 16-19 tiết/tuần): Có {', '.join(info_titles)}", expanded=False):
            if over:
                st.markdown("**Giáo viên dạy vượt trần định mức (thừa giờ):**")
                for q in over:
                    q_rng = f"{q['floor']}–{q['cap']}" if q['floor'] != q['cap'] else str(q['cap'])
                    st.write(f"- **{q['name']}**: Phân công **{q['load']}** tiết / Định mức chuẩn **{q_rng}** tiết (vượt +{q['load'] - q['cap']}t)")
            if under:
                st.markdown("**Giáo viên dạy dưới sàn tối thiểu (thiếu giờ):**")
                for q in under:
                    q_rng = f"{q['floor']}–{q['cap']}" if q['floor'] != q['cap'] else str(q['cap'])
                    st.write(f"- **{q['name']}**: Phân công **{q['load']}** tiết / Định mức chuẩn **{q_rng}** tiết (thiếu -{q['floor'] - q['load']}t)")

    with st.expander("⚙️ Tùy chỉnh riêng cho tuần này (Môn kép tạm thời, Phương án HĐTN)", expanded=False):
        extra_kep_options = [s.name for s in subjects if s.role_code != ROLE_HDTN]
        extra_kep_names = st.multiselect(
            "Môn cần xếp 2 tiết liền kề (kép) CHỈ cho tuần này",
            extra_kep_options,
            help="Không đổi vĩnh viễn phân loại môn học -- chỉ áp dụng cho lần chạy xếp TKB này.",
        )
        extra_kep_ids = frozenset(s.subject_id for s in subjects if s.name in extra_kep_names)

        sched_config = repo.get_scheduling_config(conn)

        with st.container(border=True):
            st.markdown("##### 🎯 Phương án xếp môn Hoạt động trải nghiệm (HĐTN)")
            st.caption("Lựa chọn cách tổ chức môn HĐTN cho tuần này. Mặc định nhận theo Cấu hình xếp lịch của trường.")

            default_hdtn_is_thematic = (getattr(sched_config, "hdtn_mode", "separate") == "thematic")
            hdtn_plan = st.radio(
                "Phương án tổ chức HĐTN tuần này:",
                ["separate", "thematic"],
                index=1 if default_hdtn_is_thematic else 0,
                format_func=lambda p: (
                    "📅 Tuần học chuẩn (3 tiết: Chào cờ + Hoạt động chủ đề + Sinh hoạt lớp)"
                    if p == "separate"
                    else "🎪 Tuần chuyên đề (Dồn 3 tiết liền kề toàn trường)"
                ),
                key="single_hdtn_plan_radio",
                horizontal=True,
            )

            hdtn_thematic_week = (hdtn_plan == "thematic")
            hdtn_thematic_mode = "auto"
            hdtn_thematic_weekday = None
            hdtn_thematic_session = "S"
            hdtn_thematic_start_period = None

            single_custom_cfg = None
            if not hdtn_thematic_week:
                p1_str = f"{WEEKDAY_NAMES.get(sched_config.hdtn_p1_weekday, f'Thứ {sched_config.hdtn_p1_weekday}')} ({'Sáng' if sched_config.hdtn_p1_session == 'S' else 'Chiều'} Tiết {sched_config.hdtn_p1_period})"
                if sched_config.hdtn_p2_weekday is not None:
                    p2_str = f"{WEEKDAY_NAMES.get(sched_config.hdtn_p2_weekday, f'Thứ {sched_config.hdtn_p2_weekday}')} ({'Sáng' if sched_config.hdtn_p2_session == 'S' else 'Chiều'} Tiết {sched_config.hdtn_p2_period})"
                else:
                    p2_str = "Tự do linh hoạt" + (" (ưu tiên chiều)" if getattr(sched_config, "hdtn_period2_afternoon", True) else "")
                if sched_config.hdtn_p3_weekday is not None:
                    p3_str = f"{WEEKDAY_NAMES.get(sched_config.hdtn_p3_weekday, f'Thứ {sched_config.hdtn_p3_weekday}')} ({'Sáng' if sched_config.hdtn_p3_session == 'S' else 'Chiều'} {'Tiết ' + str(sched_config.hdtn_p3_period) if sched_config.hdtn_p3_period else 'cuối buổi'})"
                else:
                    p3_str = "Tự động tiết cuối tuần (Chiều T6 hoặc Sáng T7)"

                custom_single_periods = st.checkbox(
                    "✏️ Tự chỉnh lịch 3 tiết HĐTN riêng cho tuần này (không đổi cấu hình gốc)",
                    value=False,
                    key="single_custom_periods_chk",
                )

                if not custom_single_periods:
                    st.info(
                        f"📌 **Mốc tiết HĐTN áp dụng tuần này**:\n"
                        f"- **Tiết 1 (Chào cờ)**: {p1_str}\n"
                        f"- **Tiết 2 (Chủ đề)**: {p2_str}\n"
                        f"- **Tiết 3 (SHL)**: {p3_str}"
                    )
                else:
                    c_p1_col, c_p2_col, c_p3_col = st.columns(3)
                    with c_p1_col:
                        st.markdown("**🚩 Tiết 1 (Chào cờ)**")
                        c1_w, c1_s, c1_p = st.columns(3)
                        p1_w_cur = getattr(sched_config, "hdtn_p1_weekday", 2)
                        w_p1 = c1_w.selectbox("Thứ", WEEKDAYS, index=WEEKDAYS.index(p1_w_cur) if p1_w_cur in WEEKDAYS else 0,
                                              format_func=lambda w: f"T{w}", key="sin_p1_w")
                        s_p1 = c1_s.selectbox("Buổi", ["S", "C"], index=0 if getattr(sched_config, "hdtn_p1_session", "S") == "S" else 1,
                                              format_func=lambda s: "Sáng" if s == "S" else "Chiều", key="sin_p1_s")
                        p_p1 = c1_p.selectbox("Tiết", list(range(1, 6)), index=max(0, min(getattr(sched_config, "hdtn_p1_period", 1) - 1, 4)), key="sin_p1_p")

                    with c_p2_col:
                        st.markdown("**📘 Tiết 2 (Chủ đề)**")
                        p2_is_fixed = getattr(sched_config, "hdtn_p2_weekday", None) is not None
                        m_p2 = st.selectbox("Chế độ", ["auto", "fixed"], index=1 if p2_is_fixed else 0,
                                            format_func=lambda m: "🤖 Tự do" if m == "auto" else "📌 Cố định", key="sin_p2_m")
                        if m_p2 == "fixed":
                            c2_w, c2_s, c2_p = st.columns(3)
                            p2_w_cur = getattr(sched_config, "hdtn_p2_weekday", 4) or 4
                            w_p2 = c2_w.selectbox("Thứ", WEEKDAYS, index=WEEKDAYS.index(p2_w_cur) if p2_w_cur in WEEKDAYS else 2,
                                                  format_func=lambda w: f"T{w}", key="sin_p2_w")
                            s_p2 = c2_s.selectbox("Buổi", ["S", "C"], index=0 if getattr(sched_config, "hdtn_p2_session", "S") == "S" else 1,
                                                  format_func=lambda s: "Sáng" if s == "S" else "Chiều", key="sin_p2_s")
                            p_p2 = c2_p.selectbox("Tiết", list(range(1, 6)), index=max(0, min((getattr(sched_config, "hdtn_p2_period", 2) or 2) - 1, 4)), key="sin_p2_p")
                        else:
                            w_p2, s_p2, p_p2 = None, "S", None
                            p2_chieu_pref = st.checkbox(
                                "Ưu tiên xếp chiều",
                                value=getattr(sched_config, "hdtn_period2_afternoon", True),
                                key="sin_p2_chieu_pref",
                            )

                    with c_p3_col:
                        st.markdown("**👥 Tiết 3 (SHL)**")
                        p3_is_fixed = getattr(sched_config, "hdtn_p3_weekday", None) is not None
                        m_p3 = st.selectbox("Chế độ", ["auto", "fixed"], index=1 if p3_is_fixed else 0,
                                            format_func=lambda m: "🤖 Tiết cuối tuần" if m == "auto" else "📌 Cố định", key="sin_p3_m")
                        if m_p3 == "fixed":
                            c3_w, c3_s, c3_p = st.columns(3)
                            p3_w_cur = getattr(sched_config, "hdtn_p3_weekday", 6) or 6
                            w_p3 = c3_w.selectbox("Thứ", WEEKDAYS, index=WEEKDAYS.index(p3_w_cur) if p3_w_cur in WEEKDAYS else 4,
                                                  format_func=lambda w: f"T{w}", key="sin_p3_w")
                            s_p3 = c3_s.selectbox("Buổi", ["S", "C"], index=0 if getattr(sched_config, "hdtn_p3_session", "S") == "S" else 1,
                                                  format_func=lambda s: "Sáng" if s == "S" else "Chiều", key="sin_p3_s")
                            p3_opts = [0, 1, 2, 3, 4, 5]
                            cur_p3_val = getattr(sched_config, "hdtn_p3_period", 0) or 0
                            p_p3 = c3_p.selectbox("Tiết", p3_opts, index=p3_opts.index(cur_p3_val) if cur_p3_val in p3_opts else 0,
                                                  format_func=lambda p: "Cuối" if p == 0 else f"T{p}", key="sin_p3_p")
                        else:
                            w_p3, s_p3, p_p3 = None, "S", None

                    single_custom_cfg = dataclasses.replace(
                        sched_config,
                        hdtn_p1_weekday=int(w_p1),
                        hdtn_p1_session=str(s_p1),
                        hdtn_p1_period=int(p_p1),
                        chao_co_weekday=int(w_p1),
                        chao_co_session=str(s_p1),
                        chao_co_period=int(p_p1),
                        hdtn_p2_weekday=int(w_p2) if m_p2 == "fixed" else None,
                        hdtn_p2_session=str(s_p2) if m_p2 == "fixed" else "S",
                        hdtn_p2_period=int(p_p2) if m_p2 == "fixed" else None,
                        hdtn_period2_afternoon=bool(p2_chieu_pref if m_p2 != "fixed" else getattr(sched_config, "hdtn_period2_afternoon", True)),
                        hdtn_p3_weekday=int(w_p3) if m_p3 == "fixed" else None,
                        hdtn_p3_session=str(s_p3) if m_p3 == "fixed" else "S",
                        hdtn_p3_period=int(p_p3) if (m_p3 == "fixed" and int(p_p3) > 0) else None,
                    )
            else:
                hdtn_thematic_mode = "auto"
                hdtn_thematic_weekday = None
                hdtn_thematic_session = "S"
                hdtn_thematic_start_period = None

                st.success(
                    "🤖 **Chế độ Tự động tối ưu toàn trường (Mặc định)**:\n\n"
                    "Thuật toán CP-SAT sẽ tự động tìm dải 3 tiết liền kề tối ưu nhất trong tuần, đồng thời bảo đảm 100% các lớp "
                    "được học HĐTN cùng lúc. **Bạn không cần phải tự chọn thời gian thủ công**."
                )
                allow_manual_fixed = st.checkbox(
                    "Chỉ định khung giờ cố định (chỉ dùng nếu có lịch ấn định sẵn từ Ban Giám hiệu)",
                    value=False,
                    key="single_allow_manual_thematic_fixed",
                )
                if allow_manual_fixed:
                    c_wd, c_sess, c_p = st.columns(3)
                    def_wd = getattr(sched_config, "hdtn_thematic_weekday", None) or 2
                    hdtn_thematic_weekday = c_wd.selectbox(
                        "Thứ", [2, 3, 4, 5, 6, 7],
                        index=[2, 3, 4, 5, 6, 7].index(def_wd) if def_wd in [2, 3, 4, 5, 6, 7] else 0,
                        format_func=lambda w: f"Thứ {w}",
                        key="single_hdtn_thematic_wd",
                    )
                    def_sess = getattr(sched_config, "hdtn_thematic_session", "S") or "S"
                    hdtn_thematic_session = c_sess.selectbox(
                        "Buổi", ["S", "C"],
                        index=0 if def_sess == "S" else 1,
                        format_func=lambda s: "Sáng" if s == "S" else "Chiều",
                        key="single_hdtn_thematic_sess",
                    )
                    def_p = getattr(sched_config, "hdtn_thematic_start_period", None) or 1
                    hdtn_thematic_start_period = c_p.selectbox(
                        "Dải 3 tiết bắt đầu", [1, 2, 3],
                        index=[1, 2, 3].index(def_p) if def_p in [1, 2, 3] else 0,
                        format_func=lambda p: f"Tiết {p} → Tiết {p+2}",
                        key="single_hdtn_thematic_p",
                    )
                    hdtn_thematic_mode = "fixed"

    st.caption(
        f"Áp dụng: HĐTN **{'Tuần chuyên đề' if hdtn_thematic_week else 'Tuần chuẩn'}**"
        + (f" • Môn kép tạm thời: **{', '.join(extra_kep_names)}**" if extra_kep_names else "")
    )

    st.caption("✨ Động cơ lập lịch: **Google OR-Tools CP-SAT** (Tối ưu hóa toàn cục, triệt tiêu vi phạm II.3, II.4, II.8)")

    def _run_single_solver(s_seed, s_cfg_override, s_locked_slots=None, s_reference_assignment=None, strategy="default", banned_slots_subjects=None, deep=False):
        inp_obj = repo.build_scheduling_input(
            conn, parity=parity, seed=s_seed, extra_kep_ids=extra_kep_ids,
            hdtn_thematic_week=hdtn_thematic_week,
            hdtn_thematic_mode=hdtn_thematic_mode,
            hdtn_thematic_weekday=hdtn_thematic_weekday,
            hdtn_thematic_session=hdtn_thematic_session,
            hdtn_thematic_start_period=hdtn_thematic_start_period,
            week_no=chosen_week,
            config_override=s_cfg_override,
            locked_slots=s_locked_slots,
            reference_assignment=s_reference_assignment,
        )
        progress_bar = st.progress(0, text="Đang khởi tạo mô hình toán học CP-SAT...")
        status_log = st.empty()
        log_lines = []

        def _on_cpsat_progress(info):
            max_passes = max(info.get("max_passes", 1), 1)
            event = info.get("event")
            pass_no = info.get("pass", 1)
            if event == "pass_start":
                hard_rids = info.get("hard_rids") or []
                relaxed = info.get("relaxed_so_far") or []
                desc = (f"ràng buộc cứng: {', '.join(hard_rids)}" if hard_rids
                        else "phần còn lại (chỉ còn ràng buộc mềm)")
                workers = info.get("workers")
                w_str = f" ({workers} luồng CPU)" if workers else ""
                line = f"⏳ Lần thử {pass_no}/{max_passes}{w_str}: đang giải {desc}"
                if relaxed:
                    line += f" — đã nới lỏng trước đó: {', '.join(relaxed)}"
                progress_bar.progress(min(0.95, (pass_no - 1) / max_passes), text=line)
            elif event == "solution":
                sol_count = info.get("sol_count", 1)
                obj = info.get("objective", 0)
                wall_time = info.get("wall_time_s", 0.0)
                line = f"💡 Nghiệm #{sol_count}: điểm phạt {obj:.0f} (sau {wall_time:.1f}s)"
                progress_bar.progress(min(0.98, max(0.05, (pass_no - 0.5) / max_passes)), text=line)
            else:
                status_str = info.get("status", "HOÀN TẤT")
                wall_time = info.get("wall_time_s", 0.0)
                line = f"✓ Lần thử {pass_no} kết thúc: {status_str} (mất {wall_time:.1f}s)"
                progress_bar.progress(min(0.99, pass_no / max_passes), text=line)
            log_lines.append(line)
            status_log.caption("  \n".join(log_lines[-8:]))

        from core.scheduler import cpsat_model
        built = cpsat_model.build_model(inp_obj)
        if banned_slots_subjects:
            for (b_slot_id, b_subj_id) in banned_slots_subjects:
                b_key = (b_slot_id, b_subj_id)
                if b_key in built.x:
                    built.model.Add(built.x[b_key] == 0)

        t_limit = getattr(s_cfg_override, "cpsat_time_limit_seconds", getattr(s_cfg_override, "cpsat_time_limit_s", 45)) if s_cfg_override else 45
        res_obj = cpsat_model.solve_to_result(
            built,
            time_limit_s=t_limit,
            progress_cb=_on_cpsat_progress,
            strategy=strategy,
            deep=deep,
        )
        if res_obj is None:
            from core.models import ScheduleResult
            res_obj = ScheduleResult(
                success=False, attempts_tried=1, successes_found=0,
                cells_total=len(inp_obj.slots), failure_reason="Không tìm được phương án thỏa mãn ràng buộc.",
            )
        progress_bar.progress(1.0, text="Hoàn tất.")
        return inp_obj, res_obj

    def _run_multi_strategy_solver(s_seed, s_cfg_override):
        inp_obj = repo.build_scheduling_input(
            conn, parity=parity, seed=s_seed, extra_kep_ids=extra_kep_ids,
            hdtn_thematic_week=hdtn_thematic_week,
            hdtn_thematic_mode=hdtn_thematic_mode,
            hdtn_thematic_weekday=hdtn_thematic_weekday,
            hdtn_thematic_session=hdtn_thematic_session,
            hdtn_thematic_start_period=hdtn_thematic_start_period,
            week_no=chosen_week,
            config_override=s_cfg_override,
        )
        progress_bar = st.progress(0, text="Đang khởi tạo CP-SAT giải đồng thời 3 chiến lược...")
        status_log = st.empty()
        log_lines = []

        def _on_cpsat_progress(info):
            event = info.get("event")
            if event == "strategy_start":
                s_label = info.get("strategy_label", "")
                line = f"🚀 Tối ưu chiến lược: {s_label}"
                progress_bar.progress(0.2, text=line)
            elif event == "pass_start":
                hard_rids = info.get("hard_rids") or []
                line = f"⏳ Đang giải tiêu chí cứng: {', '.join(hard_rids) if hard_rids else 'ràng buộc mềm'}"
                progress_bar.progress(0.5, text=line)
            elif event == "solution":
                obj = info.get("objective", 0)
                line = f"💡 Nghiệm tốt: điểm phạt {obj:.0f}"
                progress_bar.progress(0.8, text=line)
            else:
                line = "✓ Đã tìm thấy phương án tối ưu."
                progress_bar.progress(0.95, text=line)
            log_lines.append(line)
            status_log.caption("  \n".join(log_lines[-6:]))

        results_map = sched.run_three_strategies(inp_obj, progress_cb=_on_cpsat_progress)
        progress_bar.progress(1.0, text="Đã hoàn tất tính toán cả 3 phương án!")
        return inp_obj, results_map

    if "candidates" not in st.session_state or st.session_state.get("candidates_week") != chosen_week:
        st.session_state["candidates"] = {}
        st.session_state["candidates_week"] = chosen_week
        st.session_state["active_candidate_id"] = None
        st.session_state["locked_classes"] = []
        st.session_state["locked_teachers"] = []

    c_run1, c_run2 = st.columns([3, 1])
    with c_run1:
        run_multi_clicked = st.button(
            "🚀 Chạy Xếp TKB (Tính Toán 3 Phương Án Tối Ưu Cùng Lúc)",
            type="primary",
            use_container_width=True,
            help="Bộ giải CP-SAT sẽ tính toán đồng thời 3 chiến lược nới lỏng (Triệt tiêu buổi lẻ, Kỷ luật hiện diện, Cân bằng tối ưu) để so sánh và lựa chọn phương án ưng ý nhất.",
        )
    with c_run2:
        run_single_clicked = st.button(
            "⚡ Xếp nhanh 1 phương án",
            use_container_width=True,
            help="Chạy nhanh 1 lượt giải chuẩn.",
        )

    if run_multi_clicked:
        inp, results_dict = _run_multi_strategy_solver(seed, single_custom_cfg)
        st.session_state["last_input"] = inp
        st.session_state["last_scheduled_week"] = chosen_week
        st.session_state["candidates"] = {}

        strat_defs = [
            ("anti_lone", 1, "Phương án 1 (Triệt tiêu buổi lẻ)", "🛡️ Ưu tiên II.4: Triệt tiêu tối đa các buổi lẻ của GV"),
            ("presence", 2, "Phương án 2 (Kỷ luật hiện diện)", "🚩 Ưu tiên II.3: Bảo đảm 100% GV có mặt sáng Thứ 2"),
            ("pareto", 3, "Phương án 3 (Cân bằng tối ưu)", "⚖️ Hài hòa đa mục tiêu, phân bố đều các ngày trong tuần"),
        ]

        best_cand_id = None
        best_score = -1

        for key, cid, name, desc in strat_defs:
            res = results_dict.get(key)
            if res and res.success:
                metrics = compute_candidate_metrics(inp, res)
                st.session_state["candidates"][cid] = {
                    "id": cid,
                    "key": key,
                    "name": name,
                    "strategy_desc": desc,
                    "seed": seed or 0,
                    "time_limit": 45,
                    "result": res,
                    "inp": inp,
                    "metrics": metrics,
                }
                cur_score = metrics["health_score"]["overall_score"]
                if cur_score > best_score:
                    best_score = cur_score
                    best_cand_id = cid

        if st.session_state["candidates"]:
            active_id = best_cand_id or 1
            st.session_state["active_candidate_id"] = active_id
            st.session_state["last_result"] = st.session_state["candidates"][active_id]["result"]
            st.success(f"🎉 Đã sinh thành công {len(st.session_state['candidates'])} phương án tối ưu!")
            st.rerun()
        else:
            first_fail = next(iter(results_dict.values())).failure_reason if results_dict else "Không thể xếp TKB"
            from core.models import ScheduleResult
            st.session_state["last_result"] = ScheduleResult(success=False, failure_reason=first_fail)

    if run_single_clicked:
        inp, result = _run_single_solver(seed, single_custom_cfg)
        st.session_state["last_result"] = result
        st.session_state["last_input"] = inp
        st.session_state["last_scheduled_week"] = chosen_week
        if result.success:
            metrics = compute_candidate_metrics(inp, result)
            st.session_state["candidates"] = {
                1: {
                    "id": 1,
                    "key": "single",
                    "name": "Phương án 1 (Tiêu chuẩn)",
                    "strategy_desc": "Phương án tiêu chuẩn theo cấu hình hiện tại",
                    "seed": seed or 0,
                    "time_limit": getattr(single_custom_cfg, "cpsat_time_limit_seconds", getattr(single_custom_cfg, "cpsat_time_limit_s", 45)) if single_custom_cfg else 45,
                    "result": result,
                    "inp": inp,
                    "metrics": metrics,
                }
            }
            st.session_state["active_candidate_id"] = 1

    result = st.session_state.get("last_result")
    inp = st.session_state.get("last_input")
    scheduled_week = st.session_state.get("last_scheduled_week")

    if result is not None and scheduled_week == chosen_week:
        if not result.success:
            st.error(result.failure_reason)
        else:
            all_cands = st.session_state.get("candidates", {})
            active_cid = st.session_state.get("active_candidate_id")
            cand_items = sorted(
                all_cands.values(),
                key=lambda c: (0 if c.get("id") == active_cid else 1, c.get("id", 0)),
            )
            # ══════════════════════════════════════════════════════════════════
            # 🌟 BENTO GRID ĐỐI SÁNH ĐA PHƯƠNG ÁN (UI/UX PRO MAX)
            # ══════════════════════════════════════════════════════════════════
            if cand_items:
                st.markdown("#### 🎯 So Sánh & Chọn Lựa Phương Án Thời Khóa Biểu")
                st.caption("Các phương án được tính toán với trọng số ưu tiên khác nhau. Bấm **Chọn Phương Án** để áp dụng và xem chi tiết.")

                card_cols = st.columns(min(3, len(cand_items)))
                for idx, c in enumerate(cand_items[:3]):
                    cid = c["id"]
                    is_active = (cid == st.session_state.get("active_candidate_id"))
                    m = c["metrics"]
                    h_score = m["health_score"]["overall_score"]
                    rating = m["health_score"]["rating"]
                    lone = m.get("lone_sessions", 0)
                    holes = m.get("hole_periods", 0)
                    long_gaps = m.get("long_gaps_count", 0)
                    single_gaps = m.get("single_gaps_count", 0)
                    morn = m.get("missing_mornings", 0)
                    aft_status = m.get("afternoon_off_status", {})

                    card_border = "#2563EB" if is_active else "#E2E8F0"
                    card_bg = "#F0F7FF" if is_active else "#FFFFFF"
                    shadow = "0 4px 14px rgba(37, 99, 235, 0.15)" if is_active else "0 2px 4px rgba(0,0,0,0.05)"
                    status_chip = "<span style='background: #2563EB; color: #FFFFFF; font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 9999px;'>🌟 ĐANG CHỌN</span>" if is_active else "<span style='background: #F1F5F9; color: #64748B; font-size: 11px; font-weight: 600; padding: 3px 8px; border-radius: 9999px;'>ỨNG VIÊN</span>"
                    score_color = "#10B981" if h_score >= 85 else "#2563EB" if h_score >= 75 else "#F59E0B"

                    lone_badge = "<span style='color: #10B981; font-weight: 700;'>0 buổi (Tuyệt đối) ✅</span>" if lone == 0 else f"<span style='color: #F59E0B; font-weight: 700;'>{lone} buổi ⚠️</span>"
                    if long_gaps == 0:
                        gap_badge = "<span style='color: #10B981; font-weight: 700;'>0 (Không lủng dài) ✅</span>"
                    else:
                        gap_badge = f"<span style='color: #EF4444; font-weight: 700;'>{long_gaps} buổi lủng ≥2 tiết ⚠️</span>"

                    if holes == 0:
                        sub_gap_text = "Lịch kín 100%"
                    elif single_gaps > 0 and long_gaps == 0:
                        sub_gap_text = f"{single_gaps} lượt nghỉ 1 tiết lẻ"
                    else:
                        sub_gap_text = f"{holes} tiết trống"

                    morn_badge = "<span style='color: #10B981; font-weight: 700;'>100% đủ mặt ✅</span>" if morn == 0 else f"<span style='color: #EF4444; font-weight: 600;'>Thiếu {morn} lượt</span>"

                    aft_lines = []
                    for tname, stat in aft_status.items():
                        mark = "✅" if stat["satisfied"] else "⚠️"
                        aft_lines.append(f"{tname}: {stat['actual']}/{stat['target']} buổi {mark}")
                    aft_text = " • ".join(aft_lines) if aft_lines else "Đạt chuẩn ✅"

                    with card_cols[idx]:
                        st.markdown(
                            f"""
                            <div style="border: 2px solid {card_border}; background: {card_bg}; border-radius: 12px; padding: 16px; box-shadow: {shadow}; margin-bottom: 10px;">
                                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                                    <span style="font-weight: 700; font-size: 14px; color: #0F172A;">{c['name']}</span>
                                    {status_chip}
                                </div>
                                <div style="font-size: 12px; color: #64748B; margin-bottom: 10px; min-height: 32px;">{c.get('strategy_desc', '')}</div>
                                <div style="display: flex; align-items: baseline; gap: 6px; margin-bottom: 12px;">
                                    <span style="font-size: 28px; font-weight: 800; color: {score_color};">{h_score:.1f}</span>
                                    <span style="font-size: 13px; color: #64748B;">/ 100 ({rating})</span>
                                </div>
                                <div style="font-size: 12.5px; line-height: 1.8; color: #334155; border-top: 1px solid #E2E8F0; padding-top: 8px;">
                                    <div>🎯 <b>Buổi lẻ GV:</b> {lone_badge}</div>
                                    <div>⏱️ <b>Lủng ≥2 tiết:</b> {gap_badge} <span style="font-size: 11px; color: #64748B;">({sub_gap_text})</span></div>
                                    <div>🌅 <b>Sáng T2 có mặt:</b> {morn_badge}</div>
                                    <div>🏖️ <b>Nghỉ chiều:</b> {aft_text}</div>
                                </div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                        if not is_active:
                            if st.button(f"👉 Chọn Phương Án {cid}", key=f"btn_pick_cand_{cid}", use_container_width=True):
                                st.session_state["active_candidate_id"] = cid
                                st.session_state["last_result"] = c["result"]
                                st.session_state["last_input"] = c["inp"]
                                st.rerun()
                        else:
                            st.button(f"✓ Đang chọn #{cid}", key=f"btn_active_cand_{cid}", disabled=True, use_container_width=True)

            if result.relaxed_rules:
                st.warning(f"⚠️ Lịch được tạo là phương án khả thi tốt nhất, nhưng {len(result.relaxed_rules)} ràng buộc HĐSP đã phải nới lỏng:")
                for item in result.relaxed_rules:
                    rule_id = item.get("rule_id")
                    title = RULES[rule_id].title_vi if rule_id in RULES else rule_id
                    st.write(f"- {rule_id}: {title}")

            violations_curr = _schedule_violations(inp, result)
            has_blocking = any(v.level == BREACH and RULES[v.rule_id].blocks_save for v in violations_curr)
            can_save = (not has_blocking) or bool(st.session_state.get("proceed_with_hard_violations", False))

            if msg := st.session_state.pop("extend_msg", None):
                st.info(msg)

            # ── Top Action Bar (Save, Download, Solve Longer, Cancel) ──
            col_acc1, col_acc2, col_acc3, col_acc4 = st.columns([1.2, 1.2, 1.4, 0.8])
            with col_acc1:
                save_help = "Còn vi phạm tiêu chí bắt buộc — xem mục Kiểm định bên dưới để xác nhận." if not can_save else None
                if st.button(
                    f"✅ Chấp nhận & Lưu Tuần {scheduled_week}",
                    type="primary",
                    disabled=not can_save,
                    help=save_help,
                    key="btn_accept_save_fresh_result",
                ):
                    cells = {
                        (s.class_id, s.ts.weekday, s.ts.session, s.ts.period): result.assignment.get(s.slot_id)
                        for s in inp.slots
                    }
                    repo.bulk_replace_tkb_nhap(conn, cells)
                    save_week_no = scheduled_week if scheduled_week is not None else 1
                    repo.add_seed_history(conn, save_week_no, seed, parity)
                    run_id = repo.save_run(
                        conn, save_week_no, seed, parity, result.cells_changed, result.cells_total,
                        True, "OK",
                    )
                    repo.save_tkb_result(conn, run_id, cells)
                    st.session_state["just_saved_week"] = save_week_no
                    st.session_state["saved_success_msg"] = f"🎉 Đã lưu thành công thời khóa biểu chính thức cho Tuần {save_week_no}!"
                    st.session_state.pop("last_result", None)
                    st.session_state.pop("last_input", None)
                    st.session_state.pop("last_scheduled_week", None)
                    st.session_state.pop("candidates", None)
                    st.session_state.pop("active_candidate_id", None)
                    st.session_state.pop("locked_classes", None)
                    st.session_state.pop("locked_teachers", None)
                    st.session_state.pop("extend_msg", None)
                    st.rerun()

            with col_acc2:
                try:
                    curr_cells = {
                        (s.class_id, s.ts.weekday, s.ts.session, s.ts.period): result.assignment.get(s.slot_id)
                        for s in inp.slots
                    }
                    file_label = f"TKB_Tuan_{scheduled_week}.xlsx" if scheduled_week else f"TKB_Tuan_{'Chan' if parity == 'C' else 'Le'}.xlsx"
                    excel_bytes = export_xlsx(conn, cells=curr_cells)
                    st.download_button(
                        "📤 Tải bản Excel (.xlsx)",
                        data=excel_bytes,
                        file_name=file_label,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="btn_download_fresh_result",
                    )
                except Exception as ex_fresh:
                    st.caption(f"Xuất Excel: {ex_fresh}")

            with col_acc3:
                c_time_val = st.segmented_control(
                    "Thêm thời gian",
                    options=[30, 60, 120, 300],
                    default=30,
                    format_func=lambda s: f"+{s}s",
                    key="ctl_deep_solve_seconds",
                    label_visibility="collapsed",
                ) or 30
                can_help = more_time_can_help(result)
                btn_label = "✅ Đã tối ưu (không cần thêm)" if not can_help else "⏱️ Giải thêm thời gian"
                if st.button(
                    btn_label,
                    key="btn_solve_longer",
                    disabled=not can_help,
                    use_container_width=True,
                    help="Tiếp tục tối ưu phương án đang chọn từ nghiệm hiện tại (warm-start)" if can_help else "Bộ giải đã chứng minh phương án này tối ưu toàn cục, giải thêm không giảm điểm phạt.",
                ):
                    active_cand = st.session_state.get("candidates", {}).get(st.session_state.get("active_candidate_id", 1))
                    base_cfg = active_cand["inp"].config if active_cand else single_custom_cfg
                    deep_cfg = dataclasses.replace(base_cfg, cpsat_time_limit_seconds=int(c_time_val))
                    cand_seed = active_cand["seed"] if active_cand else (seed or 0)
                    cand_key = active_cand.get("key", "default") if active_cand else "default"
                    locked_slots = active_cand.get("locked_slots") if active_cand else None

                    inp_new, res_new = _run_single_solver(
                        s_seed=cand_seed,
                        s_cfg_override=deep_cfg,
                        s_locked_slots=locked_slots,
                        s_reference_assignment=result.assignment,
                        strategy=cand_key,
                        deep=True,
                    )
                    if not res_new.success:
                        st.error(f"Giải thêm không thành công, giữ nguyên phương án hiện tại: {res_new.failure_reason}")
                    else:
                        old_score = compute_candidate_metrics(inp, result)["health_score"]["overall_score"]
                        metrics_new = compute_candidate_metrics(inp_new, res_new)
                        new_score = metrics_new["health_score"]["overall_score"]
                        new_id = max(st.session_state["candidates"]) + 1
                        st.session_state["candidates"][new_id] = {
                            "id": new_id,
                            "key": cand_key,
                            "name": f"Phương án {new_id} (+{c_time_val}s từ PA {active_cand['id'] if active_cand else 1})",
                            "strategy_desc": f"Tiếp tục tối ưu PA {active_cand['id'] if active_cand else 1} thêm {c_time_val}s",
                            "seed": cand_seed,
                            "time_limit": int(c_time_val),
                            "locked_slots": locked_slots,
                            "result": res_new,
                            "inp": inp_new,
                            "metrics": metrics_new,
                        }
                        if new_score >= old_score:
                            st.session_state["active_candidate_id"] = new_id
                            st.session_state["last_result"] = res_new
                            st.session_state["last_input"] = inp_new
                        st.session_state["extend_msg"] = (
                            f"PA {new_id}: {new_score:.1f} điểm ({new_score - old_score:+.1f} so với PA {active_cand['id'] if active_cand else 1})"
                            + ("" if new_score >= old_score else " — giữ nguyên PA cũ vì tốt hơn.")
                        )
                        st.rerun()

            with col_acc4:
                if st.button("❌ Hủy", key="btn_cancel_fresh_result", help=f"Quay lại thời khóa biểu chính thức cũ của Tuần {scheduled_week}"):
                    st.session_state.pop("last_result", None)
                    st.session_state.pop("last_input", None)
                    st.session_state.pop("last_scheduled_week", None)
                    st.session_state.pop("candidates", None)
                    st.session_state.pop("active_candidate_id", None)
                    st.session_state.pop("locked_classes", None)
                    st.session_state.pop("locked_teachers", None)
                    st.session_state.pop("extend_msg", None)
                    st.rerun()

            # ── Panel Chẩn Đoán Nút Thắt ──
            bottlenecks = analyze_bottlenecks(inp, result, violations_curr)
            kind_badge = {
                "capacity": ("Dung lượng", "danger"),
                "rule": ("Tiêu chí", "warning"),
                "teacher": ("Giáo viên", "warning"),
                "time": ("Thời gian giải", "info"),
            }
            with st.expander(
                f"🔍 Vì sao phương án này chưa đẹp hơn? ({len(bottlenecks)} nút thắt)" if bottlenecks
                else "🔍 Nút thắt: không phát hiện",
                expanded=bool(bottlenecks) and bottlenecks[0].kind != "time",
            ):
                if not bottlenecks:
                    render_callout(
                        "Phương án đã tối ưu với cấu hình hiện tại, không có tiêu chí hay GV nào tập trung vi phạm.",
                        level="success",
                        title="Không có nút thắt",
                    )
                for b in bottlenecks:
                    label, status = kind_badge.get(b.kind, ("Khác", "info"))
                    with st.container(border=True):
                        st.markdown(f"{render_status_badge(label, status)} **{b.title}**", unsafe_allow_html=True)
                        st.caption(b.evidence)
                        st.markdown(f"👉 {b.action}")
                        if b.kind in ("capacity", "rule", "teacher"):
                            st.page_link("pages/10_Cau_hinh_Xep_lich.py", label="Mở Cấu hình xếp lịch", icon="⚙️")

            # ══════════════════════════════════════════════════════════════════
            # 🌟 STUDIO ĐIỀU PHỐI TKB & TINH CHỈNH NÂNG CAO
            # ══════════════════════════════════════════════════════════════════
            with st.expander("🛠️ Công cụ Tinh chỉnh nâng cao (Đổi Seed, Khóa lớp & Smart Swap)", expanded=False):
                if st.button(
                    "🎲 Thử phương án khác (Đổi Seed)",
                    key="btn_cand_seed",
                    help="Đổi số ngẫu nhiên (Seed) để thuật toán khám phá cách xếp mới.",
                    use_container_width=True,
                ):
                    new_seed = random.randint(100, 99999)
                    new_id = max(st.session_state["candidates"]) + 1 if st.session_state.get("candidates") else 1
                    cand_name = f"Phương án {new_id} (Seed {new_seed})"
                    inp_new, res_new = _run_single_solver(new_seed, single_custom_cfg)
                    if res_new.success:
                        metrics_new = compute_candidate_metrics(inp_new, res_new)
                        st.session_state["candidates"][new_id] = {
                            "id": new_id,
                            "key": "default",
                            "name": cand_name,
                            "strategy_desc": f"Thử nghiệm ngẫu nhiên Seed {new_seed}",
                            "seed": new_seed,
                            "time_limit": getattr(single_custom_cfg, "cpsat_time_limit_seconds", getattr(single_custom_cfg, "cpsat_time_limit_s", 45)) if single_custom_cfg else 45,
                            "result": res_new,
                            "inp": inp_new,
                            "metrics": metrics_new,
                        }
                        st.session_state["active_candidate_id"] = new_id
                        st.session_state["last_result"] = res_new
                        st.session_state["last_input"] = inp_new
                        st.rerun()
                    else:
                        st.error(f"Thử nghiệm với Seed {new_seed} không thành công: {res_new.failure_reason}")

                # GIAI ĐOẠN 2: KHÓA & TINH CHỈNH CHI TIẾT
                with st.expander("🔒 GIAI ĐOẠN 2: Khóa & Tinh chỉnh chi tiết (Incremental Re-solve & Smart Swap)", expanded=False):
                    st.markdown(
                        "Tại đây, bạn có thể **Khóa cố định** các lớp hoặc giáo viên đã có TKB rất đẹp, "
                        "sau đó yêu cầu thuật toán **chỉ đảo các ô còn lại** để triệt tiêu các điểm lủng/xấu mà không làm thay đổi các phần đã khóa."
                    )

                    tab_single_slot, tab_lock, tab_swap = st.tabs([
                        "🎯 Tinh chỉnh Tiết đơn lẻ",
                        "🔒 Khóa & Tinh chỉnh diện rộng",
                        "🔄 Đổi chéo thủ công 2 tiết",
                    ])

                    with tab_single_slot:
                        st.markdown("**Chọn lớp và tiết cụ thể cần thay đổi (hệ thống giữ nguyên toàn bộ các lớp khác, chỉ điều chỉnh lớp này):**")
                        c_single_cls = st.selectbox("Chọn lớp học cần tinh chỉnh:", options=[c.name for c in inp.classes], key="single_cls_pick")
                        target_cls = next(c for c in inp.classes if c.name == c_single_cls)
                        cls_slots = [s for s in inp.slots if s.class_id == target_cls.class_id]

                        subj_map = {s.subject_id: s.name for s in inp.subjects}
                        eff_assigned = _build_effective_assigned_teacher(inp)
                        t_map = {t.teacher_id: t.name for t in inp.teachers}

                        # Sắp xếp các slot theo thứ tự thời gian
                        cls_slots.sort(key=lambda s: (s.ts.weekday, 0 if s.ts.session == "S" else 1, s.ts.period))
                        slot_labels = {}
                        for s in cls_slots:
                            s_subj = result.assignment.get(s.slot_id)
                            subj_label = subj_map.get(s_subj, "(Trống)")
                            tid = eff_assigned.get((s_subj, target_cls.class_id))
                            tname = t_map.get(tid, "")
                            gv_str = f" | GV: {tname}" if tname else ""
                            sess_label = "Sáng" if s.ts.session == "S" else "Chiều"
                            slot_labels[s.slot_id] = f"{WEEKDAY_NAMES.get(s.ts.weekday)} - {sess_label} Tiết {s.ts.period}: {subj_label}{gv_str}"

                        c_slot_sel, c_slot_quick = st.columns([2, 1])
                        with c_slot_sel:
                            target_slot_id = st.selectbox(
                                "Chọn tiết muốn thay đổi:",
                                options=list(slot_labels.keys()),
                                format_func=lambda sid: slot_labels[sid],
                                key="single_target_slot",
                            )

                        target_s_obj = next((s for s in cls_slots if s.slot_id == target_slot_id), None)
                        curr_subj_id = result.assignment.get(target_slot_id)
                        curr_subj_name = subj_map.get(curr_subj_id, "(Trống)")
                        curr_tid = eff_assigned.get((curr_subj_id, target_cls.class_id))
                        curr_tname = t_map.get(curr_tid, "Chưa phân công")

                        with c_slot_quick:
                            st.caption("Chi tiết tiết được chọn:")
                            st.markdown(f"**{curr_subj_name}** | GV: `{curr_tname}`")

                        # Bảng TKB toàn diện của lớp đang khảo sát (Trực quan hóa 100%)
                        st.markdown(f"###### 📅 Bảng Thời Khóa Biểu đầy đủ của lớp **{target_cls.name}** (Tiết đang chọn có dấu 👉):")
                        cls_matrix_rows = []
                        for sess in ("S", "C"):
                            sess_name = "Sáng" if sess == "S" else "Chiều"
                            for per in range(1, 6):
                                row_data = {"Buổi": sess_name, "Tiết": per}
                                has_p = False
                                for wd in WEEKDAYS:
                                    s_match = next((s for s in cls_slots if s.ts.weekday == wd and s.ts.session == sess and s.ts.period == per), None)
                                    if s_match:
                                        s_subj = result.assignment.get(s_match.slot_id)
                                        s_name = subj_map.get(s_subj, "Trống") if s_subj else "Trống"
                                        tid = eff_assigned.get((s_subj, target_cls.class_id))
                                        t_name = t_map.get(tid, "")
                                        t_str = f" ({t_name})" if t_name else ""
                                        if s_match.slot_id == target_slot_id:
                                            row_data[WEEKDAY_NAMES[wd]] = f"👉 [{s_name}]{t_str}"
                                        else:
                                            row_data[WEEKDAY_NAMES[wd]] = f"{s_name}{t_str}" if s_subj else "—"
                                        has_p = True
                                    else:
                                        row_data[WEEKDAY_NAMES[wd]] = "—"
                                if has_p or sess == "S":
                                    cls_matrix_rows.append(row_data)

                        df_cls_preview = pd.DataFrame(cls_matrix_rows)
                        st.dataframe(df_cls_preview, hide_index=True, width="stretch")

                        st.markdown("---")
                        col_opt1, col_opt2 = st.columns(2)

                        with col_opt1:
                            st.markdown("##### ⚡ Cách 1: Gợi ý Đổi chéo an toàn (1-Click)")
                            st.caption("Tìm các tiết khác trong lớp có thể hoán đổi an toàn 100% (không trùng lịch GV, không vi phạm bận).")

                            valid_swaps = find_valid_swap_candidates(result.assignment, target_slot_id, inp)
                            if valid_swaps:
                                swap_choice_map = {c["slot_id"]: c["label"] for c in valid_swaps}
                                pick_swap_sid = st.selectbox(
                                    "Chọn tiết đổi cùng:",
                                    options=list(swap_choice_map.keys()),
                                    format_func=lambda sid: swap_choice_map[sid],
                                    key="pick_instant_swap",
                                )
                                if st.button("🔄 Đổi ngay với tiết này", key="btn_apply_instant_swap", type="primary"):
                                    ok, msg, new_ass = validate_and_swap_slots(result.assignment, target_slot_id, pick_swap_sid, inp)
                                    if ok:
                                        result.assignment = new_ass
                                        cur_cid = st.session_state.get("active_candidate_id", 1)
                                        if cur_cid in st.session_state.get("candidates", {}):
                                            st.session_state["candidates"][cur_cid]["metrics"] = compute_candidate_metrics(inp, result)
                                        st.session_state["last_result"] = result
                                        st.success(f"✅ {msg}")
                                        st.rerun()
                                    else:
                                        st.error(f"❌ {msg}")
                            else:
                                st.warning("Không có tiết nào trong lớp có thể đổi chéo trực tiếp mà không xung đột lịch GV.")

                        with col_opt2:
                            st.markdown("##### 🎯 Cách 2: Solver tìm phương án thế chỗ")
                            st.caption(f"Khóa cố định 100% tất cả các lớp khác, mở lớp **{target_cls.name}** và dời tiết `{curr_subj_name}` sang vị trí tối ưu mới.")
                            if st.button("🚀 Chạy Solver tìm cách đổi tiết này", key="btn_single_slot_solver"):
                                # Khóa tất cả các slot của các lớp khác
                                computed_locked = {}
                                for s in inp.slots:
                                    sid = result.assignment.get(s.slot_id)
                                    if sid is not None and s.class_id != target_cls.class_id:
                                        computed_locked[s.slot_id] = sid

                                refine_cfg = dataclasses.replace(
                                    single_custom_cfg or inp.config,
                                    cpsat_minimize_changes=True,
                                    cpsat_time_limit_seconds=15,
                                )
                                refine_seed = random.randint(100, 99999)
                                # Cấm môn hiện tại nằm tại ô hiện tại để solver bắt buộc phải chuyển sang ô khác
                                banned_pairs = [(target_slot_id, curr_subj_id)] if curr_subj_id else None
                                inp_ref, res_ref = _run_single_solver(
                                    refine_seed,
                                    refine_cfg,
                                    s_locked_slots=computed_locked,
                                    s_reference_assignment=result.assignment,
                                    banned_slots_subjects=banned_pairs,
                                )
                                if res_ref.success:
                                    metrics_ref = compute_candidate_metrics(inp_ref, res_ref)
                                    new_id = max(st.session_state["candidates"]) + 1 if st.session_state.get("candidates") else 1
                                    cand_name = f"Phương án {new_id} (Đổi riêng tiết {target_cls.name})"
                                    st.session_state["candidates"][new_id] = {
                                        "id": new_id,
                                        "key": "default",
                                        "name": cand_name,
                                        "seed": refine_seed,
                                        "time_limit": 15,
                                        "locked_slots": computed_locked,
                                        "result": res_ref,
                                        "inp": inp_ref,
                                        "metrics": metrics_ref,
                                    }
                                    st.session_state["active_candidate_id"] = new_id
                                    st.session_state["last_result"] = res_ref
                                    st.session_state["last_input"] = inp_ref
                                    st.success(f"🎉 Tinh chỉnh tiết thành công! Đã sinh phương án {new_id}.")
                                    st.rerun()
                                else:
                                    st.error(f"Solver không tìm được phương án hoán vị khả dĩ: {res_ref.failure_reason}")

                    with tab_lock:
                        col_l1, col_l2 = st.columns(2)
                        with col_l1:
                            st.markdown("**1. Chọn Lớp cần khóa (Giữ nguyên 100% TKB của lớp):**")
                            c_names = [c.name for c in inp.classes]
                            # Nút chọn nhanh
                            btn_k12, btn_k11, btn_k10, btn_clr = st.columns(4)
                            if btn_k12.button("Khóa K12", key="btn_lk12"):
                                st.session_state["locked_classes"] = [c.name for c in inp.classes if "12" in c.name]
                                st.rerun()
                            if btn_k11.button("Khóa K11", key="btn_lk11"):
                                st.session_state["locked_classes"] = [c.name for c in inp.classes if "11" in c.name]
                                st.rerun()
                            if btn_k10.button("Khóa K10", key="btn_lk10"):
                                st.session_state["locked_classes"] = [c.name for c in inp.classes if "10" in c.name]
                                st.rerun()
                            if btn_clr.button("Bỏ chọn", key="btn_lclr"):
                                st.session_state["locked_classes"] = []
                                st.rerun()

                            sel_classes = st.multiselect(
                                "Danh sách lớp khóa:",
                                options=c_names,
                                default=st.session_state.get("locked_classes", []),
                                key="ms_locked_classes",
                            )
                            st.session_state["locked_classes"] = sel_classes

                        with col_l2:
                            st.markdown("**2. Chọn Giáo viên cần khóa (Giữ nguyên lịch dạy của GV):**")
                            t_names = [t.name for t in inp.teachers]
                            sel_teachers = st.multiselect(
                                "Danh sách giáo viên khóa:",
                                options=t_names,
                                default=st.session_state.get("locked_teachers", []),
                                key="ms_locked_teachers",
                            )
                            st.session_state["locked_teachers"] = sel_teachers

                        st.markdown("---")
                        if st.button("🎯 Tinh chỉnh các ô còn lại (Chạy Solver Khóa)", type="primary", key="btn_do_refine"):
                            locked_class_ids = {c.class_id for c in inp.classes if c.name in sel_classes}
                            locked_teacher_ids = {t.teacher_id for t in inp.teachers if t.name in sel_teachers}

                            # Tìm các slot thuộc lớp bị khóa hoặc GV bị khóa
                            eff_assigned = _build_effective_assigned_teacher(inp)
                            computed_locked_slots = {}
                            for s in inp.slots:
                                subj_id = result.assignment.get(s.slot_id)
                                if subj_id is None:
                                    continue
                                if s.class_id in locked_class_ids:
                                    computed_locked_slots[s.slot_id] = subj_id
                                else:
                                    tid = eff_assigned.get((subj_id, s.class_id))
                                    if tid in locked_teacher_ids:
                                        computed_locked_slots[s.slot_id] = subj_id

                            # Bật cờ cpsat_minimize_changes
                            refine_cfg = dataclasses.replace(
                                single_custom_cfg or inp.config,
                                cpsat_minimize_changes=True,
                            )
                            refine_seed = seed or random.randint(100, 99999)
                            inp_ref, res_ref = _run_single_solver(
                                refine_seed,
                                refine_cfg,
                                s_locked_slots=computed_locked_slots,
                                s_reference_assignment=result.assignment,
                            )
                            if res_ref.success:
                                metrics_ref = compute_candidate_metrics(inp_ref, res_ref)
                                new_id = max(st.session_state["candidates"]) + 1 if st.session_state.get("candidates") else 1
                                cand_name = f"Phương án {new_id} (Tinh chỉnh: {len(sel_classes)} lớp, {len(sel_teachers)} GV khóa)"
                                st.session_state["candidates"][new_id] = {
                                    "id": new_id,
                                    "key": "default",
                                    "name": cand_name,
                                    "seed": refine_seed,
                                    "time_limit": getattr(refine_cfg, "cpsat_time_limit_seconds", getattr(refine_cfg, "cpsat_time_limit_s", 45)),
                                    "locked_slots": computed_locked_slots,
                                    "result": res_ref,
                                    "inp": inp_ref,
                                    "metrics": metrics_ref,
                                }
                                st.session_state["active_candidate_id"] = new_id
                                st.session_state["last_result"] = res_ref
                                st.session_state["last_input"] = inp_ref
                                st.success(f"🎉 Tinh chỉnh thành công! Đã khóa cố định {len(computed_locked_slots)} ô tiết.")
                                st.rerun()
                            else:
                                st.error(f"Không thể tinh chỉnh với các ràng buộc khóa hiện tại: {res_ref.failure_reason}")

                    with tab_swap:
                        st.markdown("**Đổi chéo thủ công 2 tiết có kiểm tra an toàn sư phạm:**")
                        c_swap_cls = st.selectbox("Chọn lớp:", options=[c.name for c in inp.classes], key="swap_cls_pick")
                        target_cls = next(c for c in inp.classes if c.name == c_swap_cls)
                        cls_slots = [s for s in inp.slots if s.class_id == target_cls.class_id]

                        subj_map = {s.subject_id: s.name for s in inp.subjects}
                        slot_labels = {}
                        for s in cls_slots:
                            s_subj = result.assignment.get(s.slot_id)
                            subj_label = subj_map.get(s_subj, "(Trống)")
                            sess_label = "Sáng" if s.ts.session == "S" else "Chiều"
                            slot_labels[s.slot_id] = f"{WEEKDAY_NAMES.get(s.ts.weekday)} - {sess_label} Tiết {s.ts.period}: {subj_label}"

                        col_sw1, col_sw2 = st.columns(2)
                        with col_sw1:
                            slot_a_id = st.selectbox("Chọn Tiết 1:", options=list(slot_labels.keys()), format_func=lambda sid: slot_labels[sid], key="sw_slot_a")
                        with col_sw2:
                            slot_b_id = st.selectbox("Chọn Tiết 2:", options=list(slot_labels.keys()), index=min(1, len(slot_labels) - 1), format_func=lambda sid: slot_labels[sid], key="sw_slot_b")

                        if st.button("🔄 Thực hiện Đổi chéo 2 tiết", key="btn_exec_smart_swap"):
                            ok, msg, new_ass = validate_and_swap_slots(result.assignment, slot_a_id, slot_b_id, inp)
                            if ok:
                                result.assignment = new_ass
                                cur_cid = st.session_state.get("active_candidate_id", 1)
                                if cur_cid in st.session_state.get("candidates", {}):
                                    st.session_state["candidates"][cur_cid]["metrics"] = compute_candidate_metrics(inp, result)
                                st.session_state["last_result"] = result
                                st.success(f"✅ {msg}")
                                st.rerun()
                            else:
                                st.error(f"❌ Không thể đổi chéo: {msg}")

                st.markdown("---")

            # ── Bảng Đánh Giá Sức Khỏe TKB (Thang điểm 100) ──
            health = compute_tkb_health_score(inp, result.assignment)
            with st.container():
                st.markdown(f"### 🩺 Bảng Đánh Giá Sức Khỏe TKB: **{health['overall_score']}/100** — *Xếp loại: {health['rating']}*")
                rating_variant = (
                    "success" if health["overall_score"] >= 85
                    else "primary" if health["overall_score"] >= 75
                    else "warning" if health["overall_score"] >= 60
                    else "danger"
                )
                render_kpi_row([
                    {
                        "title": "Điểm Tổng Thể",
                        "value": f"{health['overall_score']}/100",
                        "subtitle": f"Xếp loại: {health['rating']}",
                        "icon": "🏆",
                        "variant": rating_variant,
                    },
                    {
                        "title": "Sư Phạm Học Sinh",
                        "value": f"{health['pedagogical_score']}/100",
                        "subtitle": "Phân bổ môn & giãn cách",
                        "icon": "📚",
                        "variant": "info",
                    },
                    {
                        "title": "Tiện Nghi & Công Bằng GV",
                        "value": f"{health['teacher_score']}/100",
                        "subtitle": "Tránh lủng tiết & trống lẻ",
                        "icon": "👩‍🏫",
                        "variant": "warning",
                    },
                    {
                        "title": "Tuân Thủ HĐSP",
                        "value": f"{health['compliance_score']}/100",
                        "subtitle": "Ràng buộc mềm & ưu tiên",
                        "icon": "⚖️",
                        "variant": "success",
                    },
                ])

                with st.expander(f"📋 Khuyến nghị sư phạm & Chi tiết đánh giá ({len(health['recommendations'])} mục)", expanded=(health["overall_score"] < 85)):
                    for rec in health["recommendations"]:
                        t = rec["type"]
                        cat = rec.get("category", "")
                        msg = rec["message"]
                        if t == "error":
                            st.error(f"**[{cat}]** {msg}")
                        elif t == "warning":
                            st.warning(f"**[{cat}]** {msg}")
                        elif t == "info":
                            st.info(f"**[{cat}]** {msg}")
                        else:
                            st.success(f"**[{cat}]** {msg}")
                st.markdown("---")

            cells_curr = {
                (s.class_id, s.ts.weekday, s.ts.session, s.ts.period): result.assignment.get(s.slot_id)
                for s in inp.slots
            }
            eff_assigned = _build_effective_assigned_teacher(inp)
            _render_interactive_timetable_studio(
                classes=inp.classes,
                subjects=inp.subjects,
                teachers=inp.teachers,
                cells=cells_curr,
                assignments=eff_assigned,
                key_prefix="fresh_result_",
                title="Studio Khảo Sát Chi Tiết Phương Án Vừa Xếp",
                config=inp.config,
            )

            view_curr = build_schedule_view(inp, result.assignment)
            if not violations_curr:
                render_callout("Thời khóa biểu tuân thủ 100% quy chuẩn sư phạm.", level="success", title="Kiểm định HĐSP")
            single_gaps_curr = find_teacher_single_gaps(view_curr)
            proceed_with_hard_violations = _render_rule_violations(
                violations_curr, "proceed_with_hard_violations",
                single_gaps=single_gaps_curr,
            )

            # ── Kiểm tra định mức số tiết (Progressive Disclosure) ──
            if scheduled_week is not None:
                expected_quota = repo.get_periods_for_week(conn, week_no=scheduled_week, parity=parity)
            else:
                expected_quota = repo.get_periods_per_week(conn)
            diff = compute_quota_diff(inp.slots, result.assignment, expected_quota, parity)
            classes_sorted = sorted(inp.classes, key=lambda c: getattr(c, "sort_order", 0) or 0)
            non_zero_diffs = sum(1 for v in diff.values() if v != 0)

            if non_zero_diffs == 0:
                render_callout(f"Khớp 100% định mức số tiết chuẩn của Tuần {scheduled_week}.", level="success", title="Định mức")
            else:
                st.subheader(f"⚠️ Kiểm tra định mức (Có {non_zero_diffs} ô lệch định mức)")
                check_rows = []
                for subj in sorted(inp.subjects, key=lambda s: s.sort_order):
                    row = {"Môn": subj.name}
                    for cls in classes_sorted:
                        row[cls.name] = diff.get((subj.subject_id, cls.class_id), 0)
                    check_rows.append(row)
                def _highlight_nonzero(row):
                    return ["background-color: #ffc7ce" if col != "Môn" and row[col] != 0 else "" for col in row.index]
                st.dataframe(
                    pd.DataFrame(check_rows).style.apply(_highlight_nonzero, axis=1),
                    hide_index=True, width="stretch",
                )

    else:
        # ── Hiển thị Thời khóa biểu chính thức đã lưu của Tuần {chosen_week} (nếu có) ──
        saved_run = repo.get_latest_run_by_week(conn, chosen_week)
        saved_success = st.session_state.pop("saved_success_msg", None)
        if saved_success:
            st.success(saved_success)

        if saved_run:
            st.markdown("---")
            st.success(
                f"📖 **Thời khóa biểu chính thức đang áp dụng: Tuần {chosen_week}** — "
                f"Đã lưu lúc: **{saved_run['created_at']}** | "
                f"Seed: **{saved_run['seed']}** | Tổng số tiết đã xếp: **{saved_run['cells_total']}**\n\n"
                f"*(Nếu bạn muốn xếp lại lịch mới cho Tuần {chosen_week}, hãy tùy chỉnh ở trên và bấm nút **'🚀 Chạy xếp TKB'**)*"
            )

            col_s_dl, col_s_nhap = st.columns([1, 1])
            with col_s_dl:
                try:
                    week_xlsx = export_xlsx(conn, run_id=saved_run["run_id"])
                    st.download_button(
                        f"📥 Xuất Excel Tuần {chosen_week} (.xlsx)",
                        data=week_xlsx,
                        file_name=f"TKB_Tuan_{chosen_week}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key=f"btn_dl_active_week_{chosen_week}_{saved_run['run_id']}",
                        type="primary",
                    )
                except Exception as ex:
                    st.error(f"Lỗi xuất Excel: {ex}")

            with col_s_nhap:
                if st.button(f"🔄 Nạp Tuần {chosen_week} vào TKB Nháp", key=f"btn_load_to_nhap_tab1_{chosen_week}"):
                    saved_cells = repo.get_tkb_result(conn, saved_run["run_id"])
                    repo.bulk_replace_tkb_nhap(conn, saved_cells)
                    st.success(f"Đã nạp thành công TKB Tuần {chosen_week} vào bản nháp!")
                    st.rerun()

            st.markdown(f"##### Chi tiết Thời khóa biểu Tuần {chosen_week}")
            saved_cells = repo.get_tkb_result(conn, saved_run["run_id"])
            _render_saved_tkb(conn, saved_cells, classes, subjects, repo.list_teachers(conn), key_prefix=f"tab1_w{chosen_week}_")
        else:
            st.markdown("---")
            saved_weeks = repo.list_saved_weeks(conn)
            st.info(
                f"ℹ️ **Tuần {chosen_week}** chưa có thời khóa biểu chính thức được lưu trong hệ thống.\n\n"
                f"Nhấn nút **'🚀 Chạy xếp TKB'** ở trên để tạo và lưu thời khóa biểu cho Tuần {chosen_week}."
            )
            if saved_weeks:
                st.caption(f"📌 Các tuần đã có TKB chính thức: **{', '.join(f'Tuần {w}' for w in saved_weeks)}**")

    st.write("---")
    with st.expander("📅 Xếp nhiều tuần cùng lúc (tạm thời tắt)", expanded=False):
        st.info("Tính năng xếp nhiều tuần cùng lúc đang tạm thời tắt theo yêu cầu. Dùng chế độ xếp từng tuần ở trên.")
        _batch_scheduling_enabled = False
        if _batch_scheduling_enabled:
            st.caption("Xếp tự động hàng loạt tuần theo đúng định lượng số tiết của từng tuần tương ứng.")

            preset_choice = st.radio(
                "Chọn nhanh nhóm tuần:",
                ["Tùy chọn", "Toàn bộ Học kỳ I (Tuần 1 - 18)", "Toàn bộ Học kỳ II (Tuần 19 - 35)", "Tất cả 35 tuần trong năm"],
                horizontal=True,
                key="batch_preset_radio",
            )

            if preset_choice == "Toàn bộ Học kỳ I (Tuần 1 - 18)":
                default_batch = list(range(1, 19))
            elif preset_choice == "Toàn bộ Học kỳ II (Tuần 19 - 35)":
                default_batch = list(range(19, 36))
            elif preset_choice == "Tất cả 35 tuần trong năm":
                default_batch = list(range(1, 36))
            else:
                default_batch = [1, 2]

            batch_week_nos = st.multiselect(
                "Danh sách các tuần cần xếp:",
                options=list(range(1, 36)),
                default=default_batch,
                format_func=lambda wn: f"Tuần {wn}",
                key="batch_week_select",
            )

            batch_extra_kep_names = st.multiselect(
                "Môn cần xếp 2 tiết liền kề (kép) CHỈ cho các tuần này",
                extra_kep_options,
                key="batch_extra_kep_select",
            )
            batch_extra_kep_ids = frozenset(s.subject_id for s in subjects if s.name in batch_extra_kep_names)

            batch_sched_config = repo.get_scheduling_config(conn)
            with st.container(border=True):
                st.markdown("##### 🎯 Phương án xếp môn Hoạt động trải nghiệm (HĐTN) cho các tuần chọn")
                st.caption("Lựa chọn cách tổ chức môn HĐTN áp dụng cho toàn bộ các tuần được xếp đợt này.")

                batch_default_thematic = (getattr(batch_sched_config, "hdtn_mode", "separate") == "thematic")
                batch_hdtn_plan = st.radio(
                    "Phương án tổ chức HĐTN cho các tuần này:",
                    ["separate", "thematic"],
                    index=1 if batch_default_thematic else 0,
                    format_func=lambda p: (
                        "📅 Các tuần học chuẩn (3 tiết: Chào cờ + Hoạt động chủ đề + Sinh hoạt lớp)"
                        if p == "separate"
                        else "🎪 Các tuần chuyên đề (Dồn 3 tiết liền kề toàn trường)"
                    ),
                    key="batch_hdtn_plan_radio",
                    horizontal=True,
                )

                batch_hdtn_thematic_week = (batch_hdtn_plan == "thematic")
                batch_hdtn_thematic_mode = "auto"
                batch_hdtn_thematic_weekday = None
                batch_hdtn_thematic_session = "S"
                batch_hdtn_thematic_start_period = None

                batch_custom_cfg = None
                if not batch_hdtn_thematic_week:
                    batch_custom_periods = st.checkbox(
                        "✏️ Tự chỉnh lịch 3 tiết HĐTN riêng cho các tuần này (không đổi cấu hình gốc)",
                        value=False,
                        key="batch_custom_periods_chk",
                    )
                    if not batch_custom_periods:
                        st.info("📌 Các tuần này sẽ tự động áp dụng cấu hình 3 tiết HĐTN phân bổ chuẩn của trường (Chào cờ đầu tuần, Chủ đề, SHL cuối tuần).")
                    else:
                        c_bp1, c_bp2, c_bp3 = st.columns(3)
                        with c_bp1:
                            st.markdown("**🚩 Tiết 1 (Chào cờ)**")
                            b_c1w, b_c1s, b_c1p = st.columns(3)
                            bp1_w_cur = getattr(batch_sched_config, "hdtn_p1_weekday", 2)
                            bw_p1 = b_c1w.selectbox("Thứ", WEEKDAYS, index=WEEKDAYS.index(bp1_w_cur) if bp1_w_cur in WEEKDAYS else 0,
                                                    format_func=lambda w: f"T{w}", key="b_p1_w")
                            bs_p1 = b_c1s.selectbox("Buổi", ["S", "C"], index=0 if getattr(batch_sched_config, "hdtn_p1_session", "S") == "S" else 1,
                                                    format_func=lambda s: "Sáng" if s == "S" else "Chiều", key="b_p1_s")
                            bp_p1 = b_c1p.selectbox("Tiết", list(range(1, 6)), index=max(0, min(getattr(batch_sched_config, "hdtn_p1_period", 1) - 1, 4)), key="b_p1_p")

                        with c_bp2:
                            st.markdown("**📘 Tiết 2 (Chủ đề)**")
                            bp2_is_fixed = getattr(batch_sched_config, "hdtn_p2_weekday", None) is not None
                            bm_p2 = st.selectbox("Chế độ", ["auto", "fixed"], index=1 if bp2_is_fixed else 0,
                                                 format_func=lambda m: "🤖 Tự do" if m == "auto" else "📌 Cố định", key="b_p2_m")
                            if bm_p2 == "fixed":
                                b_c2w, b_c2s, b_c2p = st.columns(3)
                                bp2_w_cur = getattr(batch_sched_config, "hdtn_p2_weekday", 4) or 4
                                bw_p2 = b_c2w.selectbox("Thứ", WEEKDAYS, index=WEEKDAYS.index(bp2_w_cur) if bp2_w_cur in WEEKDAYS else 2,
                                                        format_func=lambda w: f"T{w}", key="b_p2_w")
                                bs_p2 = b_c2s.selectbox("Buổi", ["S", "C"], index=0 if getattr(batch_sched_config, "hdtn_p2_session", "S") == "S" else 1,
                                                        format_func=lambda s: "Sáng" if s == "S" else "Chiều", key="b_p2_s")
                                bp_p2 = b_c2p.selectbox("Tiết", list(range(1, 6)), index=max(0, min((getattr(batch_sched_config, "hdtn_p2_period", 2) or 2) - 1, 4)), key="b_p2_p")
                            else:
                                bw_p2, bs_p2, bp_p2 = None, "S", None

                        with c_bp3:
                            st.markdown("**👥 Tiết 3 (SHL)**")
                            bp3_is_fixed = getattr(batch_sched_config, "hdtn_p3_weekday", None) is not None
                            bm_p3 = st.selectbox("Chế độ", ["auto", "fixed"], index=1 if bp3_is_fixed else 0,
                                                 format_func=lambda m: "🤖 Tiết cuối tuần" if m == "auto" else "📌 Cố định", key="b_p3_m")
                            if bm_p3 == "fixed":
                                b_c3w, b_c3s, b_c3p = st.columns(3)
                                bp3_w_cur = getattr(batch_sched_config, "hdtn_p3_weekday", 6) or 6
                                bw_p3 = b_c3w.selectbox("Thứ", WEEKDAYS, index=WEEKDAYS.index(bp3_w_cur) if bp3_w_cur in WEEKDAYS else 4,
                                                        format_func=lambda w: f"T{w}", key="b_p3_w")
                                bs_p3 = b_c3s.selectbox("Buổi", ["S", "C"], index=0 if getattr(batch_sched_config, "hdtn_p3_session", "S") == "S" else 1,
                                                        format_func=lambda s: "Sáng" if s == "S" else "Chiều", key="b_p3_s")
                                bp3_opts = [0, 1, 2, 3, 4, 5]
                                cur_bp3_val = getattr(batch_sched_config, "hdtn_p3_period", 0) or 0
                                bp_p3 = b_c3p.selectbox("Tiết", bp3_opts, index=bp3_opts.index(cur_bp3_val) if cur_bp3_val in bp3_opts else 0,
                                                        format_func=lambda p: "Cuối" if p == 0 else f"T{p}", key="b_p3_p")
                            else:
                                bw_p3, bs_p3, bp_p3 = None, "S", None

                        batch_custom_cfg = dataclasses.replace(
                            batch_sched_config,
                            hdtn_p1_weekday=int(bw_p1),
                            hdtn_p1_session=str(bs_p1),
                            hdtn_p1_period=int(bp_p1),
                            chao_co_weekday=int(bw_p1),
                            chao_co_session=str(bs_p1),
                            chao_co_period=int(bp_p1),
                            hdtn_p2_weekday=int(bw_p2) if bm_p2 == "fixed" else None,
                            hdtn_p2_session=str(bs_p2) if bm_p2 == "fixed" else "S",
                            hdtn_p2_period=int(bp_p2) if bm_p2 == "fixed" else None,
                            hdtn_p3_weekday=int(bw_p3) if bm_p3 == "fixed" else None,
                            hdtn_p3_session=str(bs_p3) if bm_p3 == "fixed" else "S",
                            hdtn_p3_period=int(bp_p3) if (bm_p3 == "fixed" and int(bp_p3) > 0) else None,
                        )
                else:
                    batch_hdtn_thematic_mode = "auto"
                    batch_hdtn_thematic_weekday = None
                    batch_hdtn_thematic_session = "S"
                    batch_hdtn_thematic_start_period = None

                    st.success(
                        "🤖 **Chế độ Tự động tối ưu toàn trường (Mặc định)**:\n\n"
                        "Thuật toán CP-SAT sẽ tự động tìm dải 3 tiết liền kề tối ưu cho mỗi tuần và đồng bộ tất cả các lớp cùng thời điểm. **Bạn không cần phải tự chọn thời gian thủ công**."
                    )
                    b_allow_fixed = st.checkbox(
                        "Chỉ định khung giờ cố định cho các tuần này (nếu có lịch ấn định sẵn)",
                        value=False,
                        key="batch_allow_manual_thematic_fixed",
                    )
                    if b_allow_fixed:
                        c_wd, c_sess, c_p = st.columns(3)
                        b_def_wd = getattr(batch_sched_config, "hdtn_thematic_weekday", None) or 2
                        batch_hdtn_thematic_weekday = c_wd.selectbox(
                            "Thứ", [2, 3, 4, 5, 6, 7],
                            index=[2, 3, 4, 5, 6, 7].index(b_def_wd) if b_def_wd in [2, 3, 4, 5, 6, 7] else 0,
                            format_func=lambda w: f"Thứ {w}",
                            key="batch_hdtn_thematic_wd",
                        )
                        b_def_sess = getattr(batch_sched_config, "hdtn_thematic_session", "S") or "S"
                        batch_hdtn_thematic_session = c_sess.selectbox(
                            "Buổi", ["S", "C"],
                            index=0 if b_def_sess == "S" else 1,
                            format_func=lambda s: "Sáng" if s == "S" else "Chiều",
                            key="batch_hdtn_thematic_sess",
                        )
                        b_def_p = getattr(batch_sched_config, "hdtn_thematic_start_period", None) or 1
                        batch_hdtn_thematic_start_period = c_p.selectbox(
                            "Dải 3 tiết bắt đầu", [1, 2, 3],
                            index=[1, 2, 3].index(b_def_p) if b_def_p in [1, 2, 3] else 0,
                            format_func=lambda p: f"Tiết {p} → Tiết {p+2}",
                            key="batch_hdtn_thematic_p",
                        )
                        batch_hdtn_thematic_mode = "fixed"

            batch_quota_warnings = []
            for wn in batch_week_nos:
                b_qv = repo.get_teacher_quota_view(conn, week_no=wn)
                b_over = [q for q in b_qv if q["cap"] > 0 and q["load"] > q["cap"]]
                b_under = [q for q in b_qv if q["load"] < q["floor"]]
                if b_over or b_under:
                    parts = []
                    if b_over:
                        parts.append("Vượt: " + ", ".join(f"{q['name']} ({q['load']}/{q['cap']})" for q in b_over))
                    if b_under:
                        parts.append("Dưới sàn: " + ", ".join(f"{q['name']} ({q['load']}/{q['floor']})" for q in b_under))
                    batch_quota_warnings.append(
                        f"**Tuần {wn}**: " + " | ".join(parts)
                    )

            if batch_quota_warnings:
                with st.expander(f"ℹ️ Thông tin: Có {len(batch_quota_warnings)} tuần có GV vượt trần hoặc dưới sàn (chuẩn 16-19t)", expanded=False):
                    st.write("\n\n".join(f"- {w}" for w in batch_quota_warnings))

            if st.button("🚀 Xếp các tuần đã chọn", disabled=not batch_week_nos, type="primary"):
                batch_results = {}
                history = repo.list_seed_history(conn)
                seed_lookup = {h["week_no"]: h["seed"] for h in history}

                for wn in batch_week_nos:
                    b_parity = "C" if wn % 2 == 0 else "L"
                    b_seed = seed_lookup.get(wn, (seed + wn) if seed else 0)
                    b_inp = repo.build_scheduling_input(
                        conn, parity=b_parity, seed=b_seed,
                        extra_kep_ids=batch_extra_kep_ids,
                        hdtn_thematic_week=batch_hdtn_thematic_week,
                        hdtn_thematic_mode=batch_hdtn_thematic_mode,
                        hdtn_thematic_weekday=batch_hdtn_thematic_weekday,
                        hdtn_thematic_session=batch_hdtn_thematic_session,
                        hdtn_thematic_start_period=batch_hdtn_thematic_start_period,
                        week_no=wn,
                        config_override=batch_custom_cfg,
                    )
                    with st.spinner(f"Đang xếp Tuần {wn} (áp dụng định lượng Tuần {wn})..."):
                        b_result = sched.run(b_inp)
                    batch_results[wn] = (b_seed, b_parity, b_inp, b_result)
                st.session_state["batch_results"] = batch_results

            def _batch_highlight_nonzero(row):
                return ["background-color: #ffc7ce" if col != "Môn" and row[col] != 0 else "" for col in row.index]

            batch_results = st.session_state.get("batch_results", {})
            for wn, (b_seed, b_parity, b_inp, b_result) in list(batch_results.items()):
                with st.expander(f"Kết quả Tuần {wn}", expanded=True):
                    if not b_result.success:
                        st.error(b_result.failure_reason)
                        continue

                    if b_result.successes_found > 0:
                        st.success(
                            f"Xếp thành công sau {b_result.attempts_tried} lần thử "
                            f"({b_result.successes_found} phương án hợp lệ). "
                            f"Giữ nguyên {b_result.cells_total - b_result.cells_changed}/{b_result.cells_total} ô, "
                            f"thay đổi {b_result.cells_changed} ô."
                        )
                    else:
                        # successes_found == 0 is the ONLY other case where b_result.success is
                        # True (relaxed-fallback path) -- must not read as an unqualified success.
                        st.warning(
                            f"⚠️ Xếp xong sau {b_result.attempts_tried} lần thử. Lịch được tạo là phương án khả thi tốt "
                            f"nhất (một số ràng buộc HĐSP đã phải nới lỏng — xem chi tiết bên dưới). "
                            f"Giữ nguyên {b_result.cells_total - b_result.cells_changed}/{b_result.cells_total} ô, "
                            f"thay đổi {b_result.cells_changed} ô."
                        )

                    if b_result.relaxed_rules:
                        st.warning(f"⚠️ Lịch được tạo là phương án khả thi tốt nhất, nhưng {len(b_result.relaxed_rules)} ràng buộc HĐSP đã phải nới lỏng:")
                        for item in b_result.relaxed_rules:
                            rule_id = item.get("rule_id")
                            title = RULES[rule_id].title_vi if rule_id in RULES else rule_id
                            st.write(f"- {rule_id}: {title}")

                    b_subject_names = {s.subject_id: s.name for s in b_inp.subjects}
                    b_classes_sorted = sorted(b_inp.classes, key=lambda c: c.sort_order)
                    b_tabs = st.tabs([c.name for c in b_classes_sorted])
                    for tab, cls in zip(b_tabs, b_classes_sorted):
                        with tab:
                            cls_slots = [s for s in b_inp.slots if s.class_id == cls.class_id]
                            periods = sorted({(s.ts.session, s.ts.period) for s in cls_slots},
                                              key=lambda sp: (0 if sp[0] == "S" else 1, sp[1]))
                            grid = {key: {} for key in periods}
                            for s in cls_slots:
                                subj_id = b_result.assignment.get(s.slot_id)
                                grid[(s.ts.session, s.ts.period)][s.ts.weekday] = b_subject_names.get(subj_id, "")
                            rows = []
                            for (sess, per) in periods:
                                row = {"Buổi": "Sáng" if sess == "S" else "Chiều", "Tiết": per}
                                for wd in WEEKDAYS:
                                    row[WEEKDAY_NAMES[wd]] = grid[(sess, per)].get(wd, "")
                                rows.append(row)
                            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

                    b_view = build_schedule_view(b_inp, b_result.assignment)
                    b_single_gaps = find_teacher_single_gaps(b_view)
                    b_proceed_with_hard_violations = _render_rule_violations(
                        _schedule_violations(b_inp, b_result), f"batch_proceed_with_hard_violations_{wn}",
                        f" cho Tuần {wn}",
                        single_gaps=b_single_gaps,
                    )

                    st.caption(f"Kiểm tra định mức Tuần {wn} (thực tế − định mức tuần {wn}, kỳ vọng 0)")
                    b_expected_quota = repo.get_periods_for_week(conn, week_no=wn, parity=b_parity)
                    b_diff = compute_quota_diff(b_inp.slots, b_result.assignment, b_expected_quota, b_parity)
                    b_check_rows = []
                    for subj in sorted(b_inp.subjects, key=lambda s: s.sort_order):
                        row = {"Môn": subj.name}
                        for cls in b_classes_sorted:
                            row[cls.name] = b_diff.get((subj.subject_id, cls.class_id), 0)
                        b_check_rows.append(row)
                    st.dataframe(
                        pd.DataFrame(b_check_rows).style.apply(_batch_highlight_nonzero, axis=1),
                        hide_index=True, width="stretch",
                    )

                    if st.button(
                        f"✅ Chấp nhận & Lưu Tuần {wn}", key=f"batch_accept_{wn}",
                        disabled=not b_proceed_with_hard_violations,
                    ):
                        b_cells = {
                            (s.class_id, s.ts.weekday, s.ts.session, s.ts.period): b_result.assignment.get(s.slot_id)
                            for s in b_inp.slots
                        }
                        repo.bulk_replace_tkb_nhap(conn, b_cells)
                        repo.add_seed_history(conn, wn, b_seed, b_parity)
                        b_run_id = repo.save_run(conn, wn, b_seed, b_parity, b_result.cells_changed, b_result.cells_total,
                                                  True, "OK")
                        repo.save_tkb_result(conn, b_run_id, b_cells)
                        st.success(f"Đã lưu Tuần {wn} làm thời khóa biểu chính thức.")
                        del st.session_state["batch_results"][wn]
                        st.rerun()


with tab_history:
    st.subheader("📖 Xem lại & Xuất Excel Thời khóa biểu các tuần (1 - 35)")
    st.caption(
        "Xem lại chi tiết thời khóa biểu đã lưu chính thức của từng tuần trong năm học. "
        "Tải file Excel (.xlsx) chuẩn hoặc nạp lại bản TKB của tuần vào TKB Nháp."
    )

    saved_weeks = repo.list_saved_weeks(conn)
    col_w_sel, col_w_info = st.columns([1, 2])

    default_week = st.session_state.get("just_saved_week", saved_weeks[0] if saved_weeks else 1)
    if default_week not in range(1, 36):
        default_week = 1

    selected_view_week = col_w_sel.selectbox(
        "Chọn tuần muốn xem lại:",
        options=list(range(1, 36)),
        index=default_week - 1,
        format_func=lambda w: f"Tuần {w}{' — ✅ Đã lưu' if w in saved_weeks else ''}",
        key="history_week_select",
    )

    run_for_week = repo.get_latest_run_by_week(conn, selected_view_week)
    if not run_for_week:
        st.info(
            f"Tuần {selected_view_week} chưa có thời khóa biểu chính thức được lưu trong hệ thống. "
            f"Hãy sang tab **'🚀 Xếp Thời khóa biểu mới'** và chọn Tuần {selected_view_week} để tạo TKB."
        )
        if saved_weeks:
            st.caption(f"Các tuần đã có TKB chính thức: **{', '.join(f'Tuần {w}' for w in saved_weeks)}**")
    else:
        st.success(
            f"✅ **Thời khóa biểu Tuần {selected_view_week}** — "
            f"Đã lưu lúc: **{run_for_week['created_at']}** | "
            f"Seed: **{run_for_week['seed']}** | "
            f"Tổng số ô tiết đã xếp: **{run_for_week['cells_total']}**"
        )

        c_dl1, c_dl2 = st.columns([1, 1])
        with c_dl1:
            try:
                week_xlsx = export_xlsx(conn, run_id=run_for_week["run_id"])
                st.download_button(
                    f"📥 Xuất Excel Tuần {selected_view_week} (.xlsx)",
                    data=week_xlsx,
                    file_name=f"TKB_Tuan_{selected_view_week}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"btn_dl_history_week_{selected_view_week}_{run_for_week['run_id']}",
                    type="primary",
                )
            except Exception as ex:
                st.error(f"Lỗi xuất Excel: {ex}")

        with c_dl2:
            if st.button(f"🔄 Nạp Tuần {selected_view_week} vào TKB Nháp", key=f"btn_load_to_nhap_{selected_view_week}"):
                saved_cells = repo.get_tkb_result(conn, run_for_week["run_id"])
                repo.bulk_replace_tkb_nhap(conn, saved_cells)
                st.success(f"Đã nạp thành công TKB Tuần {selected_view_week} vào bản nháp!")
                st.rerun()

        st.markdown("---")
        saved_cells = repo.get_tkb_result(conn, run_for_week["run_id"])
        _render_saved_tkb(conn, saved_cells, classes, subjects, repo.list_teachers(conn), key_prefix="tab2_")


sidebar_backup_export(conn)
sidebar_school_switcher()
