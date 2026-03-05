"""SDG data dashboard page (manual selection)."""

import json

import pandas as pd
import streamlit as st

from app.components.analysis import render_analysis_tabs
from app.components.charts import show_data_availability_heatmap
from app.components.styles import page_header, section_divider
from app.components.tables import show_pygwalker
from app.services.geo_service import get_iso_reference_df
from app.services.sdg_service import enrich_sdg_dataframe, get_data, get_sdg_base_url

chat_session_id = "sdg-dashboard-chat-id"
BASE_URL = get_sdg_base_url()
iso3_df = get_iso_reference_df()

page_header(
    "🎯",
    "UN SDG Dashboard",
    "Explore the 17 Sustainable Development Goals — select indicators, countries, and a time range.",
)

# --- Goals ---
section_divider("Sustainable Development Goal")
goals_data = get_data(f"{BASE_URL}/v1/sdg/Goal/List?includechildren=false")
indicator_data = None
if not isinstance(goals_data, Exception):
    goal_title = st.selectbox(
        "Goals:",
        [f"{g['code']}. {g['title']}" for g in goals_data],
        label_visibility="collapsed",
    )
    goal_code = next(g["code"] for g in goals_data if f"{g['code']}. {g['title']}" == goal_title)
    goal_obj = next(g for g in goals_data if g["code"] == goal_code)
    st.caption(goal_obj["description"])
    indicator_data = get_data(f"{BASE_URL}/v1/sdg/Indicator/List")
else:
    st.error(f"Error loading goals: {goals_data}")

# --- Indicators ---
section_divider("Indicators")
selected_indicator_codes: list[str] = []
if indicator_data and not isinstance(indicator_data, Exception):
    filtered = [i for i in indicator_data if i.get("goal") == goal_code]
    options = [f"{i['code']}: {i['description']}" for i in filtered]
    sel = st.multiselect(
        "Indicators:",
        options,
        label_visibility="collapsed",
        placeholder="Select indicators...",
    )
    selected_indicator_codes = [s.split(":")[0] for s in sel]

# --- Countries ---
section_divider("Countries")
regions = iso3_df["Region Name"].dropna().unique()
sel_regions = st.multiselect(
    "Regions:",
    ["SELECT ALL"] + list(regions),
    label_visibility="collapsed",
    placeholder="Filter by region (optional)",
)
if "SELECT ALL" in sel_regions:
    sel_regions = list(regions)
sel_codes: list[str] = []
for r in sel_regions:
    sel_codes.extend(iso3_df.loc[iso3_df["Region Name"] == r, "m49"].tolist())
sel_codes = list(set(sel_codes))
m49_to_name = dict(zip(iso3_df["m49"], iso3_df["Country or Area"]))
defaults = [f"{c} - {m49_to_name[c]}" for c in sel_codes]
available = [f"{row.m49} - {row['Country or Area']}" for _, row in iso3_df.iterrows()]
final = st.multiselect(
    "Countries:",
    available,
    default=defaults,
    label_visibility="collapsed",
    placeholder="Select by country",
)
selected_country_codes = [e.split(" - ")[0] for e in final]

# --- Year range ---
section_divider("Time Range")
selected_years = st.slider("Years:", 1963, 2025, (1963, 2025), label_visibility="collapsed")

# --- Pagination ---
col1, col2 = st.columns(2)
with col1:
    max_pages = st.number_input(
        "Max pages (1 000 rows each):",
        min_value=1,
        value=None,
        placeholder="Defaults to 100",
        label_visibility="collapsed",
    )
    if max_pages is None:
        max_pages = 100

# --- Fetch ---
with col2:
    if st.button("Get Data", type="primary", use_container_width=True):
        ind_params = "indicator=" + "&indicator=".join(selected_indicator_codes)
        area_params = "&areaCode=" + "&areaCode=".join(selected_country_codes)
        year_params = "&timePeriod=" + "&timePeriod=".join(str(y) for y in range(selected_years[0], selected_years[1] + 1))
        page_size = 1000
        data_url = f"{BASE_URL}/v1/sdg/Indicator/Data?{ind_params}{area_params}{year_params}&pageSize={page_size}"

        rows: list[dict] = []
        for page in range(1, max_pages + 1):
            result = get_data(f"{data_url}&page={page}")
            if isinstance(result, Exception):
                st.error(f"Error: {result}")
                break
            page_data = result.get("data", [])
            if not page_data:
                break
            for entry in page_data:
                row: dict = {}
                ind = entry.get("indicator")
                row["Indicator"] = ind[0] if isinstance(ind, list) and ind else (ind or "")
                for k, v in entry.items():
                    if k == "indicator":
                        continue
                    if k in ("dimensions", "attributes") and isinstance(v, (str, dict)):
                        d = json.loads(v) if isinstance(v, str) else v
                        if isinstance(d, dict):
                            prefix = "dimension_" if k == "dimensions" else "attribute_"
                            for dk, dv in d.items():
                                row[f"{prefix}{dk}"] = dv
                            continue
                    row[k] = v
                rows.append(row)
            if len(page_data) < page_size:
                break

        df = pd.DataFrame(rows)
        if not df.empty:
            df = enrich_sdg_dataframe(df)
            st.session_state.sdg_data = df

df = st.session_state.get("sdg_data")

if df is not None and not df.empty:
    section_divider("Dataset")
    st.dataframe(df, use_container_width=True)

    section_divider("Data Availability")
    show_data_availability_heatmap(df)

    section_divider("AI Analysis & Visualizations")
    render_analysis_tabs(df, chat_session_id, page="sdg", dataset_name="SDG Indicators")

    section_divider("PyGWalker Explorer")
    show_pygwalker(df)

elif df is not None and df.empty:
    st.info("No data returned for the selected filters.")
