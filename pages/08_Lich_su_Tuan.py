import random

import pandas as pd
import streamlit as st

from core import seed_history as sh
from data import repository as repo
from ui_common import get_conn, require_auth, require_school, sidebar_backup_export, sidebar_school_switcher
from ui_theme import render_callout, render_page_header

require_auth()
school_slug = require_school()
conn = get_conn(school_slug)

render_page_header(
    title="Lịch Sử Xếp Lịch & Quản Lý Seed",
    subtitle="Theo dõi lịch sử các tuần đã lưu & tái lập phương án bằng giá trị Seed ngẫu nhiên",
    badge="35 tuần năm học",
    icon="🕘",
)

seed, parity = repo.get_tuan_config(conn)
history = repo.list_seed_history(conn)
current_week = history[-1]["week_no"] if history else 1

st.markdown(f"**Tuần gần nhất:** `Tuần {current_week}` &nbsp;|&nbsp; **Seed hiện tại:** `{seed}`")
render_callout(
    "Giá trị Seed cho phép tái lập chính xác 100% thời khóa biểu trên cùng dữ liệu đầu vào. "
    "Bạn có thể nạp lại seed của một tuần đã lưu để tái lập hoặc thử nghiệm cải tiến phương án.",
    level="info",
    title="Nguyên lý hoạt động của Seed",
)

next_week = sh.next_week_no([h["week_no"] for h in history])
if st.button(f"🆕 Tạo Tuần {next_week} (với seed ngẫu nhiên mới)", type="primary"):
    used_seeds = {h["seed"] for h in history}
    new_seed = sh.generate_unused_seed(used_seeds, random.Random())
    new_parity = "C" if next_week % 2 == 0 else "L"
    repo.set_tuan_config(conn, new_seed, new_parity)
    repo.add_seed_history(conn, next_week, new_seed, new_parity)
    st.success(f"✅ Đã tạo Tuần {next_week} với seed {new_seed}.")
    st.rerun()

history = repo.list_seed_history(conn)
if history:
    st.markdown("### 📋 Bảng danh mục các tuần đã khởi tạo")
    history_df = pd.DataFrame(history)
    if "parity" in history_df.columns:
        history_df = history_df.drop(columns=["parity"])
    history_df = history_df.rename(columns={"week_no": "Tuần", "seed": "Seed", "created_at": "Thời điểm tạo"})
    st.dataframe(history_df, hide_index=True, use_container_width=True)

    c_act1, c_act2 = st.columns(2)
    with c_act1:
        week_options = [h["week_no"] for h in history]
        pick = st.selectbox("Chọn tuần cần nạp lại:", week_options, format_func=lambda w: f"Tuần {w}")
        if st.button("🔄 Nạp seed của tuần đã chọn", type="secondary"):
            row = next(h for h in history if h["week_no"] == pick)
            repo.set_tuan_config(conn, row["seed"], row["parity"])
            st.success(f"✅ Đã nạp seed {row['seed']} của Tuần {pick}. Bạn có thể sang trang Xếp TKB để chạy lại.")
            st.rerun()

    with c_act2:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        if st.button("🗑️ Xoá toàn bộ lịch sử", type="secondary"):
            repo.clear_seed_history(conn)
            st.success("✅ Đã xoá toàn bộ lịch sử seed.")
            st.rerun()
else:
    render_callout("Chưa có lịch sử tuần nào được ghi nhận.", level="info", title="Thông tin")

sidebar_backup_export(conn)
sidebar_school_switcher()
