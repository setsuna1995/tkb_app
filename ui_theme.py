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

/* Dark Mode Tokens (OS auto-detect & Streamlit dark theme parity) */
@media (prefers-color-scheme: dark) {
    :root {
        --tkb-primary: #3B82F6;
        --tkb-primary-hover: #60A5FA;
        --tkb-primary-light: rgba(59, 130, 246, 0.18);
        --tkb-primary-border: rgba(59, 130, 246, 0.35);
        --tkb-secondary: #60A5FA;
        --tkb-accent: #FB923C;
        --tkb-bg: #0B0F19;
        --tkb-surface: #131B2E;
        --tkb-text: #F8FAFC;
        --tkb-text-muted: #94A3B8;
        --tkb-border: #1E293B;
        --tkb-border-hover: #334155;
        --tkb-success: #34D399;
        --tkb-success-light: rgba(16, 185, 129, 0.18);
        --tkb-success-text: #6EE7B7;
        --tkb-warning: #FBBF24;
        --tkb-warning-light: rgba(245, 158, 11, 0.18);
        --tkb-warning-text: #FDE68A;
        --tkb-danger: #F87171;
        --tkb-danger-light: rgba(239, 68, 68, 0.18);
        --tkb-danger-text: #FCA5A5;
        --tkb-info: #38BDF8;
        --tkb-info-light: rgba(2, 132, 199, 0.18);
        --tkb-info-text: #7DD3FC;
        --tkb-shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.4);
        --tkb-shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.5), 0 2px 4px -2px rgb(0 0 0 / 0.4);
        --tkb-shadow-hover: 0 10px 15px -3px rgb(0 0 0 / 0.6), 0 4px 6px -4px rgb(0 0 0 / 0.5);
    }
}

[data-theme="dark"], .stDarkTheme {
    --tkb-primary: #3B82F6;
    --tkb-primary-hover: #60A5FA;
    --tkb-primary-light: rgba(59, 130, 246, 0.18);
    --tkb-primary-border: rgba(59, 130, 246, 0.35);
    --tkb-secondary: #60A5FA;
    --tkb-accent: #FB923C;
    --tkb-bg: #0B0F19;
    --tkb-surface: #131B2E;
    --tkb-text: #F8FAFC;
    --tkb-text-muted: #94A3B8;
    --tkb-border: #1E293B;
    --tkb-border-hover: #334155;
    --tkb-success: #34D399;
    --tkb-success-light: rgba(16, 185, 129, 0.18);
    --tkb-success-text: #6EE7B7;
    --tkb-warning: #FBBF24;
    --tkb-warning-light: rgba(245, 158, 11, 0.18);
    --tkb-warning-text: #FDE68A;
    --tkb-danger: #F87171;
    --tkb-danger-light: rgba(239, 68, 68, 0.18);
    --tkb-danger-text: #FCA5A5;
    --tkb-info: #38BDF8;
    --tkb-info-light: rgba(2, 132, 199, 0.18);
    --tkb-info-text: #7DD3FC;
    --tkb-shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.4);
    --tkb-shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.5), 0 2px 4px -2px rgb(0 0 0 / 0.4);
    --tkb-shadow-hover: 0 10px 15px -3px rgb(0 0 0 / 0.6), 0 4px 6px -4px rgb(0 0 0 / 0.5);
}

/* Global Typography */
html, body, .stApp {
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

h1, h2, h3, h4, h5, h6, p, label, button, input, select, textarea,
.stMarkdown, .stText, .stCaption, [data-testid="stMarkdownContainer"] {
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

/* Bảo toàn tuyệt đối font biểu tượng Material Symbols & Icons của Streamlit */
[data-testid="stIconMaterial"],
[data-testid="stExpanderToggleIcon"],
[data-testid*="Icon"],
[data-testid*="icon"],
.material-symbols-rounded,
.material-symbols-outlined,
.material-icons,
[class*="material-symbols"],
[class*="material-icons"] {
    font-family: 'Material Symbols Rounded', 'Material Icons' !important;
    font-weight: normal !important;
    font-style: normal !important;
    line-height: 1 !important;
    letter-spacing: normal !important;
    text-transform: none !important;
    display: inline-block !important;
    white-space: nowrap !important;
    word-wrap: normal !important;
    direction: ltr !important;
    -webkit-font-smoothing: antialiased !important;
}

/* Đảm bảo căn chỉnh và khoảng cách của expander không bị đè chữ */
[data-testid="stExpander"] details summary {
    display: flex !important;
    align-items: center !important;
    gap: 0.5rem !important;
}

[data-testid="stExpander"] details summary [data-testid="stExpanderToggleIcon"] {
    flex-shrink: 0 !important;
    margin-right: 0.25rem !important;
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
    background: linear-gradient(135deg, var(--tkb-surface) 0%, var(--tkb-bg) 100%);
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
    cursor: pointer !important;
    border-radius: var(--tkb-radius-btn) !important;
    font-weight: 600 !important;
    padding: 0.5rem 1.15rem !important;
    transition: all 0.18s cubic-bezier(0.4, 0, 0.2, 1) !important;
}

.stButton > button:focus-visible {
    outline: 2px solid var(--tkb-primary) !important;
    outline-offset: 2px !important;
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
    background-color: var(--tkb-bg) !important;
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
    cursor: pointer !important;
    transition: all 0.15s ease-in-out !important;
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
    background-color: var(--tkb-surface) !important;
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

/* Reduced Motion (WCAG 2.3.3) */
@media (prefers-reduced-motion: reduce) {
    *, ::before, ::after {
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
        scroll-behavior: auto !important;
    }
}

/* Responsive Breakpoints (Tablet & Mobile) */
@media (max-width: 768px) {
    .block-container {
        padding-top: 1rem !important;
        padding-left: 0.75rem !important;
        padding-right: 0.75rem !important;
    }
    .tkb-page-header {
        padding: 1.1rem 1.25rem;
        gap: 0.75rem;
    }
    .tkb-page-header-h1 {
        font-size: 1.35rem !important;
    }
    .tkb-kpi-grid {
        grid-template-columns: 1fr;
    }
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

    header_html = (
        f'<div class="tkb-page-header">'
        f'<div class="tkb-page-header-title-group">'
        f'{icon_html}'
        f'<div>'
        f'<h1 class="tkb-page-header-h1">{html.escape(title)}</h1>'
        f'{desc_html}'
        f'</div>'
        f'</div>'
        f'{badge_html}'
        f'</div>'
    )
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
    return (
        f'<div class="tkb-kpi-card variant-{html.escape(variant)}">'
        f'<div class="tkb-kpi-top">'
        f'<span class="tkb-kpi-title">{html.escape(title)}</span>'
        f'{icon_html}'
        f'</div>'
        f'<div class="tkb-kpi-value">{html.escape(str(value))}</div>'
        f'{sub_html}'
        f'</div>'
    )


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
    """Returns a styled HTML pill badge with vector SVG icon."""
    svg_badges = {
        "success": '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>',
        "warning": '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>',
        "danger": '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>',
        "info": '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>',
    }
    icon_svg = svg_badges.get(status, svg_badges["info"])
    return f'<span class="tkb-badge tkb-badge-{html.escape(status)}">{icon_svg} <span>{html.escape(label)}</span></span>'


def render_callout_html(message: str, level: str = "info", title: str | None = None) -> str:
    """Returns HTML for a custom callout box with vector SVG icons."""
    svg_icons = {
        "info": '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>',
        "warning": '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
        "danger": '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>',
        "success": '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>',
    }
    icon_svg = svg_icons.get(level, svg_icons["info"])
    title_text = title if title else "Thông báo"
    return (
        f'<div class="tkb-callout tkb-callout-{html.escape(level)}">'
        f'<div class="tkb-callout-title">{icon_svg} <span>{html.escape(title_text)}</span></div>'
        f'<div>{html.escape(message)}</div>'
        f'</div>'
    )


def render_callout(message: str, level: str = "info", title: str | None = None) -> None:
    """Renders a custom callout box directly in Streamlit."""
    st.markdown(render_callout_html(message, level=level, title=title), unsafe_allow_html=True)


def render_card(title: str, content_html: str, badge: str | None = None) -> None:
    """Renders a bento card container."""
    badge_html = f'<span class="tkb-badge tkb-badge-info">{html.escape(badge)}</span>' if badge else ""
    card_html = (
        f'<div class="tkb-card">'
        f'<div class="tkb-card-header">'
        f'<h3 class="tkb-card-title">{html.escape(title)}</h3>'
        f'{badge_html}'
        f'</div>'
        f'<div>{content_html}</div>'
        f'</div>'
    )
    st.markdown(card_html, unsafe_allow_html=True)
