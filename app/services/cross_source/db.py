"""DuckDB storage for Cross-Source Studio metadata and dataset cache.

Manages a persistent DuckDB database that stores indicator metadata (sourced
from World Bank, ACLED, UN SDG, and other APIs) and a time-stamped dataset
cache used by the hybrid sync pipeline.  Key exports: ``get_db_connection``,
``upsert_metadata``, ``get_cached_dataset``, and ``store_cached_dataset``.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

DB_PATH = Path("content/cross_source.duckdb")


def _con() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(DB_PATH))


def init_storage() -> None:
    """Create storage tables (idempotent)."""
    with _con() as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS xsrc_metadata_series (
                source          VARCHAR NOT NULL,
                series_id       VARCHAR NOT NULL,
                series_name     VARCHAR,
                description     VARCHAR,
                unit            VARCHAR,
                dimensions      VARCHAR DEFAULT '[]',
                tags            VARCHAR DEFAULT '[]',
                updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (source, series_id)
            )
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS xsrc_cache (
                cache_key        VARCHAR PRIMARY KEY,
                source           VARCHAR NOT NULL,
                metric_id        VARCHAR NOT NULL,
                country_iso3     VARCHAR,
                start_year       INTEGER,
                end_year         INTEGER,
                grain            VARCHAR,
                payload_json     TEXT NOT NULL,
                fetched_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at       TIMESTAMP,
                row_count        INTEGER DEFAULT 0,
                payload_hash     VARCHAR
            )
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS xsrc_materialized_results (
                result_key        VARCHAR PRIMARY KEY,
                query_text        TEXT,
                merged_json       TEXT NOT NULL,
                fetched_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at        TIMESTAMP,
                row_count         INTEGER DEFAULT 0
            )
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS xsrc_refresh_log (
                id              BIGINT,
                action          VARCHAR,
                source          VARCHAR,
                status          VARCHAR,
                details         VARCHAR,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def make_cache_key(
    source: str,
    metric_id: str,
    country_iso3: str,
    start_year: int,
    end_year: int,
    grain: str,
    extra: dict[str, Any] | None = None,
) -> str:
    data = {
        "source": source,
        "metric_id": metric_id,
        "country_iso3": country_iso3,
        "start_year": start_year,
        "end_year": end_year,
        "grain": grain,
        "extra": extra or {},
    }
    digest = hashlib.sha256(json.dumps(data, sort_keys=True).encode("utf-8")).hexdigest()
    return digest[:32]


def read_cache(cache_key: str) -> pd.DataFrame | None:
    init_storage()
    with _con() as con:
        row = con.execute(
            """
            SELECT payload_json, expires_at
            FROM xsrc_cache
            WHERE cache_key = ?
            """,
            [cache_key],
        ).fetchone()

    if not row:
        return None

    payload_json, expires_at = row
    if expires_at is not None:
        if datetime.now(timezone.utc).replace(tzinfo=None) > expires_at:
            return None

    try:
        records = json.loads(payload_json)
        return pd.DataFrame(records)
    except Exception:
        return None


def read_yearly_cached_slice(
    source: str,
    metric_id: str,
    country_iso3: str,
    start_year: int,
    end_year: int,
    value_label: str,
) -> tuple[pd.DataFrame, list[int]]:
    """Read overlapping yearly cache rows and return (cached_df, missing_years)."""
    init_storage()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with _con() as con:
        rows = con.execute(
            """
            SELECT payload_json
            FROM xsrc_cache
            WHERE source = ?
              AND metric_id = ?
              AND country_iso3 = ?
              AND grain = 'year'
              AND (expires_at IS NULL OR expires_at > ?)
              AND NOT (end_year < ? OR start_year > ?)
            """,
            [source, metric_id, country_iso3, now, start_year, end_year],
        ).fetchall()

    if not rows:
        default_key = "geo_group" if ":" in country_iso3 else "iso3"
        return pd.DataFrame(columns=[default_key, "year", value_label]), list(range(start_year, end_year + 1))

    parts: list[pd.DataFrame] = []
    key_col = "iso3"
    for (payload,) in rows:
        try:
            df = pd.DataFrame(json.loads(payload))
            if df.empty:
                continue
            if "year" not in df.columns:
                continue
            if "geo_group" in df.columns:
                key_col = "geo_group"
            elif "iso3" not in df.columns:
                df["iso3"] = country_iso3

            # Normalize value column name to the requested label.
            if value_label not in df.columns:
                candidates = [c for c in df.columns if c not in ("iso3", "geo_group", "year", "country", "scope")]
                if len(candidates) == 1:
                    df = df.rename(columns={candidates[0]: value_label})
                elif candidates:
                    # Prefer first numeric-looking column
                    chosen = candidates[0]
                    for c in candidates:
                        if pd.api.types.is_numeric_dtype(df[c]):
                            chosen = c
                            break
                    df = df.rename(columns={chosen: value_label})
            if value_label in df.columns:
                if key_col == "geo_group" and "geo_group" in df.columns:
                    parts.append(df[["geo_group", "year", value_label]].copy())
                else:
                    if "iso3" not in df.columns:
                        df["iso3"] = country_iso3
                    parts.append(df[["iso3", "year", value_label]].copy())
        except Exception:
            continue

    if not parts:
        default_key = "geo_group" if ":" in country_iso3 else "iso3"
        return pd.DataFrame(columns=[default_key, "year", value_label]), list(range(start_year, end_year + 1))

    merged = pd.concat(parts, ignore_index=True)
    merged["year"] = pd.to_numeric(merged["year"], errors="coerce").astype("Int64")
    merged = merged.dropna(subset=["year"])
    merged["year"] = merged["year"].astype(int)
    merged = merged[(merged["year"] >= start_year) & (merged["year"] <= end_year)]
    dedup_key = "geo_group" if "geo_group" in merged.columns else "iso3"
    if dedup_key in merged.columns:
        merged = merged.sort_values([dedup_key, "year"]).drop_duplicates(subset=[dedup_key, "year"], keep="last")

    covered = set(merged["year"].dropna().astype(int).tolist())
    missing = [y for y in range(start_year, end_year + 1) if y not in covered]
    return merged.reset_index(drop=True), missing


def write_cache(
    cache_key: str,
    source: str,
    metric_id: str,
    country_iso3: str,
    start_year: int,
    end_year: int,
    grain: str,
    df: pd.DataFrame,
    ttl_hours: int = 72,
) -> None:
    init_storage()
    records = df.to_dict(orient="records")
    payload = json.dumps(records, default=str)
    payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)

    with _con() as con:
        con.execute(
            """
            INSERT OR REPLACE INTO xsrc_cache (
                cache_key, source, metric_id, country_iso3, start_year, end_year,
                grain, payload_json, fetched_at, expires_at, row_count, payload_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?)
            """,
            [
                cache_key,
                source,
                metric_id,
                country_iso3,
                start_year,
                end_year,
                grain,
                payload,
                expires_at,
                len(df),
                payload_hash,
            ],
        )


def write_materialized_result(
    query_text: str,
    merged_df: pd.DataFrame,
    ttl_hours: int = 24,
) -> str:
    init_storage()
    key_raw = f"{query_text}|{sorted(merged_df.columns.tolist())}|{merged_df.shape}"
    result_key = hashlib.sha256(key_raw.encode("utf-8")).hexdigest()[:32]
    payload = json.dumps(merged_df.to_dict(orient="records"), default=str)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)

    with _con() as con:
        con.execute(
            """
            INSERT OR REPLACE INTO xsrc_materialized_results (
                result_key, query_text, merged_json, fetched_at, expires_at, row_count
            ) VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?, ?)
            """,
            [result_key, query_text, payload, expires_at, len(merged_df)],
        )
    return result_key


def read_materialized_result(result_key: str) -> pd.DataFrame | None:
    init_storage()
    with _con() as con:
        row = con.execute(
            """
            SELECT merged_json, expires_at
            FROM xsrc_materialized_results
            WHERE result_key = ?
            """,
            [result_key],
        ).fetchone()

    if not row:
        return None

    payload, expires_at = row
    if expires_at is not None and datetime.now(timezone.utc).replace(tzinfo=None) > expires_at:
        return None

    try:
        return pd.DataFrame(json.loads(payload))
    except Exception:
        return None


def upsert_metadata_rows(rows: list[dict[str, Any]]) -> int:
    """Insert or replace metadata rows. Returns number of rows written."""
    if not rows:
        return 0

    init_storage()
    with _con() as con:
        for r in rows:
            con.execute(
                """
                INSERT OR REPLACE INTO xsrc_metadata_series (
                    source, series_id, series_name, description, unit, dimensions, tags, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                [
                    r.get("source", ""),
                    r.get("series_id", ""),
                    r.get("series_name", ""),
                    r.get("description", ""),
                    r.get("unit", ""),
                    json.dumps(r.get("dimensions", []), default=str),
                    json.dumps(r.get("tags", []), default=str),
                ],
            )
    return len(rows)


def search_metadata_series(query_text: str, limit: int = 30) -> pd.DataFrame:
    init_storage()
    q = f"%{query_text.lower()}%"
    with _con() as con:
        return con.execute(
            """
            SELECT source, series_id, series_name, description, unit, tags, updated_at
            FROM xsrc_metadata_series
            WHERE lower(series_id) LIKE ?
               OR lower(series_name) LIKE ?
               OR lower(description) LIKE ?
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            [q, q, q, limit],
        ).df()


def list_metadata_counts() -> pd.DataFrame:
    init_storage()
    with _con() as con:
        return con.execute(
            """
            SELECT source, COUNT(*) AS series_count
            FROM xsrc_metadata_series
            GROUP BY source
            ORDER BY source
            """
        ).df()


def log_refresh(action: str, source: str, status: str, details: str = "") -> None:
    init_storage()
    with _con() as con:
        next_id = con.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM xsrc_refresh_log").fetchone()[0]
        con.execute(
            """
            INSERT INTO xsrc_refresh_log (id, action, source, status, details)
            VALUES (?, ?, ?, ?, ?)
            """,
            [next_id, action, source, status, details[:1000]],
        )


def get_cache_source_summary() -> pd.DataFrame:
    """Return cache availability summary grouped by source."""
    init_storage()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with _con() as con:
        return con.execute(
            """
            SELECT
                source,
                COUNT(*) AS cache_entries,
                COUNT(DISTINCT metric_id) AS indicator_count,
                COALESCE(SUM(row_count), 0) AS cached_rows,
                MIN(start_year) AS min_year,
                MAX(end_year) AS max_year,
                MAX(fetched_at) AS last_fetch_at,
                SUM(CASE WHEN expires_at IS NULL OR expires_at > ? THEN 1 ELSE 0 END) AS active_entries
            FROM xsrc_cache
            GROUP BY source
            ORDER BY source
            """,
            [now],
        ).df()


def get_cache_metric_availability(source: str = "", limit: int = 300) -> pd.DataFrame:
    """Return per-metric cache availability details (optionally filtered by source)."""
    init_storage()
    source = (source or "").strip()
    with _con() as con:
        if source:
            return con.execute(
                """
                SELECT
                    source,
                    metric_id,
                    COUNT(*) AS cache_entries,
                    COUNT(DISTINCT country_iso3) AS scope_count,
                    COALESCE(SUM(row_count), 0) AS cached_rows,
                    MIN(start_year) AS min_year,
                    MAX(end_year) AS max_year,
                    MAX(fetched_at) AS last_fetch_at
                FROM xsrc_cache
                WHERE source = ?
                GROUP BY source, metric_id
                ORDER BY last_fetch_at DESC, metric_id
                LIMIT ?
                """,
                [source, limit],
            ).df()
        return con.execute(
            """
            SELECT
                source,
                metric_id,
                COUNT(*) AS cache_entries,
                COUNT(DISTINCT country_iso3) AS scope_count,
                COALESCE(SUM(row_count), 0) AS cached_rows,
                MIN(start_year) AS min_year,
                MAX(end_year) AS max_year,
                MAX(fetched_at) AS last_fetch_at
            FROM xsrc_cache
            GROUP BY source, metric_id
            ORDER BY last_fetch_at DESC, source, metric_id
            LIMIT ?
            """,
            [limit],
        ).df()


def get_refresh_logs(limit: int = 200) -> pd.DataFrame:
    """Return sync/refresh audit logs newest first."""
    init_storage()
    with _con() as con:
        return con.execute(
            """
            SELECT id, action, source, status, details, created_at
            FROM xsrc_refresh_log
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            [limit],
        ).df()
