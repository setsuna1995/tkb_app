import pandas as pd
import streamlit as st

from core import scheduler as sched
from core.models import ROLE_GDTC, ROLE_HDTN, ROLE_KEP, ROLE_NANG_KEP, WEEKDAY_NAMES, WEEKDAYS
from core.validation import (
    compute_quota_diff, find_consecutive_subject_days, find_invalid_gdtc_periods,
    find_teacher_conflicts, find_teacher_unavailability_violations,
)
from data import repository as repo
from ui_common import get_conn, require_auth, require_school, sidebar_backup_export, sidebar_school_switcher

require_auth()
school_slug = require_school()
conn = get_conn(school_slug)
st.title("Xếp thời khóa biểu")

classes = repo.list_classes(conn)
subjects = repo.list_subjects(conn)
if not classes or not subjects:
    st.info("Chưa có lớp/môn. Vào trang Khai báo hoặc Nhập/Xuất Excel trước.")
    st.stop()

seed, parity = repo.get_tuan_config(conn)
chosen_label = st.radio("Tuần", ["Chẵn", "Lẻ"], index=0 if parity == "C" else 1, horizontal=True)
chosen_parity = "C" if chosen_label == "Chẵn" else "L"
if chosen_parity != parity:
    repo.set_tuan_config(conn, seed, chosen_parity)  # giữ nguyên seed, chỉ đổi tuần
    st.rerun()
seed, parity = repo.get_tuan_config(conn)
st.write(f"Tuần hiện tại: **{'Chẵn' if parity == 'C' else 'Lẻ'}**, seed = {seed or '(ngẫu nhiên mỗi lần chạy)'}")

quota_view = repo.get_teacher_quota_view(conn, parity)
over = [q for q in quota_view if q["cap"] > 0 and q["over"] > 0]
proceed_anyway = True
if over:
    st.warning(
        "Các GV vượt định mức trung bình 2 tuần (xếp TKB không tự giảm được tải, cần sửa "
        "Phân công trước nếu muốn):\n"
        + "\n".join(f"- {q['name']}: TB {q['load_avg']}/{q['cap']} (vượt {q['over']})" for q in over)
    )
    proceed_anyway = st.checkbox("Vẫn tiếp tục xếp dù vượt định mức")

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

if st.button("🚀 Chạy xếp TKB", disabled=bool(over) and not proceed_anyway):
    inp = repo.build_scheduling_input(conn, parity=parity, seed=seed, extra_kep_ids=extra_kep_ids,
                                       hdtn_thematic_week=hdtn_thematic_week)
    with st.spinner("Đang xếp thời khóa biểu..."):
        result = sched.run(inp)
    st.session_state["last_result"] = result
    st.session_state["last_input"] = inp

result = st.session_state.get("last_result")
inp = st.session_state.get("last_input")

if result is not None:
    if not result.success:
        st.error(result.failure_reason)
    else:
        st.success(
            f"Xếp thành công sau {result.attempts_tried} lần thử "
            f"({result.successes_found} phương án hợp lệ). "
            f"Giữ nguyên {result.cells_total - result.cells_changed}/{result.cells_total} ô, "
            f"thay đổi {result.cells_changed} ô."
        )

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
                st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

        conflicts = find_teacher_conflicts(inp.slots, result.assignment, inp.assigned_teacher)
        if conflicts:
            st.error(f"Phát hiện {len(conflicts)} trường hợp GV trùng lịch (không nên xảy ra, báo lỗi này).")

        busy_violations = find_teacher_unavailability_violations(
            inp.slots, result.assignment, inp.assigned_teacher, inp.ban_busy
        )
        if busy_violations:
            st.error(f"Phát hiện {len(busy_violations)} tiết xếp vào giờ GV đã khai báo bận (GV_Bận).")

        gdtc_id = next((s.subject_id for s in inp.subjects if s.role_code == ROLE_GDTC), None)
        if gdtc_id:
            gdtc_period_violations = find_invalid_gdtc_periods(
                inp.slots, result.assignment, gdtc_id,
                getattr(inp.config, "gdtc_morning_allowed_periods", (1, 2, 3, 4)),
                getattr(inp.config, "gdtc_afternoon_allowed_periods", (2, 3)),
            )
            if gdtc_period_violations:
                st.error(f"Phát hiện {len(gdtc_period_violations)} tiết GDTC xếp ngoài khung giờ cho phép (Sáng 1-4, Chiều 2-3).")

            consec_violations = find_consecutive_subject_days(inp.slots, result.assignment, {gdtc_id})
            if consec_violations:
                st.error(f"Phát hiện {len(consec_violations)} trường hợp GDTC xếp 2 ngày liền nhau.")

        st.subheader("Kiểm tra định mức (thực tế − định mức, kỳ vọng 0)")
        diff = compute_quota_diff(inp.slots, result.assignment, repo.get_periods_per_week(conn), parity)
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
            hide_index=True, use_container_width=True,
        )

        if st.button("✅ Chấp nhận và lưu làm lịch chính thức"):
            cells = {
                (s.class_id, s.ts.weekday, s.ts.session, s.ts.period): result.assignment.get(s.slot_id)
                for s in inp.slots
            }
            repo.bulk_replace_tkb_nhap(conn, cells)
            history = repo.list_seed_history(conn)
            week_no = history[-1]["week_no"] if history else 1
            run_id = repo.save_run(conn, week_no, seed, parity, result.cells_changed, result.cells_total,
                                    True, "OK")
            repo.save_tkb_result(conn, run_id, cells)
            st.success("Đã lưu làm thời khóa biểu chính thức.")
            st.session_state.pop("last_result", None)
            st.session_state.pop("last_input", None)
            st.rerun()

st.write("---")
with st.expander("📅 Xếp nhiều tuần cùng lúc", expanded=False):
    history = repo.list_seed_history(conn)
    week_lookup = {h["week_no"]: (h["seed"], h["parity"]) for h in history}
    if not week_lookup:
        cur_seed, cur_parity = repo.get_tuan_config(conn)
        week_lookup = {1: (cur_seed, cur_parity)}

    def _batch_week_label(wn):
        s, p = week_lookup[wn]
        return f"Tuần {wn} ({'Chẵn' if p == 'C' else 'Lẻ'}, seed {s})"

    batch_week_nos = st.multiselect(
        "Chọn các tuần cần xếp",
        options=sorted(week_lookup),
        default=sorted(week_lookup)[:1],
        format_func=_batch_week_label,
        key="batch_week_select",
    )

    batch_extra_kep_names = st.multiselect(
        "Môn cần xếp 2 tiết liền kề (kép) CHỈ cho các tuần này",
        extra_kep_options,
        key="batch_extra_kep_select",
    )
    batch_extra_kep_ids = frozenset(s.subject_id for s in subjects if s.name in batch_extra_kep_names)
    batch_hdtn_thematic_week = st.checkbox(
        "Các tuần này tổ chức chuyên đề (HDTN dồn 3 tiết liền kề toàn trường, bỏ ghim chào cờ + SHL)",
        key="batch_hdtn_thematic_week",
    )

    batch_parities = {week_lookup[wn][1] for wn in batch_week_nos}
    batch_proceed_anyway = True
    for par in sorted(batch_parities):
        par_quota = repo.get_teacher_quota_view(conn, par)
        par_over = [q for q in par_quota if q["cap"] > 0 and q["over"] > 0]
        if par_over:
            st.warning(
                f"Tuần {'Chẵn' if par == 'C' else 'Lẻ'} — Các GV vượt định mức trung bình 2 tuần:\n"
                + "\n".join(f"- {q['name']}: TB {q['load_avg']}/{q['cap']} (vượt {q['over']})" for q in par_over)
            )
            if not st.checkbox(
                f"Vẫn tiếp tục xếp tuần {'Chẵn' if par == 'C' else 'Lẻ'} dù vượt định mức",
                key=f"batch_proceed_{par}",
            ):
                batch_proceed_anyway = False

    if st.button("🚀 Xếp các tuần đã chọn", disabled=not batch_week_nos or not batch_proceed_anyway):
        batch_results = {}
        for wn in batch_week_nos:
            b_seed, b_parity = week_lookup[wn]
            b_inp = repo.build_scheduling_input(conn, parity=b_parity, seed=b_seed,
                                                 extra_kep_ids=batch_extra_kep_ids,
                                                 hdtn_thematic_week=batch_hdtn_thematic_week)
            with st.spinner(f"Đang xếp Tuần {wn}..."):
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
            st.success(
                f"Xếp thành công sau {b_result.attempts_tried} lần thử "
                f"({b_result.successes_found} phương án hợp lệ). "
                f"Giữ nguyên {b_result.cells_total - b_result.cells_changed}/{b_result.cells_total} ô, "
                f"thay đổi {b_result.cells_changed} ô."
            )

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
                    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

            b_conflicts = find_teacher_conflicts(b_inp.slots, b_result.assignment, b_inp.assigned_teacher)
            if b_conflicts:
                st.error(f"Phát hiện {len(b_conflicts)} trường hợp GV trùng lịch (không nên xảy ra, báo lỗi này).")

            st.caption("Kiểm tra định mức (thực tế − định mức, kỳ vọng 0)")
            b_diff = compute_quota_diff(b_inp.slots, b_result.assignment, repo.get_periods_per_week(conn), b_parity)
            b_check_rows = []
            for subj in sorted(b_inp.subjects, key=lambda s: s.sort_order):
                row = {"Môn": subj.name}
                for cls in b_classes_sorted:
                    row[cls.name] = b_diff.get((subj.subject_id, cls.class_id), 0)
                b_check_rows.append(row)
            st.dataframe(
                pd.DataFrame(b_check_rows).style.apply(_batch_highlight_nonzero, axis=1),
                hide_index=True, use_container_width=True,
            )

            if st.button(f"✅ Chấp nhận Tuần {wn}", key=f"batch_accept_{wn}"):
                b_cells = {
                    (s.class_id, s.ts.weekday, s.ts.session, s.ts.period): b_result.assignment.get(s.slot_id)
                    for s in b_inp.slots
                }
                repo.bulk_replace_tkb_nhap(conn, b_cells)
                b_run_id = repo.save_run(conn, wn, b_seed, b_parity, b_result.cells_changed, b_result.cells_total,
                                          True, "OK")
                repo.save_tkb_result(conn, b_run_id, b_cells)
                st.success(f"Đã lưu Tuần {wn} làm thời khóa biểu chính thức.")
                del st.session_state["batch_results"][wn]
                st.rerun()

sidebar_backup_export(conn)
sidebar_school_switcher()
