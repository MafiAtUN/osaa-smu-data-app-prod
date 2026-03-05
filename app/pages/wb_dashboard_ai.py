"""World Bank data dashboard page (AI-powered query)."""

import plotly.express as px
import streamlit as st
import wbgapi as wb

from app.components.analysis import render_analysis_tabs
from app.components.query_suggestions import render_query_suggestions
from app.components.styles import page_header, section_divider
from app.components.tables import show_pygwalker
from app.services.geo_service import get_iso_reference_df
from app.services.wb_service import (
    WB_QUERY_SUGGESTIONS,
    enrich_wb_dataframe,
    fetch_wb_data_ai,
    generate_wb_suggestions,
    get_countries,
    get_databases,
    get_wb_data,
    parse_wb_query_with_llm,
    set_database,
)

iso3_df = get_iso_reference_df()
chat_session_id = "wb-dashboard-ai-chat-id"

if "wb_query_history" not in st.session_state:
    st.session_state["wb_query_history"] = []

page_header(
    "🌐",
    "World Bank Dashboard",
    "Explore World Bank development indicators using AI-powered natural language queries or manual filters.",
    badge="AI",
)

tab_ai, tab_manual = st.tabs(["🤖 AI-Powered Query", "⚙️ Manual Selection"])

# ---- AI Tab ----
with tab_ai:
    st.markdown(
        "**Describe the World Bank data you need in plain English.** "
        "The AI will identify the right indicators, countries, and time range automatically."
    )

    ai_query = render_query_suggestions(
        WB_QUERY_SUGGESTIONS,
        text_area_key="wb_ai_query_input",
        default_index=0,
        placeholder="e.g., GDP per capita for African countries from 2010 to 2023",
    )

    if st.button("🔍 Fetch Data", type="primary", use_container_width=True) and ai_query:
        with st.spinner("Analyzing your query..."):
            parsed = parse_wb_query_with_llm(ai_query)

        if parsed:
            with st.expander("📋 Extracted Parameters", expanded=True):
                st.write(f"**Explanation:** {parsed.get('explanation', 'N/A')}")
                st.write("**Indicators:**", parsed.get("indicators") or "From search terms")
                if parsed.get("search_terms"):
                    st.write("**Search terms:**", parsed.get("search_terms"))
                st.write(
                    "**Countries:**",
                    f"{len(parsed.get('country_codes', []))} resolved" if parsed.get("country_codes") else "All countries",
                )
                st.write(
                    "**Regions:**",
                    f"{len(parsed.get('region_codes', []))} countries from regions" if parsed.get("region_codes") else "None",
                )
                st.write("**Years:**", parsed.get("from_year", "—"), "to", parsed.get("to_year", "—"))

            with st.spinner("Fetching World Bank data..."):
                df, err = fetch_wb_data_ai(parsed)

            if err:
                st.error(err)
                st.session_state["wb_query_history"].append((ai_query, parsed.get("explanation", ""), False))
            elif df is not None and not df.empty:
                st.success(f"Retrieved {len(df):,} records.")
                st.session_state["wb_df"] = df
                st.session_state["wb_query_history"].append((ai_query, parsed.get("explanation", ""), True))
                st.rerun()
            else:
                st.warning("No data returned for the selected parameters.")
                st.session_state["wb_query_history"].append((ai_query, parsed.get("explanation", ""), False))
        else:
            st.warning("Could not extract parameters from your query. Please try rephrasing.")

# ---- Manual Tab ----
with tab_manual:
    st.markdown("**Select a database, indicators, countries, and time range manually.**")

    # Database selection
    databases = get_databases()
    if isinstance(databases, Exception):
        st.error(f"Error loading databases: {databases}")
    else:
        db_names = [d[1] for d in databases]
        default_idx = next((i for i, n in enumerate(db_names) if "World Development Indicator" in n), 0)
        selected_db_name = st.selectbox(
            "Database:",
            db_names,
            index=default_idx,
            label_visibility="collapsed",
            key="m_wb_db",
        )
        selected_db_id = next(d[0] for d in databases if d[1] == selected_db_name)
        if selected_db_id:
            set_database(selected_db_id)

    # Indicators
    indicators = list(wb.series.list())
    fmt = [f"{ind['id']} - {ind['value']}" for ind in indicators]
    selected_names = st.multiselect(
        "Indicators:",
        fmt,
        label_visibility="collapsed",
        placeholder="Select indicator(s)",
        key="m_wb_indicators",
    )
    selected_indicator_codes = [s.split(" - ")[0] for s in selected_names]

    # Countries with region filter
    countries = get_countries()
    if isinstance(countries, Exception):
        st.error(f"Error loading countries: {countries}")
    else:
        regions = iso3_df["Region Name"].dropna().unique()
        sel_regions = st.multiselect(
            "Regions:",
            ["SELECT ALL"] + list(regions),
            label_visibility="collapsed",
            placeholder="Filter by region (optional)",
            key="m_wb_regions",
        )
        if "SELECT ALL" in sel_regions:
            sel_regions = list(regions)
        else:
            sel_regions = [r for r in sel_regions if r != "SELECT ALL"]

        sel_countries: list[str] = []
        for r in sel_regions:
            sel_countries.extend(iso3_df.loc[iso3_df["Region Name"] == r, "iso3"].tolist())
        sel_countries = list(set(sel_countries))

        iso3_to_name = dict(zip(iso3_df["iso3"], iso3_df["Country or Area"]))
        defaults = [f"{c} - {iso3_to_name[c]}" for c in sel_countries if c in iso3_to_name]
        available = [f"{row.iso3} - {row['Country or Area']}" for _, row in iso3_df.iterrows()]
        final = st.multiselect(
            "Countries:",
            available,
            default=defaults,
            label_visibility="collapsed",
            placeholder="Select by country",
            key="m_wb_countries",
        )
        selected_iso3 = [e.split(" - ")[0] for e in final]

    selected_years = st.slider(
        "Years:",
        1960, 2025, (2000, 2025),
        label_visibility="collapsed",
        key="m_wb_years",
    )

    if st.button("Get Data", type="primary", use_container_width=True, key="manual_wb_fetch"):
        try:
            raw = get_wb_data(
                selected_indicator_codes,
                selected_iso3,
                list(range(selected_years[0], selected_years[1])),
            )
            if raw is not None and not raw.empty:
                df_manual = enrich_wb_dataframe(raw, selected_indicator_codes, selected_iso3, indicators)
                st.success(f"Retrieved {len(df_manual):,} records.")
                st.session_state["wb_df"] = df_manual
                st.rerun()
            else:
                st.warning("No data returned.")
        except Exception as exc:
            st.error(
                f"No data retrieved — ensure indicator, country, and time range are not blank.\n\nError: {exc}"
            )

# ---- Results ----
df = st.session_state.get("wb_df")

if df is not None and not df.empty:
    section_divider("Dataset")
    st.dataframe(df, use_container_width=True)

    section_divider("Time Series Chart")
    try:
        fig = px.line(
            df,
            x="Year",
            y="Value",
            color="Country or Area",
            symbol="Indicator",
            markers=True,
            title="Time Series by Country and Indicator",
        )
        fig.update_layout(
            plot_bgcolor="#FFFFFF",
            paper_bgcolor="#FFFFFF",
            font={"color": "#0F172A"},
        )
        st.plotly_chart(fig, use_container_width=True)
    except Exception as exc:
        st.error(f"Error generating chart: {exc}")

    section_divider("AI Analysis & Visualizations")
    cache_key = hash(str(df.shape) + str(df.columns.tolist()))
    if "wb_suggestions" not in st.session_state or st.session_state.get("wb_df_hash") != cache_key:
        with st.spinner("Generating suggestions..."):
            qs, vs = generate_wb_suggestions(df)
            st.session_state["wb_suggestions"] = (qs, vs)
            st.session_state["wb_df_hash"] = cache_key
    else:
        qs, vs = st.session_state["wb_suggestions"]

    render_analysis_tabs(
        df,
        chat_session_id,
        page="wb",
        dataset_name="World Bank Indicators",
        suggestions=qs + vs,
    )

    section_divider("PyGWalker Explorer")
    show_pygwalker(df)

elif df is not None and df.empty:
    st.info("No data returned for the selected filters.")
