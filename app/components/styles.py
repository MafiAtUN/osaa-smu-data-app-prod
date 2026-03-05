"""Centralized CSS design system and reusable UI header components.

Call inject_global_css() once in main.py (after st.set_page_config).
Use page_header() and section_divider() on individual pages.
"""

from __future__ import annotations

import streamlit as st

# ---------------------------------------------------------------------------
# Design tokens
# ---------------------------------------------------------------------------
# Sidebar:    #1E293B  •  Primary: #2563EB  •  AI accent: #7C3AED
# BG:         #F8FAFC  •  Card:    #FFFFFF  •  Border: #E2E8F0
# Text:       #0F172A  •  Muted:   #64748B

_GLOBAL_CSS = """
/* ═══════════════════════════════════════════════════════════
   SMU DATA APP — UN Professional Blue Design System
   ═══════════════════════════════════════════════════════════ */

/* ── HIDE DEFAULT STREAMLIT CHROME ────────────────────────── */
#MainMenu { visibility: hidden !important; }
footer { visibility: hidden !important; }
[data-testid="stToolbar"] { display: none !important; }
[data-testid="stDecoration"] { display: none !important; }
[data-testid="stHeader"] { display: none !important; }

/* ── PAGE BACKGROUND ──────────────────────────────────────── */
.stApp { background: #F8FAFC !important; }

/* ── MAIN CONTENT CONTAINER ───────────────────────────────── */
.main .block-container {
    padding: 2rem 3rem 3rem !important;
    max-width: 1400px !important;
}

/* ── COLUMNS — clip overflow so cards can't bleed out ─────── */
[data-testid="column"] {
    min-width: 0 !important;
    overflow: hidden !important;
    box-sizing: border-box !important;
}

/* ── SIDEBAR ──────────────────────────────────────────────── */
section[data-testid="stSidebar"],
section[data-testid="stSidebar"] > div,
section[data-testid="stSidebar"] > div > div {
    background: #1E293B !important;
}
section[data-testid="stSidebar"] {
    border-right: 1px solid #334155 !important;
}

/* Sidebar text defaults */
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] small,
section[data-testid="stSidebar"] .stCaption,
section[data-testid="stSidebar"] .stMarkdown p {
    color: #94A3B8 !important;
}
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {
    color: #F1F5F9 !important;
}

/* Sidebar nav links */
[data-testid="stSidebarNavLink"] {
    border-radius: 8px !important;
    padding: 0.45rem 0.75rem !important;
    margin: 1px 0 !important;
    color: #CBD5E1 !important;
    text-decoration: none !important;
    transition: all 0.15s ease !important;
    display: flex !important;
    align-items: center !important;
    gap: 0.5rem !important;
    overflow: hidden !important;
    min-width: 0 !important;
    width: 100% !important;
    box-sizing: border-box !important;
}
[data-testid="stSidebarNavLink"] > * {
    min-width: 0 !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    white-space: nowrap !important;
    flex-shrink: 1 !important;
}
[data-testid="stSidebarNavLink"]:hover {
    background: rgba(255,255,255,0.08) !important;
    color: #F1F5F9 !important;
}
[data-testid="stSidebarNavLink"][aria-current="page"],
[data-testid="stSidebarNavLink"][aria-selected="true"] {
    background: #2563EB !important;
    color: #FFFFFF !important;
    font-weight: 600 !important;
}

/* Sidebar nav section separators / group headers */
[data-testid="stSidebarNavSeparator"],
[data-testid="stSidebarNavItems"] > div > hr + div,
section[data-testid="stSidebar"] .stSidebarNavSeparator {
    color: #64748B !important;
    font-size: 0.65rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
    padding-top: 0.65rem !important;
    margin-top: 0.35rem !important;
    border-top: 1px solid #334155 !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    white-space: nowrap !important;
}

/* Sidebar selectbox & widgets */
section[data-testid="stSidebar"] [data-baseweb="select"] > div {
    background: #334155 !important;
    border-color: #475569 !important;
    border-radius: 8px !important;
}
section[data-testid="stSidebar"] [data-baseweb="select"] span,
section[data-testid="stSidebar"] [data-baseweb="select"] div {
    color: #F1F5F9 !important;
}
section[data-testid="stSidebar"] [data-baseweb="popover"] {
    background: #1E293B !important;
}
section[data-testid="stSidebar"] [role="option"] {
    background: #1E293B !important;
    color: #CBD5E1 !important;
}
section[data-testid="stSidebar"] [role="option"]:hover {
    background: #334155 !important;
}

/* Sidebar divider */
section[data-testid="stSidebar"] hr {
    border-color: #334155 !important;
}

/* Sidebar warning/info boxes */
section[data-testid="stSidebar"] [data-testid="stAlert"] {
    background: rgba(239,68,68,0.1) !important;
    border: 1px solid rgba(239,68,68,0.3) !important;
    border-radius: 8px !important;
}

/* ── BUTTONS ──────────────────────────────────────────────── */
.stButton > button {
    border-radius: 8px !important;
    font-weight: 600 !important;
    transition: all 0.15s ease !important;
    font-size: 0.875rem !important;
    letter-spacing: 0.01em !important;
}
/* Primary */
.stButton > button[kind="primary"] {
    background: #2563EB !important;
    border: none !important;
    color: #FFFFFF !important;
    box-shadow: 0 1px 3px rgba(37,99,235,0.25) !important;
}
.stButton > button[kind="primary"]:hover {
    background: #1D4ED8 !important;
    box-shadow: 0 4px 12px rgba(37,99,235,0.4) !important;
    transform: translateY(-1px) !important;
}
/* Secondary */
.stButton > button[kind="secondary"] {
    background: transparent !important;
    border: 1.5px solid #CBD5E1 !important;
    color: #475569 !important;
}
.stButton > button[kind="secondary"]:hover {
    border-color: #2563EB !important;
    color: #2563EB !important;
    background: #EFF6FF !important;
}

/* ── PAGE LINKS (styled as interactive cards in main content) ─ */
/* Outer wrapper: contain overflow so nothing bleeds outside the card */
.main [data-testid="stPageLink"],
[data-testid="stAppViewContainer"] [data-testid="stPageLink"] {
    overflow: hidden !important;
    min-width: 0 !important;
    width: 100% !important;
    box-sizing: border-box !important;
}
.main [data-testid="stPageLink"] a,
[data-testid="stAppViewContainer"] [data-testid="stPageLink"] a {
    border-radius: 10px !important;
    padding: 1rem 1.1rem !important;
    text-decoration: none !important;
    display: block !important;
    background: #FFFFFF !important;
    border: 1.5px solid #E2E8F0 !important;
    color: #1E293B !important;
    transition: all 0.2s ease !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06) !important;
    /* Contain text inside the card */
    overflow: hidden !important;
    min-width: 0 !important;
    width: 100% !important;
    box-sizing: border-box !important;
    overflow-wrap: break-word !important;
    word-wrap: break-word !important;
    word-break: break-word !important;
}
.main [data-testid="stPageLink"] a:hover,
[data-testid="stAppViewContainer"] [data-testid="stPageLink"] a:hover {
    border-color: #93C5FD !important;
    box-shadow: 0 6px 20px rgba(37,99,235,0.12) !important;
    transform: translateY(-2px) !important;
    color: #1D4ED8 !important;
}
/* All elements inside the page link must wrap and not overflow */
.main [data-testid="stPageLink"] a *,
[data-testid="stAppViewContainer"] [data-testid="stPageLink"] a * {
    white-space: normal !important;
    overflow-wrap: break-word !important;
    word-break: break-word !important;
    min-width: 0 !important;
    max-width: 100% !important;
}
/* Hide the external-link icon streamlit adds */
.main [data-testid="stPageLink"] a svg,
[data-testid="stAppViewContainer"] [data-testid="stPageLink"] a svg {
    display: none !important;
}
/* Bold (card title) inside page link */
.main [data-testid="stPageLink"] a strong {
    font-size: 0.9rem !important;
    color: #0F172A !important;
    display: block !important;
    margin-bottom: 0.2rem !important;
}

/* ── DATA SOURCE GROUP HEADER (home page) ─────────────────── */
.smu-ds-group {
    background: linear-gradient(135deg, #1E3A8A 0%, #2563EB 100%);
    border-radius: 12px 12px 0 0;
    padding: 0.875rem 1.1rem 0.75rem;
    margin-bottom: 0;
    display: flex;
    align-items: center;
    gap: 0.75rem;
}
.smu-ds-group-icon { font-size: 1.4rem; line-height: 1; flex-shrink: 0; }
.smu-ds-group-name {
    color: #FFFFFF;
    font-size: 0.95rem;
    font-weight: 700;
    display: block;
    line-height: 1.2;
}
.smu-ds-group-tag {
    color: #93C5FD;
    font-size: 0.68rem;
    font-weight: 500;
    display: block;
    margin-top: 0.1rem;
    letter-spacing: 0.03em;
}
/* Page links that directly follow a .smu-ds-group header */
/* Streamlit renders the page_link divs right after the markdown div */
.smu-ds-group ~ div [data-testid="stPageLink"]:first-child a,
.smu-ds-group + div [data-testid="stPageLink"] a {
    border-radius: 0 !important;
    border-top: none !important;
}
/* Last page link in each group gets bottom rounded corners */
.smu-ds-group ~ div + div [data-testid="stPageLink"] a {
    border-radius: 0 0 12px 12px !important;
    border-top: none !important;
}

/* ── FORM INPUTS ──────────────────────────────────────────── */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea {
    border-radius: 8px !important;
    border: 1.5px solid #E2E8F0 !important;
    background: #FFFFFF !important;
    padding: 0.5rem 0.75rem !important;
    transition: border-color 0.15s ease, box-shadow 0.15s ease !important;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: #2563EB !important;
    box-shadow: 0 0 0 3px rgba(37,99,235,0.1) !important;
    outline: none !important;
}
/* Selectbox / multiselect */
[data-baseweb="select"] > div:first-child {
    border-radius: 8px !important;
    border: 1.5px solid #E2E8F0 !important;
    transition: border-color 0.15s ease !important;
}
[data-baseweb="select"] > div:first-child:focus-within {
    border-color: #2563EB !important;
    box-shadow: 0 0 0 3px rgba(37,99,235,0.1) !important;
}
/* Slider */
[data-testid="stSlider"] [role="slider"] {
    background: #2563EB !important;
}
[data-testid="stSlider"] [data-testid="stSliderTrack"] {
    background: #DBEAFE !important;
}

/* ── TABS ─────────────────────────────────────────────────── */
[data-baseweb="tab-list"] {
    background: transparent !important;
    border-bottom: 2px solid #E2E8F0 !important;
    gap: 0 !important;
    padding: 0 !important;
}
[data-baseweb="tab"] {
    font-weight: 600 !important;
    color: #64748B !important;
    background: transparent !important;
    border-radius: 0 !important;
    padding: 0.65rem 1.25rem !important;
    border-bottom: 3px solid transparent !important;
    margin-bottom: -2px !important;
    transition: color 0.15s ease !important;
    font-size: 0.875rem !important;
}
[data-baseweb="tab"]:hover {
    color: #2563EB !important;
    background: transparent !important;
}
[data-baseweb="tab"][aria-selected="true"] {
    color: #2563EB !important;
    border-bottom-color: #2563EB !important;
    background: transparent !important;
}
[data-baseweb="tab-highlight"] { display: none !important; }
[data-testid="stTabPanel"] { padding-top: 1.25rem !important; }

/* ── METRICS ──────────────────────────────────────────────── */
[data-testid="stMetric"] {
    background: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 12px !important;
    padding: 1rem 1.25rem !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
}
[data-testid="stMetricValue"] {
    color: #0F172A !important;
    font-weight: 700 !important;
}
[data-testid="stMetricLabel"] {
    color: #64748B !important;
    font-size: 0.8rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
}

/* ── DATAFRAME ────────────────────────────────────────────── */
[data-testid="stDataFrame"] {
    border-radius: 10px !important;
    overflow: hidden !important;
    border: 1px solid #E2E8F0 !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
}

/* ── EXPANDER ─────────────────────────────────────────────── */
[data-testid="stExpander"] {
    border: 1px solid #E2E8F0 !important;
    border-radius: 10px !important;
    overflow: hidden !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.04) !important;
}
[data-testid="stExpander"] summary {
    background: #F8FAFC !important;
    font-weight: 600 !important;
    color: #0F172A !important;
    padding: 0.75rem 1rem !important;
    border-radius: 10px !important;
}
[data-testid="stExpander"][open] summary {
    border-radius: 10px 10px 0 0 !important;
}

/* ── CHAT MESSAGES ────────────────────────────────────────── */
[data-testid="stChatMessage"] {
    background: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 12px !important;
    margin-bottom: 0.75rem !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.04) !important;
    padding: 0.75rem 1rem !important;
}
[data-testid="stChatInput"] {
    border-radius: 10px !important;
    border: 1.5px solid #E2E8F0 !important;
    background: #FFFFFF !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06) !important;
}
[data-testid="stChatInput"] textarea {
    border: none !important;
    outline: none !important;
}

/* ── ALERTS ───────────────────────────────────────────────── */
[data-testid="stAlert"] {
    border-radius: 10px !important;
    border: none !important;
    font-size: 0.875rem !important;
}

/* ── CODE BLOCKS ──────────────────────────────────────────── */
[data-testid="stCode"],
.stCode,
pre {
    border-radius: 8px !important;
    overflow: hidden !important;
}

/* ── SPINNER ──────────────────────────────────────────────── */
[data-testid="stSpinner"] {
    color: #2563EB !important;
}

/* ══════════════════════════════════════════════════════
   CUSTOM SMU COMPONENT CLASSES
   ══════════════════════════════════════════════════════ */

/* ── HERO SECTION ─────────────────────────────────────────── */
.smu-hero {
    background: linear-gradient(135deg, #0F172A 0%, #1E3A8A 55%, #2563EB 100%);
    padding: 2.5rem 2.5rem 2rem;
    border-radius: 16px;
    margin-bottom: 2rem;
    position: relative;
    overflow: hidden;
}
.smu-hero::before {
    content: "";
    position: absolute;
    top: -80px; right: -60px;
    width: 300px; height: 300px;
    background: rgba(255,255,255,0.04);
    border-radius: 50%;
    pointer-events: none;
}
.smu-hero::after {
    content: "";
    position: absolute;
    bottom: -70px; left: 30%;
    width: 250px; height: 250px;
    background: rgba(124,58,237,0.12);
    border-radius: 50%;
    pointer-events: none;
}
.smu-hero-content {
    display: flex;
    align-items: center;
    gap: 1.5rem;
    margin-bottom: 2rem;
    position: relative;
    z-index: 1;
}
.smu-hero-logo {
    width: 108px;
    height: 108px;
    flex-shrink: 0;
    filter: brightness(0) invert(1);
    opacity: 0.92;
}
.smu-hero-title {
    color: #FFFFFF !important;
    font-size: 2.4rem !important;
    font-weight: 800 !important;
    margin: 0 0 0.2rem !important;
    letter-spacing: -0.02em !important;
    line-height: 1.15 !important;
}
.smu-hero-org {
    color: #93C5FD !important;
    font-size: 0.875rem !important;
    font-weight: 500 !important;
    margin: 0 0 0.5rem !important;
    letter-spacing: 0.03em !important;
    text-transform: uppercase !important;
}
.smu-hero-tagline {
    color: #CBD5E1 !important;
    font-size: 0.9rem !important;
    margin: 0 !important;
    max-width: 480px !important;
    line-height: 1.5 !important;
}
.smu-hero-stats {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    position: relative;
    z-index: 1;
}
.smu-stat {
    background: rgba(255,255,255,0.08);
    border: 1px solid rgba(255,255,255,0.12);
    padding: 0.6rem 1.25rem;
    border-radius: 10px;
    min-width: 90px;
    backdrop-filter: blur(4px);
}
.smu-stat-number {
    color: #FFFFFF;
    font-size: 1.5rem;
    font-weight: 700;
    line-height: 1;
}
.smu-stat-label {
    color: #93C5FD;
    font-size: 0.7rem;
    font-weight: 600;
    margin-top: 0.2rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

/* ── SECTION HEADING ──────────────────────────────────────── */
.smu-section-heading {
    padding: 0 0 0 0.875rem;
    border-left: 4px solid #2563EB;
    margin: 1.75rem 0 1.25rem;
}
.smu-section-heading .smu-sh-label {
    font-size: 0.68rem;
    font-weight: 700;
    color: #64748B;
    text-transform: uppercase;
    letter-spacing: 0.09em;
    display: block;
    margin-bottom: 0.1rem;
}
.smu-section-heading .smu-sh-title {
    font-size: 1.1rem;
    font-weight: 700;
    color: #0F172A;
    display: block;
    line-height: 1.2;
}
.smu-section-heading.tools { border-left-color: #7C3AED; }

/* ── PAGE HEADER ──────────────────────────────────────────── */
.smu-page-header {
    display: flex;
    align-items: flex-start;
    gap: 1rem;
    padding: 0 0 1.5rem;
    border-bottom: 2px solid #E2E8F0;
    margin-bottom: 1.75rem;
}
.smu-page-icon {
    font-size: 1.9rem;
    background: #EFF6FF;
    border-radius: 10px;
    padding: 0.55rem 0.65rem;
    min-width: 3.25rem;
    text-align: center;
    display: block;
    line-height: 1;
    flex-shrink: 0;
}
.smu-page-icon.ai { background: #F5F3FF; }
.smu-page-icon.rag { background: #ECFDF5; }
.smu-page-icon.tool { background: #FFF7ED; }
.smu-page-title {
    margin: 0 0 0.25rem !important;
    font-size: 1.65rem !important;
    font-weight: 800 !important;
    color: #0F172A !important;
    line-height: 1.2 !important;
    display: flex !important;
    align-items: center !important;
    gap: 0.5rem !important;
    flex-wrap: wrap !important;
}
.smu-page-subtitle {
    margin: 0 !important;
    color: #64748B !important;
    font-size: 0.9rem !important;
    font-weight: 400 !important;
    line-height: 1.5 !important;
}

/* ── BADGES ───────────────────────────────────────────────── */
.smu-badge {
    display: inline-flex;
    align-items: center;
    font-size: 0.62rem;
    font-weight: 700;
    padding: 0.15rem 0.55rem;
    border-radius: 999px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    vertical-align: middle;
    background: #EFF6FF;
    color: #2563EB;
}
.smu-badge-ai {
    background: #F5F3FF;
    color: #7C3AED;
}
.smu-badge-rag {
    background: #ECFDF5;
    color: #059669;
}

/* ── SECTION DIVIDER ──────────────────────────────────────── */
.smu-divider {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin: 2rem 0 1.25rem;
}
.smu-divider-label {
    font-size: 0.75rem;
    font-weight: 700;
    color: #475569;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    white-space: nowrap;
    padding-left: 0.75rem;
    border-left: 3px solid #2563EB;
}
.smu-divider-line {
    flex: 1;
    height: 1px;
    background: #E2E8F0;
}

/* ── FOOTER ───────────────────────────────────────────────── */
.smu-footer {
    margin-top: 3rem;
    padding: 1.5rem 0 0;
    border-top: 1px solid #E2E8F0;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.75rem;
}
.smu-footer-warning {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.78rem;
    color: #92400E;
    background: #FEF3C7;
    padding: 0.35rem 0.75rem;
    border-radius: 6px;
    font-weight: 600;
}
.smu-footer-info {
    font-size: 0.78rem;
    color: #94A3B8;
    text-align: right;
    line-height: 1.6;
}
.smu-footer-info a { color: #60A5FA !important; text-decoration: none !important; }
.smu-footer-info a:hover { text-decoration: underline !important; }

/* ── LLM SELECTOR IN SIDEBAR ─────────────────────────────── */
.smu-llm-header {
    font-size: 0.65rem;
    font-weight: 700;
    color: #64748B;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    padding: 1rem 0 0.4rem 0;
    display: block;
    border-top: 1px solid #334155;
    margin-top: 0.25rem;
}
.smu-llm-info {
    background: rgba(255,255,255,0.06);
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 0.6rem 0.75rem;
    margin-top: 0.5rem;
}
.smu-llm-info-row {
    display: flex;
    justify-content: space-between;
    font-size: 0.72rem;
    color: #64748B;
    margin-bottom: 0.2rem;
    line-height: 1.4;
}
.smu-llm-info-row span:last-child {
    color: #CBD5E1;
    font-weight: 500;
    text-align: right;
    max-width: 60%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
"""


def inject_global_css() -> None:
    """Inject the global CSS design system. Call once in main.py."""
    st.markdown(f"<style>{_GLOBAL_CSS}</style>", unsafe_allow_html=True)


def page_header(icon: str, title: str, subtitle: str, badge: str | None = None) -> None:
    """Render a consistent page header with icon, title, subtitle, and optional badge pill.

    Args:
        icon: Emoji or character shown in the icon box.
        title: Page title (plain text).
        subtitle: Descriptive subtitle (plain text).
        badge: Optional badge label — "AI", "RAG", or any short string.
    """
    _badge_class_map = {"AI": "smu-badge-ai", "RAG": "smu-badge-rag"}
    _icon_class_map = {"AI": "ai", "RAG": "rag"}

    badge_html = ""
    icon_cls = ""
    if badge:
        badge_cls = _badge_class_map.get(badge, "smu-badge")
        icon_cls = _icon_class_map.get(badge, "tool")
        badge_html = f'<span class="smu-badge {badge_cls}">{badge}</span>'

    icon_class = f'smu-page-icon {icon_cls}' if icon_cls else "smu-page-icon"

    st.markdown(
        f"""
        <div class="smu-page-header">
            <span class="{icon_class}">{icon}</span>
            <div>
                <h1 class="smu-page-title">{title} {badge_html}</h1>
                <p class="smu-page-subtitle">{subtitle}</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_divider(label: str = "", subtitle: str = "") -> None:
    """Render a styled section divider with an optional label.

    If label is empty, renders a plain horizontal rule.
    """
    if label:
        sub_html = (
            f'<span style="font-size:0.8rem;color:#94A3B8;margin-left:0.5rem;">{subtitle}</span>'
            if subtitle
            else ""
        )
        st.markdown(
            f"""
            <div class="smu-divider">
                <span class="smu-divider-label">{label}{sub_html}</span>
                <div class="smu-divider-line"></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div style="height:1px;background:#E2E8F0;margin:2rem 0;"></div>',
            unsafe_allow_html=True,
        )
