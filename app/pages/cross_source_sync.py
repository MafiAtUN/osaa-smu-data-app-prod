"""Hybrid sync control center for cross-source cache and metadata refresh.

Provides an admin-style UI for managing the Cross-Source Studio's DuckDB cache:
shows cache statistics (row counts, staleness), triggers on-demand metadata
ingestion for individual or all data sources, and allows clearing stale entries.
Calls ``cross_source.sync`` and ``cross_source.metadata`` directly; no LLM calls
are made on this page.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.components.styles import page_header, section_divider
from app.services.cross_source import (
    default_year_window,
    get_hybrid_sync_dashboard,
    init_storage,
    run_hybrid_sync,
    run_metadata_sync,
)
from app.services.geo_service import get_iso_reference_df

page_header(
    "🗄️",
    "Hybrid Sync",
    "Cache-first data operations: sync metadata fully, fetch data incrementally, and audit updates by source.",
    badge="Admin",
)

init_storage()

section_divider("How It Works")
st.markdown(
    """
1. Metadata can be refreshed per source (full catalogue sync).
2. Data sync fetches only missing/stale ranges by default (`missing_only`), or full refresh when forced.
3. Every run is logged with source, status, timestamp, and update counts.
"""
)

sources = ["world_bank", "acled", "sdg", "uis", "un_data"]
default_from, default_to = default_year_window()

section_divider("Run Sync")
col1, col2 = st.columns(2)
with col1:
    selected_sources = st.multiselect(
        "Sources",
        options=sources,
        default=["world_bank", "acled"],
        help="Choose one or more sources to sync.",
    )
with col2:
    sync_mode = st.selectbox(
        "Sync mode",
        options=["missing_only", "force_refresh"],
        help="`missing_only` reuses cache and fetches gaps only. `force_refresh` refreshes full selected windows.",
    )

col3, col4, col5 = st.columns([1, 1, 1])
with col3:
    from_year = st.number_input("From year", min_value=1960, max_value=2100, value=default_from, step=1)
with col4:
    to_year = st.number_input("To year", min_value=1960, max_value=2100, value=default_to, step=1)
with col5:
    scope_mode = st.selectbox("Scope", options=["all_regions", "country_list"], index=0)

country_names: list[str] = []
if scope_mode == "country_list":
    iso_df = get_iso_reference_df()
    available_countries = sorted(iso_df["Country or Area"].dropna().astype(str).unique().tolist())
    country_names = st.multiselect(
        "Countries",
        options=available_countries,
        default=["Algeria", "Kenya", "Nigeria"],
        help="Used only when Scope is `country_list`.",
    )

custom_text = st.text_area(
    "Custom indicators (optional)",
    height=90,
    placeholder=(
        "One per line, format: source:series_id\n"
        "Example:\n"
        "world_bank:NY.GDP.PCAP.CD\n"
        "acled:event_count"
    ),
)
max_indicators = st.slider("Max indicators per source", min_value=1, max_value=10, value=5)
refresh_meta_first = st.toggle("Refresh metadata before data sync", value=True)

btn_a, btn_b = st.columns(2)
with btn_a:
    run_metadata_only = st.button("Run Metadata Refresh", use_container_width=True)
with btn_b:
    run_hybrid = st.button("Run Hybrid Data Sync", type="primary", use_container_width=True)

if run_metadata_only:
    if not selected_sources:
        st.warning("Select at least one source.")
    else:
        with st.spinner("Refreshing metadata..."):
            counts = run_metadata_sync(selected_sources)
        counts_df = pd.DataFrame(
            [{"source": k, "metadata_rows_written": v} for k, v in counts.items()]
        ).sort_values("source")
        st.success("Metadata refresh complete.")
        st.dataframe(counts_df, use_container_width=True, hide_index=True)

if run_hybrid:
    if not selected_sources:
        st.warning("Select at least one source.")
    elif int(from_year) > int(to_year):
        st.warning("From year must be less than or equal to To year.")
    elif scope_mode == "country_list" and not country_names:
        st.warning("Choose at least one country for country_list scope.")
    else:
        custom_indicators: dict[str, list[str]] = {}
        for raw in custom_text.splitlines():
            line = raw.strip()
            if not line or ":" not in line:
                continue
            src, sid = line.split(":", 1)
            src = src.strip().lower()
            sid = sid.strip()
            if not src or not sid:
                continue
            custom_indicators.setdefault(src, []).append(sid)

        with st.spinner("Running hybrid sync..."):
            try:
                summaries = run_hybrid_sync(
                    sources=selected_sources,
                    from_year=int(from_year),
                    to_year=int(to_year),
                    strategy=sync_mode,
                    scope_mode=scope_mode,
                    countries=country_names,
                    custom_indicators=custom_indicators,
                    refresh_metadata=refresh_meta_first,
                    max_indicators_per_source=int(max_indicators),
                )
                df = pd.DataFrame([s.__dict__ for s in summaries]).sort_values("source")
                st.success("Hybrid sync run complete.")
                st.dataframe(df, use_container_width=True, hide_index=True)
            except Exception as exc:
                st.error("Hybrid sync failed. Please try again later or inspect server logs.")

section_divider("Data Availability")
payload = get_hybrid_sync_dashboard(limit_metrics=300, limit_logs=300)
source_summary = payload["source_summary"]
metric_availability = payload["metric_availability"]
refresh_logs = payload["refresh_logs"]

if source_summary.empty:
    st.info("No cache entries yet. Run a sync to populate availability tables.")
else:
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric("Sources cached", int(source_summary["source"].nunique()))
    with k2:
        st.metric("Indicators cached", int(source_summary["indicator_count"].sum()))
    with k3:
        st.metric("Cache entries", int(source_summary["cache_entries"].sum()))
    with k4:
        st.metric("Cached rows", int(source_summary["cached_rows"].sum()))

    st.caption("Source-level availability")
    st.dataframe(source_summary, use_container_width=True, hide_index=True)

with st.expander("Indicator Availability", expanded=False):
    if metric_availability.empty:
        st.caption("No per-indicator cache availability yet.")
    else:
        st.dataframe(metric_availability, use_container_width=True, hide_index=True)

section_divider("Update Log")
if refresh_logs.empty:
    st.caption("No refresh/sync log entries yet.")
else:
    st.dataframe(refresh_logs, use_container_width=True, hide_index=True)
