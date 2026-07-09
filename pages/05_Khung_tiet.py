import pandas as pd
import streamlit as st

from core import frame as frame_mod
from core.models import WEEKDAY_NAMES
from data import repository as repo
from ui_common import get_conn, require_auth, require_school, sidebar_backup_export, sidebar_school_switcher


def _class_quota_total(ppw: dict, class_id: int, parity: str) -> int:
    return sum(v for (_s, c, p), v in ppw.items() if c == class_id and p == parity)

require_auth()
school_slug = require_school()
conn = get_conn(school_slug)
st.title("Khung tiết (buổi sáng / chiều)")

classes = repo.list_classes(conn)
if not classes:
    st.info("Chưa có lớp. Vào trang Khai báo trước.")
    st.stop()

class_names = [c.name for c in classes]
class_by_name = {c.name: c.class_id for c in classes}
selected = st.multiselect("Áp dụng cho lớp", class_names, default=class_names)

st.subheader("Mẫu có sẵn")
preset_cols = st.columns(len(frame_mod.PRESETS))
chosen = None
preset_display = {"S4_C3": "Sáng 4 + Chiều 3", "S5": "Sáng 5", "S5_C2": "Sáng 5 + Chiều 2", "S4_C4": "Sáng 4 + Chiều 4"}
for col, (key, (m, a)) in zip(preset_cols, frame_mod.PRESETS.items()):
    total = frame_mod.total_cells_per_class(m, a)
    if col.button(f"{preset_display.get(key, key)}\n({total} ô/tuần/lớp)", key=f"preset_{key}"):
        chosen = (m, a)

st.subheader("Tùy chỉnh")
c1, c2, c3 = st.columns(3)
custom_m = c1.number_input("Số tiết buổi sáng", 0, 5, 5)
custom_a = c2.number_input("Số tiết buổi chiều", 0, 5, 0)
if c3.button("Áp dụng tùy chỉnh", key="apply_custom"):
    chosen = (custom_m, custom_a)

allow_saturday = st.checkbox(
    "Học bù Thứ 7",
    help="Học 2 buổi/ngày thì mặc định nghỉ Thứ 7 và Chủ nhật (chỉ học 1 buổi/ngày mới học Thứ 7). "
    "Tick ô này để tự bật ngoại lệ học bù Thứ 7 khi cần -- không tự động theo định mức.",
)

if chosen:
    morning, afternoon = chosen
    try:
        for name in selected:
            # Áp preset/tùy chỉnh mới luôn reset ngày lệch tiết cũ (nếu có) về đồng nhất --
            # đề xuất ngày lệch mới (nếu cần) sẽ hiện lại ở mục bên dưới sau khi rerun.
            repo.set_frame_template(conn, class_by_name[name], morning, afternoon, allow_saturday=allow_saturday)
    except ValueError as e:
        st.error(str(e))
    else:
        _, parity = repo.get_tuan_config(conn)
        ppw = repo.get_periods_per_week(conn)
        quota_totals = {class_by_name[name]: _class_quota_total(ppw, class_by_name[name], parity) for name in selected}
        msg = frame_mod.check_capacity(morning, afternoon, quota_totals, allow_saturday=allow_saturday)
        st.success(f"Đã áp dụng khung Sáng {morning} + Chiều {afternoon} cho {len(selected)} lớp.")
        st.info(msg)
        st.rerun()

st.subheader("Khung hiện tại theo lớp")
rows = []
for c in classes:
    m, a, ss, allow_sat, short_wd, short_m, short_a = repo.get_frame_template(conn, c.class_id)
    total = frame_mod.total_cells_per_class(m, a, bool(ss), bool(allow_sat), short_wd, short_m, short_a)
    short_desc = "-"
    if short_wd:
        parts = []
        if short_m is not None:
            parts.append(f"Sáng {short_m}")
        if short_a is not None:
            parts.append(f"Chiều {short_a}")
        short_desc = f"{WEEKDAY_NAMES.get(short_wd, short_wd)}: {', '.join(parts)}"
    rows.append({
        "Lớp": c.name, "Sáng": m, "Chiều": a,
        "Học bù Thứ 7": "Có" if allow_sat else "Không",
        "Ngày lệch tiết": short_desc,
        "Tổng ô/tuần": total,
    })
st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

st.subheader("Ngày lệch tiết")
st.caption(
    "Khi định mức tiết/tuần của lớp không chia hết cho khung đồng nhất, hệ thống đề xuất dồn "
    "toàn bộ phần chênh lệch vào 1 ngày duy nhất (ưu tiên Thứ 7) thay vì để thuật toán xếp lịch "
    "vô tình để trống rải rác."
)

_, parity = repo.get_tuan_config(conn)
ppw = repo.get_periods_per_week(conn)
suggestions = []
for c in classes:
    m, a, ss, allow_sat, short_wd, short_m, short_a = repo.get_frame_template(conn, c.class_id)
    if short_wd is not None:
        continue  # đã có ngày lệch (tự đề xuất hoặc tự cấu hình trước đó) -- không đề xuất chồng lên.
    quota = _class_quota_total(ppw, c.class_id, parity)
    suggestion = frame_mod.suggest_short_day(m, a, quota, allow_saturday=bool(allow_sat))
    if suggestion is not None:
        suggestions.append((c, suggestion))

if suggestions:
    for c, (short_wd, short_m, short_a) in suggestions:
        parts = []
        if short_m is not None:
            parts.append(f"{short_m} tiết sáng")
        if short_a is not None:
            parts.append(f"{short_a} tiết chiều")
        label = f"Lớp {c.name}: đề xuất {WEEKDAY_NAMES.get(short_wd, short_wd)} chỉ xếp {' + '.join(parts)}"
        col1, col2 = st.columns([4, 1])
        col1.write(label)
        if col2.button("Áp dụng", key=f"apply_short_{c.class_id}"):
            m, a, ss, allow_sat, _, _, _ = repo.get_frame_template(conn, c.class_id)
            repo.set_frame_template(
                conn, c.class_id, m, a, bool(ss), bool(allow_sat),
                short_weekday=short_wd, short_morning_periods=short_m, short_afternoon_periods=short_a,
            )
            st.rerun()
else:
    st.caption("Không có lớp nào cần đề xuất ngày lệch tiết (định mức đã khớp khung, hoặc đã cấu hình sẵn).")

with st.expander("Tuỳ chỉnh / bỏ ngày lệch tiết thủ công"):
    manual_class = st.selectbox("Lớp", class_names, key="manual_short_class")
    manual_cid = class_by_name[manual_class]
    cur_m, cur_a, cur_ss, cur_allow_sat, cur_short_wd, cur_short_m, cur_short_a = repo.get_frame_template(conn, manual_cid)
    weekday_options = [2, 3, 4, 5, 6, 7]
    default_idx = weekday_options.index(cur_short_wd) if cur_short_wd in weekday_options else weekday_options.index(7)
    mc1, mc2, mc3 = st.columns(3)
    manual_wd = mc1.selectbox("Ngày lệch", weekday_options, index=default_idx,
                               format_func=lambda w: WEEKDAY_NAMES.get(w, str(w)), key="manual_short_wd")
    manual_m = mc2.number_input("Tiết sáng ngày lệch", 0, 5, cur_short_m if cur_short_m is not None else cur_m,
                                 key="manual_short_m")
    manual_a = mc3.number_input("Tiết chiều ngày lệch", 0, 5, cur_short_a if cur_short_a is not None else cur_a,
                                 key="manual_short_a")
    bcol1, bcol2 = st.columns(2)
    if bcol1.button("Áp dụng ngày lệch tuỳ chỉnh", key="apply_manual_short"):
        try:
            repo.set_frame_template(
                conn, manual_cid, cur_m, cur_a, bool(cur_ss), bool(cur_allow_sat),
                short_weekday=manual_wd, short_morning_periods=manual_m, short_afternoon_periods=manual_a,
            )
        except ValueError as e:
            st.error(str(e))
        else:
            st.rerun()
    if bcol2.button("Bỏ ngày lệch (về đồng nhất)", key="clear_manual_short"):
        repo.set_frame_template(conn, manual_cid, cur_m, cur_a, bool(cur_ss), bool(cur_allow_sat))
        st.rerun()

sidebar_backup_export(conn)
sidebar_school_switcher()
