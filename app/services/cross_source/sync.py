"""Hybrid sync orchestration for cache-first cross-source data management.

Implements a cache-first strategy: serves data from the DuckDB dataset cache
when it is fresh, and falls back to live API fetches when the cache is stale or
missing.  Orchestrates background metadata refresh alongside on-demand data
retrieval.  Key exports: ``sync_datasets``, ``default_year_window``, and
``SyncResult``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any

from app.services.cross_source.db import (
    get_cache_metric_availability,
    get_cache_source_summary,
    get_refresh_logs,
    log_refresh,
)
from app.services.cross_source.execution import execute_plan
from app.services.cross_source.metadata import refresh_metadata_registry
from app.services.cross_source.planner import MetricPlan, QueryPlan
from app.services.geo_service import fuzzy_match_country, get_iso_reference_df
from app.services.undata_service import get_catalogue, get_uis_series

SUPPORTED_SOURCES = ["world_bank", "acled", "sdg", "uis", "un_data"]


@dataclass
class SyncSummary:
    source: str
    strategy: str
    indicators_requested: int
    indicators_with_data: int
    plans_run: int
    total_rows: int
    errors: int
    from_year: int
    to_year: int


def _default_source_indicators(source: str) -> list[str]:
    if source == "world_bank":
        return ["NY.GDP.PCAP.CD", "EG.ELC.ACCS.ZS", "SP.POP.TOTL", "NY.GDP.MKTP.CD"]
    if source == "acled":
        return ["event_count", "fatalities_sum"]
    if source == "sdg":
        return ["7.1.1", "1.1.1", "3.2.1"]
    if source == "uis":
        uis_map = get_uis_series()
        return list(uis_map.keys())[:3]
    if source == "un_data":
        return [str(item.get("id", "")).strip() for item in get_catalogue()[:3] if str(item.get("id", "")).strip()]
    return []


def _resolve_countries(country_names: list[str]) -> list[tuple[str, str]]:
    iso_df = get_iso_reference_df()
    candidates = iso_df["Country or Area"].dropna().astype(str).tolist()
    resolved: list[tuple[str, str]] = []
    for name in country_names:
        match = fuzzy_match_country(name, candidates)
        if not match:
            continue
        row = iso_df.loc[iso_df["Country or Area"] == match]
        if row.empty:
            continue
        resolved.append((match, str(row.iloc[0]["iso3"])))
    dedup: list[tuple[str, str]] = []
    seen: set[str] = set()
    for country, iso3 in resolved:
        if iso3 in seen:
            continue
        seen.add(iso3)
        dedup.append((country, iso3))
    return dedup


def _build_scopes(scope_mode: str, country_names: list[str]) -> list[dict[str, Any]]:
    scope_mode = (scope_mode or "all_regions").strip().lower()
    iso_df = get_iso_reference_df().dropna(subset=["iso3"]).copy()
    iso_df["iso3"] = iso_df["iso3"].astype(str)

    if scope_mode == "country_list":
        resolved = _resolve_countries(country_names)
        scopes = []
        for country, iso3 in resolved:
            scopes.append(
                {
                    "scope_type": "country",
                    "scope_name": country,
                    "geo_group_column": "Country or Area",
                    "iso3_codes": [iso3],
                    "country": country,
                    "country_iso3": iso3,
                }
            )
        return scopes

    all_iso3 = sorted(iso_df["iso3"].unique().tolist())
    return [
        {
            "scope_type": "all_regions",
            "scope_name": "All Regions",
            "geo_group_column": "Region Name",
            "iso3_codes": all_iso3,
            "country": "All Regions",
            "country_iso3": "MULTI",
        }
    ]


def run_hybrid_sync(
    sources: list[str],
    from_year: int,
    to_year: int,
    strategy: str = "missing_only",  # missing_only | force_refresh
    scope_mode: str = "all_regions",  # all_regions | country_list
    countries: list[str] | None = None,
    custom_indicators: dict[str, list[str]] | None = None,
    refresh_metadata: bool = True,
    max_indicators_per_source: int = 5,
) -> list[SyncSummary]:
    """Run hybrid sync for selected sources and return per-source summaries."""
    countries = countries or []
    custom_indicators = custom_indicators or {}
    strategy = strategy if strategy in {"missing_only", "force_refresh"} else "missing_only"

    selected = [s for s in sources if s in SUPPORTED_SOURCES]
    if refresh_metadata and selected:
        refresh_metadata_registry(selected)

    scopes = _build_scopes(scope_mode, countries)
    if not scopes:
        raise ValueError("No valid countries resolved for country_list scope.")

    out: list[SyncSummary] = []
    for source in selected:
        requested = custom_indicators.get(source) or _default_source_indicators(source)
        indicators = [sid.strip() for sid in requested if sid and sid.strip()][:max_indicators_per_source]
        rows_total = 0
        plan_count = 0
        error_count = 0
        with_data = 0
        errors: list[str] = []

        for sid in indicators:
            got_data_for_sid = False
            for scope in scopes:
                plan = QueryPlan(
                    country=scope["country"],
                    country_iso3=scope["country_iso3"],
                    from_year=from_year,
                    to_year=to_year,
                    metrics=[
                        MetricPlan(
                            source=source,
                            series_id=sid,
                            label=sid,
                            selection_method="hybrid_sync",
                            selection_reason=f"Hybrid sync {strategy} prefetch.",
                        )
                    ],
                    explanation=f"Hybrid sync prefetch for {source}:{sid}",
                    scope_type=scope["scope_type"],
                    scope_name=scope["scope_name"],
                    geo_group_column=scope["geo_group_column"],
                    iso3_codes=scope["iso3_codes"],
                    confidence=1.0,
                    purpose="cache_sync",
                )
                plan_count += 1
                try:
                    result = execute_plan(plan, force_refresh=(strategy == "force_refresh"))
                    row_count = int(len(result.merged_df))
                    rows_total += row_count
                    if row_count > 0:
                        got_data_for_sid = True
                except Exception as exc:
                    error_count += 1
                    if len(errors) < 5:
                        errors.append(f"{sid}@{scope['scope_type']}: {exc}")

            if got_data_for_sid:
                with_data += 1

        summary = SyncSummary(
            source=source,
            strategy=strategy,
            indicators_requested=len(indicators),
            indicators_with_data=with_data,
            plans_run=plan_count,
            total_rows=rows_total,
            errors=error_count,
            from_year=from_year,
            to_year=to_year,
        )
        out.append(summary)

        detail_payload = {
            "strategy": strategy,
            "scope_mode": scope_mode,
            "countries": countries[:20],
            "indicators_requested": len(indicators),
            "indicators_with_data": with_data,
            "plans_run": plan_count,
            "rows": rows_total,
            "errors": error_count,
            "error_samples": errors,
            "window": f"{from_year}-{to_year}",
        }
        status = "ok" if error_count == 0 else "partial"
        log_refresh("hybrid_sync_data", source, status, json.dumps(detail_payload, default=str)[:1000])

    return out


def run_metadata_sync(sources: list[str]) -> dict[str, int]:
    """Refresh metadata for selected sources and return row counts."""
    selected = [s for s in sources if s in SUPPORTED_SOURCES]
    return refresh_metadata_registry(selected)


def get_hybrid_sync_dashboard(limit_metrics: int = 200, limit_logs: int = 200) -> dict[str, Any]:
    """Return tables used by the hybrid sync dashboard."""
    return {
        "source_summary": get_cache_source_summary(),
        "metric_availability": get_cache_metric_availability(limit=limit_metrics),
        "refresh_logs": get_refresh_logs(limit=limit_logs),
    }


def default_year_window() -> tuple[int, int]:
    current = date.today().year
    return current - 10, current
