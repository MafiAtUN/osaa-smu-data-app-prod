# Refactor Plan

## Audit Summary

### Entry Points
- **`app.py`** (root) — the single Streamlit entry point. Uses `st.navigation()` +
  `st.Page()` to register ten pages.

### Pages (active — referenced by `app.py`)
| Page file | Purpose |
|---|---|
| `home.py` (root) | Landing page with navigation cards |
| `pages/dashboard.py` | Upload CSV/Excel/Parquet and analyze |
| `pages/wb_dashboard.py` | World Bank data via `wbgapi` |
| `pages/sdg_dashboard.py` | UN SDG data (manual selection) |
| `pages/sdg_dashboard_ai.py` | UN SDG data (AI-powered query) |
| `pages/acled_dashboard.py` | ACLED conflict data (manual selection) |
| `pages/acled_dashboard_ai.py` | ACLED conflict data (AI-powered query) |
| `pages/chatbot.py` | General-purpose OSAA chatbot |
| `pages/check_analysis.py` | Contradictory analysis checker (RAG) |
| `pages/pid_checker.py` | PID document validator |

### Shared Utilities
| File | Purpose |
|---|---|
| `components.py` | LLM analysis, graph maker, PyGWalker, Mitosheet, proxy patch, code validation |
| `helper_functions.py` | DuckDB setup, vectorstore, embeddings, proxy patch (duplicate) |

### Data & Assets
- `content/OSAA-Data-logo.svg` — app logo
- `content/iso3_country_reference.csv` — ISO-3166 country reference
- `content/db.duckdb` — local DuckDB database
- `content/vectorstore.duckdb` — RAG vector store

---

## Biggest Problems

1. **Massive code duplication** — `get_iso_reference_df()` is copy-pasted into
   5 files. ACLED auth functions duplicated across 2 files. SDG fetch logic
   duplicated across 2 files. Fuzzy-match helpers duplicated. LLM creation
   boilerplate repeated in every page.

2. **Dead root-level files** — `dashboard.py`, `acled_dashboard.py`,
   `check_analysis.py`, `pid_checker.py`, `wb_dashboard.py` in root are
   obsolete versions; `app.py` references `pages/` versions only.

3. **No configuration management** — API keys loaded via scattered
   `os.getenv()` calls with hard-coded defaults in every file.

4. **No logging** — all diagnostics go through `print()` or `st.error()`.

5. **Proxy patch duplicated** — `_patch_httpx_and_openai()` is in both
   `components.py` and `helper_functions.py`.

6. **Fat shared modules** — `components.py` (851 lines) mixes LLM chains,
   code execution sandboxing, graph rendering, and third-party tool wrappers.

7. **Pages contain business logic** — data fetching, API calls, parsing, and
   validation live inside page scripts instead of services.

8. **Unnecessary documentation files** — `ACLED_MODULE_EXPLANATION.md`,
   `APP_FUNCTIONALITY_ANALYSIS.md`, `GIT_USAGE.md`, `MODULE_ERRORS_FIXED.md`,
   `PROXY_ERROR_FIX.md`, `TEST_REPORT.md`, `TEST_RESULTS_SUMMARY.md` are
   debug artifacts, not part of the app.

9. **Ad-hoc test files** — `run_all_tests.py`, `test_all_modules.py`,
   `test_imports.py`, `test_api_connectivity.py`, `test_llm_functionality.py`,
   `test_module_functionality.py` are one-off scripts with no test framework.

10. **Spelling and grammar errors** in UI text, docstrings, and comments.

---

## Target Structure

```
.
├── app/
│   ├── __init__.py
│   ├── main.py                     # single Streamlit entry point
│   ├── pages/
│   │   ├── __init__.py
│   │   ├── home.py
│   │   ├── dashboard.py
│   │   ├── wb_dashboard.py
│   │   ├── sdg_dashboard.py
│   │   ├── sdg_dashboard_ai.py
│   │   ├── acled_dashboard.py
│   │   ├── acled_dashboard_ai.py
│   │   ├── chatbot.py
│   │   ├── check_analysis.py
│   │   └── pid_checker.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py               # typed config, env/secrets loading
│   │   ├── logging.py              # structured logger with redaction
│   │   └── errors.py               # custom exceptions
│   ├── services/
│   │   ├── __init__.py
│   │   ├── llm_service.py          # Azure OpenAI client, proxy patches
│   │   ├── acled_service.py        # ACLED API auth + data fetching
│   │   ├── sdg_service.py          # UN SDG API data fetching
│   │   ├── wb_service.py           # World Bank API via wbgapi
│   │   ├── data_service.py         # file upload parsing, DuckDB, vectorstore
│   │   └── geo_service.py          # ISO reference, region mapping, fuzzy match
│   ├── components/
│   │   ├── __init__.py
│   │   ├── analysis.py             # LLM data analysis + graph maker UI
│   │   ├── charts.py               # time-series, maps, heatmaps
│   │   ├── tables.py               # df_summary, PyGWalker, Mitosheet
│   │   └── filters.py              # column filters, region/country selectors
│   └── assets/
│       └── OSAA-Data-logo.svg
├── content/
│   ├── iso3_country_reference.csv
│   ├── db.duckdb
│   └── vectorstore.duckdb
├── docs/
│   ├── README.md
│   ├── ARCHITECTURE.md
│   └── REFACTOR_PLAN.md
├── tests/
│   ├── __init__.py
│   ├── test_config.py
│   ├── test_geo_service.py
│   └── test_code_validation.py
├── .streamlit/
│   ├── config.toml
│   └── secrets.toml.example
├── .github/
│   └── workflows/
│       └── main_osaa-data-app.yml
├── .env.example
├── .gitignore
├── requirements.txt
└── ruff.toml
```

---

## Risky Areas and How to Test

| Risk | Mitigation |
|---|---|
| Proxy-patch logic is fragile | Keep the exact same patch code; centralize it in `llm_service.py`; test by importing the module |
| ACLED/SDG API calls have auth + pagination | Keep existing logic unchanged; move to service; verify with a manual smoke test |
| PyGWalker + Mitosheet optional imports | Keep `try/except` import pattern; test graceful fallback |
| Session-state key collisions after rename | Keep identical session-state keys to preserve behavior |
| Page paths in `st.Page()` change | Update `app/main.py` to use new paths; update `st.switch_page()` in home |
| `.env` variable names unchanged | Config module maps same env var names; no change needed |

---

## Files to Delete (with Evidence)

### Dead root-level page duplicates
These are old versions; `app.py` references only `pages/` versions.

| File | Evidence |
|---|---|
| `dashboard.py` (root) | Not in any `st.Page()` or `import` |
| `acled_dashboard.py` (root) | Not in any `st.Page()` or `import` |
| `check_analysis.py` (root) | Not in any `st.Page()` or `import` |
| `pid_checker.py` (root) | Not in any `st.Page()` or `import` |
| `wb_dashboard.py` (root) | Not in any `st.Page()` or `import` |

### Debug / temporary documentation
| File | Evidence |
|---|---|
| `ACLED_MODULE_EXPLANATION.md` | Debug artifact, not linked anywhere |
| `APP_FUNCTIONALITY_ANALYSIS.md` | Debug artifact |
| `GIT_USAGE.md` | Debug artifact |
| `MODULE_ERRORS_FIXED.md` | Debug artifact |
| `PROXY_ERROR_FIX.md` | Debug artifact |
| `TEST_REPORT.md` | Debug artifact |
| `TEST_RESULTS_SUMMARY.md` | Debug artifact |

### Ad-hoc test scripts
| File | Evidence |
|---|---|
| `run_all_tests.py` | No framework, no imports from other files |
| `test_all_modules.py` | One-off script |
| `test_imports.py` | One-off script |
| `test_api_connectivity.py` | One-off script |
| `test_llm_functionality.py` | One-off script |
| `test_module_functionality.py` | One-off script |

### Superseded shared modules (after refactor completes)
| File | Evidence |
|---|---|
| `components.py` (root) | Replaced by `app/components/` + `app/services/` |
| `helper_functions.py` (root) | Replaced by `app/services/` |
| `home.py` (root) | Replaced by `app/pages/home.py` |
| `app.py` (root) | Replaced by `app/main.py` |
| `pages/` (root-level directory) | Replaced by `app/pages/` |

---

## Execution Order

1. Create target directory structure (done).
2. Write `app/core/` modules (config, logging, errors).
3. Extract services from existing code into `app/services/`.
4. Extract UI components into `app/components/`.
5. Create thin pages in `app/pages/`.
6. Create `app/main.py` entry point.
7. Add config examples (`.env.example`, `secrets.toml.example`).
8. Delete dead files.
9. Write documentation and minimal tests.
10. Final polish: spelling, linting, consistency.
