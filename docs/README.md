# SMU Data App

A Streamlit-based data analysis platform built by the SMU Data Team in the
United Nations Office of the Special Adviser on Africa (UN OSAA).

## Quick Start

```bash
# 1. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate   # macOS / Linux
venv\Scripts\activate      # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up environment variables
cp .env.example .env
# Edit .env with your real credentials

# 4. Run the app
streamlit run app/main.py
```

## Features

| Feature | Description |
|---|---|
| **Data Dashboard** | Upload CSV / Excel / Parquet files and analyze with AI |
| **World Bank Dashboard** | Query the World Bank API by indicator, country, and year |
| **SDG Dashboard** | Explore UN Sustainable Development Goals data |
| **SDG Dashboard (AI)** | Natural-language queries for SDG data |
| **ACLED Dashboard** | Armed Conflict Location & Event Data via ACLED API |
| **ACLED Dashboard (AI)** | Natural-language queries for ACLED data |
| **OSAA General Chatbot** | LLM chatbot with OSAA-specific context |
| **Contradictory Analysis** | RAG-based checker against OSAA publications |
| **PID Checker** | Evaluate Project Initiation Documents against criteria |

## Configuration

The app reads credentials from **environment variables** (`.env`) or
**Streamlit secrets** (`.streamlit/secrets.toml`). See `.env.example` and
`.streamlit/secrets.toml.example` for the required keys.

> **Never commit `.env` or `secrets.toml` to version control.**

## Project Structure

See [ARCHITECTURE.md](ARCHITECTURE.md) for a detailed breakdown of the
repository layout and design decisions.

## Development

```bash
# Lint with ruff
pip install ruff
ruff check app/ tests/
ruff format app/ tests/

# Run tests
pip install pytest
pytest tests/
```

## Deployment

The app is deployed to **Azure App Service**. The GitHub Actions workflow in
`.github/workflows/main_osaa-data-app.yml` handles CI/CD on pushes to `main`.

## License

Internal UN OSAA project. Not for public distribution.
