"""Shared bootstrapping for every Streamlit page: DB connection, auth gate,
school selector, and the persistent sidebar backup-export button."""
from __future__ import annotations

import re
import shutil
from pathlib import Path

import streamlit as st

from data import db
from ui_theme import inject_theme

LEGACY_DB_PATH = str(Path(__file__).parent / "tkb_app_data.db")
SCHOOLS_DIR = Path(__file__).parent / "schools"
SAMPLE_SCHOOL_XLSM_PATH = Path(__file__).parent / "io_excel" / "sample_school.xlsm"
TEMPLATE_DB_PATH = Path(__file__).parent / "data" / "sample_truong_thcs.db"
TEMPLATE_2_BUOI_DB_PATH = Path(__file__).parent / "data" / "sample_truong_thcs_2_buoi.db"

ROLE_CODE_LABELS = {0: "Thường", 1: "Nặng", 2: "Kép", 3: "Nặng+Kép", 4: "GDTC", 5: "HDTN"}
ROLE_LABEL_TO_CODE = {v: k for k, v in ROLE_CODE_LABELS.items()}

# Ràng buộc sư phạm CỐ ĐỊNH (bất biến thuật toán) -- không có trang cấu hình riêng.
CORE_INVARIANT_RULES = [
    "Không xếp trùng giáo viên trong cùng 1 tiết",
    "Tiết kép xếp liền nhau, cùng buổi",
    "Không buổi nào bị xếp đúng 1 tiết lẻ",
]


def sidebar_branding() -> None:
    """Renders modern sidebar header with school scheduler logo."""
    with st.sidebar:
        st.markdown(
            """
            <div class="tkb-sidebar-header">
                <div class="tkb-sidebar-logo">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                        <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1-2.5-2.5Z"/>
                        <path d="M6 6h10"/>
                        <path d="M6 10h10"/>
                    </svg>
                </div>
                <div>
                    <div class="tkb-sidebar-title">Xếp TKB Tự Động</div>
                    <div class="tkb-sidebar-subtitle">THCS & THPT Pro Max</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    sidebar_school_switcher()




def sidebar_fixed_rules(conn) -> None:
    from data import repository as repo

    config = repo.get_scheduling_config(conn)
    configurable_rules = [
        f"Môn nặng (Toán/Lý/Hoá) tối đa {config.max_heavy_consecutive} tiết liên tiếp trong 1 buổi",
        f"Thể dục chỉ xếp tiết {', '.join(str(p) for p in config.gdtc_morning_allowed_periods)} sáng và tiết {', '.join(str(p) for p in config.gdtc_afternoon_allowed_periods)} chiều",
        f"Chào cờ Thứ {config.chao_co_weekday} Tiết {config.chao_co_period}",
        f"Mỗi giáo viên được xếp {config.teacher_off_sessions_per_week} buổi nghỉ/tuần ({'bắt buộc tuyệt đối' if getattr(config, 'teacher_off_sessions_mode', 'soft') == 'hard' else 'ưu tiên cao'})",
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
    import unicodedata
    normalized = unicodedata.normalize("NFKD", name.strip().lower())
    ascii_str = "".join(c for c in normalized if not unicodedata.combining(c)).replace("đ", "d").replace("Đ", "d")
    s = re.sub(r"[^a-z0-9]+", "-", ascii_str).strip("-")
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
    """Ensure bundled sample schools exist so users have standard ready-to-use environments.
    Seeds both 1-shift (truong-thcs) and 2-shift (truong-thcs-2-buoi) default schools if missing."""
    SCHOOLS_DIR.mkdir(exist_ok=True)
    if any(SCHOOLS_DIR.glob("*.db")):
        return
    if TEMPLATE_DB_PATH.exists():
        dest = SCHOOLS_DIR / "truong-thcs.db"
        if not dest.exists():
            shutil.copy2(TEMPLATE_DB_PATH, dest)
    if TEMPLATE_2_BUOI_DB_PATH.exists():
        dest_2b = SCHOOLS_DIR / "truong-thcs-2-buoi.db"
        if not dest_2b.exists():
            shutil.copy2(TEMPLATE_2_BUOI_DB_PATH, dest_2b)
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
        conn = db.get_connection(str(p))
        try:
            name = repo.get_meta(conn, "school_name") or slug
        except Exception:
            name = slug
        finally:
            conn.close()
        schools.append({"slug": slug, "name": name})
    return schools


def create_school(name: str) -> str:
    slug = _slugify(name)
    path = SCHOOLS_DIR / f"{slug}.db"
    if path.exists():
        raise ValueError(f"Trường '{name}' đã tồn tại.")
    connection = db.get_connection(str(path))
    try:
        db.init_db(connection)
        from data import repository as repo
        repo.set_meta(connection, "school_name", name)
    finally:
        connection.close()
    return slug


def reset_school_session_state(new_slug: str | None = None) -> None:
    """Clear all school-dependent session state (form inputs, widget states, data editors)
    when switching schools to prevent cross-school contamination of rules and configs."""
    preserved = {
        "authenticated",
        "_theme_injected",
        "school_slug",
        "_active_school_slug",
        "sidebar_school_select_box",
        "explicit_school_switch",
    }
    for k in list(st.session_state.keys()):
        if k not in preserved and not k.startswith("db_conn_"):
            try:
                del st.session_state[k]
            except Exception:
                pass
    if new_slug:
        st.session_state["school_slug"] = new_slug
        st.session_state["_active_school_slug"] = new_slug


def get_conn(school_slug: str):
    SCHOOLS_DIR.mkdir(exist_ok=True)
    conn_key = f"db_conn_{school_slug}"
    if conn_key in st.session_state:
        conn = st.session_state[conn_key]
        try:
            conn.execute("SELECT 1")
            return conn
        except Exception:
            pass

    connection = db.get_connection(str(SCHOOLS_DIR / f"{school_slug}.db"))
    db.init_db(connection)
    st.session_state[conn_key] = connection
    return connection


def require_auth() -> None:
    """Pass-through authentication gate (password login removed)."""
    inject_theme()
    st.session_state["authenticated"] = True


def require_school() -> str:
    inject_theme()
    st.session_state["_sidebar_school_switcher_rendered"] = False
    sidebar_branding()
    slug = st.session_state.get("school_slug")
    if slug and (SCHOOLS_DIR / f"{slug}.db").exists():
        active = st.session_state.get("_active_school_slug")
        if active != slug:
            reset_school_session_state(slug)
        return slug
    st.session_state.pop("school_slug", None)
    st.session_state.pop("_active_school_slug", None)

    schools = list_schools()
    if schools and not st.session_state.get("explicit_school_switch"):
        # Tự động chọn trường THCS (2026-2027) làm trường mẫu mặc định
        default_school = next((s for s in schools if s["slug"] == "truong-thcs"), schools[0])
        reset_school_session_state(default_school["slug"])
        return default_school["slug"]

    st.title("🏫 Quản Lý & Chọn Trường Học")
    if schools:
        col_s1, col_s2 = st.columns([3, 1])
        with col_s1:
            pick = st.selectbox("Chọn trường đang có:", schools, format_func=lambda s: s["name"], key="school_pick")
        with col_s2:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            if st.button("Vào trường này", type="primary", width="stretch"):
                reset_school_session_state(pick["slug"])
                st.session_state.pop("explicit_school_switch", None)
                st.rerun()

    st.markdown("---")
    st.subheader("➕ Thêm trường mới")
    st.caption("Khởi tạo một trường học mới hoàn toàn để cấu hình và xếp thời khóa biểu riêng biệt.")
    col_c1, col_c2 = st.columns([3, 1])
    with col_c1:
        new_name = st.text_input("Tên trường mới", placeholder="Ví dụ: THCS Lê Quý Đôn", key="new_school_name")
    with col_c2:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        if st.button("➕ Tạo trường", type="primary", key="btn_create_school_direct", width="stretch"):
            if new_name.strip():
                try:
                    new_slug = create_school(new_name.strip())
                    reset_school_session_state(new_slug)
                    st.session_state.pop("explicit_school_switch", None)
                    st.rerun()
                except Exception as e:
                    st.error(f"Lỗi: {e}")
            else:
                st.warning("Vui lòng nhập tên trường.")
    st.stop()


def sidebar_school_switcher() -> None:
    if st.session_state.get("_sidebar_school_switcher_rendered"):
        return
    st.session_state["_sidebar_school_switcher_rendered"] = True

    schools = list_schools()
    if not schools:
        return
    current_slug = st.session_state.get("school_slug", schools[0]["slug"])
    slug_list = [s["slug"] for s in schools]
    names_map = {s["slug"]: s["name"] for s in schools}
    current_idx = slug_list.index(current_slug) if current_slug in slug_list else 0

    with st.sidebar:
        st.divider()
        selected_slug = st.selectbox(
            "🏫 Trường đang làm việc:",
            slug_list,
            index=current_idx,
            format_func=lambda s: names_map.get(s, s),
            key="sidebar_school_select_box",
        )
        if selected_slug != current_slug:
            reset_school_session_state(selected_slug)
            st.session_state.pop("explicit_school_switch", None)
            st.rerun()

        col_act1, col_act2 = st.columns([1, 1])
        with col_act1:
            if st.button("➕ Thêm trường", key="sidebar_btn_add_school_toggle", width="stretch"):
                st.session_state["sidebar_show_add_school"] = not st.session_state.get("sidebar_show_add_school", False)
        with col_act2:
            if st.button("🔄 Đổi trường", key="sidebar_btn_switch_school", width="stretch"):
                reset_school_session_state(None)
                st.session_state.pop("school_slug", None)
                st.session_state["explicit_school_switch"] = True
                st.rerun()

        if st.session_state.get("sidebar_show_add_school", False):
            with st.container():
                st.caption("Nhập tên trường học mới cần khởi tạo:")
                new_name = st.text_input("Tên trường mới", placeholder="Ví dụ: THCS Trần Phú", key="sidebar_new_school_name")
                if st.button("🚀 Tạo trường", type="primary", key="sidebar_btn_create_school", width="stretch"):
                    if new_name.strip():
                        try:
                            new_slug = create_school(new_name.strip())
                            reset_school_session_state(new_slug)
                            st.session_state.pop("explicit_school_switch", None)
                            st.session_state["sidebar_show_add_school"] = False
                            st.success(f"Đã tạo trường '{new_name.strip()}'!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Lỗi: {e}")
                    else:
                        st.warning("Vui lòng nhập tên trường.")
        st.divider()



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
                width="stretch",
            )
            if clicked:
                repo.set_meta(conn, "last_exported_at", datetime.now().strftime("%d/%m/%Y %H:%M"))
        st.caption(
            "⚠️ Dữ liệu có thể mất khi app khởi động lại (hosting free). "
            "Hãy xuất Excel thường xuyên để sao lưu."
        )
