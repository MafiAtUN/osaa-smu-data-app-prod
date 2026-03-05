"""UN SDG API access: data fetching, and AI query parsing."""

from __future__ import annotations

import json
import re
from typing import Any, Optional

import pandas as pd
import requests
import streamlit as st

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.geo_service import (
    fuzzy_match_country,
    fuzzy_match_region,
    get_iso_reference_df,
)
from app.services.llm_service import get_llm

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Cached data fetching
# ---------------------------------------------------------------------------

@st.cache_data
def get_data(url: str) -> Any:
    """GET *url* and return the parsed JSON. Returns an ``Exception`` on failure."""
    try:
        resp = requests.get(url)
        resp.raise_for_status()
        if not resp.text.strip():
            return Exception("Empty response from API")
        return resp.json()
    except requests.exceptions.RequestException as exc:
        st.cache_data.clear()
        return Exception(f"Request failed: {exc}")
    except ValueError as exc:
        st.cache_data.clear()
        return Exception(f"Invalid JSON: {exc}")
    except Exception as exc:
        st.cache_data.clear()
        return Exception(f"Unexpected error: {exc}")


def get_sdg_base_url() -> str:
    return get_settings().sdg.api_url


# ---------------------------------------------------------------------------
# AI query parsing
# ---------------------------------------------------------------------------

def parse_sdg_query_with_llm(
    user_query: str,
    goals_data: Any,
    indicators_data: Any,
) -> Optional[dict[str, Any]]:
    """Use the LLM to extract SDG API parameters from a natural-language query."""
    from datetime import date

    iso3_df = get_iso_reference_df()
    countries_list = iso3_df["Country or Area"].tolist()
    regions_list = iso3_df["Region Name"].dropna().unique().tolist()
    current_year = date.today().year

    # Build full goals list from live API data or fallback to static list
    goals_info: dict[str, str] = {}
    if goals_data and not isinstance(goals_data, Exception):
        for g in goals_data:
            goals_info[str(g["code"])] = g["title"]
    else:
        goals_info = {
            "1": "No Poverty", "2": "Zero Hunger", "3": "Good Health and Well-being",
            "4": "Quality Education", "5": "Gender Equality", "6": "Clean Water and Sanitation",
            "7": "Affordable and Clean Energy", "8": "Decent Work and Economic Growth",
            "9": "Industry, Innovation and Infrastructure", "10": "Reduced Inequalities",
            "11": "Sustainable Cities and Communities", "12": "Responsible Consumption and Production",
            "13": "Climate Action", "14": "Life Below Water", "15": "Life on Land",
            "16": "Peace, Justice and Strong Institutions", "17": "Partnerships for the Goals",
        }

    goals_block = "\n".join(f"  Goal {c}: {t}" for c, t in goals_info.items())
    regions_block = "\n".join(f"  - {r}" for r in regions_list)

    system_prompt = f"""You are an expert at extracting structured parameters from natural language queries about UN Sustainable Development Goals (SDG) data.

TODAY'S YEAR: {current_year}

ALL 17 SDG GOALS (use goal numbers, not names, in GOAL_CODES):
{goals_block}

ALL AVAILABLE REGIONS (use these exact names):
{regions_block}

SDG DATA SCHEMA (key fields):
  Indicator, goal, target, series, seriesDescription, geoAreaCode, geoAreaName,
  timePeriodStart, value, units, Country or Area, Region Name

CONCEPT MAPPINGS:
  "poverty" → Goal 1
  "hunger" / "food" / "nutrition" → Goal 2
  "health" / "mortality" / "disease" / "HIV" / "malaria" → Goal 3
  "education" / "literacy" / "enrollment" → Goal 4
  "gender" / "women" / "girls" / "equality" → Goal 5
  "water" / "sanitation" / "WASH" → Goal 6
  "energy" / "electricity" / "clean energy" → Goal 7
  "employment" / "economic growth" / "GDP" / "work" → Goal 8
  "infrastructure" / "industry" / "innovation" / "internet" → Goal 9
  "inequality" / "income gap" → Goal 10
  "cities" / "urban" / "housing" → Goal 11
  "consumption" / "production" / "waste" → Goal 12
  "climate" / "CO2" / "emissions" / "greenhouse" → Goal 13
  "ocean" / "marine" / "fisheries" → Goal 14
  "forests" / "biodiversity" / "land" → Goal 15
  "peace" / "justice" / "institutions" / "governance" → Goal 16
  "partnerships" / "financing" / "ODA" / "debt" → Goal 17

REGION CONCEPT MAPPINGS:
  "Africa" / "African continent"    → Eastern Africa, Middle Africa, Northern Africa, Southern Africa, Western Africa
  "sub-Saharan Africa"              → Eastern Africa, Middle Africa, Southern Africa, Western Africa
  "East Africa" / "Horn of Africa"  → Eastern Africa
  "West Africa" / "Sahel"           → Western Africa
  "Southern Africa"                 → Southern Africa
  "North Africa" / "MENA"           → Northern Africa
  "Asia"                            → Eastern Asia, South-eastern Asia, Southern Asia, Western Asia, Central Asia
  "Europe"                          → Northern Europe, Southern Europe, Western Europe, Eastern Europe

DATE RULES:
  - "current" / "now" / "today" / "latest" → TO_YEAR: {current_year}
  - "from [year]" with no end → FROM_YEAR: [year], TO_YEAR: {current_year}
  - "in 2023" → FROM_YEAR: 2023, TO_YEAR: 2023
  - "2020 to 2023" → FROM_YEAR: 2020, TO_YEAR: 2023
  - If no year mentioned and "latest" or "recent" → FROM_YEAR: {current_year - 5}, TO_YEAR: {current_year}

OUTPUT FORMAT — return EXACTLY 7 lines, no extra text:
INDICATORS: code1, code2 (use exact SDG indicator codes like 1.1.1, or NONE)
GOAL_CODES: 1, 3 (numeric codes only, or NONE)
COUNTRIES: Country1, Country2 (exact UN country names, or NONE)
REGIONS: Region1, Region2 (exact region names from the list above, or NONE)
FROM_YEAR: 2020 (4-digit year, or NONE)
TO_YEAR: 2023 (4-digit year, or NONE)
EXPLANATION: one-sentence description of the extracted parameters"""

    try:
        llm = get_llm()
        from langchain_core.prompts import ChatPromptTemplate

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "User query: {query}"),
        ])
        messages = prompt.format_messages(query=user_query)
        response = llm.invoke(messages)
        content = (response.content if hasattr(response, "content") else str(response)).strip()

        parsed: dict[str, Any] = {
            "indicators": [], "goal_codes": [], "countries": [],
            "regions": [], "from_year": None, "to_year": None, "explanation": "",
        }

        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            upper = line.upper()
            value = line.split(":", 1)[1].strip() if ":" in line else ""
            if upper.startswith("INDICATORS:") and value.upper() != "NONE":
                parsed["indicators"] = [i.strip() for i in value.split(",") if i.strip()]
            elif upper.startswith("GOAL_CODES:") and value.upper() != "NONE":
                parsed["goal_codes"] = [g.strip() for g in value.split(",") if g.strip()]
            elif upper.startswith("COUNTRIES:") and value.upper() != "NONE":
                parsed["countries"] = [c.strip() for c in value.split(",") if c.strip()]
            elif upper.startswith("REGIONS:") and value.upper() != "NONE":
                parsed["regions"] = [r.strip() for r in value.split(",") if r.strip()]
            elif upper.startswith("FROM_YEAR:") and value.upper() != "NONE":
                try:
                    parsed["from_year"] = int(value)
                except ValueError:
                    pass
            elif upper.startswith("TO_YEAR:") and value.upper() != "NONE":
                try:
                    parsed["to_year"] = int(value)
                except ValueError:
                    pass
            elif upper.startswith("EXPLANATION:"):
                parsed["explanation"] = value

        if not any([parsed["indicators"], parsed["goal_codes"], parsed["countries"], parsed["regions"], parsed["from_year"]]):
            return None

        parsed["countries"] = [m for c in parsed["countries"] if (m := fuzzy_match_country(c, countries_list))]
        parsed["regions"] = [m for r in parsed["regions"] if (m := fuzzy_match_region(r, regions_list))]

        return parsed
    except Exception as exc:
        logger.exception("Error parsing SDG query with LLM")
        st.error(f"Error parsing query: {exc}")
        return None


def fetch_sdg_data(
    parameters: dict[str, Any],
    indicators_data: Any,
    max_pages: int = 100,
) -> tuple[Optional[pd.DataFrame], Optional[str]]:
    """Fetch SDG data from the UN API and return ``(df, error_message)``."""
    base_url = get_sdg_base_url()
    iso3_df = get_iso_reference_df()

    indicator_codes: list[str] = []
    if parameters.get("goal_codes") and indicators_data and not isinstance(indicators_data, Exception):
        for gc in parameters["goal_codes"]:
            indicator_codes.extend(ind["code"] for ind in indicators_data if ind.get("goal") == gc)
    if parameters.get("indicators"):
        indicator_codes.extend(parameters["indicators"])
    indicator_codes = list(set(indicator_codes))
    if not indicator_codes:
        return None, "No indicators specified. Please specify SDG indicators or goals in your query."

    country_codes: list[str] = []
    for name in parameters.get("countries", []):
        row = iso3_df.loc[iso3_df["Country or Area"] == name]
        if not row.empty:
            country_codes.append(str(row.iloc[0]["m49"]))
    for region in parameters.get("regions", []):
        codes = iso3_df.loc[iso3_df["Region Name"] == region, "m49"].tolist()
        country_codes.extend(str(c) for c in codes)
    country_codes = list(set(country_codes))
    if not country_codes:
        return None, "No countries specified. Please specify countries or regions."

    from_year = parameters.get("from_year") or 1963
    to_year = parameters.get("to_year") or 2025
    try:
        from_year, to_year = int(from_year), int(to_year)
    except (ValueError, TypeError):
        return None, f"Invalid year values: {from_year}, {to_year}"
    if from_year > to_year:
        return None, f"Invalid year range: {from_year} > {to_year}"

    ind_params = "indicator=" + "&indicator=".join(indicator_codes)
    area_params = "&areaCode=" + "&areaCode=".join(country_codes)
    year_params = "&timePeriod=" + "&timePeriod=".join(str(y) for y in range(from_year, to_year + 1))
    page_size = 1000
    data_url = f"{base_url}/v1/sdg/Indicator/Data?{ind_params}{area_params}{year_params}&pageSize={page_size}"

    rows: list[dict] = []
    for page in range(1, max_pages + 1):
        result = get_data(f"{data_url}&page={page}")
        if isinstance(result, Exception):
            if page == 1:
                return None, f"Error fetching data: {result}"
            break
        page_data = result.get("data", [])
        if not page_data:
            break
        for entry in page_data:
            row: dict[str, Any] = {}
            ind = entry.get("indicator")
            row["Indicator"] = ind[0] if isinstance(ind, list) and ind else (ind or "")
            for k, v in entry.items():
                if k == "indicator":
                    continue
                if k in ("dimensions", "attributes") and isinstance(v, (str, dict)):
                    d = json.loads(v) if isinstance(v, str) else v
                    if isinstance(d, dict):
                        prefix = "dimension_" if k == "dimensions" else "attribute_"
                        for dk, dv in d.items():
                            row[f"{prefix}{dk}"] = dv
                        continue
                row[k] = v
            rows.append(row)
        if len(page_data) < page_size:
            break

    df = pd.DataFrame(rows)
    return (df if not df.empty else None), (None if not df.empty else "No data returned.")


def enrich_sdg_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Merge an SDG result *df* with the ISO reference table and clean up columns."""
    iso3_df = get_iso_reference_df()
    cc_col = next((c for c in ("m49", "geoAreaCode", "areaCode", "countryCode") if c in df.columns), None)
    if cc_col:
        merge_cols = [c for c in iso3_df.columns if c in (
            "Country or Area", "Region Name", "Sub-region Name",
            "Intermediate Region Name", "iso2", "iso3", "m49",
        )]
        df = df.merge(iso3_df[merge_cols], left_on=cc_col, right_on="m49", how="left", suffixes=("", "_ref"))
        for dup in [c for c in df.columns if c.endswith("_ref")]:
            orig = dup.replace("_ref", "")
            if orig in df.columns:
                df = df.drop(columns=[orig]).rename(columns={dup: orig})

    if "Value" in df.columns:
        df["Value"] = pd.to_numeric(df["Value"], errors="coerce")
    if "value" in df.columns:
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
    if "timePeriodStart" in df.columns:
        df["timePeriodStart"] = pd.to_numeric(df["timePeriodStart"], errors="coerce").astype("Int64")

    return df


def generate_sdg_suggestions(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    """Return ``(analysis_questions, visualization_ideas)`` for an SDG dataset."""
    if df is None or df.empty:
        return [], []
    try:
        llm = get_llm()
        from langchain_core.messages import HumanMessage, SystemMessage

        columns = df.columns.tolist()
        prompt_text = f"""Based on this UN SDG dataset ({len(df)} rows, columns: {', '.join(columns)}), generate:
1. 5-7 specific analysis questions about SDG indicators and progress
2. 5-7 specific visualization ideas

Return JSON: {{"analysis_questions": [...], "visualization_ideas": [...]}}"""
        response = llm.invoke([
            SystemMessage(content="You are an SDG data analyst."),
            HumanMessage(content=prompt_text),
        ])
        content = (response.content if hasattr(response, "content") else str(response)).strip()
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            parsed = json.loads(match.group(0))
            return parsed.get("analysis_questions", [])[:7], parsed.get("visualization_ideas", [])[:7]
    except Exception:
        logger.debug("SDG suggestion generation failed", exc_info=True)
    return (
        ["What is the progress of SDG indicators over time?",
         "Which countries show the best progress?"],
        ["Create a line chart showing trends", "Create a bar chart comparing countries"],
    )


# ---------------------------------------------------------------------------
# Pre-built query suggestions (displayed as clickable pills on the AI page)
# ---------------------------------------------------------------------------

#: Each entry: {"label": short pill text, "query": NL query, "description": caption}
SDG_QUERY_SUGGESTIONS: list[dict] = [
    {
        "label": "🏥 Maternal Health (SDG 3)",
        "query": "Compare maternal mortality and skilled birth attendance across Eastern Africa from 2000 to 2022",
        "description": "SDG 3.1 — Africa accounts for 70% of global maternal deaths; tracks progress toward 2030 targets.",
    },
    {
        "label": "💧 Water & Sanitation (SDG 6)",
        "query": "Track access to safely managed drinking water and sanitation services in sub-Saharan Africa from 2015 to 2023",
        "description": "SDG 6 WASH — only 33% of sub-Saharan Africans have safely managed drinking water.",
    },
    {
        "label": "🍽️ Poverty & Hunger (SDG 1+2)",
        "query": "Show progress on extreme poverty and hunger in West Africa from 2010 to 2022",
        "description": "SDG 1+2 combined — sub-Saharan Africa has ~40% extreme poverty; 283 million food insecure.",
    },
    {
        "label": "🏫 Education Outcomes (SDG 4)",
        "query": "Learning outcomes and primary completion rates in low-income African countries from 2015 to 2022",
        "description": "SDG 4 quality — 90% of African children are not learning at minimum proficiency by age 10.",
    },
    {
        "label": "⚡ Energy Access (SDG 7)",
        "query": "Access to electricity and clean cooking fuels across Africa comparing 2010 and 2022",
        "description": "SDG 7 — SSA at 56% electricity access; 900 million Africans still cook on open fires.",
    },
    {
        "label": "👩 Gender Equality (SDG 5)",
        "query": "Gender equality indicators: child marriage rates and female parliamentary representation in Africa from 2010 to 2022",
        "description": "SDG 5 — 40% of African girls marry before age 18; highest prevalence in West and Central Africa.",
    },
    {
        "label": "💼 Decent Work (SDG 8)",
        "query": "Youth unemployment and child labor rates across all African regions from 2015 to 2023",
        "description": "SDG 8 — 30–50% youth NEET rate in many African countries; 72 million children in child labour.",
    },
    {
        "label": "⚖️ Peace & Justice (SDG 16)",
        "query": "Conflict-related deaths and intentional homicide rates in Central and East Africa from 2018 to 2023",
        "description": "SDG 16 — tracks violence in the Sahel, DRC, Sudan, Somalia, and Ethiopia.",
    },
    {
        "label": "🌳 Life on Land (SDG 15)",
        "query": "Forest area trends and land degradation across the Congo Basin countries from 2000 to 2020",
        "description": "SDG 15 — the Congo Basin is losing ~500,000 ha of forest per year.",
    },
    {
        "label": "💰 Finance & Partnerships (SDG 17)",
        "query": "Domestic revenue mobilization and ODA flows for LDCs in Africa from 2015 to 2023",
        "description": "SDG 17 — tracking fiscal self-sufficiency vs. aid dependence in African least-developed countries.",
    },
]
