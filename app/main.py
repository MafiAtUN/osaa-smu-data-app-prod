"""SMU Data App — single Streamlit entry point.

Run with:
    streamlit run app/main.py
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path so "app" package is found
_here = Path(__file__).resolve()
_root = _here.parent.parent if _here.name == "main.py" else _here.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from dotenv import load_dotenv

load_dotenv()

import streamlit as st

from app.components.llm_selector import render_llm_selector
from app.components.styles import inject_global_css
from app.core.logging import setup_logging

st.set_page_config(page_title="SMU Data App", page_icon="📊", layout="wide")

# Inject the global CSS design system (runs on every page navigation)
inject_global_css()

setup_logging()

if "chat_history" not in st.session_state:
    st.session_state.chat_history = {}
if "formatted_chat_history" not in st.session_state:
    st.session_state.formatted_chat_history = {}

# ── Sidebar branding ────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        """
        <div style="padding:1.25rem 0.75rem 0.75rem;border-bottom:1px solid #334155;margin-bottom:0.25rem;">
            <div style="font-size:1rem;font-weight:700;color:#F1F5F9;letter-spacing:-0.01em;">
                SMU Data App
            </div>
            <div style="font-size:0.7rem;color:#64748B;margin-top:0.15rem;font-weight:500;
                        text-transform:uppercase;letter-spacing:0.06em;">
                UN OSAA · Strategic Monitoring Unit
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

render_llm_selector()

# Use absolute paths so pages work whether run via app.py or app/main.py
_pages_dir = _root / "app" / "pages"
# Paths for st.page_link must be relative to entrypoint (app.py vs app/main.py)
_page_prefix = "pages/" if _here.name == "main.py" else "app/pages/"
if "_page_prefix" not in st.session_state:
    st.session_state._page_prefix = _page_prefix

home_page = st.Page(str(_pages_dir / "home.py"), title="Home", icon="🏠")

dashboard_pages = [
    st.Page(str(_pages_dir / "dashboard.py"), title="Data Dashboard", icon="📊"),
]

wb_pages = [
    st.Page(str(_pages_dir / "wb_dashboard.py"), title="Manual", icon="⚙️"),
    st.Page(str(_pages_dir / "wb_dashboard_ai.py"), title="AI-Powered", icon="🤖"),
]

sdg_pages = [
    st.Page(str(_pages_dir / "sdg_dashboard.py"), title="Manual", icon="⚙️"),
    st.Page(str(_pages_dir / "sdg_dashboard_ai.py"), title="AI-Powered", icon="🤖"),
]

acled_pages = [
    st.Page(str(_pages_dir / "acled_dashboard.py"), title="Manual", icon="⚙️"),
    st.Page(str(_pages_dir / "acled_dashboard_ai.py"), title="AI-Powered", icon="🤖"),
]

tool_pages = [
    st.Page(str(_pages_dir / "chatbot.py"), title="OSAA Chatbot", icon="💬"),
    st.Page(str(_pages_dir / "check_analysis.py"), title="Analysis Checker", icon="⚖️"),
    st.Page(str(_pages_dir / "pid_checker.py"), title="PID Checker", icon="📋"),
    st.Page(str(_pages_dir / "chat_library.py"), title="Chat Library", icon="🗂️"),
]

pg = st.navigation(
    {
        "": [home_page],
        "Data": dashboard_pages,
        "World Bank": wb_pages,
        "UN SDG": sdg_pages,
        "ACLED": acled_pages,
        "Tools": tool_pages,
    }
)

pg.run()
