"""Execution engine for cross-source query plans.

Takes a structured query plan produced by the planner and dispatches fetch
calls to the appropriate data-source adapters (World Bank, ACLED, UN SDG, etc.),
then merges the resulting DataFrames into a single combined dataset.  Key
export: ``execute_plan``, which returns a merged ``pd.DataFrame`` and a list of
per-source status messages.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import pandas as pd
import wbgapi as wb

from app.core.logging import get_logger
from app.services.acled_service import (
    fetch_acled_data,
    get_access_token,
    get_acled_credentials,
)
from app.services.cross_source.db import (
    make_cache_key,
    read_yearly_cached_slice,
    write_cache,
    write_materialized_result,
)
from app.services.cross_source.metadata import search_registry
from app.services.cross_source.planner import MetricPlan, QueryPlan
from app.services.geo_service import get_iso_reference_df
from app.services.sdg_service import fetch_sdg_data
from app.services.undata_service import fetch_uis_data, fetch_undata

logger = get_logger(__name__)


@dataclass
class ExecutionResult:
    merged_df: pd.DataFrame
    metric_frames: dict[str, pd.DataFrame]
    cache_diagnostics: dict[str, dict[str, Any]]
    data_diagnostics: list[dict[str, Any]]
    guidance: list[str]
    notes: list[str]
    result_key: str


FetchRangeFn = Callable[[int, int], pd.DataFrame]

SOURCE_TTL_HOURS: dict[str, int] = {
    "acled": 24,
    "world_bank": 96,
    "sdg": 72,
    "uis": 120,
    "un_data": 120,
}


def _map_iso3_to_m49(iso3: str) -> str | None:
    iso_df = get_iso_reference_df()
    row = iso_df.loc[iso_df["iso3"] == iso3]
    if row.empty:
        return None
    return str(row.iloc[0]["m49"])


def _map_iso3_list_to_m49(iso3_codes: list[str]) -> list[str]:
    out: list[str] = []
    for code in iso3_codes:
        m49 = _map_iso3_to_m49(code)
        if m49:
            out.append(m49)
    return sorted(set(out))


def _scope_cache_id(plan: QueryPlan) -> str:
    if plan.scope_type == "country":
        return plan.country_iso3
    if plan.scope_name:
        return f"{plan.scope_type}:{plan.scope_name}"
    return f"{plan.scope_type}:MULTI"


def _target_iso3_codes(plan: QueryPlan) -> list[str]:
    if plan.iso3_codes:
        return sorted(set(plan.iso3_codes))
    if plan.country_iso3 and plan.country_iso3 != "MULTI":
        return [plan.country_iso3]
    return []


def _metric_aggfunc(metric: MetricPlan) -> str:
    if metric.source == "acled":
        return "sum"
    sid = metric.series_id.lower()
    lbl = metric.label.lower()
    if any(k in sid for k in (".zs", "rate", "percent")) or "%" in lbl:
        return "mean"
    if any(k in lbl for k in ("total", "count", "fatalit", "events")):
        return "sum"
    return "mean"


def _apply_scope_grouping(df: pd.DataFrame, plan: QueryPlan, metric: MetricPlan) -> pd.DataFrame:
    """Aggregate country-level frame into requested geo scope when needed."""
    if plan.scope_type == "country" or df.empty:
        return df
    if "iso3" not in df.columns or "year" not in df.columns:
        return df

    value_col = metric.label
    if value_col not in df.columns:
        candidates = [c for c in df.columns if c not in ("iso3", "year", "country", "geo_group")]
        if not candidates:
            return df
        value_col = candidates[0]

    iso_df = get_iso_reference_df()
    keep_cols = ["iso3", "Country or Area", "Region Name", "Sub-region Name", "Intermediate Region Name"]
    geo_ref = iso_df[[c for c in keep_cols if c in iso_df.columns]].dropna(subset=["iso3"]).copy()
    merged = df.merge(geo_ref, on="iso3", how="left")

    if plan.scope_type == "all_regions":
        group_col = "Region Name"
    elif plan.scope_type == "all_sub_regions":
        group_col = "Sub-region Name"
    else:
        group_col = plan.geo_group_column or "Region Name"

    if group_col not in merged.columns:
        return df

    aggfunc = _metric_aggfunc(metric)
    grouped = (
        merged.dropna(subset=[group_col, "year"])
        .groupby([group_col, "year"], as_index=False)[value_col]
        .agg(aggfunc)
        .rename(columns={group_col: "geo_group", value_col: metric.label})
    )
    grouped["year"] = pd.to_numeric(grouped["year"], errors="coerce").astype("Int64")
    grouped = grouped.dropna(subset=["year"])
    grouped["year"] = grouped["year"].astype(int)
    return grouped


def _frame_keys(frames: list[pd.DataFrame]) -> list[str]:
    for df in frames:
        if df is None or df.empty:
            continue
        if "geo_group" in df.columns:
            return ["geo_group", "year"]
        if "iso3" in df.columns:
            return ["iso3", "year"]
    return ["iso3", "year"]


def _yearly_aggregate(df: pd.DataFrame, value_col: str, out_col: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["iso3", "year", out_col])

    if "year" not in df.columns and "event_date" in df.columns:
        df = df.copy()
        df["year"] = pd.to_datetime(df["event_date"], errors="coerce").dt.year

    if "year" not in df.columns:
        for candidate in ("Year", "TIME_PERIOD", "timePeriodStart"):
            if candidate in df.columns:
                df = df.copy()
                df["year"] = pd.to_numeric(df[candidate], errors="coerce")
                break

    if "year" not in df.columns:
        return pd.DataFrame(columns=["iso3", "year", out_col])

    grouped = (
        df.dropna(subset=["year"])
        .groupby(["iso3", "year"], as_index=False)[value_col]
        .sum()
        .rename(columns={value_col: out_col})
    )
    grouped["year"] = grouped["year"].astype(int)
    return grouped


def _to_ranges(years: list[int]) -> list[tuple[int, int]]:
    if not years:
        return []
    years = sorted(set(years))
    ranges: list[tuple[int, int]] = []
    start = prev = years[0]
    for y in years[1:]:
        if y == prev + 1:
            prev = y
            continue
        ranges.append((start, prev))
        start = prev = y
    ranges.append((start, prev))
    return ranges


def _cache_first_fetch(
    source: str,
    metric: MetricPlan,
    plan: QueryPlan,
    fetch_fn: FetchRangeFn,
    ttl_hours: int,
    force_refresh: bool,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    scope_id = _scope_cache_id(plan)
    if force_refresh:
        fresh = fetch_fn(plan.from_year, plan.to_year)
        fresh = _apply_scope_grouping(fresh, plan, metric)
        ck_full = make_cache_key(source, metric.series_id, scope_id, plan.from_year, plan.to_year, "year")
        write_cache(
            ck_full,
            source,
            metric.series_id,
            scope_id,
            plan.from_year,
            plan.to_year,
            "year",
            fresh,
            ttl_hours=ttl_hours,
        )
        return fresh, {
            "force_refresh": True,
            "cache_hit_years": 0,
            "fetched_years": list(range(plan.from_year, plan.to_year + 1)),
            "fetched_ranges": [(plan.from_year, plan.to_year)],
        }

    cached_df, missing_years = read_yearly_cached_slice(
        source=source,
        metric_id=metric.series_id,
        country_iso3=scope_id,
        start_year=plan.from_year,
        end_year=plan.to_year,
        value_label=metric.label,
    )

    parts: list[pd.DataFrame] = [cached_df] if not cached_df.empty else []
    fetched_ranges: list[tuple[int, int]] = []

    for seg_start, seg_end in _to_ranges(missing_years):
        fetched = fetch_fn(seg_start, seg_end)
        fetched = _apply_scope_grouping(fetched, plan, metric)
        parts.append(fetched)
        fetched_ranges.append((seg_start, seg_end))
        ck = make_cache_key(source, metric.series_id, scope_id, seg_start, seg_end, "year")
        write_cache(
            ck,
            source,
            metric.series_id,
            scope_id,
            seg_start,
            seg_end,
            "year",
            fetched,
            ttl_hours=ttl_hours,
        )

    merge_keys = ["geo_group", "year"] if plan.scope_type != "country" else ["iso3", "year"]

    if not parts:
        return pd.DataFrame(columns=[*merge_keys, metric.label]), {
            "force_refresh": False,
            "cache_hit_years": 0,
            "fetched_years": [],
            "fetched_ranges": [],
        }

    merged = pd.concat(parts, ignore_index=True)
    if merged.empty:
        return pd.DataFrame(columns=[*merge_keys, metric.label]), {
            "force_refresh": False,
            "cache_hit_years": 0,
            "fetched_years": missing_years,
            "fetched_ranges": fetched_ranges,
        }

    if metric.label not in merged.columns:
        candidates = [c for c in merged.columns if c not in ("iso3", "year", "country")]
        if candidates:
            merged = merged.rename(columns={candidates[0]: metric.label})

    merged["year"] = pd.to_numeric(merged["year"], errors="coerce")
    merged = merged.dropna(subset=["year"])
    merged["year"] = merged["year"].astype(int)
    merged = merged[(merged["year"] >= plan.from_year) & (merged["year"] <= plan.to_year)]
    dedup_keys = [k for k in merge_keys if k in merged.columns]
    if not dedup_keys:
        dedup_keys = ["year"] if "year" in merged.columns else []
    if dedup_keys:
        merged = merged.sort_values(dedup_keys).drop_duplicates(subset=dedup_keys, keep="last")

    # Also persist one full-slice cache entry for fast exact reuse.
    ck_full = make_cache_key(source, metric.series_id, scope_id, plan.from_year, plan.to_year, "year")
    write_cache(
        ck_full,
        source,
        metric.series_id,
        scope_id,
        plan.from_year,
        plan.to_year,
        "year",
        merged,
        ttl_hours=ttl_hours,
    )

    merged = merged.reset_index(drop=True)
    covered = sorted(set(merged["year"].tolist())) if "year" in merged.columns else []
    cache_hit_years = [y for y in covered if y not in missing_years]
    return merged, {
        "force_refresh": False,
        "cache_hit_years": len(cache_hit_years),
        "fetched_years": missing_years,
        "fetched_ranges": fetched_ranges,
    }


def _fetch_world_bank_metric(
    metric: MetricPlan,
    plan: QueryPlan,
    force_refresh: bool = False,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    target_iso3 = _target_iso3_codes(plan)
    if not target_iso3:
        return pd.DataFrame(columns=["iso3", "year", metric.label]), {"error": "No ISO3 targets resolved for scope."}

    def _fetch_range(start_year: int, end_year: int) -> pd.DataFrame:
        # For broad scopes use a single 'all economies' pull then filter to target ISO3.
        raw_parts: list[pd.DataFrame] = []
        if plan.scope_type != "country" and len(target_iso3) >= 20:
            try:
                all_df = wb.data.DataFrame(
                    [metric.series_id],
                    ["all"],
                    list(range(start_year, end_year + 1)),
                ).reset_index()
                if all_df is not None and not all_df.empty:
                    if "economy" in all_df.columns:
                        all_df = all_df[all_df["economy"].isin(target_iso3)]
                    raw_parts.append(all_df)
            except Exception:
                pass

        # Fallback / country mode: batch by explicit countries.
        if not raw_parts:
            batch_size = 40
            for i in range(0, len(target_iso3), batch_size):
                batch = target_iso3[i : i + batch_size]
                try:
                    chunk = wb.data.DataFrame(
                        [metric.series_id],
                        batch,
                        list(range(start_year, end_year + 1)),
                    ).reset_index()
                    if chunk is not None and not chunk.empty:
                        raw_parts.append(chunk)
                except Exception:
                    continue

        if not raw_parts:
            return pd.DataFrame(columns=["iso3", "year", metric.label])
        raw = pd.concat(raw_parts, ignore_index=True)

        id_cols = [c for c in raw.columns if not str(c).startswith("YR")]
        long_df = raw.melt(id_vars=id_cols, var_name="year_col", value_name=metric.label)
        long_df["year"] = long_df["year_col"].astype(str).str.extract(r"(\d{4})").astype(float)
        long_df = long_df.dropna(subset=["year"])
        long_df["year"] = long_df["year"].astype(int)

        iso_series = (
            long_df["economy"].astype(str)
            if "economy" in long_df.columns
            else pd.Series([plan.country_iso3] * len(long_df))
        )
        return pd.DataFrame(
            {
                "iso3": iso_series,
                "year": long_df["year"],
                metric.label: pd.to_numeric(long_df[metric.label], errors="coerce"),
            }
        ).dropna(subset=[metric.label])

    return _cache_first_fetch(
        "world_bank",
        metric,
        plan,
        _fetch_range,
        ttl_hours=SOURCE_TTL_HOURS["world_bank"],
        force_refresh=force_refresh,
    )


def _fetch_acled_metric(
    metric: MetricPlan,
    plan: QueryPlan,
    force_refresh: bool = False,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    iso_df = get_iso_reference_df()
    target_iso3 = _target_iso3_codes(plan)
    if not target_iso3:
        return pd.DataFrame(columns=["iso3", "year", metric.label]), {"error": "No ISO3 targets resolved for scope."}

    rows = iso_df.loc[iso_df["iso3"].isin(target_iso3)].dropna(subset=["Country or Area"])
    if rows.empty:
        return pd.DataFrame(columns=["iso3", "year", metric.label]), {"error": "Scope ISO3 values not found in ISO reference."}
    country_names = sorted(rows["Country or Area"].astype(str).unique().tolist())
    country_to_iso3 = rows.set_index("Country or Area")["iso3"].astype(str).to_dict()

    email, key = get_acled_credentials()
    if not email or not key:
        raise ValueError("ACLED credentials are not configured.")
    token = get_access_token(email, key)
    if not token:
        raise ValueError("Failed to authenticate ACLED.")

    def _fetch_range(start_year: int, end_year: int) -> pd.DataFrame:
        frames: list[pd.DataFrame] = []
        chunk_size = 20
        for i in range(0, len(country_names), chunk_size):
            chunk = country_names[i : i + chunk_size]
            params: dict[str, Any] = {
                "_format": "json",
                "country": "|".join(chunk),
                "event_date": f"{start_year}-01-01:{end_year}-12-31",
                "event_date_where": "BETWEEN",
                "limit": 50000,
            }
            if metric.series_id.startswith("sub_event::"):
                subtype = metric.series_id.split("::", 1)[1]
                params["sub_event_type"] = subtype

            raw_chunk = fetch_acled_data(params, token)
            if raw_chunk is not None and not raw_chunk.empty:
                frames.append(raw_chunk)

        if not frames:
            return pd.DataFrame(columns=["iso3", "year", metric.label])

        raw = pd.concat(frames, ignore_index=True)

        raw = raw.copy()
        if "country" in raw.columns:
            raw["iso3"] = raw["country"].map(country_to_iso3)
        if "iso3" not in raw.columns:
            raw["iso3"] = None
        raw = raw.dropna(subset=["iso3"])

        if metric.series_id == "fatalities_sum":
            raw["fatalities"] = pd.to_numeric(raw.get("fatalities"), errors="coerce").fillna(0)
            return _yearly_aggregate(raw, "fatalities", metric.label)

        raw["event_count"] = 1
        return _yearly_aggregate(raw, "event_count", metric.label)

    return _cache_first_fetch(
        "acled",
        metric,
        plan,
        _fetch_range,
        ttl_hours=SOURCE_TTL_HOURS["acled"],
        force_refresh=force_refresh,
    )


def _fetch_sdg_metric(
    metric: MetricPlan,
    plan: QueryPlan,
    force_refresh: bool = False,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    iso_df = get_iso_reference_df()
    target_iso3 = _target_iso3_codes(plan)
    if not target_iso3:
        return pd.DataFrame(columns=["iso3", "year", metric.label]), {"error": "No ISO3 targets resolved for scope."}
    country_rows = iso_df.loc[iso_df["iso3"].isin(target_iso3)].dropna(subset=["Country or Area"])
    if country_rows.empty:
        return pd.DataFrame(columns=["iso3", "year", metric.label]), {"error": "Scope ISO3 values not found in ISO reference."}
    country_names = sorted(country_rows["Country or Area"].astype(str).unique().tolist())
    country_to_iso3 = country_rows.set_index("Country or Area")["iso3"].astype(str).to_dict()

    def _fetch_range(start_year: int, end_year: int) -> pd.DataFrame:
        params = {
            "indicators": [metric.series_id],
            "goal_codes": [],
            "countries": country_names,
            "regions": [],
            "from_year": start_year,
            "to_year": end_year,
        }
        raw, err = fetch_sdg_data(params, indicators_data=[])
        if err or raw is None or raw.empty:
            return pd.DataFrame(columns=["iso3", "year", metric.label])

        if "value" not in raw.columns and "Value" in raw.columns:
            raw = raw.rename(columns={"Value": "value"})
        raw = raw.copy()
        if "iso3" in raw.columns:
            raw["iso3"] = raw["iso3"].astype(str)
        elif "Country or Area" in raw.columns:
            raw["iso3"] = raw["Country or Area"].map(country_to_iso3)
        elif "geoAreaName" in raw.columns:
            raw["iso3"] = raw["geoAreaName"].map(country_to_iso3)
        else:
            raw["iso3"] = None
        raw = raw.dropna(subset=["iso3"])
        return _yearly_aggregate(raw, "value", metric.label)

    return _cache_first_fetch(
        "sdg",
        metric,
        plan,
        _fetch_range,
        ttl_hours=SOURCE_TTL_HOURS["sdg"],
        force_refresh=force_refresh,
    )


def _fetch_uis_metric(
    metric: MetricPlan,
    plan: QueryPlan,
    force_refresh: bool = False,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    target_iso3 = _target_iso3_codes(plan)
    if not target_iso3:
        return pd.DataFrame(columns=["iso3", "year", metric.label]), {"error": "No ISO3 targets resolved for scope."}

    def _fetch_range(start_year: int, end_year: int) -> pd.DataFrame:
        raw = fetch_uis_data((metric.series_id,), tuple(target_iso3), start_year, end_year)
        if raw is None or raw.empty:
            return pd.DataFrame(columns=["iso3", "year", metric.label])

        raw = raw.copy()
        if "REF_AREA" in raw.columns:
            raw["iso3"] = raw["REF_AREA"].astype(str)
        else:
            raw["iso3"] = None
        raw = raw.dropna(subset=["iso3"])
        if "OBS_VALUE" in raw.columns:
            raw = raw.rename(columns={"OBS_VALUE": "value"})
        return _yearly_aggregate(raw, "value", metric.label)

    return _cache_first_fetch(
        "uis",
        metric,
        plan,
        _fetch_range,
        ttl_hours=SOURCE_TTL_HOURS["uis"],
        force_refresh=force_refresh,
    )


def _fetch_un_data_metric(
    metric: MetricPlan,
    plan: QueryPlan,
    force_refresh: bool = False,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    target_iso3 = _target_iso3_codes(plan)
    if not target_iso3:
        return pd.DataFrame(columns=["iso3", "year", metric.label]), {"error": "No ISO3 targets resolved for scope."}
    m49_codes = _map_iso3_list_to_m49(target_iso3)
    if not m49_codes:
        return pd.DataFrame(columns=["iso3", "year", metric.label]), {"error": "Could not map ISO3 scope to M49 codes."}
    geo_codes = tuple(f"G{m49}" for m49 in m49_codes)
    iso_df = get_iso_reference_df().dropna(subset=["m49", "iso3"])
    m49_to_iso3 = {f"G{str(row['m49'])}": str(row["iso3"]) for _, row in iso_df.iterrows()}

    def _fetch_range(start_year: int, end_year: int) -> pd.DataFrame:
        raw = fetch_undata(metric.series_id, geo_codes, start_year, end_year)
        if raw is None or raw.empty:
            return pd.DataFrame(columns=["iso3", "year", metric.label])

        raw = raw.copy()
        if "GEOGRAPHY" in raw.columns:
            raw["iso3"] = raw["GEOGRAPHY"].map(m49_to_iso3)
        elif "geo_code" in raw.columns:
            raw["iso3"] = raw["geo_code"].map(m49_to_iso3)
        else:
            raw["iso3"] = None
        raw = raw.dropna(subset=["iso3"])
        if "OBS_VALUE" in raw.columns:
            raw = raw.rename(columns={"OBS_VALUE": "value"})
        return _yearly_aggregate(raw, "value", metric.label)

    return _cache_first_fetch(
        "un_data",
        metric,
        plan,
        _fetch_range,
        ttl_hours=SOURCE_TTL_HOURS["un_data"],
        force_refresh=force_refresh,
    )


def fetch_metric_frame(
    metric: MetricPlan,
    plan: QueryPlan,
    force_refresh: bool = False,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    src = metric.source
    if src == "world_bank":
        return _fetch_world_bank_metric(metric, plan, force_refresh=force_refresh)
    if src == "acled":
        return _fetch_acled_metric(metric, plan, force_refresh=force_refresh)
    if src == "sdg":
        return _fetch_sdg_metric(metric, plan, force_refresh=force_refresh)
    if src == "uis":
        return _fetch_uis_metric(metric, plan, force_refresh=force_refresh)
    if src == "un_data":
        return _fetch_un_data_metric(metric, plan, force_refresh=force_refresh)

    raise ValueError(f"Unsupported source in v1 execution: {src}")


def _merge_frames(frames: list[pd.DataFrame]) -> pd.DataFrame:
    if not frames:
        return pd.DataFrame(columns=["iso3", "year"])

    keys = _frame_keys(frames)
    merged = None
    for df in frames:
        if df is None or df.empty:
            continue
        if merged is None:
            merged = df.copy()
        else:
            merged = merged.merge(df, on=keys, how="outer")

    if merged is None:
        return pd.DataFrame(columns=["iso3", "year"])

    sort_cols = [c for c in keys if c in merged.columns]
    return merged.sort_values(sort_cols).reset_index(drop=True)


def _suggest_alternative_series(metric: MetricPlan) -> list[str]:
    """Suggest nearby series IDs for sparse/missing coverage."""
    try:
        hits = search_registry(metric.label or metric.series_id, limit=10)
    except Exception:
        return []
    if hits.empty:
        return []

    scoped = hits[hits["source"] == metric.source]
    if scoped.empty:
        scoped = hits
    suggestions: list[str] = []
    for _, row in scoped.iterrows():
        sid = str(row["series_id"])
        if sid == metric.series_id:
            continue
        suggestions.append(f"{row['source']}:{sid} ({row['series_name']})")
        if len(suggestions) >= 3:
            break
    return suggestions


def _build_data_diagnostics(plan: QueryPlan, metrics: list[MetricPlan], frames: dict[str, pd.DataFrame]) -> tuple[list[dict[str, Any]], list[str]]:
    requested_years = list(range(plan.from_year, plan.to_year + 1))
    current_year = pd.Timestamp.utcnow().year
    diagnostics: list[dict[str, Any]] = []
    guidance: list[str] = []
    scope_label = plan.scope_name or plan.country or plan.scope_type

    if plan.to_year > current_year:
        guidance.append(
            f"Requested range includes future year(s) up to {plan.to_year}; most APIs only have partial/no data beyond {current_year}."
        )

    nonempty_metric_year_sets: list[set[int]] = []
    for metric in metrics:
        key = f"{metric.source}:{metric.series_id}"
        df = frames.get(key, pd.DataFrame())

        if df.empty or "year" not in df.columns:
            alt = _suggest_alternative_series(metric)
            diagnostics.append(
                {
                    "metric": key,
                    "label": metric.label,
                    "available_points": 0,
                    "coverage_ratio": 0.0,
                    "missing_years": len(requested_years),
                    "status": "no_data",
                    "alternatives": " | ".join(alt) if alt else "",
                }
            )
            guidance.append(
                f"No data for {metric.label} in {scope_label} ({plan.from_year}-{plan.to_year}). "
                f"Try widening date range or alternative series."
            )
            continue

        years = pd.to_numeric(df["year"], errors="coerce").dropna().astype(int)
        year_set = set(y for y in years.tolist() if plan.from_year <= y <= plan.to_year)
        nonempty_metric_year_sets.append(year_set)
        coverage_ratio = len(year_set) / max(len(requested_years), 1)
        missing_count = max(len(requested_years) - len(year_set), 0)
        points = len(df.dropna())

        if points < 3:
            status = "insufficient_points"
            guidance.append(
                f"{metric.label} has only {points} point(s); correlation/trend inference may be unreliable."
            )
        elif coverage_ratio < 0.6:
            status = "sparse"
            guidance.append(
                f"{metric.label} covers only {coverage_ratio:.0%} of requested years. Consider broader years or a proxy metric."
            )
        else:
            status = "ok"

        alt = _suggest_alternative_series(metric) if status in ("no_data", "insufficient_points", "sparse") else []
        diagnostics.append(
            {
                "metric": key,
                "label": metric.label,
                "available_points": points,
                "coverage_ratio": round(coverage_ratio, 3),
                "missing_years": missing_count,
                "status": status,
                "alternatives": " | ".join(alt) if alt else "",
            }
        )

    if len(nonempty_metric_year_sets) >= 2:
        overlap = set.intersection(*nonempty_metric_year_sets) if nonempty_metric_year_sets else set()
        if len(overlap) < 3:
            guidance.append(
                f"Only {len(overlap)} overlapping year(s) across selected metrics. "
                "Consider changing date range or selecting alternative indicators for stronger correlation analysis."
            )

    return diagnostics, guidance


def execute_plan(plan: QueryPlan, force_refresh: bool = False) -> ExecutionResult:
    """Run all source fetches in a query plan and return a merged dataframe."""
    metric_frames: dict[str, pd.DataFrame] = {}
    cache_diagnostics: dict[str, dict[str, Any]] = {}
    notes: list[str] = []

    for metric in plan.metrics:
        key = f"{metric.source}:{metric.series_id}"
        try:
            frame, diag = fetch_metric_frame(metric, plan, force_refresh=force_refresh)
            metric_frames[key] = frame
            cache_diagnostics[key] = diag
            if frame.empty:
                notes.append(f"No data returned for {key}")
        except Exception as exc:
            logger.exception("Failed metric fetch for %s", key)
            metric_frames[key] = pd.DataFrame(columns=["iso3", "year", metric.label])
            cache_diagnostics[key] = {"error": str(exc)}
            notes.append(f"Fetch failed for {key}: {exc}")

    data_diagnostics, guidance = _build_data_diagnostics(plan, plan.metrics, metric_frames)

    merged = _merge_frames(list(metric_frames.values()))

    if not merged.empty and "iso3" in merged.columns:
        iso_df = get_iso_reference_df()
        lookup = iso_df.dropna(subset=["iso3"]).set_index("iso3")["Country or Area"].to_dict()
        merged.insert(1, "country", merged["iso3"].map(lookup).fillna(plan.country))
    elif not merged.empty and "geo_group" in merged.columns:
        merged.insert(1, "scope", plan.scope_name or plan.scope_type)

    result_key = write_materialized_result(
        query_text=(
            f"{plan.scope_type}:{plan.scope_name or plan.country}"
            f"|{plan.from_year}-{plan.to_year}"
            f"|{','.join(m.series_id for m in plan.metrics)}"
        ),
        merged_df=merged,
    )

    return ExecutionResult(
        merged_df=merged,
        metric_frames=metric_frames,
        cache_diagnostics=cache_diagnostics,
        data_diagnostics=data_diagnostics,
        guidance=guidance,
        notes=notes,
        result_key=result_key,
    )
