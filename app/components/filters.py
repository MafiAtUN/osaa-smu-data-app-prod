"""Reusable filter widgets for column selection, date ranges, and regions."""

from __future__ import annotations

import pandas as pd
import streamlit as st


def column_filters(df: pd.DataFrame) -> pd.DataFrame:
    """Render column and value filters inside an expander. Returns filtered copy."""
    st.markdown("#### Filter Uploaded Data")
    st.markdown(
        "Click **Show Filters** below to reveal column and value filters. "
        "Use them to select the subset of data you need."
    )
    with st.expander("Show Filters"):
        st.markdown("##### Column Filters")
        selected_columns = st.multiselect(
            "Select columns to filter:", df.columns.tolist(), df.columns.tolist(),
        )
        filtered = df.copy()

        for col in selected_columns:
            st.markdown(f"##### Filter by {col}")

            if pd.api.types.is_numeric_dtype(df[col]):
                if df[col].isna().all() or df[col].min() == df[col].max():
                    st.markdown(f"Cannot filter *{col}* because it has invalid or constant values.")
                else:
                    if pd.api.types.is_integer_dtype(df[col]):
                        mn, mx = int(df[col].min()), int(df[col].max())
                        rng = st.slider(f"Range for {col} (int):", mn, mx, (mn, mx), step=1)
                    else:
                        mn, mx = float(df[col].min()), float(df[col].max())
                        rng = st.slider(f"Range for {col} (float):", mn, mx, (mn, mx))
                    filtered = filtered[(filtered[col].isna()) | ((filtered[col] >= rng[0]) & (filtered[col] <= rng[1]))]

            elif pd.api.types.is_categorical_dtype(df[col]) or pd.api.types.is_object_dtype(df[col]):
                if df[col].isna().all() or df[col].nunique() == 1:
                    st.markdown(f"Cannot filter *{col}* because it has invalid or constant values.")
                else:
                    unique = df[col].dropna().unique().tolist()
                    selected = st.multiselect(f"Values for {col}:", unique, unique)
                    filtered = filtered[filtered[col].isin(selected)]

            elif pd.api.types.is_datetime64_any_dtype(df[col]):
                if df[col].isna().all() or df[col].min() == df[col].max():
                    st.markdown(f"Cannot filter *{col}* because it has invalid or constant values.")
                else:
                    dates = st.date_input(f"Date range for {col}:", [df[col].min(), df[col].max()])
                    if len(dates) == 2:
                        filtered = filtered[(df[col] >= pd.to_datetime(dates[0])) & (df[col] <= pd.to_datetime(dates[1]))]
            else:
                st.write(f"Unsupported column type for filtering: {df[col].dtype}")

        filtered = filtered[selected_columns]
    return filtered
