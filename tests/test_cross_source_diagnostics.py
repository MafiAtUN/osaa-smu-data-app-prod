"""Tests for cross-source execution diagnostics."""

from __future__ import annotations

import pandas as pd

from app.services.cross_source.execution import _build_data_diagnostics
from app.services.cross_source.planner import MetricPlan, QueryPlan


def test_build_data_diagnostics_flags_sparse_and_overlap():
    plan = QueryPlan(
        country="Algeria",
        country_iso3="DZA",
        from_year=2018,
        to_year=2022,
        metrics=[
            MetricPlan(source="world_bank", series_id="NY.GDP.MKTP.CD", label="GDP"),
            MetricPlan(source="acled", series_id="event_count", label="Conflict events"),
        ],
        explanation="test",
        confidence=0.8,
    )

    frames = {
        "world_bank:NY.GDP.MKTP.CD": pd.DataFrame(
            {"iso3": ["DZA", "DZA"], "year": [2018, 2019], "GDP": [1.0, 2.0]}
        ),
        "acled:event_count": pd.DataFrame(
            {"iso3": ["DZA"], "year": [2022], "Conflict events": [10]}
        ),
    }

    diagnostics, guidance = _build_data_diagnostics(plan, plan.metrics, frames)

    assert len(diagnostics) == 2
    statuses = {d["metric"]: d["status"] for d in diagnostics}
    assert statuses["world_bank:NY.GDP.MKTP.CD"] in {"sparse", "insufficient_points"}
    assert statuses["acled:event_count"] in {"sparse", "insufficient_points"}
    assert any("overlapping year" in g.lower() for g in guidance)
