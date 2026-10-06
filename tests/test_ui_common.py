import pytest
import sqlite3
import streamlit as st
from ui_common import require_auth, reset_school_session_state
from data import db, repository as repo
from core.models import SchedulingConfig


def test_require_auth_does_not_block():
    # require_auth should be a pass-through and not stop or raise
    require_auth()
    assert True


def test_reset_school_session_state_purges_widget_state_and_preserves_system():
    # Setup mock session state
    st.session_state.clear()
    st.session_state["authenticated"] = True
    st.session_state["_theme_injected"] = True
    st.session_state["school_slug"] = "truong-thcs"
    st.session_state["_active_school_slug"] = "truong-thcs"
    st.session_state["sidebar_school_select_box"] = "truong-thcs"
    st.session_state["db_conn_truong-thcs"] = "fake_conn"
    st.session_state["_sidebar_school_switcher_rendered"] = True
    # School-specific widget/editor states
    st.session_state["cfg_truong-thcs_hdtn_mode"] = "thematic"
    st.session_state["cfg_truong-thcs_off_sessions_per_week"] = 2
    st.session_state["editor_teachers"] = {"edited_rows": {0: {"name": "GV A"}}}
    st.session_state["gvban_selected_teacher"] = "Thầy Khu"
    st.session_state["khung_selected_classes"] = ["6A1", "6A2"]
    st.session_state["single_hdtn_plan_radio"] = "thematic"

    # Switch school to truong-thcs-2-buoi
    reset_school_session_state("truong-thcs-2-buoi")

    # Preserved keys
    assert st.session_state["authenticated"] is True
    assert st.session_state["_theme_injected"] is True
    assert st.session_state["sidebar_school_select_box"] == "truong-thcs"
    assert st.session_state["db_conn_truong-thcs"] == "fake_conn"
    assert st.session_state["_sidebar_school_switcher_rendered"] is True
    assert st.session_state["school_slug"] == "truong-thcs-2-buoi"
    assert st.session_state["_active_school_slug"] == "truong-thcs-2-buoi"

    # Purged keys (no leakage across schools)
    assert "cfg_truong-thcs_hdtn_mode" not in st.session_state
    assert "cfg_truong-thcs_off_sessions_per_week" not in st.session_state
    assert "editor_teachers" not in st.session_state
    assert "gvban_selected_teacher" not in st.session_state
    assert "khung_selected_classes" not in st.session_state
    assert "single_hdtn_plan_radio" not in st.session_state


def test_independent_school_scheduling_configs(tmp_path):
    # Two distinct school databases
    db_a = str(tmp_path / "school_a.db")
    db_b = str(tmp_path / "school_b.db")

    conn_a = db.get_connection(db_a)
    db.init_db(conn_a)

    conn_b = db.get_connection(db_b)
    db.init_db(conn_b)

    # Initial configs should both be default
    cfg_a = repo.get_scheduling_config(conn_a)
    cfg_b = repo.get_scheduling_config(conn_b)
    assert cfg_a.teacher_off_sessions_per_week == 0
    assert cfg_b.teacher_off_sessions_per_week == 0
    assert cfg_a.hdtn_mode == "separate"
    assert cfg_b.hdtn_mode == "separate"

    # Modify and save School A
    cfg_a.teacher_off_sessions_per_week = 3
    cfg_a.hdtn_mode = "thematic"
    cfg_a.heavy_subjects_morning_only = True
    repo.set_scheduling_config(conn_a, cfg_a)

    # Add slot rule to School A
    sid = repo.upsert_subject(conn_a, "Toán", role_code=1, sort_order=1)
    cid = repo.upsert_class(conn_a, "6A1", sort_order=1)
    repo.upsert_subject_class_rule(conn_a, sid, [cid], [(2, "S")])

    # Re-read both
    reloaded_a = repo.get_scheduling_config(conn_a)
    reloaded_b = repo.get_scheduling_config(conn_b)

    # School A has the new configuration
    assert reloaded_a.teacher_off_sessions_per_week == 3
    assert reloaded_a.hdtn_mode == "thematic"
    assert reloaded_a.heavy_subjects_morning_only is True
    rules_a = repo.list_subject_class_rules(conn_a)
    assert len(rules_a) == 1

    # School B remains completely unaffected
    assert reloaded_b.teacher_off_sessions_per_week == 0
    assert reloaded_b.hdtn_mode == "separate"
    assert reloaded_b.heavy_subjects_morning_only is False
    rules_b = repo.list_subject_class_rules(conn_b)
    assert len(rules_b) == 0

    conn_a.close()
    conn_b.close()

