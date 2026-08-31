import pandas as pd
import streamlit as st

from core import frame as frame_mod
from data import repository as repo
from ui_common import get_conn, require_auth, require_school, sidebar_backup_export, sidebar_fixed_rules, \
    sidebar_school_switcher

require_auth()
school_slug = require_school()
conn = get_conn(school_slug)
config = repo.get_scheduling_config(conn)

st.title("Khung tiết (Cho phép xếp tiết)")
st.caption(
    "Đánh dấu các tiết học ĐƯỢC PHÉP xếp thời khóa biểu cho lớp. "
    "Mặc định các tiết hợp lệ theo khung chuẩn đã được tích sẵn. "
    "Bạn có thể bỏ tích để cấm thuật toán xếp tiết vào vị trí đó (ví dụ: ngày nghỉ, tiết lệch)."
)

classes = repo.list_classes(conn)
if not classes:
    st.info("Chưa có lớp. Vào trang **Khai báo** trước.")
    st.stop()

class_names = [c.name for c in classes]
class_by_name = {c.name: c.class_id for c in classes}

col_sel, col_info = st.columns([2, 3])
with col_sel:
    selected_class_names = st.multiselect(
        "Chọn lớp cần thiết lập (có thể chọn nhiều lớp để áp dụng hàng loạt):",
        options=class_names,
        default=[class_names[0]],
        key="khung_selected_classes",
    )

if not selected_class_names:
    st.warning("Vui lòng chọn ít nhất một lớp.")
    st.stop()

# For the grid display, we load the setup of the *first* selected class.
# If multiple are selected, we warn that we are showing the first one.
primary_class_name = selected_class_names[0]
primary_cid = class_by_name[primary_class_name]

all_allowed = repo.get_all_class_allowed_cells(conn)
primary_allowed = all_allowed.get(primary_cid)

if primary_allowed is None:
    # Fallback to current frame_template
    m, a, ss, allow_sat, short_wd, short_m, short_a = repo.get_frame_template(conn, primary_cid)
    primary_allowed = set(frame_mod.active_cells(
        m, a, bool(ss), bool(allow_sat), short_wd, short_m, short_a,
        reserved_off_weekdays_chieu=config.reserved_off_weekdays_chieu
    ))
else:
    primary_allowed = set(primary_allowed)

with col_info:
    st.markdown(f"**Lớp hiển thị trên lưới:** `{primary_class_name}`")
    st.markdown(f"**Số ô cho phép xếp:** `{len(primary_allowed)}` tiết/tuần")
    if len(selected_class_names) > 1:
        st.info(f"Đang chọn {len(selected_class_names)} lớp. Khi nhấn Lưu, cấu hình trên lưới sẽ được áp dụng cho toàn bộ các lớp này.")

st.write("---")
st.subheader("Lưới khung tiết (Cho phép xếp lịch)")
st.caption("☑️ **Tích chọn ô** = Lớp có thể học. ☐ **Bỏ tích** = Khóa (không được xếp tiết).")

# Build DataFrame for grid
grid_rows = []
for sess, sess_label in [("S", "Sáng"), ("C", "Chiều")]:
    max_p = 5 if sess == "S" else 4
    for p in range(1, max_p + 1):
        row_data = {
            "Buổi": sess_label,
            "Tiết": f"Tiết {p}",
        }
        for wd in range(2, 8):
            col_name = f"Thứ {wd}"
            row_data[col_name] = (wd, sess, p) in primary_allowed
        grid_rows.append(row_data)

df_grid = pd.DataFrame(grid_rows)

column_config = {
    "Buổi": st.column_config.TextColumn("Buổi", disabled=True, width="small"),
    "Tiết": st.column_config.TextColumn("Tiết", disabled=True, width="small"),
}
for wd in range(2, 8):
    column_config[f"Thứ {wd}"] = st.column_config.CheckboxColumn(
        f"Thứ {wd}",
        help=f"Tích để cho phép xếp tiết vào Thứ {wd}",
        default=False,
    )

edited_grid = st.data_editor(
    df_grid,
    hide_index=True,
    use_container_width=True,
    key=f"editor_khung_grid",
    column_config=column_config,
)

btn_col1, btn_col2 = st.columns([2, 4])
with btn_col1:
    if st.button("💾 Lưu khung tiết", type="primary", use_container_width=True):
        new_allowed_cells = set()
        for _, r in edited_grid.iterrows():
            sess_code = "S" if r["Buổi"] == "Sáng" else "C"
            p_code = int(str(r["Tiết"]).replace("Tiết ", "").strip())
            for wd in range(2, 8):
                if bool(r.get(f"Thứ {wd}")):
                    new_allowed_cells.add((wd, sess_code, p_code))
        
        for name in selected_class_names:
            cid = class_by_name[name]
            repo.set_class_allowed_cells(conn, cid, list(new_allowed_cells))
        
        st.success(f"✅ Đã lưu khung tiết ({len(new_allowed_cells)} ô) cho {len(selected_class_names)} lớp!")
        st.rerun()

st.write("---")
st.subheader("Cấu hình hiện tại toàn trường")
overview_rows = []
for c in classes:
    allowed = all_allowed.get(c.class_id)
    if allowed is None:
        # Check fallback
        m, a, ss, allow_sat, short_wd, short_m, short_a = repo.get_frame_template(conn, c.class_id)
        cells = set(frame_mod.active_cells(
            m, a, bool(ss), bool(allow_sat), short_wd, short_m, short_a,
            reserved_off_weekdays_chieu=config.reserved_off_weekdays_chieu
        ))
        status = "Mặc định (Từ công thức cũ)"
    else:
        cells = set(allowed)
        status = "Tùy chỉnh (Từ lưới)"
    
    overview_rows.append({
        "Lớp": c.name,
        "Số ô cho phép": len(cells),
        "Trạng thái": status
    })

st.dataframe(pd.DataFrame(overview_rows), hide_index=True, use_container_width=True)

sidebar_backup_export(conn)
sidebar_fixed_rules(conn)
sidebar_school_switcher()
