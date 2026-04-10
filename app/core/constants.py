"""Application-wide shared constants.

Single source of truth for display names, source labels, and cache TTL
values that are referenced across multiple modules.  Import from here
rather than hard-coding the same strings in individual files.

Usage::

    from app.core.constants import PAGE_DISPLAY_NAMES, SOURCE_DISPLAY_LABELS, CACHE_TTL_HOURS
"""

from __future__ import annotations

# ── Page display names ───────────────────────────────────────────────────────
# Maps the short route/page-key used internally (e.g. by chat_history_service)
# to a human-readable label shown in the UI.
PAGE_DISPLAY_NAMES: dict[str, str] = {
    "acled": "ACLED Conflict",
    "wb": "World Bank",
    "sdg": "SDG Indicators",
    "dashboard": "Data Explorer",
    "cross_source_studio": "Cross-Source Studio",
    "cross_source_sync": "Hybrid Sync",
    "chatbot": "OSAA Chatbot",
    "check_analysis": "Analysis Checker",
    "pid_checker": "PID Checker",
    "chat_library": "Chat Library",
    "un_education": "UNESCO Education",
    "un_energy": "UN Energy",
    "un_data_explorer": "SDG Explorer",
    "home": "Home",
}

# ── Data source display labels ────────────────────────────────────────────────
# Maps short API-key names to the labels shown in the sync dashboard and logs.
SOURCE_DISPLAY_LABELS: dict[str, str] = {
    "wb": "World Bank",
    "acled": "ACLED",
    "sdg": "UN SDG",
    "uis": "UNESCO UIS",
    "undata": "UN Data",
}

# ── Cross-source cache TTLs (hours) ─────────────────────────────────────────
# Controls how long fetched data slices are retained in the DuckDB cache
# before being considered stale and re-fetched on the next request.
# Higher values reduce API load; lower values ensure fresher data.
CACHE_TTL_HOURS: dict[str, int] = {
    "acled": 24,    # ACLED updates daily
    "wb": 96,       # World Bank updates infrequently; 4-day TTL is safe
    "sdg": 72,      # UN SDG API is stable; 3-day TTL
    "uis": 120,     # UNESCO UIS updates rarely; 5-day TTL
    "undata": 120,  # UN Data endpoint updates rarely; 5-day TTL
}
