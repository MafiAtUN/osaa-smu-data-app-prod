"""UN Data Explorer — 658 UN SDG indicators via the UNDATA NSI SDMX API.

Provides two query modes:
  🤖 AI Query     — describe what you need in plain English; the LLM picks the
                    indicator, geography, and time range automatically.
  ⚙️ Manual       — browse categories, select an indicator, choose countries and
                    a year range, then click Get Data.

Both modes share the same results section (dataset table → data availability
heatmap → AI analysis & chat → PyGWalker explorer).
"""

import streamlit as st

from app.components.analysis import render_analysis_tabs
from app.components.charts import show_data_availability_heatmap
from app.components.query_suggestions import render_query_suggestions
from app.components.styles import page_header, section_divider
from app.components.tables import show_pygwalker
from app.services.geo_service import get_iso_reference_df
from app.services.undata_service import (
    UNDATA_QUERY_SUGGESTIONS,
    fetch_geography_codelist,
    fetch_undata,
    generate_undata_suggestions,
    get_african_geo_codes,
    get_categories,
    get_display_columns,
    get_indicators_for_category,
    parse_undata_query_with_llm,
)

chat_session_id = "un-data-explorer-chat-id"

page_header(
    "🌐",
    "UN Data Explorer",
    "658 UN SDG indicators across 43 thematic categories — AI-powered or manual exploration.",
    badge="AI",
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
        "**Describe the data you need in plain English.** "
        "The AI will select the right indicator, geography, and time range automatically."
    )

    ai_query = render_query_suggestions(
        UNDATA_QUERY_SUGGESTIONS,
        text_area_key="undata_ai_query",
        default_index=0,
        placeholder="e.g., child mortality rates across Africa from 2015 to 2023",
    )

    if st.button("🔍 Fetch Data", type="primary", use_container_width=True, key="undata_ai_fetch") and ai_query:
        with st.spinner("Analysing your query…"):
            parsed = parse_undata_query_with_llm(ai_query)

        if parsed:
            with st.expander("📋 Extracted Parameters", expanded=True):
                st.write(f"**Indicator:** `{parsed['series_id']}` — {parsed['series_name']}")
                geo_label = (
                    "All Africa" if parsed["africa_only"]
                    else (", ".join(parsed["country_names"]) or "All countries")
                )
                st.write(f"**Geography:** {geo_label}")
                st.write(f"**Years:** {parsed['start_year']} – {parsed['end_year']}")
                st.write(f"**Explanation:** {parsed['explanation']}")

            with st.spinner("Loading geography…"):
                if parsed["africa_only"]:
                    geo_map = get_african_geo_codes(parsed["series_id"])
                else:
                    full_codelist = fetch_geography_codelist(parsed["series_id"])
                    if parsed["country_names"]:
                        from app.services.geo_service import fuzzy_match_country
                        name_to_code = {v.lower(): k for k, v in full_codelist.items()}
                        matched: dict[str, str] = {}
                        for cname in parsed["country_names"]:
                            code = name_to_code.get(cname.lower())
                            if not code:
                                fm = fuzzy_match_country(cname, list(full_codelist.values()))
                                if fm:
                                    code = name_to_code.get(fm.lower())
                            if code:
                                matched[code] = full_codelist[code]
                        geo_map = matched if matched else full_codelist
                    else:
                        geo_map = full_codelist

            if not geo_map:
                st.warning("Could not resolve geography for this indicator. Fetching all available data.")

            with st.spinner(
                f"Fetching `{parsed['series_id']}` data "
                f"({parsed['start_year']}–{parsed['end_year']})…"
            ):
                df = fetch_undata(
                    parsed["series_id"],
                    tuple(geo_map.keys()) if geo_map else (),
                    parsed["start_year"],
                    parsed["end_year"],
                )

            if df is not None and not df.empty:
                st.success(f"Retrieved {len(df):,} records.")
                st.session_state["undata_df"] = df
                st.session_state["undata_series_id"] = parsed["series_id"]
                st.session_state["undata_indicator_name"] = parsed["series_name"]
                st.rerun()
            else:
                st.info(
                    "No data returned for the selected parameters. "
                    "Try a broader year range or a different indicator."
                )

# ============================================================
# Manual Selection Tab
# ============================================================
with tab_manual:
    st.markdown("**Browse categories, select an indicator, choose countries, and set a year range.**")

    categories = get_categories()
    if not categories:
        st.error("Could not load the UN Data catalogue. Check that `content/un_sdg_catalogue.json` exists.")
        st.stop()

    section_divider("Theme")
    category_options = [f"{label} ({count} indicators)" for _, label, count in categories]
    selected_category_option = st.selectbox(
        "Select a theme:",
        category_options,
        label_visibility="collapsed",
        key="undata_category",
    )
    selected_category_label = selected_category_option.split(" (")[0]

    section_divider("Indicator")
    indicators = get_indicators_for_category(selected_category_label)
    indicator_options = [f"{e['id']} — {e['name']}" for e in indicators]
    selected_indicator_option = st.selectbox(
        "Select an indicator:",
        indicator_options,
        label_visibility="collapsed",
        key="undata_indicator",
    )
    selected_series_id = selected_indicator_option.split(" — ")[0].strip()
    selected_entry = next((e for e in indicators if e["id"] == selected_series_id), None)

    if selected_entry and selected_entry.get("stat_url"):
        st.caption(
            f"ID: `{selected_series_id}` · "
            f"[View on UN .Stat portal ↗]({selected_entry['stat_url']})"
        )
    else:
        st.caption(f"ID: `{selected_series_id}`")

    section_divider("Geography")

    with st.spinner("Loading available countries for this indicator…"):
        geo_map_m = fetch_geography_codelist(selected_series_id)  # {g_code: country_name}

    if not geo_map_m:
        st.warning(
            "Could not load geography for this indicator. "
            "The API may be temporarily unavailable. You can still try fetching all data."
        )
        selected_geo_codes: tuple = ()
    else:
        # Cross-reference G-code country names with iso_df to get region info
        iso_df_geo = get_iso_reference_df()
        name_lower_to_region: dict[str, str] = {
            str(row["Country or Area"]).lower(): str(row["Region Name"])
            for _, row in iso_df_geo.iterrows()
            if row["Region Name"] and str(row["Region Name"]) != "nan"
        }
        gcode_to_region: dict[str, str] = {
            g: name_lower_to_region.get(name.lower(), "Other")
            for g, name in geo_map_m.items()
        }
        available_regions = sorted(set(gcode_to_region.values()))

        # Region filter (default: Africa)
        sel_regions = st.multiselect(
            "Regions:",
            ["SELECT ALL"] + available_regions,
            default=["Africa"] if "Africa" in available_regions else available_regions[:1],
            label_visibility="collapsed",
            placeholder="Filter by region (optional)",
            key="undata_geo_regions",
        )
        if "SELECT ALL" in sel_regions:
            effective_regions = available_regions
        else:
            effective_regions = [r for r in sel_regions if r != "SELECT ALL"]

        # Build defaults from selected regions
        g_name_to_code = {v: k for k, v in geo_map_m.items()}
        default_names = sorted(
            geo_map_m[g] for g, r in gcode_to_region.items()
            if r in effective_regions and g in geo_map_m
        )
        all_country_names = sorted(geo_map_m.values())

        selected_country_names = st.multiselect(
            "Countries:",
            all_country_names,
            default=default_names,
            label_visibility="collapsed",
            placeholder="Select countries…",
            key="undata_countries",
        )
        selected_geo_codes = tuple(
            g_name_to_code[n] for n in selected_country_names if n in g_name_to_code
        )
        st.caption(f"{len(selected_geo_codes)} of {len(geo_map_m)} countries selected.")

    section_divider("Time Range")
    selected_years = st.slider(
        "Years:",
        min_value=2000,
        max_value=2025,
        value=(2015, 2025),
        label_visibility="collapsed",
        key="undata_years",
    )

    _, col_btn = st.columns([3, 1])
    with col_btn:
        fetch_clicked = st.button(
            "Get Data", type="primary", use_container_width=True, key="undata_manual_fetch"
        )

    if fetch_clicked:
        if not selected_geo_codes and geo_map_m:
            st.warning("Please select at least one country.")
        else:
            with st.spinner(f"Fetching {selected_series_id} data…"):
                df = fetch_undata(
                    selected_series_id,
                    selected_geo_codes,
                    selected_years[0],
                    selected_years[1],
                )
            if df is not None and not df.empty:
                st.success(f"Retrieved {len(df):,} records.")
                st.session_state["undata_df"] = df
                st.session_state["undata_series_id"] = selected_series_id
                st.session_state["undata_indicator_name"] = (
                    selected_entry["name"] if selected_entry else selected_series_id
                )
                st.rerun()
            else:
                no_data_msg = (
                    "No data returned. Try a broader year range, different countries, or check the "
                    f"[UN .Stat portal]({selected_entry['stat_url']})."
                    if selected_entry and selected_entry.get("stat_url")
                    else "No data returned. Try a broader year range or different countries."
                )
                st.info(no_data_msg)

# ===========================================================================
# Shared Results (below both tabs)
# ===========================================================================
df = st.session_state.get("undata_df")
indicator_name = st.session_state.get("undata_indicator_name", "")

if df is not None and not df.empty:
    display_cols = get_display_columns(df)
    df_display = df[display_cols]

    section_divider("Dataset")
    st.caption(f"{len(df):,} rows · {len(df.columns)} columns · Indicator: {indicator_name}")
    st.dataframe(df_display, use_container_width=True)

    section_divider("Data Availability")
    show_data_availability_heatmap(df_display)

    section_divider("AI Analysis & Visualizations")
    cache_key = hash(str(df.shape) + str(df.columns.tolist()))
    if (
        "undata_suggestions" not in st.session_state
        or st.session_state.get("undata_df_hash") != cache_key
    ):
        with st.spinner("Generating suggestions…"):
            qs, vs = generate_undata_suggestions(df_display, f"UN Data — {indicator_name}")
            st.session_state["undata_suggestions"] = (qs, vs)
            st.session_state["undata_df_hash"] = cache_key
    else:
        qs, vs = st.session_state["undata_suggestions"]

    render_analysis_tabs(
        df_display,
        chat_session_id,
        page="undata",
        dataset_name=f"UN Data — {indicator_name}",
        suggestions=qs + vs,
    )

    section_divider("PyGWalker Explorer")
    show_pygwalker(df_display)
