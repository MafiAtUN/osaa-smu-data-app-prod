"""Metadata ingestion and search for Cross-Source Studio.

Fetches and indexes indicator metadata from multiple data sources (World Bank,
ACLED, UN SDG) into the local DuckDB metadata store, and exposes a keyword-
search interface used by the query planner.  Key exports: ``ingest_all_metadata``,
``search_metadata``, and per-source ingest helpers such as ``ingest_wb_metadata``.
"""

from __future__ import annotations

from typing import Any

import wbgapi as wb

from app.core.logging import get_logger
from app.services.cross_source.db import (
    list_metadata_counts,
    log_refresh,
    search_metadata_series,
    upsert_metadata_rows,
)
from app.services.geo_service import ACLED_SUB_EVENT_TYPES
from app.services.sdg_service import get_data, get_sdg_base_url
from app.services.undata_service import (
    CATEGORY_LABELS,
    get_catalogue,
    get_uis_series,
)
from app.services.wb_service import _WB_INDICATOR_CATALOGUE

logger = get_logger(__name__)


def _load_wb_metadata() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        for item in wb.series.list():
            sid = str(item.get("id") or item.get("code") or "").strip()
            name = str(item.get("value") or item.get("name") or sid).strip()
            if not sid:
                continue
            rows.append(
                {
                    "source": "world_bank",
                    "series_id": sid,
                    "series_name": name,
                    "description": name,
                    "unit": "",
                    "dimensions": ["country_iso3", "year"],
                    "tags": ["world bank", "wdi", "development"],
                }
            )
    except Exception as exc:
        logger.warning("Could not fetch full WB series list, using curated catalogue: %s", exc)
        for sid, name in _WB_INDICATOR_CATALOGUE.items():
            rows.append(
                {
                    "source": "world_bank",
                    "series_id": sid,
                    "series_name": name,
                    "description": name,
                    "unit": "",
                    "dimensions": ["country_iso3", "year"],
                    "tags": ["world bank", "wdi", "development"],
                }
            )
    return rows


def _load_acled_metadata() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    rows.append(
        {
            "source": "acled",
            "series_id": "event_count",
            "series_name": "Conflict event count",
            "description": "Number of ACLED events in the selected period",
            "unit": "events",
            "dimensions": ["country_name", "date", "year", "sub_event_type"],
            "tags": ["acled", "conflict", "events"],
        }
    )
    rows.append(
        {
            "source": "acled",
            "series_id": "fatalities_sum",
            "series_name": "Conflict fatalities",
            "description": "Sum of fatalities in ACLED events",
            "unit": "fatalities",
            "dimensions": ["country_name", "date", "year", "sub_event_type"],
            "tags": ["acled", "conflict", "fatalities"],
        }
    )

    for subtype in ACLED_SUB_EVENT_TYPES:
        sid = f"sub_event::{subtype}"
        rows.append(
            {
                "source": "acled",
                "series_id": sid,
                "series_name": f"ACLED events: {subtype}",
                "description": f"Event count filtered to ACLED sub-event type '{subtype}'",
                "unit": "events",
                "dimensions": ["country_name", "date", "year"],
                "tags": ["acled", "conflict", "event type", subtype.lower()],
            }
        )
    return rows


def _load_undata_metadata() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in get_catalogue():
        sid = str(item.get("id", "")).strip()
        if not sid:
            continue
        cat = str(item.get("category", "")).strip()
        cat_name = CATEGORY_LABELS.get(cat, cat)
        name = str(item.get("name") or sid)
        rows.append(
            {
                "source": "un_data",
                "series_id": sid,
                "series_name": name,
                "description": f"{name} | Category: {cat_name}",
                "unit": "",
                "dimensions": ["geography_code", "year"],
                "tags": ["un data", "sdg", cat_name.lower()],
            }
        )
    return rows


def _load_uis_metadata() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for sid, name in get_uis_series().items():
        rows.append(
            {
                "source": "uis",
                "series_id": sid,
                "series_name": name,
                "description": name,
                "unit": "",
                "dimensions": ["iso3", "year"],
                "tags": ["unesco", "uis", "education"],
            }
        )
    return rows


def _load_sdg_metadata() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        base_url = get_sdg_base_url()
        indicators = get_data(f"{base_url}/v1/sdg/Indicator/List")
        if isinstance(indicators, list):
            for item in indicators:
                sid = str(item.get("code", "")).strip()
                name = str(item.get("description") or item.get("title") or sid).strip()
                if not sid:
                    continue
                rows.append(
                    {
                        "source": "sdg",
                        "series_id": sid,
                        "series_name": name,
                        "description": name,
                        "unit": "",
                        "dimensions": ["m49", "year"],
                        "tags": ["un sdg", "sdg"],
                    }
                )
    except Exception as exc:
        logger.warning("Could not load SDG metadata from API: %s", exc)

    if rows:
        return rows

    # Conservative fallback when SDG metadata endpoint is unavailable.
    fallback = {
        "7.1.1": "Population with access to electricity",
        "4.1.1": "Minimum proficiency in reading and mathematics",
        "3.2.1": "Under-five mortality rate",
        "1.1.1": "Population below international poverty line",
        "13.2.2": "Total greenhouse gas emissions per year",
    }
    return [
        {
            "source": "sdg",
            "series_id": sid,
            "series_name": name,
            "description": name,
            "unit": "",
            "dimensions": ["m49", "year"],
            "tags": ["un sdg", "sdg"],
        }
        for sid, name in fallback.items()
    ]


_SOURCE_LOADERS = {
    "world_bank": _load_wb_metadata,
    "acled": _load_acled_metadata,
    "sdg": _load_sdg_metadata,
    "un_data": _load_undata_metadata,
    "uis": _load_uis_metadata,
}


def refresh_metadata_registry(sources: list[str] | None = None) -> dict[str, int]:
    """Fetch and persist metadata for selected sources (or all configured sources)."""
    counts: dict[str, int] = {}
    requested = sources or list(_SOURCE_LOADERS.keys())

    for source in requested:
        loader = _SOURCE_LOADERS.get(source)
        if loader is None:
            counts[source] = 0
            log_refresh("refresh_metadata", source, "error", "unsupported source")
            continue
        try:
            rows = loader()
            written = upsert_metadata_rows(rows)
            counts[source] = written
            log_refresh("refresh_metadata", source, "ok", f"rows={written}")
        except Exception as exc:
            logger.exception("Metadata refresh failed for %s", source)
            counts[source] = 0
            log_refresh("refresh_metadata", source, "error", str(exc))

    return counts


def search_registry(query_text: str, limit: int = 30):
    """Search all metadata rows using fuzzy SQL LIKE matching."""
    return search_metadata_series(query_text, limit=limit)


def get_registry_counts():
    """Return metadata counts grouped by source."""
    return list_metadata_counts()
