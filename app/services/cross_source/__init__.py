"""Cross-source query modules (isolated from existing dashboards)."""

from app.services.cross_source.db import init_storage
from app.services.cross_source.execution import execute_plan
from app.services.cross_source.metadata import (
    get_registry_counts,
    refresh_metadata_registry,
    search_registry,
)
from app.services.cross_source.planner import parse_query_plan
from app.services.cross_source.sync import (
    default_year_window,
    get_hybrid_sync_dashboard,
    run_hybrid_sync,
    run_metadata_sync,
)

__all__ = [
    "init_storage",
    "refresh_metadata_registry",
    "get_registry_counts",
    "search_registry",
    "parse_query_plan",
    "execute_plan",
    "run_metadata_sync",
    "run_hybrid_sync",
    "get_hybrid_sync_dashboard",
    "default_year_window",
]
