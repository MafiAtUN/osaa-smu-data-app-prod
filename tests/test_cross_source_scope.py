"""Tests for geographic scope support (region/sub-region/all regions)."""

from __future__ import annotations

import pandas as pd

import app.services.cross_source.execution as execution
import app.services.cross_source.planner as planner
from app.services.cross_source.planner import MetricPlan, QueryPlan


class _FailLLM:
    def invoke(self, *args, **kwargs):
        raise RuntimeError("llm unavailable")


def test_planner_detects_all_regions_from_query(monkeypatch):
    monkeypatch.setattr(planner, "get_llm", lambda **kwargs: _FailLLM())

    plan = planner.parse_query_plan("From 2020 to 2025, show R&D spending trend for all regions")

    assert plan.scope_type in {"all_regions", "region"}
    assert len(plan.iso3_codes) > 30
    assert plan.geo_group_column in {"Region Name", "Sub-region Name", "Intermediate Region Name"}


def test_execution_merges_geo_group_frames(monkeypatch):
    plan = QueryPlan(
        country="All Regions",
        country_iso3="MULTI",
        from_year=2020,
        to_year=2022,
        metrics=[
            MetricPlan(source="world_bank", series_id="NY.GDP.MKTP.CD", label="GDP"),
            MetricPlan(source="world_bank", series_id="GB.XPD.RSDV.GD.ZS", label="R&D % GDP"),
        ],
        explanation="region test",
        scope_type="all_regions",
        scope_name="All Regions",
        geo_group_column="Region Name",
        iso3_codes=["DZA", "KEN", "FRA"],
        confidence=0.9,
    )

    def fake_fetch(metric, _plan, force_refresh=False):
        if metric.series_id == "NY.GDP.MKTP.CD":
            df = pd.DataFrame(
                {
                    "geo_group": ["Africa", "Africa", "Europe", "Europe"],
                    "year": [2020, 2021, 2020, 2021],
                    "GDP": [10.0, 11.0, 20.0, 21.0],
                }
            )
            return df, {"cache_hit_years": 0, "fetched_years": [2020, 2021], "fetched_ranges": [(2020, 2021)]}

        df = pd.DataFrame(
            {
                "geo_group": ["Africa", "Africa", "Europe", "Europe"],
                "year": [2020, 2021, 2020, 2021],
                "R&D % GDP": [0.4, 0.5, 1.2, 1.3],
            }
        )
        return df, {"cache_hit_years": 0, "fetched_years": [2020, 2021], "fetched_ranges": [(2020, 2021)]}

    monkeypatch.setattr(execution, "fetch_metric_frame", fake_fetch)
    monkeypatch.setattr(execution, "write_materialized_result", lambda **kwargs: "scope_r1")

    result = execution.execute_plan(plan)

    assert not result.merged_df.empty
    assert "geo_group" in result.merged_df.columns
    assert "GDP" in result.merged_df.columns
    assert "R&D % GDP" in result.merged_df.columns
