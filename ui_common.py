"""Shared bootstrapping for every Streamlit page: DB connection, auth gate,
school selector, and the persistent sidebar backup-export button."""
from __future__ import annotations

import re
import shutil
from pathlib import Path

import streamlit as st

from data import db

LEGACY_DB_PATH = str(Path(__file__).parent / "tkb_app_data.db")
SCHOOLS_DIR = Path(__file__).parent / "schools"

ROLE_CODE_LABELS = {0: "Thường", 1: "Nặng", 2: "Kép", 3: "Nặng+Kép", 4: "GDTC", 5: "HDTN"}
ROLE_LABEL_TO_CODE = {v: k for k, v in ROLE_CODE_LABELS.items()}


def _slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return s or "truong"


def _migrate_legacy_single_db() -> None:
    """One-time: if no per-school DB exists yet but the old single-DB file does,
    copy (never move) it in as the first school so existing production data
    survives untouched on disk."""
    SCHOOLS_DIR.mkdir(exist_ok=True)
    if any(SCHOOLS_DIR.glob("*.db")):
        return
    if not Path(LEGACY_DB_PATH).exists():
        return
    dest = SCHOOLS_DIR / "truong-1.db"
    shutil.copy2(LEGACY_DB_PATH, dest)
    connection = db.get_connection(str(dest))
    db.init_db(connection)
    from data import repository as repo
    if not repo.get_meta(connection, "school_name"):
        repo.set_meta(connection, "school_name", "Trường 1 (dữ liệu cũ)")
    connection.close()


def list_schools() -> list:
    _migrate_legacy_single_db()
    from data import repository as repo
    schools = []
    for p in sorted(SCHOOLS_DIR.glob("*.db")):
        slug = p.stem
        connection = db.get_connection(str(p))
        db.init_db(connection)
        name = repo.get_meta(connection, "school_name") or slug
        schools.append({"slug": slug, "name": name})
    return schools


def create_school(name: str) -> str:
    slug = _slugify(name)
    path = SCHOOLS_DIR / f"{slug}.db"
    if path.exists():
        raise ValueError(f"Trường '{name}' đã tồn tại.")
    connection = db.get_connection(str(path))
    db.init_db(connection)
    from data import repository as repo
    repo.set_meta(connection, "school_name", name)
    return slug


@st.cache_resource
def get_conn(school_slug: str):
    SCHOOLS_DIR.mkdir(exist_ok=True)
    connection = db.get_connection(str(SCHOOLS_DIR / f"{school_slug}.db"))
    db.init_db(connection)
    return connection


def require_auth() -> None:
    if st.session_state.get("authenticated"):
        return
    st.title("Đăng nhập")
    pwd = st.text_input("Mật khẩu", type="password")
    if st.button("Đăng nhập"):
        if pwd == st.secrets.get("app_password"):
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Sai mật khẩu.")
    st.stop()


def require_school() -> str:
    slug = st.session_state.get("school_slug")
    if slug and (SCHOOLS_DIR / f"{slug}.db").exists():
        return slug
    st.session_state.pop("school_slug", None)

    st.title("Chọn trường")
    schools = list_schools()
    if schools:
        pick = st.selectbox("Trường", schools, format_func=lambda s: s["name"], key="school_pick")
        if st.button("Vào trường này"):
            st.session_state["school_slug"] = pick["slug"]
            st.rerun()
    with st.expander("➕ Tạo trường mới", expanded=not schools):
        new_name = st.text_input("Tên trường mới", key="new_school_name")
        if st.button("Tạo trường") and new_name.strip():
            new_slug = create_school(new_name.strip())
            st.session_state["school_slug"] = new_slug
            st.rerun()
    st.stop()


def sidebar_school_switcher() -> None:
    slug = st.session_state.get("school_slug")
    if not slug:
        return
    names = {s["slug"]: s["name"] for s in list_schools()}
    with st.sidebar:
        if st.button(f"🏫 Đổi trường ({names.get(slug, slug)})"):
            st.session_state.pop("school_slug", None)
            st.rerun()


def week_selector(conn, *, label: str = "Tuần làm việc", key: str = "week_selector") -> int:
    from data import repository as repo
    history = repo.list_seed_history(conn)
    current = repo.get_current_week_no(conn)
    options = sorted({h["week_no"] for h in history} | {current})
    idx = options.index(current) if current in options else len(options) - 1
    return st.selectbox(label, options, index=idx, key=key)


def format_substitution_line(sub: dict, name_by_id: dict, class_names: dict) -> str:
    from core.models import WEEKDAY_NAMES
    return (
        f"{class_names.get(sub['class_id'], '?')} — {WEEKDAY_NAMES[sub['weekday']]} "
        f"{'Sáng' if sub['session'] == 'S' else 'Chiều'} tiết {sub['period']}: "
        f"{name_by_id.get(sub['original_teacher_id'], '?')} → {name_by_id.get(sub['sub_teacher_id'], '?')}"
        + (f" ({sub['note']})" if sub.get("note") else "")
    )


def sidebar_backup_export(conn) -> None:
    from datetime import datetime

    from data import repository as repo
    from io_excel.exporter import export_xlsx

    with st.sidebar:
        st.divider()
        last = repo.get_meta(conn, "last_exported_at")
        st.caption(f"Lần xuất gần nhất: {last or 'chưa xuất lần nào'}")
        try:
            data = export_xlsx(conn)
        except Exception:
            data = None
        if data is not None:
            clicked = st.download_button(
                "📥 Xuất Excel (sao lưu)", data=data, file_name="TKB_sao_luu.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="sidebar_backup_export",
            )
            if clicked:
                repo.set_meta(conn, "last_exported_at", datetime.now().strftime("%d/%m/%Y %H:%M"))
        st.caption(
            "⚠️ Dữ liệu có thể mất khi app khởi động lại (hosting free). "
            "Hãy xuất Excel thường xuyên để sao lưu."
        )
