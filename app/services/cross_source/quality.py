"""Quality assessment utilities for cross-source scenario outputs.

Inspects a merged output DataFrame from the execution engine and returns a
human-readable quality verdict (status label + explanatory note) indicating
whether the dataset is suitable for analysis.  Key export:
``scenario_quality_score(df) -> tuple[str, str]``.
"""

from __future__ import annotations

import pandas as pd


def scenario_quality_score(df: pd.DataFrame) -> tuple[str, str]:
    """Return (status, note) indicating whether output is strong for analysis."""
    if df is None or df.empty:
        return "fail", "No rows returned."

    numeric_cols = [
        c for c in df.columns
        if c not in ("iso3", "country", "geo_group", "scope", "year")
        and pd.api.types.is_numeric_dtype(df[c])
    ]
    if len(numeric_cols) == 0:
        return "warn", "Rows exist but no numeric metric columns."

    if len(numeric_cols) >= 2 and len(df.dropna(subset=numeric_cols[:2])) >= 8:
        return "pass", "Good overlap for trend + correlation analysis."
    if len(numeric_cols) >= 1 and len(df) >= 8:
        return "pass", "Good trend coverage; correlation may be limited."
    return "warn", "Sparse output; use Revise Query actions."
