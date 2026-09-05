import random

import pandas as pd
import streamlit as st

from core import seed_history as sh
from data import repository as repo
from ui_common import get_conn, require_auth, require_school, sidebar_backup_export, sidebar_school_switcher

require_auth()
school_slug = require_school()
conn = get_conn(school_slug)
st.title("Lịch sử tuần / Seed")

seed, parity = repo.get_tuan_config(conn)
history = repo.list_seed_history(conn)
current_week = history[-1]["week_no"] if history else 1
st.write(f"Tuần gần nhất: **Tuần {current_week}**, Seed hiện tại: **{seed}**")
st.caption(
    "Lưu ý: seed tái lập được TKB trong công cụ Python này (cùng seed + cùng dữ liệu → cùng kết quả), "
    "nhưng KHÔNG tái lập lại đúng TKB do bản VBA cũ tạo ra (khác bộ sinh số ngẫu nhiên)."
)

next_week = sh.next_week_no([h["week_no"] for h in history])
if st.button(f"🆕 Tạo Tuần {next_week} (seed ngẫu nhiên mới)", type="primary"):
    used_seeds = {h["seed"] for h in history}
    new_seed = sh.generate_unused_seed(used_seeds, random.Random())
    new_parity = "C" if next_week % 2 == 0 else "L"
    repo.set_tuan_config(conn, new_seed, new_parity)
    repo.add_seed_history(conn, next_week, new_seed, new_parity)
    st.success(f"Đã tạo Tuần {next_week} với seed {new_seed}.")
    st.rerun()

history = repo.list_seed_history(conn)
if history:
    st.subheader("Lịch sử các tuần")
    history_df = pd.DataFrame(history)
    if "parity" in history_df.columns:
        history_df = history_df.drop(columns=["parity"])
    history_df = history_df.rename(columns={"week_no": "Tuần", "seed": "Seed", "created_at": "Ngày tạo"})
    st.dataframe(history_df, hide_index=True, width="stretch")

    week_options = [h["week_no"] for h in history]
    pick = st.selectbox("Tái tạo lại tuần", week_options, format_func=lambda w: f"Tuần {w}")
    if st.button("Nạp seed của tuần đã chọn"):
        row = next(h for h in history if h["week_no"] == pick)
        repo.set_tuan_config(conn, row["seed"], row["parity"])
        st.success(f"Đã nạp seed {row['seed']} của Tuần {pick}. Sang trang Xếp TKB để chạy lại.")
        st.rerun()

    if st.button("🗑️ Xoá toàn bộ lịch sử"):
        repo.clear_seed_history(conn)
        st.success("Đã xoá lịch sử.")
        st.rerun()
else:
    st.info("Chưa có lịch sử tuần nào.")

sidebar_backup_export(conn)
sidebar_school_switcher()
