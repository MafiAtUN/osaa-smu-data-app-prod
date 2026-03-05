"""ACLED data dashboard page (AI-powered query)."""

import streamlit as st

from app.components.analysis import render_analysis_tabs
from app.components.query_suggestions import render_query_suggestions
from app.components.styles import page_header, section_divider
from app.services.acled_service import (
    ACLED_QUERY_SUGGESTIONS,
    build_acled_api_params,
    fetch_acled_data,
    generate_acled_suggestions,
    get_access_token,
    get_acled_credentials,
    parse_acled_query_with_llm,
)
from app.services.geo_service import (
    ACLED_REGION_MAPPING,
    ACLED_SUB_EVENT_TYPES,
    get_iso_reference_df,
)

iso3_df = get_iso_reference_df()
chat_session_id = "acled-dashboard-chat-id"

if "acled_query_history" not in st.session_state:
    st.session_state["acled_query_history"] = []

page_header(
    "⚔️",
    "ACLED Dashboard",
    "Fetch and analyze armed conflict and protest event data using AI-powered queries or manual filters.",
    badge="AI",
)

tab_ai, tab_manual = st.tabs(["🤖 AI-Powered Query", "⚙️ Manual Selection"])

# ---- AI Tab ----
with tab_ai:
    st.markdown(
        "**Describe the conflict data you need in plain English.** "
        "The AI will extract countries, regions, event types, and date ranges automatically."
    )

    ai_query = render_query_suggestions(
        ACLED_QUERY_SUGGESTIONS,
        text_area_key="ai_query_input",
        default_index=0,
        placeholder="e.g., conflict events in Africa from 2023 to 2024",
    )
    if st.button("🔍 Fetch Data", type="primary", use_container_width=True) and ai_query:
        with st.spinner("Analyzing your query..."):
            parsed = parse_acled_query_with_llm(ai_query)
        if parsed:
            with st.expander("📋 Extracted Parameters", expanded=True):
                st.write(f"**Explanation:** {parsed.get('explanation', 'N/A')}")
                st.write("**Countries:**", parsed.get("countries") or "None")
                st.write("**Regions:**", parsed.get("regions") or "None")
                st.write("**Event Types:**", parsed.get("event_types") or "All")
                st.write("**Dates:**", parsed.get("from_date", "—"), "to", parsed.get("to_date", "—"))

            email, key = get_acled_credentials()
            if not email or not key:
                st.error("ACLED credentials not configured.")
            else:
                token = get_access_token(email, key)
                if token:
                    api_params = build_acled_api_params(parsed)
                    result_df = fetch_acled_data(api_params, token)
                    if result_df is not None and not result_df.empty:
                        st.success(f"Retrieved {len(result_df):,} records.")
                        st.session_state["acled_df"] = result_df
                        st.session_state["acled_query_history"].append((ai_query, parsed.get("explanation", ""), True))
                        st.rerun()
                    else:
                        st.warning("No data returned.")
                        st.session_state["acled_query_history"].append((ai_query, parsed.get("explanation", ""), False))

# ---- Manual Tab ----
with tab_manual:
    st.markdown("**Select event types, countries, and a date range manually.**")
    sel_events = st.multiselect(
        "Event types",
        ACLED_SUB_EVENT_TYPES,
        None,
        placeholder="Select event type(s)",
        label_visibility="collapsed",
    )
    sel_regions = st.multiselect(
        "Regions",
        ACLED_REGION_MAPPING.keys(),
        None,
        placeholder="Filter by region (optional)",
        label_visibility="collapsed",
    )
    sel_countries = st.multiselect(
        "Countries",
        iso3_df["Country or Area"],
        None,
        placeholder="Select by country",
        label_visibility="collapsed",
    )
    col1, col2 = st.columns(2)
    with col1:
        m_from = st.date_input("From Date", value=None, key="m_from")
    with col2:
        m_to = st.date_input("To Date", value=None, key="m_to")
    m_rows = st.number_input(
        "Max rows:",
        min_value=0,
        value=5000,
        step=1,
        label_visibility="collapsed",
        key="m_rows",
    )

    if st.button("Get Data", type="primary", use_container_width=True, key="manual_fetch"):
        email, key = get_acled_credentials()
        if email and key:
            token = get_access_token(email, key)
            if token:
                p: dict = {"_format": "json"}
                if sel_countries:
                    p["country"] = "|".join(sel_countries)
                if sel_regions:
                    codes = [str(ACLED_REGION_MAPPING[r]) for r in sel_regions if r in ACLED_REGION_MAPPING]
                    if codes:
                        p["region"] = "|".join(codes)
                if sel_events:
                    p["sub_event_type"] = "|".join(sel_events)
                if m_from and m_to and m_to >= m_from:
                    p["event_date"] = m_from.strftime("%Y-%m-%d")
                    p["event_date_where"] = ">="
                    p["event_date_end"] = m_to.strftime("%Y-%m-%d")
                if m_rows > 0:
                    p["limit"] = m_rows
                result_df = fetch_acled_data(p, token)
                if result_df is not None and not result_df.empty:
                    st.success(f"Retrieved {len(result_df):,} records.")
                    st.session_state["acled_df"] = result_df
                else:
                    st.warning("No data returned.")
        st.rerun()

# ---- Results ----
df = st.session_state.get("acled_df")

if df is not None and not df.empty:
    section_divider("Dataset")
    st.dataframe(df, use_container_width=True)

    section_divider("AI Analysis & Visualizations")
    cache_key = hash(str(df.shape) + str(df.columns.tolist()))
    if "acled_suggestions" not in st.session_state or st.session_state.get("acled_df_hash") != cache_key:
        with st.spinner("Generating suggestions..."):
            qs, vs = generate_acled_suggestions(df)
            st.session_state["acled_suggestions"] = (qs, vs)
            st.session_state["acled_df_hash"] = cache_key
    else:
        qs, vs = st.session_state["acled_suggestions"]

    render_analysis_tabs(
        df,
        chat_session_id,
        page="acled",
        dataset_name="ACLED Conflict Events",
        suggestions=qs + vs,
    )
