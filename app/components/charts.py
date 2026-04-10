"""Reusable chart and map components.

Provides Plotly-based chart and choropleth-map rendering functions used across
multiple dashboard pages.  Charts accept a ``pd.DataFrame`` plus display
parameters and return a Plotly figure or render directly via ``st.plotly_chart``.
Key exports: ``render_choropleth``, ``render_line_chart``, ``render_bar_chart``.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from app.core.logging import get_logger

logger = get_logger(__name__)


def show_time_series(
    df: pd.DataFrame,
    x: str = "Year",
    y: str = "Value",
    color: str = "Country or Area",
    symbol: str | None = "Indicator",
    title: str = "Time Series of Indicators by Country and Indicator",
) -> None:
    """Render an interactive Plotly line chart."""
    try:
        fig = px.line(
            df, x=x, y=y, color=color, symbol=symbol, markers=True, title=title,
        )
        st.plotly_chart(fig, use_container_width=True)
    except Exception as exc:
        logger.exception("Error generating time-series chart")
        st.error("Could not render the chart.")


def show_choropleth(
    df: pd.DataFrame,
    locations: str = "iso3",
    color: str = "Value",
    hover_name: str = "Country or Area",
    title: str = "Map of Indicator Value",
) -> None:
    """Render a Plotly choropleth map."""
    try:
        fig = px.choropleth(
            df,
            locations=locations,
            color=color,
            hover_name=hover_name,
            color_continuous_scale="Viridis",
            projection="natural earth",
            title=title,
        )
        st.plotly_chart(fig)
    except Exception as exc:
        logger.exception("Error generating choropleth map")
        st.error("Could not render the map.")


def show_data_availability_heatmap(df: pd.DataFrame) -> None:
    """Heatmap of data availability by country and year."""
    try:
        if "Country or Area" not in df.columns or "timePeriodStart" not in df.columns:
            st.warning("Required columns (Country or Area, timePeriodStart) not found.")
            return

        avail = df.groupby(["Country or Area", "timePeriodStart"]).size().reset_index(name="count")
        avail["has_data"] = 1
        pivot = avail.pivot(index="Country or Area", columns="timePeriodStart", values="has_data").fillna(0)
        fig = px.imshow(
            pivot, title="Data Availability Heatmap",
            labels={"x": "Year", "y": "Country", "color": "Data Available"},
            color_continuous_scale="Blues", aspect="auto",
        )
        fig.update_layout(height=600)
        st.plotly_chart(fig, use_container_width=True)
    except Exception as exc:
        logger.exception("Error generating availability heatmap")
        st.error("Could not render the heatmap.")
