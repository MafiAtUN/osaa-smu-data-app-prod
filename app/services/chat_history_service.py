"""DuckDB-backed persistent chat history service.

Stores analysis conversations so users can browse, filter, and revisit past
sessions from any dashboard. Each session maps to one DataFrame + one topic.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import duckdb
import pandas as pd

from app.core.logging import get_logger

logger = get_logger(__name__)

_DB_PATH = Path("content/db.duckdb")

# ---------------------------------------------------------------------------
# Schema init
# ---------------------------------------------------------------------------

_DDL = """
CREATE TABLE IF NOT EXISTS chat_sessions (
    id          VARCHAR PRIMARY KEY,
    name        VARCHAR NOT NULL,
    page        VARCHAR,
    dataset_name VARCHAR,
    dataset_hash VARCHAR,
    topic       VARCHAR,
    tags        VARCHAR DEFAULT '[]',
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    message_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id          VARCHAR PRIMARY KEY,
    session_id  VARCHAR NOT NULL,
    role        VARCHAR NOT NULL,
    content     TEXT    NOT NULL,
    has_code    BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def _con() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(_DB_PATH))


def init_chat_tables() -> None:
    """Create chat tables if they do not exist (idempotent)."""
    with _con() as con:
        for stmt in _DDL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                con.execute(stmt)


# ---------------------------------------------------------------------------
# Tagging helpers
# ---------------------------------------------------------------------------

_TAG_KEYWORDS: dict[str, str] = {
    "fatalities": "fatalities",
    "conflict": "conflict",
    "protest": "protests",
    "attack": "attacks",
    "military": "military",
    "civilian": "civilians",
    "trend": "trends",
    "time series": "time-series",
    "comparison": "comparison",
    "distribution": "distribution",
    "country": "country",
    "region": "region",
    "average": "statistics",
    "total": "statistics",
    "count": "statistics",
    "correlation": "correlation",
    "forecast": "forecast",
    "indicator": "indicators",
    "gdp": "economics",
    "poverty": "poverty",
    "education": "education",
    "health": "health",
    "climate": "climate",
}

_PAGE_TOPICS: dict[str, str] = {
    "acled": "Conflict Analysis",
    "wb": "World Bank Data",
    "sdg": "SDG Indicators",
    "generic": "General Data",
}


def _auto_tag(text: str) -> list[str]:
    found: list[str] = []
    lower = text.lower()
    for kw, tag in _TAG_KEYWORDS.items():
        if kw in lower and tag not in found:
            found.append(tag)
    return found[:6]


def _guess_topic(text: str, page: str) -> str:
    lower = text.lower()
    if any(w in lower for w in ["trend", "over time", "year", "month", "time series"]):
        return "Temporal Trends"
    if any(w in lower for w in ["country", "region", "geographic", "map", "spatial"]):
        return "Geographic Analysis"
    if any(w in lower for w in ["compare", " vs ", "versus", "difference", "ranking"]):
        return "Comparative Analysis"
    if any(w in lower for w in ["distribut", "histogram", "spread", "outlier"]):
        return "Distribution Analysis"
    if any(w in lower for w in ["correlat", "relationship", "scatter"]):
        return "Correlation Analysis"
    return _PAGE_TOPICS.get(page, "Data Analysis")


# ---------------------------------------------------------------------------
# Write operations
# ---------------------------------------------------------------------------

def create_session(
    page: str,
    dataset_name: str,
    dataset_hash: str,
    first_message: str,
) -> str | None:
    """Create a new chat session. Returns the session ID, or None on DB error."""
    try:
        init_chat_tables()
        session_id = str(uuid.uuid4())
        name = first_message[:70] + ("…" if len(first_message) > 70 else "")
        topic = _guess_topic(first_message, page)
        tags = json.dumps(_auto_tag(first_message))
        with _con() as con:
            con.execute(
                """INSERT INTO chat_sessions
                   (id, name, page, dataset_name, dataset_hash, topic, tags)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [session_id, name, page, dataset_name, dataset_hash, topic, tags],
            )
        return session_id
    except Exception as exc:
        logger.warning("create_session failed: %s", exc)
        return None


def save_message(session_id: str, role: str, content: str) -> None:
    """Append a message to a session and keep counters / tags up to date."""
    try:
        init_chat_tables()
        msg_id = str(uuid.uuid4())
        has_code = "```" in content
        with _con() as con:
            con.execute(
                """INSERT INTO chat_messages (id, session_id, role, content, has_code)
                   VALUES (?, ?, ?, ?, ?)""",
                [msg_id, session_id, role, content, has_code],
            )
            con.execute(
                """UPDATE chat_sessions
                   SET message_count = message_count + 1,
                       updated_at    = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                [session_id],
            )
            # Merge auto-tags derived from this message into the session
            row = con.execute("SELECT tags FROM chat_sessions WHERE id = ?", [session_id]).fetchone()
            if row:
                existing: list[str] = json.loads(row[0] or "[]")
                merged = list(dict.fromkeys(existing + _auto_tag(content)))[:8]
                con.execute(
                    "UPDATE chat_sessions SET tags = ? WHERE id = ?",
                    [json.dumps(merged), session_id],
                )
    except Exception as exc:
        logger.warning("save_message failed (session=%s): %s", session_id, exc)


# ---------------------------------------------------------------------------
# Read operations
# ---------------------------------------------------------------------------

def get_sessions(
    page: str | None = None,
    topic: str | None = None,
    tags: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    search: str | None = None,
    limit: int = 150,
) -> pd.DataFrame:
    """Return sessions matching the given filters as a DataFrame."""
    try:
        init_chat_tables()
        clauses: list[str] = []
        params: list = []

        if page:
            clauses.append("page = ?")
            params.append(page)
        if topic:
            clauses.append("topic = ?")
            params.append(topic)
        if tags:
            tag_clauses = ["tags LIKE ?" for _ in tags]
            clauses.append(f"({' OR '.join(tag_clauses)})")
            params.extend([f'%"{t}"%' for t in tags])
        if date_from:
            clauses.append("created_at >= ?")
            params.append(date_from)
        if date_to:
            clauses.append("created_at <= ?")
            params.append(date_to + " 23:59:59")
        if search:
            clauses.append("(name ILIKE ? OR dataset_name ILIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        with _con() as con:
            return con.execute(
                f"SELECT * FROM chat_sessions {where} ORDER BY updated_at DESC LIMIT ?",
                params + [limit],
            ).df()
    except Exception as exc:
        logger.warning("get_sessions failed: %s", exc)
        return pd.DataFrame()


def get_messages(session_id: str) -> pd.DataFrame:
    """Return all messages for a session ordered by time."""
    try:
        init_chat_tables()
        with _con() as con:
            return con.execute(
                """SELECT role, content, has_code, created_at
                   FROM chat_messages
                   WHERE session_id = ?
                   ORDER BY created_at""",
                [session_id],
            ).df()
    except Exception as exc:
        logger.warning("get_messages failed (session=%s): %s", session_id, exc)
        return pd.DataFrame()


def get_session_count() -> int:
    """Return the total number of stored chat sessions."""
    try:
        init_chat_tables()
        with _con() as con:
            return con.execute("SELECT COUNT(*) FROM chat_sessions").fetchone()[0]
    except Exception as exc:
        logger.warning("get_session_count failed: %s", exc)
        return 0


def get_all_topics() -> list[str]:
    """Return sorted list of distinct topic values stored in the DB."""
    try:
        init_chat_tables()
        with _con() as con:
            rows = con.execute(
                "SELECT DISTINCT topic FROM chat_sessions WHERE topic IS NOT NULL ORDER BY topic"
            ).fetchall()
        return [r[0] for r in rows]
    except Exception as exc:
        logger.warning("get_all_topics failed: %s", exc)
        return []


def get_all_tags() -> list[str]:
    """Return sorted list of all unique tags across all sessions."""
    try:
        init_chat_tables()
        with _con() as con:
            rows = con.execute("SELECT tags FROM chat_sessions").fetchall()
        all_tags: set[str] = set()
        for row in rows:
            try:
                all_tags.update(json.loads(row[0] or "[]"))
            except Exception:
                pass
        return sorted(all_tags)
    except Exception as exc:
        logger.warning("get_all_tags failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Delete operations
# ---------------------------------------------------------------------------

def delete_session(session_id: str) -> None:
    """Delete a session and all of its messages."""
    try:
        with _con() as con:
            con.execute("DELETE FROM chat_messages WHERE session_id = ?", [session_id])
            con.execute("DELETE FROM chat_sessions WHERE id = ?", [session_id])
    except Exception as exc:
        logger.warning("delete_session failed (session=%s): %s", session_id, exc)


def clear_all_sessions() -> None:
    """Wipe all sessions and messages (use with care)."""
    try:
        with _con() as con:
            con.execute("DELETE FROM chat_messages")
            con.execute("DELETE FROM chat_sessions")
    except Exception as exc:
        logger.warning("clear_all_sessions failed: %s", exc)
