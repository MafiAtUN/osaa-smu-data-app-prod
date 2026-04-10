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
- **Core** provides cross-cutting infrastructure: typed config, structured
  logging with secret redaction, and a custom exception hierarchy.

## Directory Layout

```
app/
├── main.py                      # Single Streamlit entry point (st.navigation)
├── core/                        # Cross-cutting concerns
│   ├── config.py                # Typed Settings dataclass from env / st.secrets
│   ├── constants.py             # Shared magic strings (page names, source labels, TTLs)
│   ├── logging.py               # Structured logger with secret redaction
│   └── errors.py                # Custom exception hierarchy (AppError)
├── pages/                       # Thin UI controllers (one per page, 15 total)
│   ├── home.py                  # Landing page — hero section + feature cards
│   ├── dashboard.py             # File upload + AI data analysis
│   ├── wb_dashboard_ai.py       # World Bank — AI + manual tab
│   ├── sdg_dashboard_ai.py      # UN SDG — AI + manual tab
│   ├── acled_dashboard_ai.py    # ACLED Conflict — AI + manual tab
│   ├── un_data_explorer.py      # SDG Explorer via UN Data NSI SDMX API
│   ├── un_education.py          # UNESCO UIS education indicators
│   ├── un_energy.py             # UN Energy Statistics & Balance
│   ├── cross_source_studio.py   # Multi-source data fusion (cross-source module)
│   ├── cross_source_sync.py     # Hybrid sync admin / cache control panel
│   ├── chatbot.py               # General-purpose OSAA AI chatbot
│   ├── check_analysis.py        # RAG-backed analysis contradiction checker
│   ├── pid_checker.py           # PID document quality checker
│   └── chat_library.py          # Browse / filter / delete saved chat sessions
├── services/                    # Business logic and data access
│   ├── llm_service.py           # Azure OpenAI client factory + proxy patches
│   ├── acled_service.py         # ACLED REST API auth, fetching, AI query parsing
│   ├── sdg_service.py           # UN SDG API fetching, AI query parsing
│   ├── wb_service.py            # World Bank via wbgapi
│   ├── data_service.py          # DuckDB local data, vectorstore, file uploads
│   ├── geo_service.py           # ISO reference data, regions, fuzzy matching
│   ├── undata_service.py        # UN Data NSI SDMX: SDG Explorer, UNESCO UIS, Energy
│   ├── chat_history_service.py  # DuckDB-backed persistent chat session store
│   └── cross_source/            # Multi-source query engine (isolated sub-package)
│       ├── db.py                # DuckDB metadata + data slice cache
│       ├── execution.py         # Query-plan execution, cache-first fetch, DataFrame merge
│       ├── metadata.py          # Metadata registry ingestion and search
│       ├── planner.py           # NL → structured query plan via LLM
│       ├── quality.py           # Dataset quality scoring
│       └── sync.py              # Hybrid sync strategy (cache-first + API fallback)
└── components/                  # Reusable UI blocks
    ├── analysis.py              # render_analysis_tabs: chat + llm_graph_maker
    ├── charts.py                # Plotly time-series, choropleth, heatmap helpers
    ├── tables.py                # Summary stats, PyGWalker drag-and-drop explorer
    ├── filters.py               # Column/value filter widgets
    ├── llm_selector.py          # Sidebar LLM provider/model selector
    ├── query_suggestions.py     # Clickable pill-button query suggestion grid
    └── styles.py                # Global CSS + page_header / section_divider helpers
```

## Navigation Structure (sidebar)

| Section | Pages |
|---------|-------|
| *(no label)* | Home |
| **Data** | Data Explorer, Cross-Source Studio, Hybrid Sync, World Bank, SDG Indicators, ACLED Conflict, UNESCO Education, UN Energy, SDG Explorer |
| **OSAA Tools** | OSAA Chatbot, Analysis Checker, PID Checker, Chat Library |

## Key Design Decisions

### Single Entry Point
`app/main.py` is the only file passed to `streamlit run`. It registers all
pages with `st.navigation()` and groups them into **Data** and **OSAA Tools**
in the sidebar.

### Centralized Configuration
`app/core/config.py` exposes a frozen `Settings` dataclass populated from
`os.environ` and `st.secrets`. Pages never call `os.getenv()` directly.

### Shared Constants
`app/core/constants.py` is the single source of truth for page display names,
data source labels, and cross-source cache TTL values.  Import from there
rather than hard-coding strings in individual files.

### Proxy Patching
Azure OpenAI clients fail when proxy env vars are set. The patch lives in
`app/services/llm_service.py` and is applied once at import time.

### Code Execution Sandbox
LLM-generated Python code runs through `validate_code()` which blocks unsafe
keywords (`os`, `subprocess`, `eval`, `exec`, `__`, etc.) before `exec()`.

### Caching Strategy
- `@st.cache_data` for deterministic reads (API calls, CSV loading).
- `@st.cache_resource` for expensive objects (PyGWalker HTML).
- No caching for LLM calls (non-deterministic).

### AI Analysis Component
`render_analysis_tabs(df, chat_session_id, page, dataset_name, suggestions)`
is the standard entry point for AI features on every data page. It renders:
1. **Analysis tab** — auto dataset profile + LangChain multi-turn chat
2. **Visualizations tab** — natural-language Plotly code generator

Conversations are persisted to DuckDB via `chat_history_service` and browsable
from the **Chat Library** page.

### UN Data / SDMX Module
Three pages share `app/services/undata_service.py`:
- **SDG Explorer** — NSI staging API, 658 indicators, G-prefix country filter
- **UNESCO Education** — data.un.org legacy SDMX, 333 UIS indicators, ISO-3
- **UN Energy** — DF_UNDATA_ENERGY and DF_UNData_EnergyBalance, M49 codes

## How to Add a New Page

1. Create `app/pages/my_page.py` — keep it thin (widgets + service calls only).
2. If new data access is needed, add a service in `app/services/`.
3. Register the page in `app/main.py` under the appropriate group.
4. Add a feature card in `app/pages/home.py` if desired.
5. Add the page key → display name mapping to `app/core/constants.py`.

## How to Add a New Data Source

1. Create `app/services/my_source_service.py` with cached fetch functions.
2. Create `app/pages/my_source_dashboard.py` that calls the service.
3. Register in `app/main.py` and add display labels to `app/core/constants.py`.
