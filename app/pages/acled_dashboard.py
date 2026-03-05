"""ACLED data dashboard page (manual selection)."""

import streamlit as st

from app.components.analysis import render_analysis_tabs
from app.components.styles import page_header, section_divider
from app.services.acled_service import (
    fetch_acled_data,
    get_access_token,
    get_acled_credentials,
)
from app.services.geo_service import (
    ACLED_REGION_MAPPING,
    ACLED_SUB_EVENT_TYPES,
    get_iso_reference_df,
)

chat_session_id = "acled-dashboard-chat-id"
iso3_df = get_iso_reference_df()

page_header(
    "⚔️",
    "ACLED Dashboard",
    "Select event types, countries, and a date range — then fetch records from the ACLED API.",
)

# --- Event types ---
section_divider("Event Types")
selected_sub_events = st.multiselect(
    "Event types",
    ACLED_SUB_EVENT_TYPES,
    None,
    placeholder="Select event type(s)",
    label_visibility="collapsed",
)

# --- Regions / Countries ---
section_divider("Countries")
st.caption(
    "⚠️ If you select both a region AND countries, the countries must be IN "
    "that region. The API uses AND logic."
)
selected_regions = st.multiselect(
    "Regions",
    ACLED_REGION_MAPPING.keys(),
    None,
    placeholder="Filter by region (optional)",
    label_visibility="collapsed",
)
country_map = dict(zip(iso3_df["Country or Area"], iso3_df["m49"]))
selected_countries = st.multiselect(
    "Countries",
    iso3_df["Country or Area"],
    None,
    placeholder="Select by country",
    label_visibility="collapsed",
)

# --- Date range ---
section_divider("Date Range")
col1, col2 = st.columns(2)
with col1:
    from_date = st.date_input("From Date", value=None)
with col2:
    to_date = st.date_input("To Date", value=None)
if from_date and to_date and to_date < from_date:
    st.error("To Date must be on or after From Date.")

# --- Row limit ---
section_divider("Row Limit")
num_rows = st.number_input("Max rows:", min_value=0, value=5000, step=1, label_visibility="collapsed")

if st.button("Get Data", type="primary", use_container_width=True):
    email, key = get_acled_credentials()
    if not email or not key:
        st.error("ACLED credentials not configured.")
    else:
        token = get_access_token(email, key)
        if token:
            params = {"_format": "json"}
            if selected_countries:
                params["country"] = "|".join(selected_countries)
            if selected_regions:
                codes = [str(ACLED_REGION_MAPPING[r]) for r in selected_regions if r in ACLED_REGION_MAPPING]
                if codes:
                    params["region"] = "|".join(codes) if len(codes) > 1 else codes[0]
            if selected_sub_events:
                params["sub_event_type"] = "|".join(selected_sub_events)
            if from_date and to_date and to_date >= from_date:
                params["event_date"] = from_date.strftime("%Y-%m-%d")
                params["event_date_where"] = ">="
                params["event_date_end"] = to_date.strftime("%Y-%m-%d")
            elif from_date:
                params["event_date"] = from_date.strftime("%Y-%m-%d")
                params["event_date_where"] = ">="
            elif to_date:
                params["event_date"] = to_date.strftime("%Y-%m-%d")
                params["event_date_where"] = "<="
            if num_rows > 0:
                params["limit"] = num_rows

            result_df = fetch_acled_data(params, token)
            if result_df is not None and not result_df.empty:
                st.success(f"Retrieved {len(result_df):,} records.")
                st.session_state["acled_df"] = result_df
            else:
                st.warning("No data returned for the selected filters.")
                st.session_state["acled_df"] = None
        else:
            st.error("Failed to authenticate with ACLED API.")
    st.rerun()

df = st.session_state.get("acled_df")

if df is not None and not df.empty:
    section_divider("Dataset")
    st.dataframe(df, use_container_width=True)

    section_divider("AI Analysis & Visualizations")
    render_analysis_tabs(df, chat_session_id, page="acled", dataset_name="ACLED Conflict Events")
