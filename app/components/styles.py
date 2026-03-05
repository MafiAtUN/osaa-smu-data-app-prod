"""Centralized CSS design system and reusable UI header components.

Call inject_global_css() once in main.py (after st.set_page_config).
Use page_header() and section_divider() on individual pages.
"""

from __future__ import annotations

import streamlit as st

# ---------------------------------------------------------------------------
# Design tokens — Orange-dominant professional palette
# ---------------------------------------------------------------------------
# Orange primary:  #EA580C  •  Orange dark:  #C2410C  •  Orange accent: #F97316
# Stone sidebar:   #1C1917  •  Stone border: #292524  •  Stone text:    #A8A29E
# Page BG:         #FAFAF9  •  Card BG:      #FFFFFF  •  Border:        #E7E5E4
# Text primary:    #1C1917  •  Text muted:   #78716C  •  AI accent:     #7C3AED

_GLOBAL_CSS = """
/* ═══════════════════════════════════════════════════════════════
   SMU DATA APP — OSAA Orange Design System  (Feb 2026)
   ═══════════════════════════════════════════════════════════════ */

/* ── HIDE DEFAULT STREAMLIT CHROME ────────────────────────────── */
#MainMenu { visibility: hidden !important; }
footer { visibility: hidden !important; }
[data-testid="stToolbar"]    { display: none !important; }
[data-testid="stDecoration"] { display: none !important; }
[data-testid="stHeader"]     { display: none !important; }

/* ── PAGE BACKGROUND ───────────────────────────────────────────── */
.stApp { background: #FAFAF9 !important; }

/* ── MAIN CONTENT CONTAINER ────────────────────────────────────── */
.main .block-container {
    padding: 2rem 3rem 3rem !important;
    max-width: 1400px !important;
    overflow-anchor: none !important;
}

/* ── COLUMNS — clip overflow so cards can't bleed out ──────────── */
[data-testid="column"] {
    min-width: 0 !important;
    overflow: hidden !important;
    box-sizing: border-box !important;
}

/* ══════════════════════════════════════════════════════
   SIDEBAR
   ══════════════════════════════════════════════════════ */
section[data-testid="stSidebar"],
section[data-testid="stSidebar"] > div,
section[data-testid="stSidebar"] > div > div {
    background: #1C1917 !important;
}
section[data-testid="stSidebar"] {
    border-right: 1px solid #292524 !important;
}

/* Sidebar text defaults */
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] small,
section[data-testid="stSidebar"] .stCaption,
section[data-testid="stSidebar"] .stMarkdown p {
    color: #A8A29E !important;
}
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {
    color: #F5F5F4 !important;
}

/* Logo in sidebar */
section[data-testid="stSidebar"] img {
    opacity: 1 !important;
}

/* Sidebar nav links */
[data-testid="stSidebarNavLink"] {
    border-radius: 8px !important;
    padding: 0.45rem 0.75rem !important;
    margin: 1px 0 !important;
    color: #D6D3D1 !important;
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
    background: rgba(234,88,12,0.15) !important;
    color: #FB923C !important;
}
[data-testid="stSidebarNavLink"][aria-current="page"],
[data-testid="stSidebarNavLink"][aria-selected="true"] {
    background: #EA580C !important;
    color: #FFFFFF !important;
    font-weight: 600 !important;
}

/* Sidebar nav section separators / group headers */
[data-testid="stSidebarNavSeparator"],
[data-testid="stSidebarNavItems"] > div > hr + div,
section[data-testid="stSidebar"] .stSidebarNavSeparator {
    color: #57534E !important;
    font-size: 0.65rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
    padding-top: 0.65rem !important;
    margin-top: 0.35rem !important;
    border-top: 1px solid #292524 !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    white-space: nowrap !important;
}

/* Sidebar selectbox & widgets */
section[data-testid="stSidebar"] [data-baseweb="select"] > div {
    background: #292524 !important;
    border-color: #44403C !important;
    border-radius: 8px !important;
}
section[data-testid="stSidebar"] [data-baseweb="select"] span,
section[data-testid="stSidebar"] [data-baseweb="select"] div {
    color: #F5F5F4 !important;
}
section[data-testid="stSidebar"] [data-baseweb="popover"] {
    background: #1C1917 !important;
}
section[data-testid="stSidebar"] [role="option"] {
    background: #1C1917 !important;
    color: #D6D3D1 !important;
}
section[data-testid="stSidebar"] [role="option"]:hover {
    background: #292524 !important;
}

/* Sidebar divider */
section[data-testid="stSidebar"] hr {
    border-color: #292524 !important;
}

/* Sidebar warning/info boxes */
section[data-testid="stSidebar"] [data-testid="stAlert"] {
    background: rgba(239,68,68,0.1) !important;
    border: 1px solid rgba(239,68,68,0.3) !important;
    border-radius: 8px !important;
}

/* ══════════════════════════════════════════════════════
   BUTTONS
   ══════════════════════════════════════════════════════ */
.stButton > button {
    border-radius: 8px !important;
    font-weight: 600 !important;
    transition: all 0.15s ease !important;
    font-size: 0.875rem !important;
    letter-spacing: 0.01em !important;
}
/* Primary */
.stButton > button[kind="primary"] {
    background: #EA580C !important;
    border: none !important;
    color: #FFFFFF !important;
    box-shadow: 0 1px 3px rgba(234,88,12,0.3) !important;
}
.stButton > button[kind="primary"]:hover {
    background: #C2410C !important;
    box-shadow: 0 4px 12px rgba(234,88,12,0.45) !important;
    transform: translateY(-1px) !important;
}
/* Secondary */
.stButton > button[kind="secondary"] {
    background: transparent !important;
    border: 1.5px solid #D6D3D1 !important;
    color: #57534E !important;
}
.stButton > button[kind="secondary"]:hover {
    border-color: #EA580C !important;
    color: #EA580C !important;
    background: #FFF7ED !important;
}

/* ══════════════════════════════════════════════════════
   PAGE LINKS (styled as interactive cards)
   ══════════════════════════════════════════════════════ */
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
    border: 1.5px solid #E7E5E4 !important;
    color: #1C1917 !important;
    transition: all 0.2s ease !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05) !important;
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
    border-color: #EA580C !important;
    box-shadow: 0 6px 20px rgba(234,88,12,0.15) !important;
    transform: translateY(-2px) !important;
    color: #C2410C !important;
    border-left: 4px solid #EA580C !important;
}
/* All elements inside page link wrap and not overflow */
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
    color: #1C1917 !important;
    display: block !important;
    margin-bottom: 0.2rem !important;
}

/* ══════════════════════════════════════════════════════
   DATA SOURCE GROUP HEADER (home page)
   ══════════════════════════════════════════════════════ */
.smu-ds-group {
    background: linear-gradient(135deg, #7C2D12 0%, #EA580C 100%);
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
    color: #FFEDD5;
    font-size: 0.68rem;
    font-weight: 500;
    display: block;
    margin-top: 0.1rem;
    letter-spacing: 0.03em;
}
/* Page links that follow a .smu-ds-group header */
.smu-ds-group ~ div [data-testid="stPageLink"]:first-child a,
.smu-ds-group + div [data-testid="stPageLink"] a {
    border-radius: 0 !important;
    border-top: none !important;
}
.smu-ds-group ~ div + div [data-testid="stPageLink"] a {
    border-radius: 0 0 12px 12px !important;
    border-top: none !important;
}

/* ══════════════════════════════════════════════════════
   FORM INPUTS
   ══════════════════════════════════════════════════════ */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea {
    border-radius: 8px !important;
    border: 1.5px solid #E7E5E4 !important;
    background: #FFFFFF !important;
    padding: 0.5rem 0.75rem !important;
    transition: border-color 0.15s ease, box-shadow 0.15s ease !important;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: #EA580C !important;
    box-shadow: 0 0 0 3px rgba(234,88,12,0.12) !important;
    outline: none !important;
}
/* Selectbox / multiselect */
[data-baseweb="select"] > div:first-child {
    border-radius: 8px !important;
    border: 1.5px solid #E7E5E4 !important;
    transition: border-color 0.15s ease !important;
}
[data-baseweb="select"] > div:first-child:focus-within {
    border-color: #EA580C !important;
    box-shadow: 0 0 0 3px rgba(234,88,12,0.12) !important;
}
/* Slider */
[data-testid="stSlider"] [role="slider"] {
    background: #EA580C !important;
}
[data-testid="stSlider"] [data-testid="stSliderTrack"] {
    background: #FFEDD5 !important;
}

/* ══════════════════════════════════════════════════════
   TABS
   ══════════════════════════════════════════════════════ */
[data-baseweb="tab-list"] {
    background: transparent !important;
    border-bottom: 2px solid #E7E5E4 !important;
    gap: 0 !important;
    padding: 0 !important;
}
[data-baseweb="tab"] {
    font-weight: 600 !important;
    color: #78716C !important;
    background: transparent !important;
    border-radius: 0 !important;
    padding: 0.65rem 1.25rem !important;
    border-bottom: 3px solid transparent !important;
    margin-bottom: -2px !important;
    transition: color 0.15s ease !important;
    font-size: 0.875rem !important;
}
[data-baseweb="tab"]:hover {
    color: #EA580C !important;
    background: transparent !important;
}
[data-baseweb="tab"][aria-selected="true"] {
    color: #EA580C !important;
    border-bottom-color: #EA580C !important;
    background: transparent !important;
}
[data-baseweb="tab-highlight"] { display: none !important; }
[data-testid="stTabPanel"] { padding-top: 1.25rem !important; }

/* ══════════════════════════════════════════════════════
   METRICS
   ══════════════════════════════════════════════════════ */
[data-testid="stMetric"] {
    background: #FFFFFF !important;
    border: 1px solid #E7E5E4 !important;
    border-radius: 12px !important;
    padding: 1rem 1.25rem !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
    border-left: 4px solid #EA580C !important;
}
[data-testid="stMetricValue"] {
    color: #1C1917 !important;
    font-weight: 700 !important;
}
[data-testid="stMetricLabel"] {
    color: #78716C !important;
    font-size: 0.8rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
}

/* ══════════════════════════════════════════════════════
   DATAFRAME
   ══════════════════════════════════════════════════════ */
[data-testid="stDataFrame"] {
    border-radius: 10px !important;
    overflow: hidden !important;
    border: 1px solid #E7E5E4 !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
}

/* ══════════════════════════════════════════════════════
   EXPANDER
   ══════════════════════════════════════════════════════ */
[data-testid="stExpander"] {
    border: 1px solid #E7E5E4 !important;
    border-radius: 10px !important;
    overflow: hidden !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.04) !important;
}
[data-testid="stExpander"] summary {
    background: #FAFAF9 !important;
    font-weight: 600 !important;
    color: #1C1917 !important;
    padding: 0.75rem 1rem !important;
    border-radius: 10px !important;
}
[data-testid="stExpander"][open] summary {
    border-radius: 10px 10px 0 0 !important;
    border-bottom: 1px solid #E7E5E4 !important;
}

/* ══════════════════════════════════════════════════════
   CHAT
   ══════════════════════════════════════════════════════ */
[data-testid="stChatMessage"] {
    background: #FFFFFF !important;
    border: 1px solid #E7E5E4 !important;
    border-radius: 12px !important;
    margin-bottom: 0.75rem !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.04) !important;
    padding: 0.75rem 1rem !important;
}
[data-testid="stChatInput"] {
    border-radius: 10px !important;
    border: 1.5px solid #E7E5E4 !important;
    background: #FFFFFF !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06) !important;
}
[data-testid="stChatInput"] textarea {
    border: none !important;
    outline: none !important;
}
[data-testid="stChatInput"]:focus-within {
    border-color: #EA580C !important;
    box-shadow: 0 0 0 3px rgba(234,88,12,0.12) !important;
}

/* ══════════════════════════════════════════════════════
   ALERTS / SPINNER / CODE
   ══════════════════════════════════════════════════════ */
[data-testid="stAlert"] {
    border-radius: 10px !important;
    border: none !important;
    font-size: 0.875rem !important;
}
[data-testid="stCode"], .stCode, pre {
    border-radius: 8px !important;
    overflow: hidden !important;
}
[data-testid="stSpinner"] { color: #EA580C !important; }

/* ══════════════════════════════════════════════════════════════
   CUSTOM SMU COMPONENT CLASSES
   ══════════════════════════════════════════════════════════════ */

/* ── HERO SECTION ──────────────────────────────────────────────── */
.smu-hero {
    background: #1C1917;
    border-radius: 20px;
    margin-top: -0.5rem;
    margin-bottom: 2.25rem;
    overflow: hidden;
    box-shadow: 0 4px 24px rgba(0,0,0,0.18);
    border: 1px solid #292524;
}

/* Orange top accent bar */
.smu-hero-topbar {
    background: linear-gradient(90deg, #EA580C 0%, #C2410C 100%);
    padding: 0.55rem 2.5rem;
    font-size: 0.72rem;
    font-weight: 600;
    color: #FFEDD5;
    letter-spacing: 0.05em;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}
.smu-hero-topbar-dot {
    display: inline-block;
    width: 7px;
    height: 7px;
    background: #FFEDD5;
    border-radius: 50%;
    opacity: 0.7;
    flex-shrink: 0;
}

/* Main body: logo left, text right */
.smu-hero-body {
    display: flex;
    align-items: center;
    gap: 3rem;
    padding: 2.5rem 2.75rem 2.5rem;
}
.smu-hero-logo-wrap {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 300px;
    height: 300px;
    background: rgba(255,255,255,0.04);
    border-radius: 16px;
    border: 1px solid #292524;
    padding: 1.5rem;
}
.smu-hero-logo {
    width: 100%;
    height: 100%;
    object-fit: contain;
    display: block;
}
.smu-hero-text {
    flex: 1;
    min-width: 0;
}
.smu-hero-title {
    color: #FFFFFF !important;
    font-size: 3rem !important;
    font-weight: 800 !important;
    margin: 0 0 0.75rem !important;
    letter-spacing: -0.03em !important;
    line-height: 1.05 !important;
}
.smu-hero-tagline {
    color: #A8A29E !important;
    font-size: 1rem !important;
    margin: 0 0 1.75rem !important;
    max-width: 560px !important;
    line-height: 1.65 !important;
}
.smu-hero-pills {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
}
.smu-hero-pill {
    background: rgba(234,88,12,0.12);
    border: 1px solid rgba(234,88,12,0.3);
    color: #FB923C;
    font-size: 0.78rem;
    font-weight: 600;
    padding: 0.35rem 0.85rem;
    border-radius: 999px;
    white-space: nowrap;
    letter-spacing: 0.01em;
}

/* ── HOME FEATURE CARDS ────────────────────────────────────────── */
/* When a feature card is immediately followed by a page_link, connect them */
.element-container:has(.smu-feature-card) {
    margin-bottom: 0 !important;
}
.element-container:has(.smu-feature-card) .smu-feature-card {
    border-radius: 14px 14px 0 0 !important;
    border-bottom: none !important;
    margin-bottom: 0 !important;
}
.element-container:has(.smu-feature-card) + .element-container [data-testid="stPageLink"] a {
    border-radius: 0 0 12px 12px !important;
    border-top: 1px dashed #E7E5E4 !important;
    background: #FAFAF9 !important;
    font-size: 0.82rem !important;
    font-weight: 600 !important;
    color: #EA580C !important;
    padding: 0.65rem 1.1rem !important;
}
.element-container:has(.smu-feature-card) + .element-container [data-testid="stPageLink"] a:hover {
    background: #FFF7ED !important;
    color: #C2410C !important;
    transform: none !important;
    border-top-color: #FED7AA !important;
}

.smu-feature-card {
    background: #FFFFFF;
    border: 1.5px solid #E7E5E4;
    border-radius: 14px;
    padding: 1.4rem 1.35rem;
    height: 100%;
    transition: all 0.2s ease;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05);
    position: relative;
    overflow: hidden;
}
.smu-feature-card::before {
    content: "";
    position: absolute;
    top: 0; left: 0;
    width: 4px; height: 100%;
    background: linear-gradient(180deg, #EA580C, #F97316);
    border-radius: 4px 0 0 4px;
    opacity: 0;
    transition: opacity 0.2s ease;
}
.smu-feature-card:hover::before { opacity: 1; }
.smu-feature-card:hover {
    box-shadow: 0 8px 24px rgba(234,88,12,0.12);
    border-color: #FED7AA;
    transform: translateY(-2px);
}
.smu-feature-card-icon {
    font-size: 1.75rem;
    margin-bottom: 0.75rem;
    display: block;
    line-height: 1;
}
.smu-feature-card-title {
    font-size: 1rem;
    font-weight: 700;
    color: #1C1917;
    margin-bottom: 0.35rem;
    display: block;
}
.smu-feature-card-subtitle {
    font-size: 0.7rem;
    font-weight: 600;
    color: #EA580C;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    display: block;
    margin-bottom: 0.5rem;
}
.smu-feature-card-desc {
    font-size: 0.82rem;
    color: #78716C;
    line-height: 1.55;
    display: block;
}

/* ── SECTION HEADING ───────────────────────────────────────────── */
.smu-section-heading {
    padding: 0 0 0 0.875rem;
    border-left: 4px solid #EA580C;
    margin: 2rem 0 1.35rem;
}
.smu-section-heading .smu-sh-label {
    font-size: 0.68rem;
    font-weight: 700;
    color: #78716C;
    text-transform: uppercase;
    letter-spacing: 0.09em;
    display: block;
    margin-bottom: 0.1rem;
}
.smu-section-heading .smu-sh-title {
    font-size: 1.15rem;
    font-weight: 800;
    color: #1C1917;
    display: block;
    line-height: 1.2;
}
.smu-section-heading.tools { border-left-color: #7C3AED; }
.smu-section-heading.ai    { border-left-color: #7C3AED; }

/* ── PAGE HEADER ───────────────────────────────────────────────── */
.smu-page-header {
    display: flex;
    align-items: flex-start;
    gap: 1rem;
    padding: 0 0 1.5rem;
    border-bottom: 2px solid #E7E5E4;
    margin-bottom: 1.75rem;
}
.smu-page-icon {
    font-size: 1.9rem;
    background: #FFF7ED;
    border-radius: 10px;
    padding: 0.55rem 0.65rem;
    min-width: 3.25rem;
    text-align: center;
    display: block;
    line-height: 1;
    flex-shrink: 0;
    border: 1px solid #FFEDD5;
}
.smu-page-icon.ai  { background: #F5F3FF; border-color: #EDE9FE; }
.smu-page-icon.rag { background: #ECFDF5; border-color: #D1FAE5; }
.smu-page-icon.tool { background: #FFF7ED; border-color: #FFEDD5; }
.smu-page-title {
    margin: 0 0 0.25rem !important;
    font-size: 1.65rem !important;
    font-weight: 800 !important;
    color: #1C1917 !important;
    line-height: 1.2 !important;
    display: flex !important;
    align-items: center !important;
    gap: 0.5rem !important;
    flex-wrap: wrap !important;
}
.smu-page-subtitle {
    margin: 0 !important;
    color: #78716C !important;
    font-size: 0.9rem !important;
    font-weight: 400 !important;
    line-height: 1.5 !important;
}

/* ── BADGES ────────────────────────────────────────────────────── */
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
    background: #FFF7ED;
    color: #EA580C;
    border: 1px solid #FED7AA;
}
.smu-badge-ai {
    background: #F5F3FF;
    color: #7C3AED;
    border-color: #DDD6FE;
}
.smu-badge-rag {
    background: #ECFDF5;
    color: #059669;
    border-color: #A7F3D0;
}

/* ── SECTION DIVIDER ───────────────────────────────────────────── */
.smu-divider {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin: 2rem 0 1.25rem;
}
.smu-divider-label {
    font-size: 0.75rem;
    font-weight: 700;
    color: #57534E;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    white-space: nowrap;
    padding-left: 0.75rem;
    border-left: 3px solid #EA580C;
}
.smu-divider-line {
    flex: 1;
    height: 1px;
    background: #E7E5E4;
}

/* ── FOOTER ────────────────────────────────────────────────────── */
.smu-footer {
    margin-top: 3rem;
    padding: 1.5rem 0 0;
    border-top: 2px solid #E7E5E4;
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
    color: #9A3412;
    background: #FFF7ED;
    border: 1px solid #FED7AA;
    padding: 0.35rem 0.75rem;
    border-radius: 6px;
    font-weight: 600;
}
.smu-footer-info {
    font-size: 0.78rem;
    color: #A8A29E;
    text-align: right;
    line-height: 1.6;
}
.smu-footer-info a { color: #FB923C !important; text-decoration: none !important; }
.smu-footer-info a:hover { text-decoration: underline !important; }

/* ── LLM SELECTOR IN SIDEBAR ───────────────────────────────────── */
.smu-llm-header {
    font-size: 0.65rem;
    font-weight: 700;
    color: #57534E;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    padding: 1rem 0 0.4rem 0;
    display: block;
    border-top: 1px solid #292524;
    margin-top: 0.25rem;
}
.smu-llm-info {
    background: rgba(255,255,255,0.05);
    border: 1px solid #292524;
    border-radius: 8px;
    padding: 0.6rem 0.75rem;
    margin-top: 0.5rem;
}
.smu-llm-info-row {
    display: flex;
    justify-content: space-between;
    font-size: 0.72rem;
    color: #57534E;
    margin-bottom: 0.2rem;
    line-height: 1.4;
}
.smu-llm-info-row span:last-child {
    color: #D6D3D1;
    font-weight: 500;
    text-align: right;
    max-width: 60%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

/* ── SIDEBAR BRANDING BLOCK ─────────────────────────────────────── */
.smu-sidebar-brand {
    padding: 0.25rem 0 0.75rem;
    border-bottom: 1px solid #292524;
    margin-bottom: 0.25rem;
}
.smu-sidebar-brand-name {
    font-size: 0.85rem;
    font-weight: 700;
    color: #F5F5F4;
    letter-spacing: -0.01em;
    display: block;
    margin-top: 0.35rem;
    margin-bottom: 0.1rem;
}
.smu-sidebar-brand-sub {
    font-size: 0.65rem;
    color: #57534E;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    display: block;
}
.smu-sidebar-brand-dot {
    display: inline-block;
    width: 6px;
    height: 6px;
    background: #EA580C;
    border-radius: 50%;
    margin-right: 0.4rem;
    vertical-align: middle;
    margin-top: -1px;
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

    icon_class = f"smu-page-icon {icon_cls}" if icon_cls else "smu-page-icon"

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
            f'<span style="font-size:0.8rem;color:#A8A29E;margin-left:0.5rem;">{subtitle}</span>'
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
            '<div style="height:1px;background:#E7E5E4;margin:2rem 0;"></div>',
            unsafe_allow_html=True,
        )
