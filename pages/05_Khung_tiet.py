import pandas as pd
import streamlit as st

from core import frame as frame_mod
from data import repository as repo
from ui_common import get_conn, require_auth, require_school, sidebar_backup_export, sidebar_school_switcher

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
            repo.set_frame_template(conn, class_by_name[name], morning, afternoon, allow_saturday=allow_saturday)
    except ValueError as e:
        st.error(str(e))
    else:
        _, parity = repo.get_tuan_config(conn)
        ppw = repo.get_periods_per_week(conn)
        quota_totals = {}
        for name in selected:
            cid = class_by_name[name]
            quota_totals[cid] = sum(v for (_s, c, p), v in ppw.items() if c == cid and p == parity)
        msg = frame_mod.check_capacity(morning, afternoon, quota_totals, allow_saturday=allow_saturday)
        st.success(f"Đã áp dụng khung Sáng {morning} + Chiều {afternoon} cho {len(selected)} lớp.")
        st.info(msg)
        st.rerun()

st.subheader("Khung hiện tại theo lớp")
rows = []
for c in classes:
    m, a, ss, allow_sat = repo.get_frame_template(conn, c.class_id)
    total = frame_mod.total_cells_per_class(m, a, bool(ss), bool(allow_sat))
    rows.append({
        "Lớp": c.name, "Sáng": m, "Chiều": a,
        "Học bù Thứ 7": "Có" if allow_sat else "Không",
        "Tổng ô/tuần": total,
    })
st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

sidebar_backup_export(conn)
sidebar_school_switcher()
