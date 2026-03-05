"""Reusable query-suggestion pill component.

Usage::

    from app.components.query_suggestions import render_query_suggestions
    from app.services.acled_service import ACLED_QUERY_SUGGESTIONS

    query = render_query_suggestions(
        ACLED_QUERY_SUGGESTIONS,
        text_area_key="acled_ai_query",
        default_index=0,          # which pill is pre-selected
        placeholder="e.g., conflict events in Africa from 2023 to 2024",
    )
    if st.button("Fetch Data", type="primary") and query:
        ...

Each suggestion dict must have::

    {
        "label": str,        # short emoji + name for the pill button
        "query": str,        # natural-language query pre-filled into the text area
        "description": str,  # one-line caption shown below the pill grid
    }
"""

from __future__ import annotations

import math

import streamlit as st


def render_query_suggestions(
    suggestions: list[dict],
    text_area_key: str,
    default_index: int = 0,
    placeholder: str = "Or type your own query here…",
    cols: int = 2,
) -> str:
    """Render clickable suggestion pills above a text area.

    Returns the current text-area value (selected suggestion or custom text).

    The function uses two session-state keys:
    - ``text_area_key``           — the text currently in the text area
    - ``text_area_key + "_idx"``  — index of the active suggestion (-1 = custom)
    """
    idx_key = f"{text_area_key}_idx"

    # ── First-run initialisation ──────────────────────────────────────────────
    if idx_key not in st.session_state:
        st.session_state[idx_key] = default_index
        if 0 <= default_index < len(suggestions):
            st.session_state[text_area_key] = suggestions[default_index]["query"]

    active_idx: int = st.session_state[idx_key]

    # ── Section label ─────────────────────────────────────────────────────────
    st.markdown(
        "<p style='font-size:0.78rem;font-weight:600;color:#64748B;"
        "text-transform:uppercase;letter-spacing:0.06em;margin:0.5rem 0 0.4rem;'>"
        "💡 Suggested queries — click to use</p>",
        unsafe_allow_html=True,
    )

    # ── Pill grid ─────────────────────────────────────────────────────────────
    n_rows = math.ceil(len(suggestions) / cols)
    for row in range(n_rows):
        row_cols = st.columns(cols)
        for col_i, col in enumerate(row_cols):
            sug_idx = row * cols + col_i
            if sug_idx >= len(suggestions):
                break
            sug = suggestions[sug_idx]
            is_active = sug_idx == active_idx
            with col:
                btn_label = ("✓ " if is_active else "") + sug["label"]
                if st.button(
                    btn_label,
                    key=f"{text_area_key}_pill_{sug_idx}",
                    type="primary" if is_active else "secondary",
                    use_container_width=True,
                ):
                    st.session_state[idx_key] = sug_idx
                    st.session_state[text_area_key] = sug["query"]
                    st.rerun()

    # ── Description caption for the active suggestion ─────────────────────────
    if 0 <= active_idx < len(suggestions):
        st.caption(f"📌 {suggestions[active_idx]['description']}")

    # ── Divider ───────────────────────────────────────────────────────────────
    st.markdown(
        "<p style='font-size:0.78rem;font-weight:600;color:#64748B;"
        "text-transform:uppercase;letter-spacing:0.06em;margin:0.75rem 0 0.35rem;'>"
        "✏️ Or enter a custom query</p>",
        unsafe_allow_html=True,
    )

    # ── Text area ─────────────────────────────────────────────────────────────
    query: str = st.text_area(
        "Query",
        key=text_area_key,
        height=90,
        placeholder=placeholder,
        label_visibility="collapsed",
    )

    # If the user edited the text away from the active suggestion, mark as custom
    if active_idx >= 0 and query != suggestions[active_idx]["query"]:
        st.session_state[idx_key] = -1

    return query
