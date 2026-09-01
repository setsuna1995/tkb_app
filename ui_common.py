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
SAMPLE_SCHOOL_XLSM_PATH = Path(__file__).parent / "io_excel" / "sample_school.xlsm"

ROLE_CODE_LABELS = {0: "Thường", 1: "Nặng", 2: "Kép", 3: "Nặng+Kép", 4: "GDTC", 5: "HDTN"}
ROLE_LABEL_TO_CODE = {v: k for k, v in ROLE_CODE_LABELS.items()}

# Ràng buộc sư phạm CỐ ĐỊNH (bất biến thuật toán) -- không có trang cấu hình riêng.
CORE_INVARIANT_RULES = [
    "Không xếp trùng giáo viên trong cùng 1 tiết",
    "Tiết kép xếp liền nhau, cùng buổi",
    "Không buổi nào bị xếp đúng 1 tiết lẻ",
]


def sidebar_fixed_rules(conn) -> None:
    from data import repository as repo

    config = repo.get_scheduling_config(conn)
    configurable_rules = [
        f"Môn nặng (Toán/Lý/Hoá) tối đa {config.max_heavy_consecutive} tiết liên tiếp trong 1 buổi",
        f"Thể dục chỉ xếp tiết {', '.join(str(p) for p in config.gdtc_morning_allowed_periods)} sáng và tiết {', '.join(str(p) for p in config.gdtc_afternoon_allowed_periods)} chiều",
        f"Chào cờ Thứ {config.chao_co_weekday} Tiết {config.chao_co_period}",
        f"Mỗi giáo viên được xếp đúng {config.teacher_off_sessions_per_week} buổi nghỉ/tuần",
        f"Mỗi giáo viên tối đa {config.max_periods_per_session} tiết/buổi",
        "Buổi/ngày không được chọn làm buổi nghỉ GV: "
        + ", ".join(f"Thứ {wd} {'sáng' if s == 'S' else 'chiều'}"
                     for wd, s in sorted(config.forbidden_off_cells)),
        "Buổi chiều luôn để trống toàn trường (ôn bồi dưỡng/phụ đạo): "
        + ", ".join(f"Thứ {wd}" for wd in config.reserved_off_weekdays_chieu),
    ]
    if config.heavy_subject_priority_periods > 0:
        configurable_rules.append(
            f"Môn nặng được ưu tiên (không bắt buộc) vào {config.heavy_subject_priority_periods} tiết đầu buổi sáng"
        )
    if config.afternoon_preferred_subject_ids:
        configurable_rules.append(
            "Buổi chiều được ưu tiên (không bắt buộc) cho một số môn đã chọn ở trang Cấu hình xếp lịch"
        )
    if config.avoid_teacher_gaps:
        configurable_rules.append("Tránh tiết trống / lủng của giáo viên trong buổi")
    if config.avoid_teacher_lone_periods:
        configurable_rules.append("Tránh giáo viên đi dạy 1 tiết/ngày hoặc sáng 1 + chiều 1")
    if config.balance_afternoon_teachers:
        configurable_rules.append("Cân đối tiết buổi chiều cho GV (tránh nghỉ full chiều)")
    if getattr(config, "mandatory_morning_weekdays", None):
        configurable_rules.append(
            "Buổi sáng bắt buộc toàn thể GV đi làm: "
            + ", ".join(f"Thứ {wd}" for wd in config.mandatory_morning_weekdays)
        )
    subject_class_rules = repo.list_subject_class_rules(conn)
    if subject_class_rules:
        configurable_rules.append(
            f"{len(subject_class_rules)} luật gán môn/lớp theo buổi cụ thể đang áp dụng "
            "(xem chi tiết ở trang Cấu hình xếp lịch)"
        )
    teachers = repo.list_teachers(conn)
    has_teacher_overrides = any(
        t.off_sessions_override is not None or t.pinned_full_day_off is not None
        or t.pinned_afternoon_off is not None
        for t in teachers
    )
    if has_teacher_overrides:
        configurable_rules.append(
            "Một số giáo viên có số buổi nghỉ/tuần hoặc buổi/ngày nghỉ cố định riêng "
            "(khác quy tắc chung ở trên) - xem chi tiết ở trang Khai báo"
        )
    with st.sidebar:
        with st.expander("📐 Quy tắc xếp lịch"):
            edit_pages = "trang **Cấu hình xếp lịch**"
            if has_teacher_overrides:
                edit_pages += " hoặc **Khai báo** (riêng từng GV)"
            st.caption(
                f"{len(configurable_rules)} dòng đầu chỉnh được ở {edit_pages}. "
                "3 dòng cuối là ràng buộc cố định của thuật toán."
            )
            for rule in configurable_rules:
                st.markdown(f"- {rule}")
            st.divider()
            for rule in CORE_INVARIANT_RULES:
                st.markdown(f"- {rule}")


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


def _seed_sample_school_if_empty() -> None:
    """First-run only: if truly no school exists yet (fresh install, or all data
    lost on an ephemeral-filesystem host restart), create one default school
    pre-populated from the bundled sample dataset so the app is never empty."""
    if any(SCHOOLS_DIR.glob("*.db")):
        return
    slug = create_school("Trường mẫu (dữ liệu mẫu)")
    connection = get_conn(slug)
    try:
        from io_excel.importer import import_xlsm
        import_xlsm(connection, str(SAMPLE_SCHOOL_XLSM_PATH))
    except Exception:
        connection.close()
        get_conn.clear()
        (SCHOOLS_DIR / f"{slug}.db").unlink(missing_ok=True)
        st.warning("Không thể nạp dữ liệu mẫu cho trường mặc định. Hãy thử lại hoặc tạo trường mới thủ công.")


def list_schools() -> list:
    _migrate_legacy_single_db()
    _seed_sample_school_if_empty()
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
    from io_excel.exporter import export_full_backup_xlsx

    with st.sidebar:
        st.divider()
        last = repo.get_meta(conn, "last_exported_at")
        st.caption(f"Lần xuất gần nhất: {last or 'chưa xuất lần nào'}")
        try:
            data = export_full_backup_xlsx(conn)
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
