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
