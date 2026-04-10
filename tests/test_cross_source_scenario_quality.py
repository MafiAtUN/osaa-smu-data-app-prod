"""Tests for scenario quality scoring helper."""

from __future__ import annotations

import pandas as pd

from app.services.cross_source.quality import scenario_quality_score


def test_scenario_quality_fail_on_empty():
    status, note = scenario_quality_score(pd.DataFrame())
    assert status == "fail"
    assert "No rows" in note


def test_scenario_quality_pass_on_good_overlap():
    df = pd.DataFrame(
        {
            "year": list(range(2010, 2020)),
            "GDP": [float(i) for i in range(10)],
            "Population": [float(i * 2) for i in range(10)],
        }
    )
    status, _ = scenario_quality_score(df)
    assert status == "pass"
