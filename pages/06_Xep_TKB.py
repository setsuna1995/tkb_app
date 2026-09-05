import pandas as pd
import streamlit as st

from core import scheduler as sched
from core.models import ROLE_GDTC, ROLE_HDTN, ROLE_KEP, ROLE_NANG, ROLE_NANG_KEP, WEEKDAY_NAMES, WEEKDAYS, is_bgh
from core.validation import (
    compute_quota_diff, find_consecutive_subject_days, find_heavy_afternoon_period3_violations,
    find_invalid_gdtc_periods, find_max_heavy_violations, find_morning_only_violations,
    find_single_pair_violations, find_subject_class_rule_violations, find_teacher_conflicts,
    find_teacher_day_cap_violations, find_teacher_gaps, find_teacher_unavailability_violations,
    find_teacher_4_consecutive_morning_violations, find_teacher_lone_day_violations,
    find_teacher_lone_session_violations, find_teacher_missing_mandatory_morning_violations,
    find_teacher_split_day_violations,
)
from core.rules_registry import RULES
from data import repository as repo
from io_excel.exporter import export_xlsx, export_xlsx_both_parities
from ui_common import get_conn, require_auth, require_school, sidebar_backup_export, sidebar_school_switcher


def _format_rule_item(rule_id: str, item: tuple) -> str:
    wd = item[1] if len(item) > 1 and isinstance(item[1], int) else None
    wd_str = WEEKDAY_NAMES.get(wd, f"Thứ {wd}") if wd else ""
    if rule_id == "II.3":
        return f"{wd_str} Sáng (thiếu tiết dạy sáng bắt buộc)"
    elif rule_id == "II.4":
        sess = item[2] if len(item) > 2 else ""
        if sess == "cả ngày":
            return f"{wd_str} (cả ngày chỉ có đúng 1 tiết)"
        sess_str = "Sáng" if sess == "S" else ("Chiều" if sess == "C" else str(sess))
        return f"{wd_str} {sess_str} (buổi lẻ chỉ có 1 tiết)"
    elif rule_id == "II.8":
        return f"{wd_str} (Sáng 1 tiết + Chiều 1 tiết trong ngày)"
    elif rule_id == "II.14":
        return f"{wd_str} Sáng (dạy 4 tiết liên tục)"
    else:
        return ", ".join(str(x) for x in item[1:])



def _render_saved_tkb(conn, cells: dict, classes: list, subjects: list, teachers: list):
    assignments = repo.get_assignments(conn)
    subj_map = {s.subject_id: s.name for s in subjects}
    teach_map = {t.teacher_id: t.name for t in teachers}
    classes_sorted = sorted(classes, key=lambda c: c.sort_order)
    teachers_sorted = sorted(teachers, key=lambda t: t.name)

    view_mode = st.radio(
        "Chế độ hiển thị thời khóa biểu:",
        ["🏫 Xem theo Lớp học", "👩‍🏫 Xem theo Giáo viên"],
        horizontal=True,
        key="saved_tkb_view_mode",
    )

    if view_mode == "🏫 Xem theo Lớp học":
        cls_names = [c.name for c in classes_sorted]
        c_choice = st.selectbox("Chọn lớp để xem chi tiết:", cls_names, key="saved_cls_pick")
        chosen_cls = next(c for c in classes_sorted if c.name == c_choice)

        rows = []
        for sess in ("S", "C"):
            sess_name = "Sáng" if sess == "S" else "Chiều"
            for per in range(1, 6):
                row = {"Buổi": sess_name, "Tiết": per}
                has_any = False
                for wd in WEEKDAYS:
                    sid = cells.get((chosen_cls.class_id, wd, sess, per))
                    if sid:
                        s_name = subj_map.get(sid, f"Môn #{sid}")
                        tid = assignments.get((sid, chosen_cls.class_id))
                        t_name = teach_map.get(tid, "")
                        row[WEEKDAY_NAMES[wd]] = f"{s_name} ({t_name})" if t_name else s_name
                        has_any = True
                    else:
                        row[WEEKDAY_NAMES[wd]] = ""
                rows.append(row)
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    else:
        t_names = [t.name for t in teachers_sorted]
        t_choice = st.selectbox("Chọn giáo viên để xem lịch dạy:", t_names, key="saved_t_pick")
        chosen_t = next(t for t in teachers_sorted if t.name == t_choice)

        t_grid = {}
        for (cid, wd, sess, per), sid in cells.items():
            if sid:
                tid = assignments.get((sid, cid))
                if tid == chosen_t.teacher_id:
                    c_name = next((c.name for c in classes_sorted if c.class_id == cid), f"Lớp #{cid}")
                    s_name = subj_map.get(sid, f"Môn #{sid}")
                    t_grid[(wd, sess, per)] = f"{s_name} ({c_name})"

        rows = []
        total_p = 0
        for sess in ("S", "C"):
            sess_name = "Sáng" if sess == "S" else "Chiều"
            for per in range(1, 6):
                row = {"Buổi": sess_name, "Tiết": per}
                for wd in WEEKDAYS:
                    val = t_grid.get((wd, sess, per), "")
                    if val:
                        total_p += 1
                    row[WEEKDAY_NAMES[wd]] = val
                rows.append(row)
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        st.caption(f"👉 Tổng số tiết giảng dạy trong tuần của **{chosen_t.name}**: **{total_p}** tiết.")

require_auth()
school_slug = require_school()
conn = get_conn(school_slug)
st.title("Xếp thời khóa biểu")

classes = repo.list_classes(conn)
subjects = repo.list_subjects(conn)
if not classes or not subjects:
    st.info("Chưa có lớp/môn. Vào trang Khai báo hoặc Nhập/Xuất Excel trước.")
    st.stop()

tab_schedule, tab_history = st.tabs([
    "🚀 Xếp Thời khóa biểu mới",
    "📖 Xem lại & Xuất Excel TKB các tuần (1 - 35)",
])

with tab_schedule:
    c_mode, c_sel = st.columns([1, 2])
    sched_mode = c_mode.radio(
        "Chế độ xếp",
        ["📅 Theo tuần cụ thể trong năm (1-35)", "⚖️ Theo tuần Chẵn / Lẻ"],
        horizontal=True,
        key="sched_mode_radio",
    )

    seed, parity = repo.get_tuan_config(conn)

    if sched_mode == "📅 Theo tuần cụ thể trong năm (1-35)":
        chosen_week = c_sel.selectbox(
            "Chọn tuần cần xếp:",
            options=list(range(1, 36)),
            index=0,
            format_func=lambda w: f"Tuần {w} ({'Học kỳ I' if w <= 18 else 'Học kỳ II'} — {'Chẵn' if w % 2 == 0 else 'Lẻ'})",
            key="sched_week_select",
        )
        chosen_parity = "C" if chosen_week % 2 == 0 else "L"
        if chosen_parity != parity:
            repo.set_tuan_config(conn, seed, chosen_parity)
            parity = chosen_parity
        st.write(f"Tuần đang xếp: **Tuần {chosen_week}** ({'Chẵn' if parity == 'C' else 'Lẻ'}), seed = {seed or '(ngẫu nhiên mỗi lần chạy)'}")
        st.caption(f"🎯 **Định lượng:** Tự động áp dụng phân bổ số tiết theo định mức của **Tuần {chosen_week}**.")
    else:
        chosen_week = None
        chosen_label = c_sel.radio("Tuần", ["Chẵn", "Lẻ"], index=0 if parity == "C" else 1, horizontal=True)
        chosen_parity = "C" if chosen_label == "Chẵn" else "L"
        if chosen_parity != parity:
            repo.set_tuan_config(conn, seed, chosen_parity)
            parity = chosen_parity
        st.write(f"Tuần hiện tại: **{'Chẵn' if parity == 'C' else 'Lẻ'}**, seed = {seed or '(ngẫu nhiên mỗi lần chạy)'}")

    quota_view = repo.get_teacher_quota_view(conn, parity=parity, week_no=chosen_week)
    over = [q for q in quota_view if q["cap"] > 0 and q["load"] > q["cap"]]
    under = [q for q in quota_view if q["load"] < q["floor"]]
    if over or under:
        week_label = f"Tuần {chosen_week}" if chosen_week is not None else (f"Tuần {'Chẵn' if parity == 'C' else 'Lẻ'}")
        info_titles = []
        if over:
            info_titles.append(f"{len(over)} GV dạy vượt trần (> trần)")
        if under:
            info_titles.append(f"{len(under)} GV dưới sàn (< sàn)")
        with st.expander(f"ℹ️ Tải giảng dạy {week_label} (chuẩn 16-19 tiết/tuần): Có {', '.join(info_titles)}", expanded=False):
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

    extra_kep_options = [s.name for s in subjects if s.role_code != ROLE_HDTN]
    extra_kep_names = st.multiselect(
        "Môn cần xếp 2 tiết liền kề (kép) CHỈ cho tuần này",
        extra_kep_options,
        help="Không đổi vĩnh viễn phân loại môn học -- chỉ áp dụng cho lần chạy xếp TKB này.",
    )
    extra_kep_ids = frozenset(s.subject_id for s in subjects if s.name in extra_kep_names)

    hdtn_thematic_week = st.checkbox(
        "Tuần này tổ chức chuyên đề (HDTN dồn 3 tiết liền kề toàn trường, bỏ ghim chào cờ + SHL)",
        help="Áp dụng cho toàn trường, chỉ lần chạy xếp TKB này -- không đổi vĩnh viễn.",
    )

    sched_config = repo.get_scheduling_config(conn)
    use_cpsat_run = st.checkbox(
        "🚀 Sử dụng bộ giải tối ưu toàn cục CP-SAT (Khuyên dùng — Triệt tiêu vi phạm II.3, II.4, II.8)",
        value=bool(getattr(sched_config, "use_cpsat", True)),
        help="Giải toán bằng ràng buộc toán học toàn cục thay vì tìm kiếm ngẫu nhiên. Khuyên dùng để đảm bảo chất lượng thời khóa biểu cao nhất.",
    )

    if st.button("🚀 Chạy xếp TKB", type="primary"):
        inp = repo.build_scheduling_input(
            conn, parity=parity, seed=seed, extra_kep_ids=extra_kep_ids,
            hdtn_thematic_week=hdtn_thematic_week, week_no=chosen_week,
        )
        inp.config.use_cpsat = bool(use_cpsat_run)

        if use_cpsat_run:
            # Thanh tiến trình theo TỪNG ĐỢT giải (không mượt theo giây -- CP-SAT
            # chặn luồng Python trong lúc Solve(), xem cpsat_model._diagnose_and_solve's
            # docstring), nhưng vẫn hơn hẳn spinner tĩnh không có thông tin gì
            # (2026-09-05, yêu cầu người dùng "biết sắp xếp đến đâu rồi").
            progress_bar = st.progress(0, text="Đang chuẩn bị mô hình CP-SAT...")
            status_log = st.empty()
            log_lines = []

            def _on_cpsat_progress(info):
                max_passes = max(info.get("max_passes", 1), 1)
                event = info.get("event")
                pass_no = info.get("pass", 1)
                if event == "pass_start":
                    hard_rids = info.get("hard_rids") or []
                    relaxed = info.get("relaxed_so_far") or []
                    desc = (f"ràng buộc cứng còn lại: {', '.join(hard_rids)}" if hard_rids
                            else "phần còn lại (chỉ còn ràng buộc mềm)")
                    workers = info.get("workers")
                    w_str = f" ({workers} luồng CPU)" if workers else ""
                    line = f"⏳ Lần thử {pass_no}/{max_passes}{w_str}: đang giải {desc}"
                    if relaxed:
                        line += f" — đã phải nới lỏng trước đó: {', '.join(relaxed)}"
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

            result = sched.run(inp, progress_cb=_on_cpsat_progress)
            progress_bar.progress(1.0, text="Hoàn tất.")
        else:
            with st.spinner("Đang xếp thời khóa biểu bằng bộ giải Heuristic..."):
                result = sched.run(inp)

        st.session_state["last_result"] = result
        st.session_state["last_input"] = inp
        st.session_state["last_scheduled_week"] = chosen_week

    result = st.session_state.get("last_result")
    inp = st.session_state.get("last_input")
    scheduled_week = st.session_state.get("last_scheduled_week")

    if result is not None:
        if not result.success:
            st.error(result.failure_reason)
        else:
            if getattr(result, "solver_name", "") == "cpsat":
                st.info("✨ Tối ưu hóa bằng CP-SAT (toàn cục)")
            elif inp and getattr(inp.config, "use_cpsat", False):
                st.warning("⚠️ CP-SAT quá giờ hoặc không khả thi, đã tự động chuyển sang bộ giải dự phòng.")

            if result.successes_found > 0:
                st.success(
                    f"Xếp thành công sau {result.attempts_tried} lần thử "
                    f"({result.successes_found} phương án hợp lệ). "
                    f"Giữ nguyên {result.cells_total - result.cells_changed}/{result.cells_total} ô, "
                    f"thay đổi {result.cells_changed} ô."
                )
            else:
                # successes_found == 0 is the ONLY other case where result.success is True
                # (core/scheduler/engine.py's relaxed-fallback path) -- this is NOT a fully
                # compliant schedule, so it must not look like an unqualified success.
                st.warning(
                    f"⚠️ Xếp xong sau {result.attempts_tried} lần thử. Lịch được tạo là phương án khả thi tốt "
                    f"nhất (một số ràng buộc HĐSP đã phải nới lỏng — xem chi tiết bên dưới). "
                    f"Giữ nguyên {result.cells_total - result.cells_changed}/{result.cells_total} ô, "
                    f"thay đổi {result.cells_changed} ô."
                )

            if result.relaxed_rules:
                st.warning(f"⚠️ Lịch được tạo là phương án khả thi tốt nhất, nhưng {len(result.relaxed_rules)} ràng buộc HĐSP đã phải nới lỏng:")
                for item in result.relaxed_rules:
                    rule_id = item.get("rule_id")
                    title = RULES[rule_id].title_vi if rule_id in RULES else rule_id
                    st.write(f"- {rule_id}: {title}")

            subject_names = {s.subject_id: s.name for s in inp.subjects}
            classes_sorted = sorted(inp.classes, key=lambda c: c.sort_order)
            tab_objs = st.tabs([c.name for c in classes_sorted])
            for tab, cls in zip(tab_objs, classes_sorted):
                with tab:
                    cls_slots = [s for s in inp.slots if s.class_id == cls.class_id]
                    periods = sorted({(s.ts.session, s.ts.period) for s in cls_slots},
                                      key=lambda sp: (0 if sp[0] == "S" else 1, sp[1]))
                    grid = {key: {} for key in periods}
                    for s in cls_slots:
                        subj_id = result.assignment.get(s.slot_id)
                        grid[(s.ts.session, s.ts.period)][s.ts.weekday] = subject_names.get(subj_id, "")
                    rows = []
                    for (sess, per) in periods:
                        row = {"Buổi": "Sáng" if sess == "S" else "Chiều", "Tiết": per}
                        for wd in WEEKDAYS:
                            row[WEEKDAY_NAMES[wd]] = grid[(sess, per)].get(wd, "")
                        rows.append(row)
                    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

            # ── Xem TKB theo Giáo viên ──
            teacher_map = {t.teacher_id: t.name for t in inp.teachers}
            teacher_sorted = sorted(inp.teachers, key=lambda t: t.name)
            class_name_map = {c.class_id: c.name for c in inp.classes}

            with st.expander("👩‍🏫 Xem thời khóa biểu theo Giáo viên", expanded=False):
                # Build teacher schedule lookup
                from collections import defaultdict as _ddict
                _t_sched = _ddict(lambda: _ddict(list))
                for s in inp.slots:
                    sub = result.assignment.get(s.slot_id)
                    if sub is not None and sub != -1:
                        tid = inp.assigned_teacher.get((sub, s.class_id))
                        if tid and tid > 0:
                            _t_sched[tid][(s.ts.weekday, s.ts.session, s.ts.period)].append(
                                (class_name_map.get(s.class_id, "?"), subject_names.get(sub, "?"))
                            )

                # Count periods per session for lone-session detection
                _t_sess_counts = _ddict(int)
                for tid in _t_sched:
                    for (wd, sess, per) in _t_sched[tid]:
                        _t_sess_counts[(tid, wd, sess)] += 1

                # Quick stats
                total_lone = sum(1 for v in _t_sess_counts.values() if v == 1)
                if total_lone > 0:
                    st.warning(f"⚠️ Có **{total_lone}** buổi giáo viên chỉ dạy 1 tiết (lẻ buổi).")
                else:
                    st.success("✅ Không có giáo viên nào bị lẻ 1 tiết / buổi.")

                # View mode: single teacher or all teachers overview
                view_mode = st.radio(
                    "Chế độ xem", ["Chọn 1 GV", "Tổng quan tất cả GV"],
                    horizontal=True, key="teacher_view_mode"
                )

                if view_mode == "Chọn 1 GV":
                    chosen_teacher = st.selectbox(
                        "Chọn giáo viên",
                        teacher_sorted,
                        format_func=lambda t: t.name,
                        key="teacher_tkb_select",
                    )
                    if chosen_teacher:
                        tid = chosen_teacher.teacher_id
                        # Compute all sessions/periods this school uses
                        all_periods = sorted(
                            {(s.ts.session, s.ts.period) for s in inp.slots},
                            key=lambda sp: (0 if sp[0] == "S" else 1, sp[1])
                        )
                        rows = []
                        for (sess, per) in all_periods:
                            row = {"Buổi": "Sáng" if sess == "S" else "Chiều", "Tiết": per}
                            for wd in WEEKDAYS:
                                entries = _t_sched[tid].get((wd, sess, per), [])
                                row[WEEKDAY_NAMES[wd]] = ", ".join(f"{c} ({s})" for c, s in entries) if entries else ""
                            rows.append(row)

                        df = pd.DataFrame(rows)

                        # Highlight lone sessions
                        def _highlight_lone(row):
                            styles = [""] * len(row)
                            sess_code = "S" if row["Buổi"] == "Sáng" else "C"
                            for i, col in enumerate(row.index):
                                if col in ("Buổi", "Tiết"):
                                    continue
                                wd_num = next((k for k, v in WEEKDAY_NAMES.items() if v == col), None)
                                if wd_num and row[col] and _t_sess_counts.get((tid, wd_num, sess_code), 0) == 1:
                                    styles[i] = "background-color: #ffc7ce; font-weight: bold"
                            return styles

                        st.dataframe(
                            df.style.apply(_highlight_lone, axis=1),
                            hide_index=True, width="stretch",
                        )

                        # Summary stats for this teacher
                        total_periods = sum(len(v) for k, v in _t_sched[tid].items())
                        days_teaching = len({wd for (wd, sess, per) in _t_sched[tid]})
                        sessions_teaching = len({(wd, sess) for (wd, sess, per) in _t_sched[tid]})
                        lone_count = sum(
                            1 for (wd, sess) in {(wd, sess) for (wd, sess, per) in _t_sched[tid]}
                            if _t_sess_counts.get((tid, wd, sess), 0) == 1
                        )
                        col1, col2, col3, col4 = st.columns(4)
                        col1.metric("Tổng tiết/tuần", total_periods)
                        col2.metric("Số ngày dạy", days_teaching)
                        col3.metric("Số buổi dạy", sessions_teaching)
                        col4.metric("Buổi lẻ 1 tiết", lone_count, delta=f"-{lone_count}" if lone_count else None,
                                    delta_color="inverse" if lone_count else "off")

                else:
                    # Overview: table with all teachers, their stats and lone sessions
                    overview_rows = []
                    for t in teacher_sorted:
                        tid = t.teacher_id
                        total_periods = sum(len(v) for k, v in _t_sched[tid].items())
                        if total_periods == 0:
                            continue
                        sessions_set = {(wd, sess) for (wd, sess, per) in _t_sched[tid]}
                        lone_count = sum(1 for (wd, sess) in sessions_set if _t_sess_counts.get((tid, wd, sess), 0) == 1)
                        lone_details = []
                        for (wd, sess) in sorted(sessions_set):
                            if _t_sess_counts.get((tid, wd, sess), 0) == 1:
                                sess_name = "S" if sess == "S" else "C"
                                lone_details.append(f"{WEEKDAY_NAMES[wd]} ({sess_name})")
                        overview_rows.append({
                            "Giáo viên": t.name,
                            "Tổng tiết": total_periods,
                            "Số buổi dạy": len(sessions_set),
                            "Buổi lẻ 1 tiết": lone_count,
                            "Chi tiết lẻ": ", ".join(lone_details) if lone_details else "—",
                        })

                    df_overview = pd.DataFrame(overview_rows)

                    def _highlight_lone_overview(row):
                        return [
                            "background-color: #ffc7ce; font-weight: bold" if col == "Buổi lẻ 1 tiết" and row[col] > 0
                            else "" for col in row.index
                        ]

                    st.dataframe(
                        df_overview.style.apply(_highlight_lone_overview, axis=1),
                        hide_index=True, width="stretch",
                    )

            conflicts = find_teacher_conflicts(inp.slots, result.assignment, inp.assigned_teacher)
            if conflicts:
                st.error(f"❌ Phát hiện {len(conflicts)} trường hợp GV trùng lịch.")

            busy_violations = find_teacher_unavailability_violations(
                inp.slots, result.assignment, inp.assigned_teacher, inp.ban_busy
            )
            if busy_violations:
                st.error(f"❌ Phát hiện {len(busy_violations)} tiết xếp vào giờ GV đã khai báo bận (GV_Bận).")

            gdtc_id = next((s.subject_id for s in inp.subjects if s.role_code == ROLE_GDTC), None)
            if gdtc_id:
                gdtc_period_violations = find_invalid_gdtc_periods(
                    inp.slots, result.assignment, gdtc_id,
                    getattr(inp.config, "gdtc_morning_allowed_periods", (1, 2, 3, 4)),
                    getattr(inp.config, "gdtc_afternoon_allowed_periods", (2, 3)),
                )
                if gdtc_period_violations:
                    st.error(f"❌ Phát hiện {len(gdtc_period_violations)} tiết GDTC xếp ngoài khung giờ cho phép.")

            # Kiểm tra môn không xếp liền ngày (GDTC + các môn trong non_consecutive_subject_ids)
            non_consec_ids = set(getattr(inp.config, "non_consecutive_subject_ids", frozenset()))
            if getattr(inp.config, "avoid_gdtc_consecutive_days", True) and gdtc_id:
                non_consec_ids.add(gdtc_id)
            if non_consec_ids:
                consec_violations = find_consecutive_subject_days(inp.slots, result.assignment, non_consec_ids)
                if consec_violations:
                    st.error(f"❌ Phát hiện {len(consec_violations)} trường hợp môn không xếp liền ngày bị xếp 2 ngày liền kề.")

            # Kiểm tra môn bắt buộc sáng (cấm chiều)
            morning_only_ids = set(getattr(inp.config, "morning_only_subject_ids", frozenset()))
            if getattr(inp.config, "heavy_subjects_morning_only", False):
                heavy_ids = {s.subject_id for s in inp.subjects if s.role_code in (ROLE_NANG, ROLE_NANG_KEP)}
                morning_only_ids |= heavy_ids
            if morning_only_ids:
                morn_violations = find_morning_only_violations(inp.slots, result.assignment, morning_only_ids)
                if morn_violations:
                    st.error(f"❌ Phát hiện {len(morn_violations)} tiết môn cấm chiều bị xếp vào buổi chiều.")

            # Kiểm tra vượt trần môn Nặng liên tiếp
            heavy_subject_ids = {s.subject_id for s in inp.subjects if s.role_code in (ROLE_NANG, ROLE_NANG_KEP)}
            if heavy_subject_ids:
                max_heavy = getattr(inp.config, "max_heavy_consecutive", 3)
                heavy_run_violations = find_max_heavy_violations(inp.slots, result.assignment, heavy_subject_ids, max_heavy)
                if heavy_run_violations:
                    st.error(f"❌ Phát hiện {len(heavy_run_violations)} trường hợp môn Nặng bị xếp vượt quá {max_heavy} tiết liên tiếp.")

            # Kiểm tra luật môn/lớp theo buổi cụ thể
            subject_class_rules = repo.list_subject_class_rules(conn)
            if subject_class_rules:
                rule_violations = find_subject_class_rule_violations(inp.slots, result.assignment, subject_class_rules)
                if rule_violations:
                    st.error(f"❌ Phát hiện {len(rule_violations)} tiết vi phạm ràng buộc môn/lớp theo buổi.")

            # Kiểm tra môn 1 cặp liền tiết (single pair)
            single_pair_ids = set(getattr(inp.config, "single_pair_subject_ids", frozenset()))
            if single_pair_ids:
                pair_violations = find_single_pair_violations(inp.slots, result.assignment, single_pair_ids)
                if pair_violations:
                    st.error(f"❌ Phát hiện {len(pair_violations)} trường hợp môn 1 cặp liền tiết bị phân bổ sai quy tắc.")

            # Kiểm tra trần tiết dạy/ngày của Giáo viên (Tiêu chí II.2)
            max_teacher_day = getattr(inp.config, "max_teacher_periods_per_day", 5)
            day_cap_violations = find_teacher_day_cap_violations(inp.slots, result.assignment, inp.assigned_teacher, max_teacher_day)
            if day_cap_violations:
                teacher_map = {t.teacher_id: t.name for t in inp.teachers}
                st.error(f"❌ Phát hiện {len(day_cap_violations)} trường hợp GV dạy vượt quá {max_teacher_day} tiết/ngày:")
                for tid, wd, count in day_cap_violations:
                    tname = teacher_map.get(tid, f"GV #{tid}")
                    st.write(f"- {tname}: {WEEKDAY_NAMES[wd]} dạy {count} tiết (vượt trần {max_teacher_day})")

            # Kiểm tra môn Nặng vào tiết 3 chiều (Tiêu chí II.15)
            if getattr(inp.config, "avoid_heavy_afternoon_period3", True) and heavy_subject_ids:
                heavy_p3_violations = find_heavy_afternoon_period3_violations(inp.slots, result.assignment, heavy_subject_ids)
                if heavy_p3_violations:
                    st.error(f"❌ Phát hiện {len(heavy_p3_violations)} tiết môn Nặng bị xếp vào tiết 3 buổi chiều.")

            # Kiểm tra tiêu chí HĐSP hard-gate (II.3 + II.4 + II.8 -- chặn nút lưu, per
            # quyết định 2026-09-03 [bản sửa thứ 3 trong ngày]). II.14 là cảnh báo mềm
            # (không chặn lưu) -- engine vẫn cố tránh khi có thể qua điểm trừ mềm sẵn có
            # trong quality.py, chỉ là không còn reject/relax vì nó nữa.
            teacher_map = {t.teacher_id: t.name for t in inp.teachers}
            hard_rule_violations = {}
            soft_rule_warnings = {}

            missing_morning = find_teacher_missing_mandatory_morning_violations(
                inp.slots, result.assignment, inp.assigned_teacher,
                getattr(inp.config, "mandatory_morning_weekdays", (2, 5, 6)),
                getattr(inp.config, "min_weekly_periods_for_mandatory_morning", 10),
                getattr(inp.config, "strict_morning_weekdays", ()) or (),
                frozenset(t.teacher_id for t in inp.teachers if is_bgh(t)),
                ban_busy=getattr(inp, "ban_busy", None),
            )
            if missing_morning:
                hard_rule_violations["II.3"] = missing_morning

            min_lone_load = getattr(inp.config, "min_weekly_periods_for_lone_penalty", 8)
            lone_exempt_ids = getattr(inp.config, "lone_session_exempt_teacher_ids", frozenset()) or frozenset()
            if getattr(inp.config, "avoid_teacher_lone_periods", True):
                # Gated the same way engine.py:_check_hard_post_generation_rules gates II.4/II.8.
                lone_sessions = find_teacher_lone_session_violations(inp.slots, result.assignment, inp.assigned_teacher, min_lone_load, lone_exempt_ids)
                lone_days = find_teacher_lone_day_violations(inp.slots, result.assignment, inp.assigned_teacher, min_lone_load, lone_exempt_ids)
                if lone_sessions or lone_days:
                    hard_rule_violations["II.4"] = lone_sessions + [(tid, wd, "cả ngày") for tid, wd in lone_days]

                split_days = find_teacher_split_day_violations(inp.slots, result.assignment, inp.assigned_teacher, min_lone_load, lone_exempt_ids)
                if split_days:
                    hard_rule_violations["II.8"] = split_days

            if getattr(inp.config, "avoid_teacher_4_consecutive_morning", True):
                consecutive_morning = find_teacher_4_consecutive_morning_violations(inp.slots, result.assignment, inp.assigned_teacher)
                if consecutive_morning:
                    soft_rule_warnings["II.14"] = consecutive_morning

            if hard_rule_violations:
                st.error(f"❌ Còn {len(hard_rule_violations)} tiêu chí HĐSP bắt buộc chưa được thỏa mãn (chặn lưu):")
                for rule_id, items in hard_rule_violations.items():
                    with st.expander(f"{rule_id}: {RULES[rule_id].title_vi} ({len(items)} trường hợp)", expanded=False):
                        for item in items:
                            tid = item[0]
                            tname = teacher_map.get(tid, f"GV #{tid}")
                            detail = _format_rule_item(rule_id, item)
                            st.write(f"- **{tname}**: {detail}")

            if soft_rule_warnings:
                with st.expander(
                    f"⚠️ {sum(len(v) for v in soft_rule_warnings.values())} trường hợp thuộc "
                    f"{len(soft_rule_warnings)} tiêu chí HĐSP mềm (không chặn lưu)", expanded=False,
                ):
                    for rule_id, items in soft_rule_warnings.items():
                        st.write(f"**{rule_id}: {RULES[rule_id].title_vi}** ({len(items)} trường hợp)")
                        for item in items:
                            tid = item[0]
                            tname = teacher_map.get(tid, f"GV #{tid}")
                            detail = _format_rule_item(rule_id, item)
                            st.write(f"- **{tname}**: {detail}")

            proceed_with_hard_violations = True
            if hard_rule_violations:
                proceed_with_hard_violations = st.checkbox(
                    "Vẫn lưu dù còn vi phạm tiêu chí HĐSP bắt buộc ở trên (không khuyến khích)",
                    key="proceed_with_hard_violations",
                )

            # Đánh giá chất lượng lịch dạy của Giáo viên
            teacher_gaps = find_teacher_gaps(inp.slots, result.assignment, inp.assigned_teacher)
            if teacher_gaps and getattr(inp.config, "avoid_teacher_gaps", True):
                teacher_map = {t.teacher_id: t.name for t in inp.teachers}
                gap_summaries = []
                for tid, wd, sess, p_list in teacher_gaps:
                    tname = teacher_map.get(tid, f"GV #{tid}")
                    sess_name = "Sáng" if sess == "S" else "Chiều"
                    gap_summaries.append(f"{tname} (Thứ {wd} {sess_name}: tiết {', '.join(str(p) for p in p_list)})")
                with st.expander(f"⚠️ Cảnh báo chất lượng lịch: có {len(teacher_gaps)} buổi GV bị tiết trống / lủng", expanded=False):
                    for g_info in gap_summaries:
                        st.write(f"- {g_info}")

            st.subheader("Kiểm tra định mức (thực tế − định mức, kỳ vọng 0)")
            if scheduled_week is not None:
                expected_quota = repo.get_periods_for_week(conn, week_no=scheduled_week, parity=parity)
            else:
                expected_quota = repo.get_periods_per_week(conn)
            diff = compute_quota_diff(inp.slots, result.assignment, expected_quota, parity)
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

            col_acc1, col_acc2 = st.columns([1, 1])
            with col_acc1:
                if st.button(
                    "✅ Chấp nhận và lưu làm lịch chính thức", type="primary",
                    disabled=bool(hard_rule_violations) and not proceed_with_hard_violations,
                ):
                    cells = {
                        (s.class_id, s.ts.weekday, s.ts.session, s.ts.period): result.assignment.get(s.slot_id)
                        for s in inp.slots
                    }
                    repo.bulk_replace_tkb_nhap(conn, cells)
                    save_week_no = scheduled_week if scheduled_week is not None else 1
                    repo.add_seed_history(conn, save_week_no, seed, parity)
                    run_id = repo.save_run(conn, save_week_no, seed, parity, result.cells_changed, result.cells_total,
                                            True, "OK")
                    repo.save_tkb_result(conn, run_id, cells)
                    st.session_state["just_saved_week"] = save_week_no
                    st.success(f"Đã lưu làm thời khóa biểu chính thức cho Tuần {save_week_no}.")
                    st.session_state.pop("last_result", None)
                    st.session_state.pop("last_input", None)
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
                        "📤 Tải bản Excel kết quả này (.xlsx)",
                        data=excel_bytes,
                        file_name=file_label,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="btn_download_fresh_result",
                    )
                except Exception as ex_fresh:
                    st.caption(f"Xuất Excel: {ex_fresh}")

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
                format_func=lambda wn: f"Tuần {wn} ({'Chẵn' if wn % 2 == 0 else 'Lẻ'})",
                key="batch_week_select",
            )

            batch_extra_kep_names = st.multiselect(
                "Môn cần xếp 2 tiết liền kề (kép) CHỈ cho các tuần này",
                extra_kep_options,
                key="batch_extra_kep_select",
            )
            batch_extra_kep_ids = frozenset(s.subject_id for s in subjects if s.name in batch_extra_kep_names)
            batch_quota_warnings = []
            for wn in batch_week_nos:
                b_par = "C" if wn % 2 == 0 else "L"
                b_qv = repo.get_teacher_quota_view(conn, parity=b_par, week_no=wn)
                b_over = [q for q in b_qv if q["cap"] > 0 and q["load"] > q["cap"]]
                b_under = [q for q in b_qv if q["load"] < q["floor"]]
                if b_over or b_under:
                    parts = []
                    if b_over:
                        parts.append("Vượt: " + ", ".join(f"{q['name']} ({q['load']}/{q['cap']})" for q in b_over))
                    if b_under:
                        parts.append("Dưới sàn: " + ", ".join(f"{q['name']} ({q['load']}/{q['floor']})" for q in b_under))
                    batch_quota_warnings.append(
                        f"**Tuần {wn}** ({'Chẵn' if b_par == 'C' else 'Lẻ'}): " + " | ".join(parts)
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
                        week_no=wn,
                    )
                    with st.spinner(f"Đang xếp Tuần {wn} (áp dụng định lượng Tuần {wn})..."):
                        b_result = sched.run(b_inp)
                    batch_results[wn] = (b_seed, b_parity, b_inp, b_result)
                st.session_state["batch_results"] = batch_results

            def _batch_highlight_nonzero(row):
                return ["background-color: #ffc7ce" if col != "Môn" and row[col] != 0 else "" for col in row.index]

            batch_results = st.session_state.get("batch_results", {})
            for wn, (b_seed, b_parity, b_inp, b_result) in list(batch_results.items()):
                with st.expander(f"Kết quả Tuần {wn} ({'Chẵn' if b_parity == 'C' else 'Lẻ'})", expanded=True):
                    if not b_result.success:
                        st.error(b_result.failure_reason)
                        continue

                    b_teacher_map = {t.teacher_id: t.name for t in b_inp.teachers}

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

                    b_conflicts = find_teacher_conflicts(b_inp.slots, b_result.assignment, b_inp.assigned_teacher)
                    if b_conflicts:
                        st.error(f"Phát hiện {len(b_conflicts)} trường hợp GV trùng lịch (không nên xảy ra, báo lỗi này).")

                    # Kiểm tra tiêu chí HĐSP hard-gate (II.4 + II.8) cho Tuần {wn} -- mirrors the
                    # single-week flow's block above. II.3/II.14 là cảnh báo mềm, không chặn
                    # lưu (per quyết định 2026-09-03, bản sửa thứ 2 trong ngày).
                    b_hard_rule_violations = {}
                    b_soft_rule_warnings = {}

                    b_missing_morning = find_teacher_missing_mandatory_morning_violations(
                        b_inp.slots, b_result.assignment, b_inp.assigned_teacher,
                        getattr(b_inp.config, "mandatory_morning_weekdays", (2, 5, 6)),
                        getattr(b_inp.config, "min_weekly_periods_for_mandatory_morning", 10),
                        getattr(b_inp.config, "strict_morning_weekdays", ()) or (),
                        frozenset(t.teacher_id for t in b_inp.teachers if is_bgh(t)),
                        ban_busy=getattr(b_inp, "ban_busy", None),
                    )
                    if b_missing_morning:
                        b_hard_rule_violations["II.3"] = b_missing_morning

                    b_min_lone_load = getattr(b_inp.config, "min_weekly_periods_for_lone_penalty", 8)
                    b_lone_exempt_ids = getattr(b_inp.config, "lone_session_exempt_teacher_ids", frozenset()) or frozenset()
                    if getattr(b_inp.config, "avoid_teacher_lone_periods", True):
                        # Gated the same way engine.py:_check_hard_post_generation_rules gates II.4/II.8.
                        b_lone_sessions = find_teacher_lone_session_violations(b_inp.slots, b_result.assignment, b_inp.assigned_teacher, b_min_lone_load, b_lone_exempt_ids)
                        b_lone_days = find_teacher_lone_day_violations(b_inp.slots, b_result.assignment, b_inp.assigned_teacher, b_min_lone_load, b_lone_exempt_ids)
                        if b_lone_sessions or b_lone_days:
                            b_hard_rule_violations["II.4"] = b_lone_sessions + [(tid, wd, "cả ngày") for tid, wd in b_lone_days]

                        b_split_days = find_teacher_split_day_violations(b_inp.slots, b_result.assignment, b_inp.assigned_teacher, b_min_lone_load, b_lone_exempt_ids)
                        if b_split_days:
                            b_hard_rule_violations["II.8"] = b_split_days

                    if getattr(b_inp.config, "avoid_teacher_4_consecutive_morning", True):
                        b_consecutive_morning = find_teacher_4_consecutive_morning_violations(b_inp.slots, b_result.assignment, b_inp.assigned_teacher)
                        if b_consecutive_morning:
                            b_soft_rule_warnings["II.14"] = b_consecutive_morning

                    if b_hard_rule_violations:
                        st.error(f"❌ Còn {len(b_hard_rule_violations)} tiêu chí HĐSP bắt buộc chưa được thỏa mãn (chặn lưu) cho Tuần {wn}:")
                        for rule_id, items in b_hard_rule_violations.items():
                            with st.expander(f"{rule_id}: {RULES[rule_id].title_vi} ({len(items)} trường hợp)", expanded=False):
                                for item in items:
                                    tid = item[0]
                                    tname = b_teacher_map.get(tid, f"GV #{tid}")
                                    detail = _format_rule_item(rule_id, item)
                                    st.write(f"- **{tname}**: {detail}")

                    if b_soft_rule_warnings:
                        with st.expander(
                            f"⚠️ {sum(len(v) for v in b_soft_rule_warnings.values())} trường hợp thuộc "
                            f"{len(b_soft_rule_warnings)} tiêu chí HĐSP mềm (không chặn lưu) cho Tuần {wn}", expanded=False,
                        ):
                            for rule_id, items in b_soft_rule_warnings.items():
                                st.write(f"**{rule_id}: {RULES[rule_id].title_vi}** ({len(items)} trường hợp)")
                                for item in items:
                                    tid = item[0]
                                    tname = b_teacher_map.get(tid, f"GV #{tid}")
                                    detail = _format_rule_item(rule_id, item)
                                    st.write(f"- **{tname}**: {detail}")

                    b_proceed_with_hard_violations = True
                    if b_hard_rule_violations:
                        b_proceed_with_hard_violations = st.checkbox(
                            "Vẫn lưu dù còn vi phạm tiêu chí HĐSP bắt buộc ở trên (không khuyến khích)",
                            key=f"batch_proceed_with_hard_violations_{wn}",
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
                        disabled=bool(b_hard_rule_violations) and not b_proceed_with_hard_violations,
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
        format_func=lambda w: f"Tuần {w} ({'Chẵn' if w % 2 == 0 else 'Lẻ'}{' — ✅ Đã lưu' if w in saved_weeks else ''})",
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
        w_parity = run_for_week["parity"]
        w_parity_str = "Chẵn" if w_parity == "C" else "Lẻ"
        st.success(
            f"✅ **Thời khóa biểu Tuần {selected_view_week}** ({w_parity_str}) — "
            f"Đã lưu lúc: **{run_for_week['created_at']}** | "
            f"Seed: **{run_for_week['seed']}** | "
            f"Tổng số ô tiết đã xếp: **{run_for_week['cells_total']}**"
        )

        c_dl1, c_dl2, c_dl3 = st.columns([1, 1, 1])
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
            try:
                both_xlsx, both_warnings = export_xlsx_both_parities(conn)
                st.download_button(
                    "📥 Xuất cả 2 tuần (Chẵn + Lẻ) (.xlsx)",
                    data=both_xlsx,
                    file_name="TKB_ca_2_tuan.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"btn_dl_both_parities_{selected_view_week}",
                )
            except Exception as ex:
                st.caption(f"Xuất 2 tuần: {ex}")

        with c_dl3:
            if st.button(f"🔄 Nạp Tuần {selected_view_week} vào TKB Nháp", key=f"btn_load_to_nhap_{selected_view_week}"):
                saved_cells = repo.get_tkb_result(conn, run_for_week["run_id"])
                repo.bulk_replace_tkb_nhap(conn, saved_cells)
                st.success(f"Đã nạp thành công TKB Tuần {selected_view_week} vào bản nháp!")
                st.rerun()

        st.markdown("---")
        saved_cells = repo.get_tkb_result(conn, run_for_week["run_id"])
        _render_saved_tkb(conn, saved_cells, classes, subjects, repo.list_teachers(conn))


sidebar_backup_export(conn)
sidebar_school_switcher()
