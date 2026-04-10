"""Scenario tests for Cross-Source execution behavior."""

from __future__ import annotations

import pandas as pd

import app.services.cross_source.execution as execution
from app.services.cross_source.planner import MetricPlan, QueryPlan


def _plan(from_year: int, to_year: int) -> QueryPlan:
    return QueryPlan(
        country="Algeria",
        country_iso3="DZA",
        from_year=from_year,
        to_year=to_year,
        metrics=[
            MetricPlan(source="world_bank", series_id="NY.GDP.MKTP.CD", label="GDP"),
            MetricPlan(source="acled", series_id="event_count", label="Conflict events"),
        ],
        explanation="scenario",
        confidence=0.9,
    )


def test_scenario_full_overlap(monkeypatch):
    plan = _plan(2018, 2020)

    def fake_fetch(metric, _plan, force_refresh=False):
        if metric.source == "world_bank":
            return (
                pd.DataFrame({"iso3": ["DZA", "DZA", "DZA"], "year": [2018, 2019, 2020], "GDP": [1.0, 2.0, 3.0]}),
                {"cache_hit_years": 3, "fetched_years": [], "fetched_ranges": []},
            )
        return (
            pd.DataFrame(
                {
                    "iso3": ["DZA", "DZA", "DZA"],
                    "year": [2018, 2019, 2020],
                    "Conflict events": [10.0, 12.0, 9.0],
                }
            ),
            {"cache_hit_years": 1, "fetched_years": [2019, 2020], "fetched_ranges": [(2019, 2020)]},
        )

    monkeypatch.setattr(execution, "fetch_metric_frame", fake_fetch)
    monkeypatch.setattr(execution, "write_materialized_result", lambda **kwargs: "r1")

    result = execution.execute_plan(plan)

    assert not result.merged_df.empty
    assert len(result.merged_df) == 3
    assert "GDP" in result.merged_df.columns
    assert "Conflict events" in result.merged_df.columns
    assert not result.notes


def test_scenario_sparse_and_alternatives(monkeypatch):
    plan = _plan(2018, 2022)

    def fake_fetch(metric, _plan, force_refresh=False):
        if metric.source == "world_bank":
            return (
                pd.DataFrame({"iso3": ["DZA"], "year": [2018], "GDP": [1.0]}),
                {"cache_hit_years": 0, "fetched_years": [2018], "fetched_ranges": [(2018, 2018)]},
            )
        return (
            pd.DataFrame({"iso3": ["DZA"], "year": [2022], "Conflict events": [7.0]}),
            {"cache_hit_years": 0, "fetched_years": [2022], "fetched_ranges": [(2022, 2022)]},
        )

    def fake_search_registry(query_text, limit=10):
        return pd.DataFrame(
            [
                {"source": "world_bank", "series_id": "NY.GDP.MKTP.KD.ZG", "series_name": "GDP growth"},
                {"source": "acled", "series_id": "fatalities_sum", "series_name": "Fatalities"},
            ]
        )

    monkeypatch.setattr(execution, "fetch_metric_frame", fake_fetch)
    monkeypatch.setattr(execution, "search_registry", fake_search_registry)
    monkeypatch.setattr(execution, "write_materialized_result", lambda **kwargs: "r2")

    result = execution.execute_plan(plan)

    assert len(result.data_diagnostics) == 2
    statuses = {d["metric"]: d["status"] for d in result.data_diagnostics}
    assert statuses["world_bank:NY.GDP.MKTP.CD"] in {"sparse", "insufficient_points"}
    assert statuses["acled:event_count"] in {"sparse", "insufficient_points"}
    assert any("overlapping" in g.lower() for g in result.guidance)


def test_scenario_future_year_warning(monkeypatch):
    current = pd.Timestamp.utcnow().year
    plan = _plan(current - 2, current + 2)

    def fake_fetch(metric, _plan, force_refresh=False):
        # Return data only for historical years to mimic real APIs.
        if metric.source == "world_bank":
            return (
                pd.DataFrame({"iso3": ["DZA", "DZA"], "year": [current - 2, current - 1], "GDP": [1.0, 2.0]}),
                {"cache_hit_years": 0, "fetched_years": [current - 2, current - 1], "fetched_ranges": [(current - 2, current - 1)]},
            )
        return (
            pd.DataFrame({"iso3": ["DZA", "DZA"], "year": [current - 2, current - 1], "Conflict events": [8.0, 9.0]}),
            {"cache_hit_years": 0, "fetched_years": [current - 2, current - 1], "fetched_ranges": [(current - 2, current - 1)]},
        )

    monkeypatch.setattr(execution, "fetch_metric_frame", fake_fetch)
    monkeypatch.setattr(execution, "write_materialized_result", lambda **kwargs: "r3")

    result = execution.execute_plan(plan)

    assert any("future year" in g.lower() for g in result.guidance)
