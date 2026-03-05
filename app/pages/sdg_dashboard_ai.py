"""SDG data dashboard page (AI-powered query)."""

import streamlit as st

from app.components.analysis import render_analysis_tabs
from app.components.query_suggestions import render_query_suggestions
from app.components.styles import page_header, section_divider
from app.services.geo_service import get_iso_reference_df
from app.services.sdg_service import (
    SDG_QUERY_SUGGESTIONS,
    enrich_sdg_dataframe,
    fetch_sdg_data,
    generate_sdg_suggestions,
    get_data,
    get_sdg_base_url,
    parse_sdg_query_with_llm,
)

BASE_URL = get_sdg_base_url()
iso3_df = get_iso_reference_df()
chat_session_id = "sdg-dashboard-ai-chat-id"

if "sdg_query_history" not in st.session_state:
    st.session_state["sdg_query_history"] = []

page_header(
    "🎯",
    "UN SDG Dashboard",
    "Explore Sustainable Development Goals data using AI-powered natural language queries or manual filters.",
    badge="AI",
)

goals_data = get_data(f"{BASE_URL}/v1/sdg/Goal/List?includechildren=false")
indicators_data = get_data(f"{BASE_URL}/v1/sdg/Indicator/List")

tab_ai, tab_manual = st.tabs(["🤖 AI-Powered Query", "⚙️ Manual Selection"])

# ---- AI Tab ----
with tab_ai:
    st.markdown(
        "**Describe the data you need in plain English.** "
        "The AI will extract the relevant goals, indicators, countries, and time range automatically."
    )

    ai_query = render_query_suggestions(
        SDG_QUERY_SUGGESTIONS,
        text_area_key="sdg_ai_query_input",
        default_index=0,
        placeholder="e.g., SDG 3 health indicators for Africa 2020–2023",
    )
    if st.button("🔍 Fetch Data", type="primary", use_container_width=True) and ai_query:
        with st.spinner("Analyzing your query..."):
            parsed = parse_sdg_query_with_llm(ai_query, goals_data, indicators_data)
        if parsed:
            with st.expander("📋 Extracted Parameters", expanded=True):
                st.write(f"**Explanation:** {parsed.get('explanation', 'N/A')}")
                st.write("**Goal Codes:**", parsed.get("goal_codes") or "None")
                st.write("**Indicators:**", parsed.get("indicators") or "From goals")
                st.write("**Regions:**", parsed.get("regions") or "None")
                st.write("**Years:**", parsed.get("from_year", "—"), "to", parsed.get("to_year", "—"))

            with st.spinner("Fetching SDG data..."):
                df, err = fetch_sdg_data(parsed, indicators_data)
            if err:
                st.error(err)
                st.session_state["sdg_query_history"].append((ai_query, parsed.get("explanation", ""), False))
            elif df is not None and not df.empty:
                df = enrich_sdg_dataframe(df)
                st.success(f"Retrieved {len(df):,} records.")
                st.session_state["sdg_df"] = df
                st.session_state["sdg_query_history"].append((ai_query, parsed.get("explanation", ""), True))
                st.rerun()
            else:
                st.warning("No data returned.")

# ---- Manual Tab ----
with tab_manual:
    st.markdown("**Select goals, indicators, countries, and a time range manually.**")
    if isinstance(goals_data, Exception):
        st.error(f"Error loading goals: {goals_data}")
    else:
        goal_title = st.selectbox(
            "Goals:",
            [f"{g['code']}. {g['title']}" for g in goals_data],
            label_visibility="collapsed",
        )
        goal_code = next(g["code"] for g in goals_data if f"{g['code']}. {g['title']}" == goal_title)

        sel_ind_codes: list[str] = []
        if indicators_data and not isinstance(indicators_data, Exception):
            filtered = [i for i in indicators_data if i.get("goal") == goal_code]
            opts = [f"{i['code']}: {i['description']}" for i in filtered]
            sel = st.multiselect(
                "Indicators:",
                opts,
                label_visibility="collapsed",
                placeholder="Select indicators...",
            )
            sel_ind_codes = [s.split(":")[0] for s in sel]

        regions = iso3_df["Region Name"].dropna().unique()
        sel_regions = st.multiselect(
            "Regions:",
            ["SELECT ALL"] + list(regions),
            label_visibility="collapsed",
            placeholder="Filter by region (optional)",
            key="m_regions",
        )
        if "SELECT ALL" in sel_regions:
            sel_regions = list(regions)
        codes: list[str] = []
        for r in sel_regions:
            codes.extend(iso3_df.loc[iso3_df["Region Name"] == r, "m49"].tolist())
        codes = list(set(codes))
        m49_to_name = dict(zip(iso3_df["m49"], iso3_df["Country or Area"]))
        defaults = [f"{c} - {m49_to_name[c]}" for c in codes]
        available = [f"{row.m49} - {row['Country or Area']}" for _, row in iso3_df.iterrows()]
        final = st.multiselect(
            "Countries:",
            available,
            default=defaults,
            label_visibility="collapsed",
            placeholder="Select by country",
            key="m_countries",
        )
        sel_cc = [e.split(" - ")[0] for e in final]

        sel_years = st.slider("Years:", 1963, 2025, (1963, 2025), label_visibility="collapsed", key="m_years")

        if st.button("Get Data", type="primary", use_container_width=True, key="manual_sdg_fetch"):
            params = {
                "indicators": sel_ind_codes,
                "goal_codes": [],
                "countries": [],
                "regions": [],
                "from_year": sel_years[0],
                "to_year": sel_years[1],
            }
            # Convert selected M49 codes to country names for the service
            for cc in sel_cc:
                name = m49_to_name.get(cc)
                if name:
                    params["countries"].append(name)

            with st.spinner("Fetching SDG data..."):
                df, err = fetch_sdg_data(params, indicators_data)
            if err:
                st.error(err)
            elif df is not None and not df.empty:
                df = enrich_sdg_dataframe(df)
                st.success(f"Retrieved {len(df):,} records.")
                st.session_state["sdg_df"] = df
                st.rerun()

# ---- Results ----
df = st.session_state.get("sdg_df")

if df is not None and not df.empty:
    section_divider("Dataset")
    st.dataframe(df, use_container_width=True)

    section_divider("AI Analysis & Visualizations")
    cache_key = hash(str(df.shape) + str(df.columns.tolist()))
    if "sdg_suggestions" not in st.session_state or st.session_state.get("sdg_df_hash") != cache_key:
        with st.spinner("Generating suggestions..."):
            qs, vs = generate_sdg_suggestions(df)
            st.session_state["sdg_suggestions"] = (qs, vs)
            st.session_state["sdg_df_hash"] = cache_key
    else:
        qs, vs = st.session_state["sdg_suggestions"]

    render_analysis_tabs(
        df,
        chat_session_id,
        page="sdg",
        dataset_name="SDG Indicators",
        suggestions=qs + vs,
    )
