# SMU Data App

A Streamlit-based data analysis platform built by the SMU Data Team at the
United Nations Office of the Special Adviser on Africa (UN OSAA).

## Quick Start

```bash
# 1. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure credentials
cp .env.example .env            # then fill in real values
cp .streamlit/secrets.toml.example .streamlit/secrets.toml

# 4. Run the app
streamlit run app/main.py
```

## Features

| Module | Description |
|--------|-------------|
| **Data Dashboard** | Upload CSV / Excel / Parquet and explore with AI |
| **World Bank** | Manual and AI-powered World Bank indicator queries |
| **UN SDG** | Manual and AI-powered Sustainable Development Goals data |
| **ACLED** | Armed conflict event data — manual filters or natural-language queries |
| **AI Analysis** | Auto dataset profiling, suggestions dropdown, conversational chat |
| **Visualizations** | LLM-generated Plotly charts with anti-overlap and styling rules |
| **Chat Library** | Browse, filter, and revisit all past AI analysis conversations |
| **OSAA Chatbot** | Institutional RAG chatbot grounded in OSAA publications |
| **Analysis Checker** | Contradictory-claim detection against source documents |
| **PID Checker** | Project Initiation Document evaluation tool |

## Project Structure

```
app/
├── main.py              # Single Streamlit entry point
├── pages/               # One file per page (thin UI controllers)
├── core/                # Config, logging, custom exceptions
├── services/            # Data access, API integrations, LLM factory, chat history
└── components/          # Reusable UI blocks (charts, tables, analysis, styles)
content/
├── db.duckdb            # Local DuckDB — seed data + chat history (gitignored)
└── vectorstore.duckdb   # Vector embeddings for RAG (gitignored)
```

## Credentials

Copy the example files and fill in real values — **never commit the real files**:

```
.env                          ← gitignored
.streamlit/secrets.toml       ← gitignored
```

Required: Azure OpenAI API keys, ACLED API credentials, app passwords.
See `.env.example` and `.streamlit/secrets.toml.example` for the full list.

## Deployment

Deployed via Docker to **Azure App Service** and can also run on **Railway**.
GitHub Actions workflow: `.github/workflows/main_osaa-data-app.yml` — triggers on push to `main`.

### Railway Security Checklist

Set these Railway variables before going live:

```bash
APP_PASSWORD_HASH=<output from python scripts/generate_password_hash.py>
PID_PASSWORD_HASH=<optional separate hash for PID page>
STREAMLIT_SERVER_COOKIE_SECRET=<long random secret>
```

Recommended:

- Do not set `app_password` or `pid_password` in production unless you are using them temporarily during migration.
- Keep Railway deployment public only behind HTTPS and share the password out-of-band.
- Rotate the password immediately if it is shared in chat, email, screenshots, or logs.
- Use Railway variables or a secrets manager for API keys; never bake secrets into the image.
- Limit Railway team/project access to only the people who need deploy access.
- The Docker build now excludes `.env` and `.streamlit/secrets.toml`, so keep production secrets in Railway variables only.
- On Railway, set `APP_ENV=production` so the app refuses plaintext passwords and missing cookie secrets at startup.

### Secret Rotation

If any real API keys or passwords have ever been pasted into chat, screenshots, Git history, shell history, or a shared `.env`, treat them as compromised and rotate them with the provider.

### Password Hash Generation

Generate a strong password hash locally:

```bash
python scripts/generate_password_hash.py
```

The script prints a random password and a matching `APP_PASSWORD_HASH` value that you can paste into Railway.

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — design decisions and directory layout
- [docs/REFACTOR_PLAN.md](docs/REFACTOR_PLAN.md) — audit findings and migration notes

---

*Internal UN OSAA project. Not for public distribution.*
