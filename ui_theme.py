"""UI Theme & Design System module for tkb_app.
Follows UI/UX Pro Max standards for Modern Academic Dashboard:
- Primary Color: #2563EB (Trust Blue)
- Background: #F8FAFC (Slate-50)
- Surface/Card: #FFFFFF, Border: #E2E8F0
- Font: Plus Jakarta Sans
"""
from __future__ import annotations

import html
from typing import Any

import streamlit as st

THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap');

:root {
    --tkb-primary: #2563EB;
    --tkb-primary-hover: #1D4ED8;
    --tkb-primary-light: #EFF6FF;
    --tkb-primary-border: #BFDBFE;
    --tkb-secondary: #3B82F6;
    --tkb-accent: #EA580C;
    --tkb-bg: #F8FAFC;
    --tkb-surface: #FFFFFF;
    --tkb-text: #0F172A;
    --tkb-text-muted: #64748B;
    --tkb-border: #E2E8F0;
    --tkb-border-hover: #CBD5E1;
    --tkb-success: #10B981;
    --tkb-success-light: #ECFDF5;
    --tkb-success-text: #065F46;
    --tkb-warning: #F59E0B;
    --tkb-warning-light: #FFFBEB;
    --tkb-warning-text: #92400E;
    --tkb-danger: #EF4444;
    --tkb-danger-light: #FEF2F2;
    --tkb-danger-text: #991B1B;
    --tkb-info: #0284C7;
    --tkb-info-light: #F0F9FF;
    --tkb-info-text: #075985;
    --tkb-radius-card: 12px;
    --tkb-radius-btn: 8px;
    --tkb-radius-pill: 9999px;
    --tkb-shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
    --tkb-shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.07), 0 2px 4px -2px rgb(0 0 0 / 0.07);
    --tkb-shadow-hover: 0 10px 15px -3px rgb(0 0 0 / 0.08), 0 4px 6px -4px rgb(0 0 0 / 0.04);
}

/* Global Font Override */
html, body, [class*="css"], [class*="st-"] {
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
}

/* Page Background & Padding */
.stApp {
    background-color: var(--tkb-bg);
}

.block-container {
    padding-top: 1.75rem !important;
    padding-bottom: 3rem !important;
    max-width: 1440px !important;
}

/* Header Component */
.tkb-page-header {
    background: linear-gradient(135deg, #FFFFFF 0%, #F1F5F9 100%);
    border: 1px solid var(--tkb-border);
    border-radius: var(--tkb-radius-card);
    padding: 1.5rem 1.75rem;
    margin-bottom: 1.5rem;
    box-shadow: var(--tkb-shadow-sm);
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 1rem;
}

.tkb-page-header-title-group {
    display: flex;
    align-items: center;
    gap: 0.85rem;
}

.tkb-page-header-icon {
    font-size: 2rem;
    line-height: 1;
    background: var(--tkb-primary-light);
    border: 1px solid var(--tkb-primary-border);
    border-radius: 10px;
    padding: 0.5rem;
    display: inline-flex;
    align-items: center;
    justify-content: center;
}

.tkb-page-header-h1 {
    font-size: 1.6rem !important;
    font-weight: 800 !important;
    color: var(--tkb-text) !important;
    margin: 0 !important;
    letter-spacing: -0.02em;
}

.tkb-page-header-desc {
    color: var(--tkb-text-muted) !important;
    font-size: 0.95rem !important;
    margin-top: 0.25rem !important;
    margin-bottom: 0 !important;
}

.tkb-page-header-badge {
    background-color: var(--tkb-primary);
    color: #FFFFFF;
    font-size: 0.82rem;
    font-weight: 600;
    padding: 0.35rem 0.85rem;
    border-radius: var(--tkb-radius-pill);
    box-shadow: 0 2px 4px rgba(37, 99, 235, 0.25);
}

/* KPI Metric Cards */
.tkb-kpi-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 1rem;
    margin-bottom: 1.5rem;
}

.tkb-kpi-card {
    background: var(--tkb-surface);
    border: 1px solid var(--tkb-border);
    border-radius: var(--tkb-radius-card);
    padding: 1.25rem 1.25rem;
    box-shadow: var(--tkb-shadow-sm);
    transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
    display: flex;
    flex-direction: column;
    position: relative;
    overflow: hidden;
}

.tkb-kpi-card:hover {
    transform: translateY(-2px);
    box-shadow: var(--tkb-shadow-hover);
    border-color: var(--tkb-primary-border);
}

.tkb-kpi-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.5rem;
}

.tkb-kpi-title {
    font-size: 0.88rem;
    font-weight: 600;
    color: var(--tkb-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
}

.tkb-kpi-icon {
    font-size: 1.25rem;
    background: var(--tkb-bg);
    border: 1px solid var(--tkb-border);
    border-radius: 8px;
    padding: 0.35rem 0.45rem;
    line-height: 1;
}

.tkb-kpi-value {
    font-size: 2.1rem;
    font-weight: 800;
    color: var(--tkb-text);
    line-height: 1.2;
    margin-bottom: 0.25rem;
}

.tkb-kpi-subtitle {
    font-size: 0.82rem;
    color: var(--tkb-text-muted);
}

.tkb-kpi-card.variant-primary {
    border-left: 4px solid var(--tkb-primary);
}
.tkb-kpi-card.variant-success {
    border-left: 4px solid var(--tkb-success);
}
.tkb-kpi-card.variant-warning {
    border-left: 4px solid var(--tkb-warning);
}
.tkb-kpi-card.variant-danger {
    border-left: 4px solid var(--tkb-danger);
}

/* Status Badges */
.tkb-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    font-size: 0.8rem;
    font-weight: 600;
    padding: 0.25rem 0.65rem;
    border-radius: var(--tkb-radius-pill);
    line-height: 1.2;
}

.tkb-badge-success {
    background-color: var(--tkb-success-light);
    color: var(--tkb-success-text);
    border: 1px solid #A7F3D0;
}

.tkb-badge-warning {
    background-color: var(--tkb-warning-light);
    color: var(--tkb-warning-text);
    border: 1px solid #FDE68A;
}

.tkb-badge-danger {
    background-color: var(--tkb-danger-light);
    color: var(--tkb-danger-text);
    border: 1px solid #FECACA;
}

.tkb-badge-info {
    background-color: var(--tkb-info-light);
    color: var(--tkb-info-text);
    border: 1px solid #BAE6FD;
}

/* Custom Callout Box */
.tkb-callout {
    border-radius: var(--tkb-radius-card);
    padding: 1rem 1.25rem;
    margin: 1rem 0;
    border: 1px solid transparent;
    box-shadow: var(--tkb-shadow-sm);
}

.tkb-callout-info {
    background-color: var(--tkb-info-light);
    border-color: #BAE6FD;
    color: var(--tkb-info-text);
}

.tkb-callout-warning {
    background-color: var(--tkb-warning-light);
    border-color: #FDE68A;
    color: var(--tkb-warning-text);
}

.tkb-callout-danger {
    background-color: var(--tkb-danger-light);
    border-color: #FECACA;
    color: var(--tkb-danger-text);
}

.tkb-callout-success {
    background-color: var(--tkb-success-light);
    border-color: #A7F3D0;
    color: var(--tkb-success-text);
}

.tkb-callout-title {
    font-weight: 700;
    font-size: 0.95rem;
    margin-bottom: 0.35rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

/* Bento Card Container */
.tkb-card {
    background: var(--tkb-surface);
    border: 1px solid var(--tkb-border);
    border-radius: var(--tkb-radius-card);
    padding: 1.25rem 1.5rem;
    margin-bottom: 1.25rem;
    box-shadow: var(--tkb-shadow-sm);
}

.tkb-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid var(--tkb-border);
    padding-bottom: 0.75rem;
    margin-bottom: 1rem;
}

.tkb-card-title {
    font-size: 1.15rem;
    font-weight: 700;
    color: var(--tkb-text);
    margin: 0;
}

/* Streamlit Native Widget Enhancements */
.stButton > button {
    border-radius: var(--tkb-radius-btn) !important;
    font-weight: 600 !important;
    padding: 0.5rem 1.15rem !important;
    transition: all 0.15s ease-in-out !important;
}

.stButton > button[kind="primary"] {
    background: var(--tkb-primary) !important;
    color: #FFFFFF !important;
    border: none !important;
    box-shadow: 0 2px 4px rgba(37, 99, 235, 0.25) !important;
}

.stButton > button[kind="primary"]:hover {
    background: var(--tkb-primary-hover) !important;
    box-shadow: 0 4px 6px rgba(37, 99, 235, 0.35) !important;
    transform: translateY(-1px);
}

.stButton > button[kind="secondary"] {
    background: var(--tkb-surface) !important;
    border: 1px solid var(--tkb-border) !important;
    color: var(--tkb-text) !important;
}

.stButton > button[kind="secondary"]:hover {
    border-color: var(--tkb-border-hover) !important;
    background: var(--tkb-bg) !important;
}

/* Streamlit Tabs Customization */
.stTabs [data-baseweb="tab-list"] {
    gap: 8px !important;
    background-color: #F1F5F9 !important;
    padding: 6px !important;
    border-radius: var(--tkb-radius-card) !important;
    border: 1px solid var(--tkb-border) !important;
}

.stTabs [data-baseweb="tab"] {
    border-radius: var(--tkb-radius-btn) !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
    padding: 0.45rem 1rem !important;
    border: none !important;
    background-color: transparent !important;
    color: var(--tkb-text-muted) !important;
}

.stTabs [aria-selected="true"] {
    background-color: var(--tkb-surface) !important;
    color: var(--tkb-primary) !important;
    box-shadow: var(--tkb-shadow-sm) !important;
}

/* Dataframes & Tables */
.stDataFrame {
    border-radius: 10px !important;
    overflow: hidden !important;
    border: 1px solid var(--tkb-border) !important;
}

/* Sidebar Branding */
section[data-testid="stSidebar"] {
    background-color: #FFFFFF !important;
    border-right: 1px solid var(--tkb-border) !important;
}

.tkb-sidebar-header {
    padding: 1rem 0.75rem 1.25rem;
    border-bottom: 1px solid var(--tkb-border);
    margin-bottom: 1rem;
    display: flex;
    align-items: center;
    gap: 0.75rem;
}

.tkb-sidebar-logo {
    width: 36px;
    height: 36px;
    background: var(--tkb-primary-light);
    color: var(--tkb-primary);
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 800;
    font-size: 1.2rem;
    border: 1px solid var(--tkb-primary-border);
}

.tkb-sidebar-title {
    font-size: 1.05rem;
    font-weight: 800;
    color: var(--tkb-text);
    margin: 0;
    line-height: 1.2;
}

.tkb-sidebar-subtitle {
    font-size: 0.75rem;
    color: var(--tkb-text-muted);
    margin: 0;
}
</style>
"""


def inject_theme() -> None:
    """Injects Google Fonts, design tokens, and CSS overrides into the Streamlit app."""
    if not st.session_state.get("_tkb_theme_injected"):
        st.markdown(THEME_CSS, unsafe_allow_html=True)
        st.session_state["_tkb_theme_injected"] = True
    else:
        # Re-inject on rerun to ensure newly mounted containers apply styles
        st.markdown(THEME_CSS, unsafe_allow_html=True)


def render_page_header(
    title: str,
    subtitle: str | None = None,
    badge: str | None = None,
    icon: str | None = None,
) -> None:
    """Renders a modern, high-contrast SaaS page header."""
    badge_html = f'<div class="tkb-page-header-badge">{html.escape(badge)}</div>' if badge else ""
    icon_html = f'<div class="tkb-page-header-icon">{html.escape(icon)}</div>' if icon else ""
    desc_html = f'<p class="tkb-page-header-desc">{html.escape(subtitle)}</p>' if subtitle else ""

    header_html = f"""
    <div class="tkb-page-header">
        <div class="tkb-page-header-title-group">
            {icon_html}
            <div>
                <h1 class="tkb-page-header-h1">{html.escape(title)}</h1>
                {desc_html}
            </div>
        </div>
        {badge_html}
    </div>
    """
    st.markdown(header_html, unsafe_allow_html=True)


def render_kpi_card(
    title: str,
    value: Any,
    subtitle: str = "",
    icon: str = "",
    variant: str = "primary",
) -> str:
    """Returns HTML for a modern KPI card."""
    icon_html = f'<div class="tkb-kpi-icon">{html.escape(icon)}</div>' if icon else ""
    sub_html = f'<div class="tkb-kpi-subtitle">{html.escape(subtitle)}</div>' if subtitle else ""
    card_html = f"""
    <div class="tkb-kpi-card variant-{html.escape(variant)}">
        <div class="tkb-kpi-top">
            <span class="tkb-kpi-title">{html.escape(title)}</span>
            {icon_html}
        </div>
        <div class="tkb-kpi-value">{html.escape(str(value))}</div>
        {sub_html}
    </div>
    """
    return card_html


def render_kpi_row(cards_data: list[dict[str, Any]]) -> None:
    """Renders a responsive grid of KPI cards."""
    cards_html = "".join(
        render_kpi_card(
            title=c.get("title", ""),
            value=c.get("value", 0),
            subtitle=c.get("subtitle", ""),
            icon=c.get("icon", ""),
            variant=c.get("variant", "primary"),
        )
        for c in cards_data
    )
    grid_html = f'<div class="tkb-kpi-grid">{cards_html}</div>'
    st.markdown(grid_html, unsafe_allow_html=True)


def render_status_badge(label: str, status: str = "info") -> str:
    """Returns a styled HTML pill badge."""
    icon_map = {
        "success": "✓",
        "warning": "⚠",
        "danger": "✕",
        "info": "ℹ",
    }
    icon = icon_map.get(status, "•")
    return f'<span class="tkb-badge tkb-badge-{html.escape(status)}">{icon} {html.escape(label)}</span>'


def render_callout_html(message: str, level: str = "info", title: str | None = None) -> str:
    """Returns HTML for a custom callout box."""
    icons = {"info": "ℹ️", "warning": "⚠️", "danger": "🚨", "success": "✅"}
    icon = icons.get(level, "ℹ️")
    title_html = (
        f'<div class="tkb-callout-title">{icon} {html.escape(title)}</div>'
        if title
        else f'<div class="tkb-callout-title">{icon} Thông báo</div>'
    )
    return f"""
    <div class="tkb-callout tkb-callout-{html.escape(level)}">
        {title_html}
        <div>{html.escape(message)}</div>
    </div>
    """


def render_callout(message: str, level: str = "info", title: str | None = None) -> None:
    """Renders a custom callout box directly in Streamlit."""
    st.markdown(render_callout_html(message, level=level, title=title), unsafe_allow_html=True)


def render_card(title: str, content_html: str, badge: str | None = None) -> None:
    """Renders a bento card container."""
    badge_html = f'<span class="tkb-badge tkb-badge-info">{html.escape(badge)}</span>' if badge else ""
    card_html = f"""
    <div class="tkb-card">
        <div class="tkb-card-header">
            <h3 class="tkb-card-title">{html.escape(title)}</h3>
            {badge_html}
        </div>
        <div>
            {content_html}
        </div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)
