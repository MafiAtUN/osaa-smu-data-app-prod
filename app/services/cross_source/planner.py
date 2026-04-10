"""Cross-source natural-language query planning.

Converts a free-text user question into a structured plan that specifies which
data sources, indicators, countries, and year ranges are required.  Uses an LLM
to parse the query, matches it against the metadata store, and returns a
``QueryPlan`` dataclass consumed by the execution engine.  Key export:
``build_query_plan``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.logging import get_logger
from app.services.cross_source.metadata import search_registry
from app.services.geo_service import fuzzy_match_country, get_iso_reference_df
from app.services.llm_service import get_llm

logger = get_logger(__name__)


@dataclass
class MetricPlan:
    source: str
    series_id: str
    label: str
    aggregation: str = "yearly"
    selection_method: str = "llm"
    selection_reason: str = ""
    candidates: list[dict[str, str]] = field(default_factory=list)


@dataclass
class QueryPlan:
    country: str
    country_iso3: str
    from_year: int
    to_year: int
    metrics: list[MetricPlan]
    explanation: str
    scope_type: str = "country"  # country | region | sub_region | intermediate_region | all_regions
    scope_name: str = ""
    geo_group_column: str = "Country or Area"
    iso3_codes: list[str] = field(default_factory=list)
    confidence: float = 0.5
    purpose: str = ""
    follow_up_questions: list[str] = field(default_factory=list)


def _extract_json_block(text: str) -> dict[str, Any] | None:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except Exception:
        return None


def _default_plan_from_query(user_query: str) -> dict[str, Any]:
    current = date.today().year
    return {
        "country": "Algeria",
        "from_year": current - 10,
        "to_year": current,
        "metrics": [
            {"source": "world_bank", "series_id": "NY.GDP.MKTP.CD", "label": "GDP (current US$)"},
            {"source": "acled", "series_id": "event_count", "label": "Conflict event count"},
        ],
        "explanation": "Fallback plan generated because parser confidence was low.",
        "confidence": 0.35,
    }


def _resolve_country(country_name: str) -> tuple[str, str] | None:
    iso_df = get_iso_reference_df()
    country_candidates = iso_df["Country or Area"].tolist()
    matched = fuzzy_match_country(country_name, country_candidates)
    if not matched:
        return None

    row = iso_df.loc[iso_df["Country or Area"] == matched]
    if row.empty:
        return None

    iso3 = str(row.iloc[0]["iso3"])
    return matched, iso3


def _fuzzy_match_value(name: str, candidates: list[str]) -> str | None:
    if not name:
        return None
    n = name.strip().lower()
    for c in candidates:
        if n == str(c).strip().lower():
            return str(c)
    for c in candidates:
        c_low = str(c).strip().lower()
        if n in c_low or c_low in n:
            return str(c)
    return None


def _detect_scope_from_query(user_query: str) -> tuple[str, str]:
    q = user_query.lower()
    if "all regions" in q or "by region" in q or "across regions" in q:
        return "all_regions", "All Regions"
    if "all sub-regions" in q or "all subregions" in q:
        return "all_sub_regions", "All Sub-regions"

    iso_df = get_iso_reference_df()
    # Try sub-region / intermediate / region explicit mentions.
    for col, scope_t in [
        ("Sub-region Name", "sub_region"),
        ("Intermediate Region Name", "intermediate_region"),
        ("Region Name", "region"),
    ]:
        values = [str(v) for v in iso_df[col].dropna().unique().tolist()]
        for v in values:
            vl = v.lower()
            if len(vl) >= 4 and vl in q:
                return scope_t, v

    # Common synonym
    if "sub-saharan africa" in q:
        return "sub_region", "Sub-Saharan Africa"
    return "", ""


def _resolve_scope(
    user_query: str,
    parsed_scope_type: str,
    parsed_scope_name: str,
    parsed_country: str,
) -> dict[str, Any]:
    """Resolve country/region/sub-region scope into concrete ISO3 list + grouping column."""
    iso_df = get_iso_reference_df().dropna(subset=["iso3"]).copy()
    iso_df["iso3"] = iso_df["iso3"].astype(str)

    auto_scope_type, auto_scope_name = _detect_scope_from_query(user_query)
    scope_type = (parsed_scope_type or auto_scope_type or "country").strip().lower()
    scope_name = (parsed_scope_name or auto_scope_name or "").strip()

    if scope_type in {"all_regions", "region_all"}:
        rows = iso_df[iso_df["Region Name"].notna()].copy()
        return {
            "scope_type": "all_regions",
            "scope_name": "All Regions",
            "geo_group_column": "Region Name",
            "iso3_codes": sorted(rows["iso3"].unique().tolist()),
            "country": "All Regions",
            "country_iso3": "MULTI",
        }

    if scope_type in {"all_sub_regions", "all_subregions", "sub_region_all"}:
        rows = iso_df[iso_df["Sub-region Name"].notna()].copy()
        return {
            "scope_type": "all_sub_regions",
            "scope_name": "All Sub-regions",
            "geo_group_column": "Sub-region Name",
            "iso3_codes": sorted(rows["iso3"].unique().tolist()),
            "country": "All Sub-regions",
            "country_iso3": "MULTI",
        }

    if scope_type in {"region", "sub_region", "sub-region", "subregion", "intermediate_region", "intermediate-region"}:
        col = "Region Name"
        normalized_type = "region"
        if scope_type in {"sub_region", "sub-region", "subregion"}:
            col = "Sub-region Name"
            normalized_type = "sub_region"
        elif scope_type in {"intermediate_region", "intermediate-region"}:
            col = "Intermediate Region Name"
            normalized_type = "intermediate_region"

        candidates = [str(v) for v in iso_df[col].dropna().unique().tolist()]
        matched = _fuzzy_match_value(scope_name, candidates)
        if matched:
            rows = iso_df[iso_df[col] == matched].copy()
            return {
                "scope_type": normalized_type,
                "scope_name": matched,
                "geo_group_column": col,
                "iso3_codes": sorted(rows["iso3"].unique().tolist()),
                "country": matched,
                "country_iso3": "MULTI",
            }

    # Default country scope
    country_raw = parsed_country.strip() if parsed_country else ""
    if not country_raw:
        q = user_query.lower()
        country_candidates = [str(v) for v in iso_df["Country or Area"].dropna().unique().tolist()]
        for cand in country_candidates:
            if cand.lower() in q:
                country_raw = cand
                break
    if not country_raw:
        country_raw = "Algeria"
    resolved = _resolve_country(country_raw) or _resolve_country("Algeria")
    if resolved is None:
        raise ValueError("Could not resolve country.")
    country_name, country_iso3 = resolved
    return {
        "scope_type": "country",
        "scope_name": country_name,
        "geo_group_column": "Country or Area",
        "iso3_codes": [country_iso3],
        "country": country_name,
        "country_iso3": country_iso3,
    }


def _extract_year_range_from_text(text: str, current_year: int) -> tuple[int, int]:
    years = [int(y) for y in re.findall(r"\b(19\d{2}|20\d{2})\b", text)]
    if len(years) >= 2:
        a, b = min(years), max(years)
        return a, b
    if len(years) == 1:
        y = years[0]
        return y, current_year
    return current_year - 10, current_year


def _extract_wb_codes_from_text(text: str) -> list[str]:
    # WB code pattern examples: NY.GDP.PCAP.CD, FP.CPI.TOTL.ZG
    # Support 3+ total segments (e.g., SP.POP.TOTL, NY.GDP.MKTP.KD.ZG).
    pattern = r"\b[A-Z]{2}(?:\.[A-Z0-9]{2,}){2,}\b"
    return sorted(set(re.findall(pattern, text)))


def _deterministic_parse(
    user_query: str,
    purpose: str | None,
    current_year: int,
) -> QueryPlan | None:
    """Rule-based parser for explicit queries (robust fallback when LLM parsing fails)."""
    wb_codes = _extract_wb_codes_from_text(user_query.upper())
    if not wb_codes:
        return None

    scope = _resolve_scope(
        user_query=user_query,
        parsed_scope_type="",
        parsed_scope_name="",
        parsed_country="",
    )
    from_year, to_year = _extract_year_range_from_text(user_query, current_year)

    metrics: list[MetricPlan] = []
    for code in wb_codes[:4]:
        metrics.append(
            MetricPlan(
                source="world_bank",
                series_id=code,
                label=code,
                selection_method="deterministic_parse",
                selection_reason="Detected explicit indicator code in user query.",
            )
        )

    # Optional explicit ACLED metric mention
    q = user_query.lower()
    if any(t in q for t in ("conflict", "violence", "fatalit", "acled")):
        sid = "fatalities_sum" if "fatalit" in q else "event_count"
        metrics.append(
            MetricPlan(
                source="acled",
                series_id=sid,
                label="Conflict fatalities" if sid == "fatalities_sum" else "Conflict event count",
                selection_method="deterministic_parse",
                selection_reason="Detected explicit conflict/ACLED intent in user query.",
            )
        )

    return QueryPlan(
        country=scope["country"],
        country_iso3=scope["country_iso3"],
        from_year=from_year,
        to_year=to_year,
        metrics=metrics,
        explanation="Deterministic parser used explicit series codes and scope terms from query.",
        scope_type=scope["scope_type"],
        scope_name=scope["scope_name"],
        geo_group_column=scope["geo_group_column"],
        iso3_codes=scope["iso3_codes"],
        confidence=0.9,
        purpose=(purpose or "").strip(),
        follow_up_questions=[],
    )


def _resolve_metric(
    source: str,
    series_id: str,
    label: str,
    user_query: str,
) -> dict[str, Any] | None:
    """Resolve/repair metric source+series using metadata registry + heuristics."""
    source = (source or "").strip().lower()
    series_id = (series_id or "").strip()
    label = (label or "").strip() or series_id

    allowed = {"world_bank", "acled", "sdg", "uis", "un_data", "un_energy"}
    if source in allowed and series_id:
        return {
            "source": source,
            "series_id": series_id,
            "label": label,
            "selection_method": "llm_direct",
            "selection_reason": "Series selected directly by the LLM plan.",
            "candidates": [],
        }

    search_term = label or series_id or user_query
    hits = search_registry(search_term, limit=10)
    if not hits.empty:
        if source in allowed:
            scoped = hits[hits["source"] == source]
            if not scoped.empty:
                row = scoped.iloc[0]
                candidates = [
                    {"source": str(r["source"]), "series_id": str(r["series_id"]), "series_name": str(r["series_name"])}
                    for _, r in scoped.head(5).iterrows()
                ]
                return {
                    "source": str(row["source"]),
                    "series_id": str(row["series_id"]),
                    "label": label or str(row["series_name"]),
                    "selection_method": "registry_match",
                    "selection_reason": "Resolved using metadata registry search within the requested source.",
                    "candidates": candidates,
                }
        row = hits.iloc[0]
        candidates = [
            {"source": str(r["source"]), "series_id": str(r["series_id"]), "series_name": str(r["series_name"])}
            for _, r in hits.head(5).iterrows()
        ]
        return {
            "source": str(row["source"]),
            "series_id": str(row["series_id"]),
            "label": label or str(row["series_name"]),
            "selection_method": "registry_match",
            "selection_reason": "Resolved using top metadata registry match.",
            "candidates": candidates,
        }

    # Heuristic fallback for common requests.
    q = user_query.lower()
    if "gdp growth" in q:
        return {
            "source": "world_bank",
            "series_id": "NY.GDP.MKTP.KD.ZG",
            "label": label or "GDP growth (annual %)",
            "selection_method": "heuristic",
            "selection_reason": "Heuristic mapping: 'gdp growth' -> WB GDP growth indicator.",
            "candidates": [],
        }
    if "gdp" in q:
        return {
            "source": "world_bank",
            "series_id": "NY.GDP.MKTP.CD",
            "label": label or "GDP (current US$)",
            "selection_method": "heuristic",
            "selection_reason": "Heuristic mapping: 'gdp' -> WB GDP level indicator.",
            "candidates": [],
        }
    if "fatalit" in q:
        return {
            "source": "acled",
            "series_id": "fatalities_sum",
            "label": label or "Conflict fatalities",
            "selection_method": "heuristic",
            "selection_reason": "Heuristic mapping: fatalities terms -> ACLED fatalities.",
            "candidates": [],
        }
    if "conflict" in q or "event" in q or "violence" in q:
        return {
            "source": "acled",
            "series_id": "event_count",
            "label": label or "Conflict event count",
            "selection_method": "heuristic",
            "selection_reason": "Heuristic mapping: conflict/event terms -> ACLED event count.",
            "candidates": [],
        }
    return None


def _augment_metrics(metrics: list[MetricPlan], user_query: str) -> list[MetricPlan]:
    """Ensure key obvious metrics are present when user intent strongly implies them."""
    q = user_query.lower()
    existing = {(m.source, m.series_id) for m in metrics}

    if "gdp" in q and ("world_bank", "NY.GDP.MKTP.CD") not in existing and ("world_bank", "NY.GDP.MKTP.KD.ZG") not in existing:
        metrics.append(
            MetricPlan(
                source="world_bank",
                series_id="NY.GDP.MKTP.CD",
                label="GDP (current US$)",
                selection_method="intent_augmentation",
                selection_reason="Added because query implies GDP but no explicit WB GDP series was selected.",
            )
        )
    if any(t in q for t in ("conflict", "violence", "fatalit", "event")) and not any(m.source == "acled" for m in metrics):
        metrics.append(
            MetricPlan(
                source="acled",
                series_id="event_count",
                label="Conflict event count",
                selection_method="intent_augmentation",
                selection_reason="Added because query implies conflict dynamics but no ACLED metric was selected.",
            )
        )

    dedup: list[MetricPlan] = []
    seen: set[tuple[str, str]] = set()
    for m in metrics:
        k = (m.source, m.series_id)
        if k in seen:
            continue
        seen.add(k)
        dedup.append(m)
    return dedup


def parse_query_plan(user_query: str, purpose: str | None = None) -> QueryPlan:
    """Parse natural language into a structured multi-source query plan."""
    current_year = date.today().year

    deterministic = _deterministic_parse(user_query, purpose, current_year)
    if deterministic is not None:
        return deterministic

    # Retrieve metadata hints for LLM grounding
    hints_df = search_registry(user_query, limit=20)
    hints = []
    if not hints_df.empty:
        for _, r in hints_df.iterrows():
            hints.append(f"{r['source']}::{r['series_id']}::{r['series_name']}")

    system_prompt = f"""You are a query planner for cross-source development analytics.

TODAY_YEAR: {current_year}

Your task: extract a machine-readable plan from a user query.

Return JSON only with keys:
- country (string)
- scope_type (country|region|sub_region|intermediate_region|all_regions)
- scope_name (name of region/sub-region/intermediate region when applicable)
- from_year (int)
- to_year (int)
- metrics (array of objects with keys: source, series_id, label)
- explanation (string)
- confidence (float between 0 and 1)
- purpose (short sentence about analysis goal)

Allowed sources: world_bank, acled, sdg, uis, un_data, un_energy.

Geographic scope rules:
- If user asks "all regions", set scope_type=all_regions and scope_name="All Regions".
- If user asks by sub-region (e.g., Sub-Saharan Africa), set scope_type=sub_region and scope_name accordingly.
- If user asks a named region (e.g., Africa, Europe), set scope_type=region and scope_name.
- For a single country question, use scope_type=country and set country.

Special metric mapping for ACLED:
- conflict count / number of conflicts -> source=acled, series_id=event_count
- fatalities -> source=acled, series_id=fatalities_sum

When user asks GDP and does not specify exact WB code, use NY.GDP.MKTP.CD.
When user asks GDP growth use NY.GDP.MKTP.KD.ZG.

Use year defaults:
- no years mentioned: from_year={current_year - 10}, to_year={current_year}
- "latest" means include up to {current_year}

Metadata hints (use if relevant):
{chr(10).join(hints) if hints else '(none)'}
"""

    parsed = None
    try:
        llm = get_llm(temperature=0)
        response = llm.invoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_query),
            ]
        )
        content = response.content if hasattr(response, "content") else str(response)
        parsed = _extract_json_block(content)
    except Exception:
        logger.exception("LLM query planning failed")

    if not isinstance(parsed, dict):
        parsed = _default_plan_from_query(user_query)

    scope = _resolve_scope(
        user_query=user_query,
        parsed_scope_type=str(parsed.get("scope_type", "") or ""),
        parsed_scope_name=str(parsed.get("scope_name", "") or ""),
        parsed_country=str(parsed.get("country", "") or ""),
    )

    from_year = int(parsed.get("from_year") or (current_year - 10))
    to_year = int(parsed.get("to_year") or current_year)
    if from_year > to_year:
        from_year, to_year = to_year, from_year

    metric_rows = parsed.get("metrics") or []
    metrics: list[MetricPlan] = []
    for m in metric_rows:
        try:
            src = str(m.get("source", "")).strip().lower()
            sid = str(m.get("series_id", "")).strip()
            lbl = str(m.get("label", sid)).strip() or sid
            resolved_metric = _resolve_metric(src, sid, lbl, user_query)
            if resolved_metric:
                metrics.append(
                    MetricPlan(
                        source=resolved_metric["source"],
                        series_id=resolved_metric["series_id"],
                        label=resolved_metric["label"],
                        selection_method=resolved_metric.get("selection_method", "llm"),
                        selection_reason=resolved_metric.get("selection_reason", ""),
                        candidates=resolved_metric.get("candidates", []),
                    )
                )
        except Exception:
            continue

    if not metrics:
        fallback = _default_plan_from_query(user_query)["metrics"]
        metrics = [MetricPlan(source=m["source"], series_id=m["series_id"], label=m["label"]) for m in fallback]
    else:
        metrics = _augment_metrics(metrics, user_query)

    try:
        confidence = float(parsed.get("confidence", 0.5))
    except Exception:
        confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))

    parsed_purpose = str(parsed.get("purpose", "") or "").strip()
    final_purpose = (purpose or parsed_purpose or "").strip()
    follow_ups: list[str] = []
    if not final_purpose:
        follow_ups.append("What decision or policy question should this analysis support?")
        follow_ups.append("Is your goal explanation, forecasting, monitoring, or benchmarking?")

    return QueryPlan(
        country=scope["country"],
        country_iso3=scope["country_iso3"],
        scope_type=scope["scope_type"],
        scope_name=scope["scope_name"],
        geo_group_column=scope["geo_group_column"],
        iso3_codes=scope["iso3_codes"],
        from_year=from_year,
        to_year=to_year,
        metrics=metrics,
        explanation=str(parsed.get("explanation") or "Plan generated from query."),
        confidence=confidence,
        purpose=final_purpose,
        follow_up_questions=follow_ups,
    )
