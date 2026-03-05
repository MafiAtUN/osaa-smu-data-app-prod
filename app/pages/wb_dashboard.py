"""World Bank data dashboard page."""

import plotly.express as px
import streamlit as st
import wbgapi as wb

from app.components.analysis import render_analysis_tabs
from app.components.styles import page_header, section_divider
from app.components.tables import show_pygwalker
from app.services.geo_service import get_iso_reference_df
from app.services.wb_service import (
    enrich_wb_dataframe,
    get_countries,
    get_databases,
    get_wb_data,
    set_database,
)

chat_session_id = "wb-dashboard-chat-id"

page_header(
    "🌐",
    "World Bank Dashboard",
    "Select a database, indicators, countries, and time range — then click Get Data to load and analyze.",
)

iso3_df = get_iso_reference_df()

# --- Database selection ---
section_divider("Database")
databases = get_databases()
if isinstance(databases, Exception):
    st.error(f"Error loading databases: {databases}")
else:
    db_names = [d[1] for d in databases]
    default_idx = next((i for i, n in enumerate(db_names) if "World Development Indicator" in n), 0)
    selected_db_name = st.selectbox("Databases:", db_names, index=default_idx, label_visibility="collapsed")
    selected_db_id = next(d[0] for d in databases if d[1] == selected_db_name)
    if selected_db_id:
        set_database(selected_db_id)

# --- Indicators ---
section_divider("Indicators")
indicators = list(wb.series.list())
fmt = [f"{ind['id']} - {ind['value']}" for ind in indicators]
selected_names = st.multiselect("Indicators:", fmt, label_visibility="collapsed", placeholder="Select indicator(s)")
selected_indicators = [s.split(" - ")[0] for s in selected_names]

# --- Countries (region + individual) ---
section_divider("Countries")
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
    defaults = [f"{c} - {iso3_to_name[c]}" for c in sel_countries]
    available = [f"{row.iso3} - {row['Country or Area']}" for _, row in iso3_df.iterrows()]
    final = st.multiselect(
        "Countries:",
        available,
        default=defaults,
        label_visibility="collapsed",
        placeholder="Select by country",
    )
    selected_iso3 = [e.split(" - ")[0] for e in final]

# --- Year range ---
section_divider("Time Range")
selected_years = st.slider("Years:", 1960, 2025, (1960, 2025), label_visibility="collapsed")

# --- Fetch ---
df = None
try:
    if st.button("Get Data", type="primary", use_container_width=True):
        raw = get_wb_data(selected_indicators, selected_iso3, list(range(selected_years[0], selected_years[1])))
        df = enrich_wb_dataframe(raw, selected_indicators, selected_iso3, indicators)
except Exception as exc:
    st.error(
        f"No data retrieved — ensure indicator, country, and time range are not blank.\n\nError: {exc}"
    )

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
    render_analysis_tabs(df, chat_session_id, page="wb", dataset_name="World Bank Indicators")

    section_divider("PyGWalker Explorer")
    show_pygwalker(df)

elif df is not None and df.empty:
    st.info("No data returned for the selected filters.")
