# Architecture

## Overview

The SMU Data App is a multi-page Streamlit application. It follows a
**service-component-page** pattern:

- **Pages** contain only widget definitions, calls to services/components, and
  rendering of results. No business logic.
- **Services** encapsulate data access, API integration, and LLM client
  management. They are framework-agnostic (except for caching decorators).
- **Components** are reusable UI building blocks (charts, filters, analysis
  widgets) that pages compose together.

## Directory Layout

```
app/
├── main.py                # Single Streamlit entry point
├── pages/                 # Thin UI controllers (one per page)
│   ├── home.py
│   ├── dashboard.py
│   ├── wb_dashboard.py
│   ├── sdg_dashboard.py
│   ├── sdg_dashboard_ai.py
│   ├── acled_dashboard.py
│   ├── acled_dashboard_ai.py
│   ├── chatbot.py
│   ├── check_analysis.py
│   └── pid_checker.py
├── core/                  # Cross-cutting concerns
│   ├── config.py          # Typed settings from env / st.secrets
│   ├── logging.py         # Structured logger with secret redaction
│   └── errors.py          # Custom exception hierarchy
├── services/              # Business logic and data access
│   ├── llm_service.py     # Azure OpenAI client creation + proxy patches
│   ├── acled_service.py   # ACLED API auth, fetching, AI query parsing
│   ├── sdg_service.py     # UN SDG API fetching, AI query parsing
│   ├── wb_service.py      # World Bank API via wbgapi
│   ├── data_service.py    # DuckDB, vectorstore, file uploads
│   └── geo_service.py     # ISO reference data, regions, fuzzy matching
├── components/            # Reusable UI blocks
│   ├── analysis.py        # LLM data analysis + graph maker chatbot
│   ├── charts.py          # Time-series, choropleth, heatmap wrappers
│   ├── tables.py          # Summary stats, PyGWalker, Mitosheet
│   └── filters.py         # Column/value filters
└── assets/
    └── OSAA-Data-logo.svg
```

## Key Design Decisions

### Single Entry Point
`app/main.py` is the only file passed to `streamlit run`. It registers all
pages with `st.navigation()` and groups them into **Data Sources** and
**Tools** in the sidebar.

### Centralized Configuration
`app/core/config.py` exposes a frozen `Settings` dataclass populated from
`os.environ` and `st.secrets`. Pages never call `os.getenv()` directly.

### Proxy Patching
Azure OpenAI clients fail when proxy env vars are set. The patch lives in
`app/services/llm_service.py` and is applied once at import time. All other
modules import `create_azure_llm` / `create_azure_embeddings` from there.

### Code Execution Sandbox
LLM-generated Python code runs through `validate_code()` which blocks unsafe
keywords (`os`, `subprocess`, `eval`, `exec`, `__`, etc.) before `exec()`.

### Caching Strategy
- `@st.cache_data` for deterministic reads (API calls, CSV loading).
- `@st.cache_resource` for expensive objects (PyGWalker HTML).
- No caching for LLM calls (non-deterministic).

## How to Add a New Page

1. Create `app/pages/my_page.py` — keep it thin.
2. If new data access is needed, add a service in `app/services/`.
3. Register the page in `app/main.py` under the appropriate group.
4. Add a navigation card in `app/pages/home.py` if desired.

## How to Add a New Data Source

1. Create `app/services/my_source_service.py` with cached fetch functions.
2. Create `app/pages/my_source_dashboard.py` that calls the service.
3. Register in `app/main.py`.
