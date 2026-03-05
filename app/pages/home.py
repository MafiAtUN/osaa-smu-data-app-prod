"""Home page — hero section, data-source cards, tools cards, footer."""

from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

# ── Logo (inline base64 so it renders inside the gradient hero div) ─────────
_logo_path = Path(__file__).resolve().parent.parent / "assets" / "OSAA-Data-logo.svg"
try:
    _logo_b64 = base64.b64encode(_logo_path.read_bytes()).decode()
    _logo_html = (
        f'<img src="data:image/svg+xml;base64,{_logo_b64}" '
        f'class="smu-hero-logo" alt="OSAA logo">'
    )
except Exception:
    _logo_html = '<span style="font-size:4rem;line-height:1;">🌍</span>'

# ── Hero ─────────────────────────────────────────────────────────────────────
st.markdown(
    f"""
    <div class="smu-hero">
        <div class="smu-hero-content">
            {_logo_html}
            <div>
                <h1 class="smu-hero-title">SMU Data App</h1>
                <p class="smu-hero-org">UN OSAA · Strategic Monitoring Unit</p>
                <p class="smu-hero-tagline">
                    From raw data to clear, actionable intelligence —
                    powered by AI and real-time data sources.
                </p>
            </div>
        </div>
        <div class="smu-hero-stats">
            <div class="smu-stat">
                <div class="smu-stat-number">3</div>
                <div class="smu-stat-label">Live APIs</div>
            </div>
            <div class="smu-stat">
                <div class="smu-stat-number">15+</div>
                <div class="smu-stat-label">AI Models</div>
            </div>
            <div class="smu-stat">
                <div class="smu-stat-number">6</div>
                <div class="smu-stat-label">AI Dashboards</div>
            </div>
            <div class="smu-stat">
                <div class="smu-stat-number">RAG</div>
                <div class="smu-stat-label">Retrieval AI</div>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Page-link prefix (set by main.py based on entry point) ──────────────────
_prefix = st.session_state.get("_page_prefix", "pages/")

# ── Data Sources ─────────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="smu-section-heading">
        <span class="smu-sh-label">Explore</span>
        <span class="smu-sh-title">Data Sources</span>
    </div>
    """,
    unsafe_allow_html=True,
)

# Row: Data Dashboard (col 1) + 3 grouped data sources (cols 2-4)
c_dash, c_wb, c_sdg, c_acled = st.columns(4, gap="medium")

with c_dash:
    st.page_link(
        f"{_prefix}dashboard.py",
        label=(
            "📊 **Data Dashboard**\n\n"
            "Upload your own CSV, Excel, or Parquet files. "
            "Filter, visualize, and analyze datasets with AI-generated insights and chart builder."
        ),
        use_container_width=True,
    )

# World Bank group
with c_wb:
    st.markdown(
        """
        <div class="smu-ds-group">
            <span class="smu-ds-group-icon">🌐</span>
            <div>
                <span class="smu-ds-group-name">World Bank</span>
                <span class="smu-ds-group-tag">WDI · 15,000+ development indicators</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.page_link(
        f"{_prefix}wb_dashboard.py",
        label="⚙️ **Manual Selection**\nPick indicators, countries & years.",
        use_container_width=True,
    )
    st.page_link(
        f"{_prefix}wb_dashboard_ai.py",
        label="🤖 **AI-Powered Query**\nAsk in plain English — AI fetches the data.",
        use_container_width=True,
    )

# UN SDG group
with c_sdg:
    st.markdown(
        """
        <div class="smu-ds-group">
            <span class="smu-ds-group-icon">🎯</span>
            <div>
                <span class="smu-ds-group-name">UN SDG</span>
                <span class="smu-ds-group-tag">All 17 Goals · UN official API</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.page_link(
        f"{_prefix}sdg_dashboard.py",
        label="⚙️ **Manual Selection**\nChoose goals, indicators & countries.",
        use_container_width=True,
    )
    st.page_link(
        f"{_prefix}sdg_dashboard_ai.py",
        label="🤖 **AI-Powered Query**\nDescribe what you need — AI handles the rest.",
        use_container_width=True,
    )

# ACLED group
with c_acled:
    st.markdown(
        """
        <div class="smu-ds-group">
            <span class="smu-ds-group-icon">⚔️</span>
            <div>
                <span class="smu-ds-group-name">ACLED</span>
                <span class="smu-ds-group-tag">Armed Conflict &amp; Event Data</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.page_link(
        f"{_prefix}acled_dashboard.py",
        label="⚙️ **Manual Selection**\nSelect event types, regions & dates.",
        use_container_width=True,
    )
    st.page_link(
        f"{_prefix}acled_dashboard_ai.py",
        label="🤖 **AI-Powered Query**\nQuery conflict data in plain English.",
        use_container_width=True,
    )

# ── OSAA Tools ───────────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="smu-section-heading tools">
        <span class="smu-sh-label">Analysis &amp; Compliance</span>
        <span class="smu-sh-title">OSAA Tools</span>
    </div>
    """,
    unsafe_allow_html=True,
)

_tools = [
    (
        f"{_prefix}chatbot.py",
        "💬",
        "OSAA Chatbot",
        "Conversational AI with institutional OSAA context. Ask questions about Africa, UN mandates, and OSAA publications.",
    ),
    (
        f"{_prefix}check_analysis.py",
        "⚖️",
        "Analysis Checker",
        "RAG-powered tool that checks whether your narrative analysis contradicts previous OSAA publications.",
    ),
    (
        f"{_prefix}pid_checker.py",
        "📋",
        "PID Checker",
        "Evaluate Project Initiation Documents against OSAA's 7-dimension criteria framework for each thematic cluster.",
    ),
]

tool_cols = st.columns(3, gap="medium")
for col, (page, icon, label, desc) in zip(tool_cols, _tools):
    with col:
        st.page_link(
            page,
            label=f"{icon} **{label}**\n\n{desc}",
            use_container_width=True,
        )

# ── Notes expander ────────────────────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)
with st.expander("ℹ️ Important Notes", expanded=False):
    st.markdown(
        """
        **AI-Powered Features**
        World Bank, ACLED, and UN SDG dashboards all include an AI mode that accepts natural language queries.
        Manual filter modes are also available for all three.

        **Analysis Tools**
        Every data page includes an AI analysis assistant and a graph-generation tool.
        These are powered by large language models and are intended for **exploratory use only**.

        **Exploratory Use Only**
        Always verify AI-generated results against official sources before including them in publications.

        **Data Sources**
        - World Bank data is fetched live from the World Bank API.
        - SDG data is retrieved from the official UN SDG API.
        - ACLED data requires valid API credentials configured in secrets.
        """
    )

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="smu-footer">
        <span class="smu-footer-warning">
            ⚠️&nbsp; Development version — for UN OSAA internal use only
        </span>
        <div class="smu-footer-info">
            Created by the SMU Data Team · UN OSAA<br>
            © UNOSAA 2025 &nbsp;·&nbsp;
            <a href="mailto:islam50@un.org">islam50@un.org</a>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)
