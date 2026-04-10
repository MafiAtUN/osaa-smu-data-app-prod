"""Home page — hero section, data-source feature cards, tools overview, and footer.

Renders the OSAA SMU Data App landing page including a branded hero block with
the base64-encoded logo, clickable feature cards for each data source (World Bank,
SDG, ACLED, UNESCO, UN Energy, Cross-Source Studio), and an OSAA Tools section.
No services are called here; the page is purely presentational.
"""

from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

# ── Logo (base64-encoded once at import time for hero HTML) ─────────────────
_logo_path = Path(__file__).resolve().parent.parent.parent / "content" / "OSAA Data.png"
try:
    _logo_b64 = base64.b64encode(_logo_path.read_bytes()).decode()
    _logo_html = (
        f'<img src="data:image/png;base64,{_logo_b64}" '
        f'class="smu-hero-logo" alt="OSAA SMU Data logo">'
    )
except Exception:
    _logo_html = '<span style="font-size:4rem;line-height:1;">🌍</span>'

# ── Hero ─────────────────────────────────────────────────────────────────────
st.markdown(
    f"""
    <div class="smu-hero">
        <div class="smu-hero-topbar">
            <span class="smu-hero-topbar-dot"></span>
            UN Office of the Special Adviser on Africa &nbsp;&middot;&nbsp; Strategic Management Unit
        </div>
        <div class="smu-hero-body">
            <div class="smu-hero-logo-wrap">
                {_logo_html}
            </div>
            <div class="smu-hero-text">
                <h1 class="smu-hero-title">SMU Data App</h1>
                <p class="smu-hero-tagline">
                    AI-powered data intelligence platform for Africa &mdash;
                    explore development, conflict, education, and energy data
                    from live UN and international APIs, powered by large language models.
                </p>
                <div class="smu-hero-pills">
                    <span class="smu-hero-pill">6 Live Data Sources</span>
                    <span class="smu-hero-pill">15+ AI Models</span>
                    <span class="smu-hero-pill">1,000+ Indicators</span>
                    <span class="smu-hero-pill">RAG &amp; Vector Search</span>
                    <span class="smu-hero-pill">4 OSAA Tools</span>
                </div>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Page-link prefix (set by main.py based on entry point) ──────────────────
_prefix = st.session_state.get("_page_prefix", "pages/")

# ── DATA SOURCES SECTION ─────────────────────────────────────────────────────
st.markdown(
    """
    <div class="smu-section-heading">
        <span class="smu-sh-label">Live APIs &amp; Datasets</span>
        <span class="smu-sh-title">Data Sources</span>
    </div>
    """,
    unsafe_allow_html=True,
)

# Row 1: Upload + World Bank + SDG
col_upload, col_wb, col_sdg = st.columns(3, gap="medium")

with col_upload:
    st.markdown(
        """
        <div class="smu-feature-card" style="pointer-events:none;">
            <span class="smu-feature-card-icon">📂</span>
            <span class="smu-feature-card-title">Upload Your Data</span>
            <span class="smu-feature-card-subtitle">CSV · Excel · Parquet</span>
            <span class="smu-feature-card-desc">
                Upload any dataset, apply filters, build charts with the drag-and-drop
                chart builder, and get AI-generated analysis instantly.
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.page_link(
        f"{_prefix}dashboard.py",
        label="→ Open Data Explorer",
        use_container_width=True,
    )

with col_wb:
    st.markdown(
        """
        <div class="smu-feature-card" style="pointer-events:none;">
            <span class="smu-feature-card-icon">🌐</span>
            <span class="smu-feature-card-title">World Bank</span>
            <span class="smu-feature-card-subtitle">WDI · 15,000+ Development Indicators</span>
            <span class="smu-feature-card-desc">
                Access the World Bank's full development indicator database.
                Query in plain English and let AI fetch, chart, and interpret the data.
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.page_link(
        f"{_prefix}wb_dashboard_ai.py",
        label="→ Explore World Bank Data",
        use_container_width=True,
    )

with col_sdg:
    st.markdown(
        """
        <div class="smu-feature-card" style="pointer-events:none;">
            <span class="smu-feature-card-icon">🎯</span>
            <span class="smu-feature-card-title">UN SDG Indicators</span>
            <span class="smu-feature-card-subtitle">All 17 Goals · Official UN API</span>
            <span class="smu-feature-card-desc">
                Explore all 17 Sustainable Development Goals with 658+ indicators
                from the official UN SDG data platform, filtered for Africa.
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.page_link(
        f"{_prefix}sdg_dashboard_ai.py",
        label="→ Explore SDG Indicators",
        use_container_width=True,
    )

st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)

# Row 2: ACLED + UNESCO + Energy
col_acled, col_edu, col_energy = st.columns(3, gap="medium")

with col_acled:
    st.markdown(
        """
        <div class="smu-feature-card" style="pointer-events:none;">
            <span class="smu-feature-card-icon">⚔️</span>
            <span class="smu-feature-card-title">ACLED Conflict Data</span>
            <span class="smu-feature-card-subtitle">Armed Conflict &amp; Event Data</span>
            <span class="smu-feature-card-desc">
                Real-time conflict event data for Africa. Query by region, event type,
                date range, or fatalities — with AI interpretation and mapping.
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.page_link(
        f"{_prefix}acled_dashboard_ai.py",
        label="→ Query Conflict Data",
        use_container_width=True,
    )

with col_edu:
    st.markdown(
        """
        <div class="smu-feature-card" style="pointer-events:none;">
            <span class="smu-feature-card-icon">🎓</span>
            <span class="smu-feature-card-title">UNESCO Education</span>
            <span class="smu-feature-card-subtitle">UIS · 333 Education Indicators</span>
            <span class="smu-feature-card-desc">
                UNESCO Institute for Statistics data — literacy rates, enrolment,
                teacher ratios, and more across African countries.
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.page_link(
        f"{_prefix}un_education.py",
        label="→ Explore Education Data",
        use_container_width=True,
    )

with col_energy:
    st.markdown(
        """
        <div class="smu-feature-card" style="pointer-events:none;">
            <span class="smu-feature-card-icon">⚡</span>
            <span class="smu-feature-card-title">UN Energy Data</span>
            <span class="smu-feature-card-subtitle">Energy Stats &amp; Balance · M49 Countries</span>
            <span class="smu-feature-card-desc">
                UN energy statistics and energy balance — 75 commodities, 53 transactions,
                covering production, trade, and consumption across Africa.
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.page_link(
        f"{_prefix}un_energy.py",
        label="→ Explore Energy Data",
        use_container_width=True,
    )

# ── OSAA TOOLS SECTION ───────────────────────────────────────────────────────
st.markdown(
    """
    <div class="smu-section-heading tools">
        <span class="smu-sh-label">AI-Powered Analysis &amp; Compliance</span>
        <span class="smu-sh-title">OSAA Tools</span>
    </div>
    """,
    unsafe_allow_html=True,
)

tool_cols = st.columns(4, gap="medium")

_tools = [
    (
        f"{_prefix}chatbot.py",
        "💬",
        "OSAA Chatbot",
        "Conversational AI",
        "Conversational AI grounded in OSAA institutional context. Ask about Africa, "
        "UN mandates, and OSAA publications.",
    ),
    (
        f"{_prefix}check_analysis.py",
        "⚖️",
        "Analysis Checker",
        "RAG · Consistency Check",
        "RAG-powered tool that verifies whether your narrative contradicts previous "
        "OSAA publications and research.",
    ),
    (
        f"{_prefix}pid_checker.py",
        "📋",
        "PID Checker",
        "7-Dimension Evaluation",
        "Evaluate Project Initiation Documents against OSAA's 7-dimension criteria "
        "framework for each thematic cluster.",
    ),
    (
        f"{_prefix}chat_library.py",
        "📚",
        "Chat Library",
        "Session History",
        "Browse and revisit all previous AI analysis conversations across every "
        "page and tool in the app.",
    ),
]

for col, (page, icon, label, subtitle, desc) in zip(tool_cols, _tools):
    with col:
        st.markdown(
            f"""
            <div class="smu-feature-card" style="pointer-events:none;">
                <span class="smu-feature-card-icon">{icon}</span>
                <span class="smu-feature-card-title">{label}</span>
                <span class="smu-feature-card-subtitle">{subtitle}</span>
                <span class="smu-feature-card-desc">{desc}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.page_link(page, label=f"→ Open {label}", use_container_width=True)

# ── IMPORTANT NOTES ───────────────────────────────────────────────────────────
st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)
with st.expander("ℹ️ Important Notes", expanded=False):
    st.markdown(
        """
        **AI-Powered Features**
        All data dashboards include an AI mode that accepts natural language queries.
        Manual filter modes are also available for most sources.

        **Analysis & Visualization Tools**
        Every data page includes an AI analysis assistant and a chart-generation tool.
        These are powered by large language models and are intended for **exploratory use only**.

        **Always Verify**
        Always verify AI-generated results against official sources before including
        them in publications or policy documents.

        **Data Sources**
        - **World Bank**: Fetched live from the World Bank API (WDI database).
        - **UN SDG**: Retrieved from the official UN SDG SDMX API.
        - **ACLED**: Requires valid API credentials configured in secrets.
        - **UNESCO**: UNESCO Institute for Statistics (UIS) via data.un.org.
        - **UN Energy**: UN energy statistics via SDMX at data.un.org.
        """
    )

# ── FOOTER ────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="smu-footer">
        <span class="smu-footer-warning">
            ⚠️&nbsp; Development version — for UN OSAA internal use only
        </span>
        <div class="smu-footer-info">
            Built by the SMU Data Team &nbsp;·&nbsp; UN OSAA<br>
            © UNOSAA 2025 &nbsp;·&nbsp;
            <a href="mailto:islam50@un.org">islam50@un.org</a>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)
