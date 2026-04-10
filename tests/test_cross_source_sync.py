"""Tests for hybrid sync orchestration."""

from __future__ import annotations

import pandas as pd

import app.services.cross_source.sync as sync


class _Result:
    def __init__(self, rows: int):
        self.merged_df = pd.DataFrame({"year": list(range(rows))}) if rows > 0 else pd.DataFrame()


def test_run_hybrid_sync_missing_only(monkeypatch):
    monkeypatch.setattr(sync, "refresh_metadata_registry", lambda sources=None: {s: 10 for s in (sources or [])})
    monkeypatch.setattr(sync, "log_refresh", lambda *args, **kwargs: None)

    def fake_exec(plan, force_refresh=False):
        assert force_refresh is False
        assert plan.metrics[0].source == "world_bank"
        return _Result(5)

    monkeypatch.setattr(sync, "execute_plan", fake_exec)

    out = sync.run_hybrid_sync(
        sources=["world_bank"],
        from_year=2018,
        to_year=2020,
        strategy="missing_only",
        scope_mode="all_regions",
        refresh_metadata=True,
        max_indicators_per_source=2,
    )

    assert len(out) == 1
    s = out[0]
    assert s.source == "world_bank"
    assert s.indicators_requested == 2
    assert s.indicators_with_data == 2
    assert s.total_rows == 10


def test_run_hybrid_sync_country_list_scope(monkeypatch):
    monkeypatch.setattr(sync, "refresh_metadata_registry", lambda sources=None: {s: 10 for s in (sources or [])})
    monkeypatch.setattr(sync, "log_refresh", lambda *args, **kwargs: None)
    monkeypatch.setattr(sync, "execute_plan", lambda plan, force_refresh=False: _Result(1))

    out = sync.run_hybrid_sync(
        sources=["acled"],
        from_year=2020,
        to_year=2022,
        strategy="force_refresh",
        scope_mode="country_list",
        countries=["Algeria", "Kenya"],
        refresh_metadata=False,
        max_indicators_per_source=1,
    )

    assert len(out) == 1
    s = out[0]
    assert s.source == "acled"
    assert s.plans_run == 2
    assert s.indicators_requested == 1
