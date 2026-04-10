"""ACLED API access: authentication, data fetching, and AI query parsing.

Wraps the Armed Conflict Location and Event Data (ACLED) REST API to fetch
conflict-event records for African countries.  Key exports: ``fetch_acled_data``
for raw DataFrame retrieval, ``parse_acled_query_with_llm`` for converting
natural-language questions into ACLED API filter parameters, and
``ACLED_QUERY_SUGGESTIONS`` for pre-built UI pill prompts.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

import pandas as pd
import requests
import streamlit as st

from app.core.config import get_settings
from app.core.logging import generic_user_error, get_logger
from app.services.geo_service import (
    ACLED_REGION_MAPPING,
    ACLED_SUB_EVENT_TYPES,
    fuzzy_match_country,
    fuzzy_match_event_type,
    fuzzy_match_region,
    get_iso_reference_df,
)
from app.services.llm_service import get_llm

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Auth & data fetching (cached)
# ---------------------------------------------------------------------------

@st.cache_data
def get_access_token(username: str, password: str) -> Optional[str]:
    """Obtain an OAuth access token from ACLED."""
    settings = get_settings()
    try:
        resp = requests.post(
            settings.acled.token_url,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "username": username,
                "password": password,
                "grant_type": "password",
                "client_id": "acled",
            },
            timeout=20,
        )
        if resp.status_code == 200:
            return resp.json()["access_token"]
        logger.warning("ACLED token request failed with status %s", resp.status_code)
        st.error(generic_user_error("Failed to authenticate with ACLED. Please check the server configuration."))
        return None
    except Exception as exc:
        logger.exception("Error getting ACLED access token")
        st.error(generic_user_error("Failed to authenticate with ACLED."))
        return None


@st.cache_data
def get_data(url: str, access_token: str) -> Optional[dict]:
    """GET *url* with Bearer auth and return the JSON payload."""
    try:
        resp = requests.get(
            url,
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            timeout=30,
        )
        if resp.status_code == 200:
            return resp.json()
        logger.warning("ACLED data request failed with status %s", resp.status_code)
        st.error(generic_user_error("ACLED request failed. Please try again later."))
        return None
    except Exception as exc:
        logger.exception("Error making ACLED request")
        st.error(generic_user_error("ACLED request failed."))
        return None


@st.cache_data
def get_data_with_params(base_url: str, access_token: str, parameters: dict) -> Optional[dict]:
    """GET *base_url* with query *parameters* and Bearer auth."""
    try:
        resp = requests.get(
            base_url,
            params=parameters,
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            timeout=30,
        )
        if resp.status_code == 200:
            return resp.json()
        logger.warning("ACLED parameterized request failed with status %s", resp.status_code)
        st.error(generic_user_error("ACLED request failed. Please try again later."))
        return None
    except Exception as exc:
        logger.exception("Error making ACLED parameterized request")
        st.error(generic_user_error("ACLED request failed."))
        return None


def get_acled_credentials() -> tuple[str, str]:
    """Return ``(email, key)`` from config."""
    settings = get_settings()
    return settings.acled.email, settings.acled.key


# ---------------------------------------------------------------------------
# AI query parsing
# ---------------------------------------------------------------------------

def parse_acled_query_with_llm(user_query: str) -> Optional[dict[str, Any]]:
    """Use the LLM to extract ACLED API parameters from a natural-language query."""
    from datetime import date

    iso3_df = get_iso_reference_df()
    countries_list = iso3_df["Country or Area"].tolist()
    regions_list = list(ACLED_REGION_MAPPING.keys())
    today_str = date.today().strftime("%Y-%m-%d")
    all_event_types = ", ".join(ACLED_SUB_EVENT_TYPES)

    system_prompt = f"""You are an expert at extracting structured parameters from natural language queries about ACLED (Armed Conflict Location & Event Data Project).

TODAY'S DATE: {today_str}

AVAILABLE REGIONS (use these exact names):
{chr(10).join(f"  - {r}" for r in regions_list)}

ALL AVAILABLE EVENT/SUB-EVENT TYPES (use these exact names):
{all_event_types}

ACLED DATA SCHEMA (fields in the dataset):
  event_id_cnty, event_date, year, time_precision, disorder_type, event_type, sub_event_type,
  actor1, assoc_actor_1, inter1, actor2, assoc_actor_2, inter2, interaction, civilian_targeting,
  iso, region, country, admin1, admin2, admin3, location, latitude, longitude,
  geo_precision, source, source_scale, notes, fatalities, tags, timestamp

CONCEPT MAPPINGS (map user language to exact event types):
  "conflict" / "armed conflict" / "fighting"  → Armed clash, Attack
  "protests" / "demonstrations"               → Peaceful protest, Violent demonstration, Protest with intervention, Excessive force against protesters
  "violence" / "civilian violence"            → Attack, Violence against civilians, Sexual violence, Mob violence
  "explosions" / "bombings" / "IED"           → Air/drone strike, Suicide bomb, Shelling/artillery/missile attack, Remote explosive/landmine/IED, Grenade, Chemical weapon
  "all events" / "all incidents"              → NONE (no event type filter = return all)
  "territory" / "territorial"                 → Government regains territory, Non-state actor overtakes territory, Non-violent transfer of territory
  "abduction" / "kidnapping"                  → Abduction/forced disappearance

REGION CONCEPT MAPPINGS:
  "Africa" / "African continent"      → Western Africa, Eastern Africa, Southern Africa, Northern Africa, Middle Africa
  "sub-Saharan Africa"                → Western Africa, Eastern Africa, Southern Africa, Middle Africa
  "Sahel" / "Sahel region"            → Western Africa
  "Horn of Africa"                    → Eastern Africa
  "Great Lakes"                       → Eastern Africa, Middle Africa
  "North Africa" / "MENA"             → Northern Africa, Middle East

DATE RULES:
  - "up to now" / "to date" / "to today" / "till now" → TO_DATE: {today_str}
  - "from [year]" only, no end → FROM_DATE: [year]-01-01, TO_DATE: {today_str}
  - "in 2023" / "for 2023" → FROM_DATE: 2023-01-01, TO_DATE: 2023-12-31
  - "2022 to 2024" → FROM_DATE: 2022-01-01, TO_DATE: 2024-12-31
  - "January 2025" → FROM_DATE: 2025-01-01, TO_DATE: 2025-01-31
  - "1 Jan 2025" / "January 1, 2025" → FROM_DATE: 2025-01-01

COUNTRY NAME NOTES:
  - Use exact country names as they appear in UN datasets (e.g., "South Sudan", "Democratic Republic of the Congo", "Côte d'Ivoire")
  - If the user writes a well-known country name, keep it as-is

You MUST return your answer in this EXACT format (7 lines, one parameter per line):
COUNTRIES: country1, country2 (or NONE)
REGIONS: region1, region2 (or NONE)
EVENT_TYPES: event1, event2 (or NONE)
FROM_DATE: YYYY-MM-DD (or NONE)
TO_DATE: YYYY-MM-DD (or NONE)
LIMIT: number (default 5000)
EXPLANATION: brief description of what you extracted

Return EXACTLY 7 lines. No extra text before or after."""

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
            "countries": [], "regions": [], "event_types": [],
            "from_date": None, "to_date": None, "limit": 5000, "explanation": "",
        }

        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            upper = line.upper()
            value = line.split(":", 1)[1].strip() if ":" in line else ""
            if upper.startswith("COUNTRIES:") and value.upper() != "NONE":
                parsed["countries"] = [c.strip() for c in value.split(",") if c.strip()]
            elif upper.startswith("REGIONS:") and value.upper() != "NONE":
                parsed["regions"] = [r.strip() for r in value.split(",") if r.strip()]
            elif upper.startswith("EVENT_TYPES:") and value.upper() != "NONE":
                parsed["event_types"] = [e.strip() for e in value.split(",") if e.strip()]
            elif upper.startswith("FROM_DATE:") and value.upper() != "NONE":
                parsed["from_date"] = value
            elif upper.startswith("TO_DATE:") and value.upper() != "NONE":
                parsed["to_date"] = value
            elif upper.startswith("LIMIT:"):
                try:
                    parsed["limit"] = int(value)
                except ValueError:
                    pass
            elif upper.startswith("EXPLANATION:"):
                parsed["explanation"] = value

        if not any([parsed["countries"], parsed["regions"], parsed["event_types"], parsed["from_date"]]):
            return None

        parsed["countries"] = [m for c in parsed["countries"] if (m := fuzzy_match_country(c, countries_list))]
        parsed["regions"] = [m for r in parsed["regions"] if (m := fuzzy_match_region(r, regions_list))]
        parsed["event_types"] = [m for e in parsed["event_types"] if (m := fuzzy_match_event_type(e, ACLED_SUB_EVENT_TYPES))]

        return parsed

    except Exception as exc:
        logger.exception("Error parsing ACLED query with LLM")
        st.error(generic_user_error("Could not interpret the ACLED query. Please rephrase it."))
        return None


def build_acled_api_params(parsed: dict[str, Any]) -> dict[str, Any]:
    """Convert parsed parameters into a dict suitable for the ACLED REST API."""
    params: dict[str, Any] = {"_format": "json"}

    if parsed.get("countries"):
        params["country"] = "|".join(parsed["countries"])

    if parsed.get("regions"):
        codes = [str(ACLED_REGION_MAPPING[r]) for r in parsed["regions"] if r in ACLED_REGION_MAPPING]
        if codes:
            params["region"] = "|".join(codes) if len(codes) > 1 else codes[0]

    if parsed.get("event_types"):
        params["sub_event_type"] = "|".join(parsed["event_types"])

    from_d = parsed.get("from_date")
    to_d = parsed.get("to_date")
    if from_d and to_d:
        params["event_date"] = f"{from_d}:{to_d}"
        params["event_date_where"] = "BETWEEN"
    elif from_d:
        params["event_date"] = from_d
        params["event_date_where"] = ">="
    elif to_d:
        params["event_date"] = to_d
        params["event_date_where"] = "<="

    limit = parsed.get("limit", 5000)
    if limit and limit > 0:
        params["limit"] = limit

    return params


def fetch_acled_data(api_params: dict[str, Any], access_token: str) -> Optional[pd.DataFrame]:
    """Execute an ACLED API request and return a DataFrame (or *None*)."""
    settings = get_settings()
    data = get_data_with_params(settings.acled.api_url, access_token, api_params)

    if data and isinstance(data, dict) and "data" in data:
        rows = data["data"]
        if rows:
            return pd.DataFrame(rows)
    elif data and isinstance(data, list):
        return pd.DataFrame(data)

    return None


def generate_acled_suggestions(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    """Return ``(analysis_questions, visualization_ideas)`` for an ACLED dataset."""
    if df is None or df.empty:
        return [], []

    try:
        columns = df.columns.tolist()
        num_rows = len(df)
        column_info: dict[str, str] = {}
        for col in columns:
            if df[col].dtype in ["int64", "float64"]:
                column_info[col] = f"numeric: min={df[col].min()}, max={df[col].max()}"
            else:
                column_info[col] = f"categorical: {df[col].nunique()} unique"

        llm = get_llm()
        from langchain_core.messages import HumanMessage, SystemMessage

        prompt_text = f"""Based on this ACLED dataset ({num_rows} rows, columns: {', '.join(columns)}), generate:
1. 5-7 specific analysis questions
2. 5-7 specific visualization ideas

Column details: {column_info}

Return JSON: {{"analysis_questions": [...], "visualization_ideas": [...]}}"""

        response = llm.invoke([
            SystemMessage(content="You are an expert conflict data analyst."),
            HumanMessage(content=prompt_text),
        ])
        content = (response.content if hasattr(response, "content") else str(response)).strip()
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            parsed = json.loads(match.group(0))
            return parsed.get("analysis_questions", [])[:7], parsed.get("visualization_ideas", [])[:7]
    except Exception:
        logger.debug("Suggestion generation failed; using fallback", exc_info=True)

    return (
        ["What is the total number of events?", "Which countries have the most events?",
         "What are the most common event types?", "How have events changed over time?"],
        ["Create a bar chart of events by country", "Create a time-series of events",
         "Create a pie chart of event types"],
    )


# ---------------------------------------------------------------------------
# Pre-built query suggestions (displayed as clickable pills on the AI page)
# ---------------------------------------------------------------------------

#: Each entry: {"label": short pill text, "query": NL query, "description": caption}
ACLED_QUERY_SUGGESTIONS: list[dict] = [
    {
        "label": "🌍 All Africa 2024",
        "query": "All conflict and protest events across Africa in 2024",
        "description": "Broad overview of all conflict and protest activity across the continent for the most recent full year.",
    },
    {
        "label": "🏜️ Sahel Armed Clashes",
        "query": "Armed clashes and attacks in the Sahel region from 2020 to 2024",
        "description": "Tracks the intensifying Sahel insurgency in Mali, Burkina Faso, Niger, and Chad.",
    },
    {
        "label": "✊ East Africa Protests",
        "query": "Protests and demonstrations in East Africa from 2022 to 2024",
        "description": "Tracks civil society mobilisation, including Kenya's 2024 Gen-Z protests.",
    },
    {
        "label": "💥 Sudan Crisis",
        "query": "All conflict events in Sudan since April 2023",
        "description": "Monitors the ongoing Sudan civil war between SAF and RSF — one of the world's worst current conflicts.",
    },
    {
        "label": "👥 Violence vs Civilians",
        "query": "Violence against civilians and sexual violence across Africa in 2023 and 2024",
        "description": "Monitors civilian protection and IHL compliance — critical for humanitarian actors.",
    },
    {
        "label": "🇨🇩 DRC Conflict",
        "query": "Armed clashes and rebel activity in the Democratic Republic of Congo from 2022 to 2024",
        "description": "Tracks M23, ADF, FDLR and dozens of armed groups operating in eastern DRC.",
    },
    {
        "label": "💣 Lake Chad Bombings",
        "query": "Bombings and IED attacks in Nigeria and the Lake Chad Basin from 2019 to 2024",
        "description": "Tracks Boko Haram and ISWAP IED and armed attacks in the Lake Chad Basin.",
    },
    {
        "label": "🇿🇦 Southern Africa",
        "query": "Political violence and protests in Southern Africa from 2020 to 2024",
        "description": "Monitors instability, xenophobic violence, and protests in South Africa, Zimbabwe, and Mozambique.",
    },
    {
        "label": "💀 Horn of Africa Fatalities",
        "query": "High-fatality conflict events in the Horn of Africa from 2021 to 2024",
        "description": "Tracks Tigray, Al-Shabaab in Somalia, and South Sudan civil war; includes fatality counts.",
    },
    {
        "label": "🔗 Kidnappings W+C Africa",
        "query": "Kidnappings and abductions in West and Central Africa from 2020 to 2024",
        "description": "Monitors mass kidnappings in northwest Nigeria, CAR, and DRC — critical for child-protection work.",
    },
]
