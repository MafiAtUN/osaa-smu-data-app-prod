"""Tests for cross-source cache storage/backfill helpers."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.services.cross_source import db


def test_read_yearly_cached_slice_detects_missing_years(tmp_path):
    test_db = tmp_path / "cross_source_test.duckdb"
    db.DB_PATH = Path(test_db)
    db.init_storage()

    # Cache one metric for 2018-2019 only
    df = pd.DataFrame(
        {
            "iso3": ["DZA", "DZA"],
            "year": [2018, 2019],
            "GDP (current US$)": [170.0, 175.0],
        }
    )
    cache_key = db.make_cache_key("world_bank", "NY.GDP.MKTP.CD", "DZA", 2018, 2019, "year")
    db.write_cache(
        cache_key,
        "world_bank",
        "NY.GDP.MKTP.CD",
        "DZA",
        2018,
        2019,
        "year",
        df,
        ttl_hours=24,
    )

    cached_df, missing = db.read_yearly_cached_slice(
        source="world_bank",
        metric_id="NY.GDP.MKTP.CD",
        country_iso3="DZA",
        start_year=2018,
        end_year=2020,
        value_label="GDP (current US$)",
    )

    assert not cached_df.empty
    assert sorted(cached_df["year"].tolist()) == [2018, 2019]
    assert missing == [2020]


def test_read_yearly_cached_slice_uses_overlap(tmp_path):
    test_db = tmp_path / "cross_source_test_overlap.duckdb"
    db.DB_PATH = Path(test_db)
    db.init_storage()

    df_a = pd.DataFrame({"iso3": ["DZA"], "year": [2018], "v": [1.0]})
    df_b = pd.DataFrame({"iso3": ["DZA", "DZA"], "year": [2019, 2020], "v": [2.0, 3.0]})

    db.write_cache(
        db.make_cache_key("acled", "event_count", "DZA", 2018, 2018, "year"),
        "acled",
        "event_count",
        "DZA",
        2018,
        2018,
        "year",
        df_a,
        ttl_hours=24,
    )
    db.write_cache(
        db.make_cache_key("acled", "event_count", "DZA", 2019, 2020, "year"),
        "acled",
        "event_count",
        "DZA",
        2019,
        2020,
        "year",
        df_b,
        ttl_hours=24,
    )

    cached_df, missing = db.read_yearly_cached_slice(
        source="acled",
        metric_id="event_count",
        country_iso3="DZA",
        start_year=2018,
        end_year=2020,
        value_label="events",
    )

    assert sorted(cached_df["year"].tolist()) == [2018, 2019, 2020]
    assert missing == []


def test_read_yearly_cached_slice_preserves_geo_group(tmp_path):
    test_db = tmp_path / "cross_source_test_geo_group.duckdb"
    db.DB_PATH = Path(test_db)
    db.init_storage()

    df = pd.DataFrame(
        {
            "geo_group": ["Africa", "Europe"],
            "year": [2020, 2020],
            "GDP": [1.0, 2.0],
        }
    )

    db.write_cache(
        db.make_cache_key("world_bank", "NY.GDP.MKTP.CD", "all_regions:All Regions", 2020, 2020, "year"),
        "world_bank",
        "NY.GDP.MKTP.CD",
        "all_regions:All Regions",
        2020,
        2020,
        "year",
        df,
        ttl_hours=24,
    )

    cached_df, missing = db.read_yearly_cached_slice(
        source="world_bank",
        metric_id="NY.GDP.MKTP.CD",
        country_iso3="all_regions:All Regions",
        start_year=2020,
        end_year=2020,
        value_label="GDP",
    )

    assert "geo_group" in cached_df.columns
    assert set(cached_df["geo_group"].tolist()) == {"Africa", "Europe"}
    assert missing == []
