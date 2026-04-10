"""SMU Data App — single Streamlit entry point.

Run with:
    streamlit run app/main.py

Author:   Mafizul Islam
Email:    islam50@un.org | mafi@mafizul.me
GitHub:   https://github.com/mafiatun
LinkedIn: https://www.linkedin.com/in/mafizul/
License:  MIT — Copyright (c) 2024–2026 Mafizul Islam
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path so "app" package is found
_here = Path(__file__).resolve()
_root = _here.parent.parent if _here.name == "main.py" else _here.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

import streamlit as st  # noqa: E402

from app.components.llm_selector import render_llm_selector  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.components.styles import inject_global_css  # noqa: E402
from app.core.logging import setup_logging  # noqa: E402
from app.core.security import render_logout_button, require_password, validate_runtime_security  # noqa: E402

st.set_page_config(
    page_title="SMU Data App · OSAA",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inject the global CSS design system (runs on every page navigation)
inject_global_css()

setup_logging()
settings = get_settings()
validate_runtime_security(
    password_hash=settings.app.password_hash,
    plain_password=settings.app.password,
)

require_password(
    session_prefix="app",
    password_hash=settings.app.password_hash,
    plain_password=settings.app.password,
    title="SMU Data App",
    help_text="Enter the site password to access the internal dashboard.",
)

if "chat_history" not in st.session_state:
    st.session_state.chat_history = {}
if "formatted_chat_history" not in st.session_state:
    st.session_state.formatted_chat_history = {}

# ── Sidebar branding ────────────────────────────────────────────────────────
_logo_path = _root / "content" / "OSAA Data.png"

with st.sidebar:
    # Logo
    if _logo_path.exists():
        st.image(str(_logo_path), use_container_width=True)

    # Brand text beneath logo
    st.markdown(
        """
        <div class="smu-sidebar-brand">
            <span class="smu-sidebar-brand-name">SMU Data App</span>
            <span class="smu-sidebar-brand-sub">
                <span class="smu-sidebar-brand-dot"></span>UN OSAA · Strategic Management Unit
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

render_logout_button(session_prefix="app")

render_llm_selector()

# Use absolute paths so pages work whether run via app.py or app/main.py
_pages_dir = _root / "app" / "pages"
# Paths for st.page_link must be relative to entrypoint (app.py vs app/main.py)
_page_prefix = "pages/" if _here.name == "main.py" else "app/pages/"
if "_page_prefix" not in st.session_state:
    st.session_state._page_prefix = _page_prefix

home_page = st.Page(str(_pages_dir / "home.py"), title="Home", icon="🏠")

data_pages = [
    st.Page(str(_pages_dir / "dashboard.py"), title="Data Explorer", icon="📂"),
    st.Page(str(_pages_dir / "cross_source_studio.py"), title="Cross-Source Studio", icon="🔗"),
    st.Page(str(_pages_dir / "cross_source_sync.py"), title="Hybrid Sync", icon="🗄️"),
    st.Page(str(_pages_dir / "wb_dashboard_ai.py"), title="World Bank", icon="🌐"),
    st.Page(str(_pages_dir / "sdg_dashboard_ai.py"), title="SDG Indicators", icon="🎯"),
    st.Page(str(_pages_dir / "acled_dashboard_ai.py"), title="ACLED Conflict", icon="⚔️"),
    st.Page(str(_pages_dir / "un_education.py"), title="UNESCO Education", icon="🎓"),
    st.Page(str(_pages_dir / "un_energy.py"), title="UN Energy", icon="⚡"),
    st.Page(str(_pages_dir / "un_data_explorer.py"), title="SDG Explorer", icon="🔭"),
]

tool_pages = [
    st.Page(str(_pages_dir / "chatbot.py"), title="OSAA Chatbot", icon="💬"),
    st.Page(str(_pages_dir / "check_analysis.py"), title="Analysis Checker", icon="⚖️"),
    st.Page(str(_pages_dir / "pid_checker.py"), title="PID Checker", icon="📋"),
    st.Page(str(_pages_dir / "chat_library.py"), title="Chat Library", icon="📚"),
]

pg = st.navigation(
    {
        "": [home_page],
        "Data": data_pages,
        "OSAA Tools": tool_pages,
    }
)

pg.run()
