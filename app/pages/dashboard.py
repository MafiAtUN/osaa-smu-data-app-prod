"""Data file upload and analysis page.

Lets users upload CSV or Excel files and immediately explore them with
column filters, a PyGWalker interactive spreadsheet, and AI-powered analysis
via ``render_analysis_tabs``.  Calls ``data_service`` only for file persistence;
all analysis is handled by the shared analysis component.
"""

import pandas as pd
import streamlit as st

from app.components.analysis import render_analysis_tabs
from app.components.filters import column_filters
from app.components.styles import page_header, section_divider
from app.components.tables import show_pygwalker

page_header(
    "📊",
    "Data Explorer",
    "Upload a CSV, Excel, or Parquet file — then filter, visualize, and analyze your data with AI.",
)

st.subheader("Upload Dataset")
uploaded = st.file_uploader(
    "Choose a file",
    type=["csv", "xlsx", "parquet"],
    label_visibility="collapsed",
    help="Supported formats: CSV, Excel (.xlsx), Parquet",
)

# Scoped to the specific file so chat history and dataset context reset on new upload.
chat_session_id = (
    f"data-dashboard-{uploaded.name}-{uploaded.size}"
    if uploaded is not None
    else "data-dashboard-default"
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
