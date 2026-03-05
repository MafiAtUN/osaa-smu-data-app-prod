"""Reusable table and spreadsheet components."""

from __future__ import annotations

import warnings

import pandas as pd
import streamlit as st

from app.core.logging import get_logger

logger = get_logger(__name__)


def df_summary(df: pd.DataFrame) -> None:
    """Display per-column summary statistics in tabs."""
    summary = df.describe()
    columns = summary.columns
    tabs = st.tabs(columns.to_list())

    def _stat(stat: str, col: str) -> str:
        return summary.loc[stat, col] if stat in summary.index else "N/A"

    for i, col in enumerate(columns):
        with tabs[i]:
            for label, key in [
                ("Count", "count"), ("Mean", "mean"),
                ("Standard Deviation", "std"), ("Min", "min"),
                ("25th Percentile", "25%"), ("Median", "50%"),
                ("75th Percentile", "75%"), ("Max", "max"),
            ]:
                st.markdown(f"**{label}**: {_stat(key, col)}")


def show_mitosheet(df: pd.DataFrame) -> None:
    """Show a Mitosheet spreadsheet (if installed)."""
    try:
        from mitosheet.streamlit.v1 import spreadsheet
    except ImportError:
        st.info("Mitosheet is not installed. Install it with: pip install mitosheet")
        return

    new_dfs, code = spreadsheet(df)
    if code:
        st.markdown("##### Generated Code:")
        st.code(code)


def show_pygwalker(df: pd.DataFrame) -> None:
    """Show the PyGWalker interactive visualization tool."""
    if hasattr(st, "user") and (not hasattr(st, "experimental_user") or st.experimental_user != st.user):
        try:
            st.experimental_user = st.user
        except Exception:
            pass

    warnings.filterwarnings("ignore", message=".*experimental_user.*")
    warnings.filterwarnings("ignore", category=FutureWarning, message=".*experimental_user.*")

    import streamlit.components.v1 as components
    from pygwalker.api.streamlit import get_streamlit_html, init_streamlit_comm

    try:
        init_streamlit_comm()
    except Exception as exc:
        if any(kw in str(exc).lower() for kw in ("openai", "credentials", "api_key")):
            st.warning("PyGWalker encountered an OpenAI-related issue. The visualization may still work.")
        else:
            raise

    @st.cache_resource
    def _get_html(_df: pd.DataFrame) -> str:
        return get_streamlit_html(_df, spec="./gw0.json", use_kernel_calc=True, debug=False)

    components.html(_get_html(df), width=1300, height=1000, scrolling=True)
