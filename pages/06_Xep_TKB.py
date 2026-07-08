import pandas as pd
import streamlit as st

from core import scheduler as sched
from core.models import WEEKDAY_NAMES, WEEKDAYS
from core.validation import find_teacher_conflicts
from data import repository as repo
from ui_common import get_conn, require_auth, require_school, sidebar_backup_export, sidebar_school_switcher, \
    week_selector

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

if st.button("🚀 Chạy xếp TKB", disabled=bool(over) and not proceed_anyway):
    inp = repo.build_scheduling_input(conn, parity=parity, seed=seed)
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

sidebar_backup_export(conn)
sidebar_school_switcher()
