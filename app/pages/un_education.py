"""UNESCO UIS Education data page — 333 indicators from data.un.org.

Provides two query modes:
  🤖 AI Query  — describe what you need; the LLM selects indicators, countries,
                 and years automatically.
  ⚙️ Manual    — search and pick UIS series codes, choose a country scope, set a
                 year range, then click Get Data.

Both modes share the same results section.
"""

import streamlit as st

from app.components.analysis import render_analysis_tabs
from app.components.charts import show_data_availability_heatmap
from app.components.query_suggestions import render_query_suggestions
from app.components.styles import page_header, section_divider
from app.components.tables import show_pygwalker
from app.services.geo_service import get_iso_reference_df
from app.services.undata_service import (
    UIS_QUERY_SUGGESTIONS,
    fetch_uis_data,
    generate_undata_suggestions,
    get_uis_series,
    parse_uis_query_with_llm,
)

chat_session_id = "un-education-chat-id"

# Default series to pre-select in manual mode
_DEFAULT_SERIES = {
    "LR_AG15T24",       # Youth literacy rate, 15-24
    "LR_AG15T24_GPI",   # Youth literacy GPI
    "NERA_1",           # Net enrolment rate, primary
    "NERA_2",           # Net enrolment rate, lower secondary
    "CR_L1",            # Completion rate, primary
}

page_header(
    "🎓",
    "UNESCO Education Statistics",
    "333 indicators from the UNESCO Institute for Statistics — AI-powered or manual exploration.",
    badge="AI",
)

# Load the indicator list once (needed by both tabs and AI parser)
with st.spinner("Loading UIS indicator list…"):
    uis_series = get_uis_series()

if not uis_series:
    st.warning(
        "Could not load the UIS indicator list from `data.un.org` "
        "(API temporarily unavailable). "
        "You can still fetch data by entering indicator codes manually in the **Manual** tab."
    )

# ---------------------------------------------------------------------------
# Query mode tabs
# ---------------------------------------------------------------------------
tab_ai, tab_manual = st.tabs(["🤖 AI Query", "⚙️ Manual Selection"])

# ============================================================
# AI Query Tab
# ============================================================
with tab_ai:
    st.markdown(
        "**Describe the education data you need in plain English.** "
        "The AI will select the relevant UIS indicators, countries, and year range automatically."
    )

    ai_query = render_query_suggestions(
        UIS_QUERY_SUGGESTIONS,
        text_area_key="uis_ai_query",
        default_index=0,
        placeholder="e.g., youth literacy rates by gender across Africa 2010–2023",
    )

    if st.button("🔍 Fetch Data", type="primary", use_container_width=True, key="uis_ai_fetch") and ai_query:
        with st.spinner("Analysing your query…"):
            parsed = parse_uis_query_with_llm(ai_query, uis_series)

        if parsed:
            series_labels = [f"`{c}` {uis_series.get(c, '')}" for c in parsed["series_codes"]]
            n_countries = len(parsed["iso3_codes"])
            geo_label = (
                "All Africa (54 countries)" if n_countries >= 50
                else f"{n_countries} countries"
            )

            with st.expander("📋 Extracted Parameters", expanded=True):
                st.write("**Indicators:**", " · ".join(series_labels))
                st.write(f"**Geography:** {geo_label}")
                st.write(f"**Years:** {parsed['start_year']} – {parsed['end_year']}")
                st.write(f"**Explanation:** {parsed['explanation']}")

            with st.spinner(
                f"Fetching {len(parsed['series_codes'])} indicator(s) "
                f"for {n_countries} countries ({parsed['start_year']}–{parsed['end_year']})…"
            ):
                df = fetch_uis_data(
                    parsed["series_codes"],
                    parsed["iso3_codes"],
                    parsed["start_year"],
                    parsed["end_year"],
                )

            if df is not None and not df.empty:
                st.success(f"Retrieved {len(df):,} records.")
                st.session_state["uis_df"] = df
                st.rerun()
            else:
                st.info(
                    "No data returned. The selected indicators may not have coverage "
                    "for the chosen countries and year range. "
                    "Try different indicators or a wider time range."
                )

# ============================================================
# Manual Selection Tab
# ============================================================
with tab_manual:
    st.markdown("**Search and select UIS indicators, choose a country scope, and set a year range.**")

    section_divider("Indicators")
    if uis_series:
        series_options = [
            f"{code}: {name}" for code, name in sorted(uis_series.items(), key=lambda x: x[1])
        ]
        default_options = [
            f"{code}: {uis_series[code]}" for code in _DEFAULT_SERIES if code in uis_series
        ]
        selected_series_options = st.multiselect(
            "Indicators:",
            series_options,
            default=default_options,
            label_visibility="collapsed",
            placeholder="Search and select UIS indicators…",
            key="uis_series",
        )
        selected_series_codes = tuple(opt.split(":")[0].strip() for opt in selected_series_options)
    else:
        st.caption(
            "Indicator list unavailable. Enter series codes manually "
            "(comma-separated, e.g. `LR_AG15T24, NERA_1, CR_L1`)."
        )
        raw_codes = st.text_input(
            "Series codes:",
            value=", ".join(_DEFAULT_SERIES),
            label_visibility="collapsed",
            key="uis_series_manual",
        )
        selected_series_codes = tuple(c.strip() for c in raw_codes.split(",") if c.strip())

    if not selected_series_codes:
        st.info("Select at least one indicator to continue.")
    else:
        section_divider("Countries")
        iso_df = get_iso_reference_df()

        # Region filter → cascading country multiselect (WB-style)
        regions = sorted(iso_df["Region Name"].dropna().unique())
        sel_regions = st.multiselect(
            "Regions:",
            ["SELECT ALL"] + regions,
            default=["Africa"],
            label_visibility="collapsed",
            placeholder="Filter by region (optional)",
            key="uis_regions",
        )
        if "SELECT ALL" in sel_regions:
            effective_regions = regions
        else:
            effective_regions = [r for r in sel_regions if r != "SELECT ALL"]

        # Build defaults from selected regions
        iso3_to_name = dict(zip(iso_df["iso3"].dropna(), iso_df.dropna(subset=["iso3"])["Country or Area"]))
        default_iso3: list[str] = []
        for r in effective_regions:
            default_iso3.extend(iso_df.loc[iso_df["Region Name"] == r, "iso3"].dropna().tolist())
        default_iso3 = list(set(default_iso3))

        available = sorted(
            f"{row['iso3']} — {row['Country or Area']}"
            for _, row in iso_df.dropna(subset=["iso3"]).iterrows()
        )
        defaults = sorted(
            f"{c} — {iso3_to_name[c]}" for c in default_iso3 if c in iso3_to_name
        )

        # Reactive cascade: write new defaults directly into session state BEFORE the widget renders
        if frozenset(st.session_state.get("uis_regions_prev", [])) != frozenset(effective_regions):
            st.session_state["uis_regions_prev"] = list(effective_regions)
            st.session_state["uis_countries"] = defaults

        selected_country_opts = st.multiselect(
            "Countries:",
            available,
            default=defaults,
            label_visibility="collapsed",
            placeholder="Select countries…",
            key="uis_countries",
        )
        selected_iso3 = tuple(opt.split(" — ")[0].strip() for opt in selected_country_opts)
        st.caption(f"{len(selected_iso3)} countries selected.")

        section_divider("Time Range")
        selected_years = st.slider(
            "Years:",
            min_value=2000,
            max_value=2025,
            value=(2010, 2025),
            label_visibility="collapsed",
            key="uis_years",
        )

        _, col_btn = st.columns([3, 1])
        with col_btn:
            fetch_clicked = st.button(
                "Get Data", type="primary", use_container_width=True, key="uis_manual_fetch"
            )

        if fetch_clicked:
            if not selected_iso3:
                st.warning("Please select at least one country.")
            else:
                with st.spinner(
                    f"Fetching {len(selected_series_codes)} indicator(s) "
                    f"for {len(selected_iso3)} countries…"
                ):
                    df = fetch_uis_data(
                        selected_series_codes,
                        selected_iso3,
                        selected_years[0],
                        selected_years[1],
                    )
                if df is not None and not df.empty:
                    st.success(f"Retrieved {len(df):,} records.")
                    st.session_state["uis_df"] = df
                    st.rerun()
                else:
                    st.session_state.pop("uis_df", None)
                    st.info(
                        "No data returned. The selected indicators may not have coverage "
                        "for the chosen countries and year range. "
                        "Try different indicators or a wider time range."
                    )

# ===========================================================================
# Shared Results (below both tabs)
# ===========================================================================
df = st.session_state.get("uis_df")

if df is not None and not df.empty:
    section_divider("Dataset")
    st.caption(f"{len(df):,} rows · {len(df.columns)} columns")
    st.dataframe(df, use_container_width=True)

    section_divider("Data Availability")
    show_data_availability_heatmap(df)

    section_divider("AI Analysis & Visualizations")
    cache_key = hash(str(df.shape) + str(df.columns.tolist()))
    if (
        "uis_suggestions" not in st.session_state
        or st.session_state.get("uis_df_hash") != cache_key
    ):
        with st.spinner("Generating suggestions…"):
            qs, vs = generate_undata_suggestions(df, "UNESCO Education Statistics")
            st.session_state["uis_suggestions"] = (qs, vs)
            st.session_state["uis_df_hash"] = cache_key
    else:
        qs, vs = st.session_state["uis_suggestions"]

    render_analysis_tabs(
        df,
        chat_session_id,
        page="uis",
        dataset_name="UNESCO Education Statistics",
        suggestions=qs + vs,
    )

    section_divider("PyGWalker Explorer")
    show_pygwalker(df)
