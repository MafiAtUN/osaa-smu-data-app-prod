"""Data file upload and analysis page."""

import pandas as pd
import streamlit as st

from app.components.analysis import render_analysis_tabs
from app.components.filters import column_filters
from app.components.styles import page_header, section_divider
from app.components.tables import show_pygwalker

chat_session_id = "data-dashboard-chat-id"

page_header(
    "📊",
    "Data Dashboard",
    "Upload a CSV, Excel, or Parquet file — then filter, visualize, and analyze your data with AI.",
)

st.subheader("Upload Dataset")
uploaded = st.file_uploader(
    "Choose a file",
    type=["csv", "xlsx", "parquet"],
    label_visibility="collapsed",
    help="Supported formats: CSV, Excel (.xlsx), Parquet",
)

df = None
if uploaded is not None:
    if uploaded.name.endswith(".csv"):
        df = pd.read_csv(uploaded)
    elif uploaded.name.endswith(".xlsx"):
        df = pd.read_excel(uploaded)
    elif uploaded.name.endswith(".parquet"):
        df = pd.read_parquet(uploaded)

filtered_df = column_filters(df) if df is not None else None

if filtered_df is not None and not filtered_df.empty:
    section_divider("Dataset")
    st.dataframe(filtered_df, use_container_width=True)

    section_divider("AI Analysis & Visualizations")
    render_analysis_tabs(df, chat_session_id, page="generic", dataset_name="Uploaded Dataset")

    section_divider("PyGWalker Explorer")
    show_pygwalker(filtered_df)

elif filtered_df is not None and filtered_df.empty:
    st.info("No data returned for the selected filters.")
