"""Tests for cross-source planner fallback and confidence handling."""

from __future__ import annotations

import app.services.cross_source.planner as planner


class _FailLLM:
    def invoke(self, *args, **kwargs):
        raise RuntimeError("llm unavailable")


def test_parse_query_plan_fallback_when_llm_fails(monkeypatch):
    monkeypatch.setattr(planner, "get_llm", lambda **kwargs: _FailLLM())

    plan = planner.parse_query_plan(
        "For Algeria, compare conflict events and GDP over time and test correlation."
    )

    assert plan.country_iso3 == "DZA"
    assert plan.from_year <= plan.to_year
    assert len(plan.metrics) >= 2
    keys = {(m.source, m.series_id) for m in plan.metrics}
    assert ("world_bank", "NY.GDP.MKTP.CD") in keys
    assert ("acled", "event_count") in keys
    assert 0 <= plan.confidence <= 1


def test_augment_metrics_adds_missing_conflict_or_gdp(monkeypatch):
    monkeypatch.setattr(planner, "get_llm", lambda **kwargs: _FailLLM())

    plan = planner.parse_query_plan("Show GDP growth and conflict trend for Algeria.")
    keys = {(m.source, m.series_id) for m in plan.metrics}

    assert any(src == "acled" for src, _ in keys)
    assert any(src == "world_bank" for src, _ in keys)


def test_extracts_five_segment_world_bank_code(monkeypatch):
    monkeypatch.setattr(planner, "get_llm", lambda **kwargs: _FailLLM())

    plan = planner.parse_query_plan(
        "For Eastern Africa from 2000 to 2024 compare NY.GDP.MKTP.KD.ZG and SP.POP.GROW."
    )
    keys = {(m.source, m.series_id) for m in plan.metrics}

    assert ("world_bank", "NY.GDP.MKTP.KD.ZG") in keys
    assert ("world_bank", "SP.POP.GROW") in keys
