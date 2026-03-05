"""Chat History Library — browse, filter, and review past AI analysis conversations."""

from __future__ import annotations

import json

import streamlit as st

from app.components.styles import page_header, section_divider
from app.services.chat_history_service import (
    clear_all_sessions,
    delete_session,
    get_all_tags,
    get_all_topics,
    get_messages,
    get_session_count,
    get_sessions,
)

page_header(
    "💬",
    "Chat Library",
    "Browse, search, and revisit all past AI analysis conversations.",
    badge="Library",
)

# ---------------------------------------------------------------------------
# Sidebar — filters
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("### Filter Conversations")
    st.divider()

    _PAGE_MAP = {
        "All sources": None,
        "ACLED": "acled",
        "World Bank": "wb",
        "SDG": "sdg",
        "Data Dashboard": "generic",
    }
    sel_page_label = st.selectbox("Data source", list(_PAGE_MAP.keys()), key="lib_page")
    sel_page = _PAGE_MAP[sel_page_label]

    topics = ["All topics"] + get_all_topics()
    sel_topic_label = st.selectbox("Topic", topics, key="lib_topic")
    sel_topic = None if sel_topic_label == "All topics" else sel_topic_label

    all_tags = get_all_tags()
    sel_tags: list[str] = st.multiselect("Tags", all_tags, key="lib_tags")

    st.markdown("**Date range**")
    col1, col2 = st.columns(2)
    date_from = col1.date_input("From", value=None, key="lib_from", label_visibility="collapsed")
    col1.caption("From")
    date_to = col2.date_input("To", value=None, key="lib_to", label_visibility="collapsed")
    col2.caption("To")

    search_q = st.text_input(
        "Search",
        key="lib_search",
        placeholder="Search by name or dataset…",
        label_visibility="collapsed",
    )
    st.caption("Search by name / dataset")

    st.divider()
    if st.button("Reset Filters", use_container_width=True):
        for k in ["lib_page", "lib_topic", "lib_tags", "lib_from", "lib_to", "lib_search"]:
            if k in st.session_state:
                del st.session_state[k]
        st.rerun()

    total = get_session_count()
    st.caption(f"{total} total conversation(s) stored")

# ---------------------------------------------------------------------------
# Fetch matching sessions
# ---------------------------------------------------------------------------

sessions_df = get_sessions(
    page=sel_page,
    topic=sel_topic,
    tags=sel_tags or None,
    date_from=str(date_from) if date_from else None,
    date_to=str(date_to) if date_to else None,
    search=search_q or None,
)

# ---------------------------------------------------------------------------
# Main area — session list
# ---------------------------------------------------------------------------

section_divider("Conversations")

if sessions_df.empty:
    st.info(
        "No conversations match the current filters. "
        "Start an analysis in any dashboard to create your first entry.",
        icon="💬",
    )
else:
    st.caption(f"Showing **{len(sessions_df)}** conversation(s)")

    # Bulk-delete toggle (shown only when there are results)
    with st.expander("⚠️ Danger zone", expanded=False):
        st.warning("Permanently delete **all** conversations. This cannot be undone.")
        if st.button("Delete all conversations", type="secondary", key="lib_clear_all"):
            clear_all_sessions()
            st.success("All conversations deleted.")
            st.rerun()

    st.divider()

    _SOURCE_LABELS = {"acled": "ACLED", "wb": "World Bank", "sdg": "SDG", "generic": "Dashboard"}

    for _, row in sessions_df.iterrows():
        tags: list[str] = []
        try:
            tags = json.loads(row.get("tags") or "[]")
        except Exception:
            pass

        source_label = _SOURCE_LABELS.get(row.get("page", ""), (row.get("page") or "?").upper())
        updated_str = str(row.get("updated_at", ""))[:16]
        msg_count = int(row.get("message_count", 0))
        topic = row.get("topic") or "—"

        tag_chips = "  ".join([f"`{t}`" for t in tags]) if tags else ""
        expander_label = (
            f"**{row['name']}**  ·  {source_label}  ·  {topic}  ·  "
            f"{msg_count} msg{'s' if msg_count != 1 else ''}  ·  {updated_str}"
        )

        with st.expander(expander_label, expanded=False):
            meta_col1, meta_col2, meta_col3 = st.columns([2, 2, 2])
            with meta_col1:
                st.markdown(f"**Dataset:** {row.get('dataset_name') or '—'}")
            with meta_col2:
                st.markdown(f"**Topic:** {topic}")
            with meta_col3:
                st.markdown(f"**Tags:** {tag_chips or '—'}")

            st.divider()

            msgs_df = get_messages(str(row["id"]))
            if msgs_df.empty:
                st.caption("No messages recorded.")
            else:
                for _, msg in msgs_df.iterrows():
                    role = str(msg["role"])
                    content = str(msg["content"])
                    with st.chat_message(role if role in ("human", "assistant") else "assistant"):
                        # Truncate very long messages in the library view
                        if len(content) > 2000:
                            st.markdown(content[:2000] + "\n\n*…[truncated — full text in original session]*")
                        else:
                            st.markdown(content)

            st.divider()
            if st.button(
                "🗑 Delete this conversation",
                key=f"del_{row['id']}",
                type="secondary",
                use_container_width=False,
            ):
                delete_session(str(row["id"]))
                st.success("Conversation deleted.")
                st.rerun()
