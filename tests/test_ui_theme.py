import pytest
from ui_theme import render_kpi_card, render_status_badge, render_callout_html

def test_render_kpi_card():
    html = render_kpi_card("Số lớp", 12, subtitle="Khối 6-9", icon="🏫", variant="primary")
    assert "Số lớp" in html
    assert "12" in html
    assert "tkb-kpi-card" in html

def test_render_status_badge():
    badge = render_status_badge("Đạt chuẩn", status="success")
    assert "Đạt chuẩn" in badge
    assert "tkb-badge-success" in badge

def test_render_callout_html():
    callout = render_callout_html("Cảnh báo định mức", level="warning", title="Chú ý")
    assert "Cảnh báo định mức" in callout
    assert "tkb-callout-warning" in callout


def test_render_kpi_card_no_markdown_code_block_indentation():
    card = render_kpi_card("Số môn", 16, subtitle="Phân loại", icon="📚", variant="info")
    for line in card.strip().splitlines():
        assert not line.startswith("    "), f"Line should not have 4-space indent (breaks st.markdown): {line}"


def test_role_cell_css_palette_and_fallback():
    from core.models import ROLE_GDTC, ROLE_HDTN, ROLE_NANG
    from ui_theme import role_cell_css

    assert "#EFF6FF" in role_cell_css(ROLE_NANG)
    assert "#FFF7ED" in role_cell_css(ROLE_GDTC)
    assert "#F0FDF4" in role_cell_css(ROLE_HDTN)
    assert role_cell_css(None) == role_cell_css(999)
    assert "#94A3B8" in role_cell_css(None)

