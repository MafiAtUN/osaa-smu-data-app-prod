"""UN Data NSI SDMX service — fetches data from the UN Data SDMX REST API.

API base: https://nsi-reset-undata-dst.dev.officialstatistics.org/rest
Catalogue: content/un_sdg_catalogue.json (658 SDG indicators)
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from collections import Counter
from io import StringIO
from pathlib import Path
from typing import Optional

import pandas as pd
import requests
import streamlit as st

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.geo_service import fuzzy_match_country, get_iso_reference_df

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# SDMX XML namespace prefixes used in structural metadata responses
# ---------------------------------------------------------------------------
_NS = {
    "mes": "http://www.sdmx.org/resources/sdmxml/schemas/v2_1/message",
    "str": "http://www.sdmx.org/resources/sdmxml/schemas/v2_1/structure",
    "com": "http://www.sdmx.org/resources/sdmxml/schemas/v2_1/common",
}

# ---------------------------------------------------------------------------
# Category prefix → human-readable label
# ---------------------------------------------------------------------------
CATEGORY_LABELS: dict[str, str] = {
    "AG": "Agriculture & Food",
    "BN": "Finance & Investment",
    "BX": "Finance & Investment",
    "DC": "Development Cooperation",
    "DI": "Debt & Finance",
    "DP": "Debt & Finance",
    "DT": "Debt & Finance",
    "EG": "Energy Access",
    "EN": "Environment & Climate",
    "ER": "Ecosystems & Biodiversity",
    "FB": "Financial Inclusion",
    "FC": "Financial Systems",
    "FI": "Financial Systems",
    "FM": "Monetary Policy",
    "FP": "Prices & Inflation",
    "GB": "Government Spending",
    "GC": "Government Finance",
    "GF": "Foreign Investment",
    "GR": "Government Revenue",
    "IC": "ICT & Digital",
    "IQ": "Institutional Quality",
    "IS": "Infrastructure",
    "IT": "Technology & Internet",
    "IU": "Governance & Corruption",
    "NE": "National Expenditure",
    "NV": "Industry & Manufacturing",
    "NY": "GDP & National Accounts",
    "PA": "Prices & Exchange Rates",
    "PD": "Agricultural Productivity",
    "SD": "Social Protection",
    "SE": "Education",
    "SG": "Governance & Institutions",
    "SH": "Health",
    "SI": "Poverty & Inequality",
    "SL": "Labour & Employment",
    "SM": "Migration",
    "SN": "Nutrition",
    "SP": "Population",
    "ST": "Tourism",
    "TG": "Trade",
    "TM": "Trade Policy",
    "TX": "Trade & Exports",
    "VC": "Peace & Security",
}


# ---------------------------------------------------------------------------
# Catalogue helpers
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def get_catalogue() -> list[dict]:
    """Load the UN SDG catalogue from JSON (658 indicators)."""
    path = Path(get_settings().undata.catalogue_path)
    if not path.exists():
        logger.warning("UN Data catalogue JSON not found at %s", path)
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@st.cache_data(show_spinner=False)
def get_categories() -> list[tuple[str, str, int]]:
    """Return ``[(prefix, label, count), ...]`` sorted by label."""
    catalogue = get_catalogue()
    counts: Counter = Counter(e["category"] for e in catalogue)
    seen_labels: dict[str, tuple[str, str, int]] = {}
    for prefix, count in counts.items():
        label = CATEGORY_LABELS.get(prefix, prefix)
        if label not in seen_labels:
            seen_labels[label] = (prefix, label, 0)
        existing = seen_labels[label]
        seen_labels[label] = (existing[0], label, existing[2] + count)
    return sorted(seen_labels.values(), key=lambda x: x[1])


def get_indicators_for_category(category_label: str) -> list[dict]:
    """Return catalogue entries whose ``category_name`` matches *category_label*."""
    return [e for e in get_catalogue() if e["category_name"] == category_label]


# ---------------------------------------------------------------------------
# Geography helpers
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_geography_codelist(series_id: str) -> dict[str, str]:
    """Fetch structural metadata for *series_id* and return ``{g_code: country_name}``.

    Calls ``GET /rest/dataflow/UNDATA/{series_id}/1.0?references=all`` and
    parses the first ``CL_GEOGRAPHY`` codelist found in the SDMX-ML XML.
    Returns an empty dict on failure.
    """
    base_url = get_settings().undata.api_url
    url = f"{base_url}/dataflow/UNDATA/{series_id}/1.0?references=all"
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
    except requests.exceptions.RequestException as exc:
        logger.warning("Failed to fetch geography codelist for %s: %s", series_id, exc)
        return {}

    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError as exc:
        logger.warning("XML parse error for geography codelist %s: %s", series_id, exc)
        return {}

    codelist: dict[str, str] = {}
    # Find all Codelist elements — pick the one whose id contains "GEOGRAPHY"
    for cl in root.iter("{http://www.sdmx.org/resources/sdmxml/schemas/v2_1/structure}Codelist"):
        cl_id = cl.get("id", "")
        if "GEOGRAPHY" not in cl_id.upper():
            continue
        for code in cl.iter("{http://www.sdmx.org/resources/sdmxml/schemas/v2_1/structure}Code"):
            g_code = code.get("id", "")
            # Only keep country-level codes (G-prefix).
            # C-prefix = cities, S-prefix = sampling stations.
            if not g_code.startswith("G"):
                continue
            name_el = code.find("{http://www.sdmx.org/resources/sdmxml/schemas/v2_1/common}Name")
            name = name_el.text.strip() if name_el is not None and name_el.text else g_code
            codelist[g_code] = name
        if codelist:
            break  # stop at first matching codelist

    logger.debug("Geography codelist for %s: %d country entries", series_id, len(codelist))
    return codelist


@st.cache_data(ttl=3600, show_spinner=False)
def get_african_geo_codes(series_id: str) -> dict[str, str]:
    """Return ``{g_code: country_name}`` for African countries in *series_id*.

    Cross-references the geography codelist with the ISO reference table
    (Region Name == "Africa") using fuzzy country name matching.
    """
    codelist = fetch_geography_codelist(series_id)
    if not codelist:
        return {}

    iso_df = get_iso_reference_df()
    african_names = iso_df.loc[
        iso_df["Region Name"] == "Africa", "Country or Area"
    ].tolist()

    result: dict[str, str] = {}
    for g_code, country_name in codelist.items():
        matched = fuzzy_match_country(country_name, african_names)
        if matched:
            result[g_code] = country_name
    return result


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

@st.cache_data(ttl=86400, show_spinner=False)
def fetch_undata(
    series_id: str,
    geo_codes: tuple[str, ...],  # tuple for hashability (cache key)
    start_year: int,
    end_year: int,
) -> pd.DataFrame:
    """Fetch data for *series_id* filtered to *geo_codes* and return a DataFrame.

    Always fetches with ``all`` key path (country-in-URL filtering returns 422),
    then filters the result in Python to the requested *geo_codes*.
    Uses ``Accept: text/csv`` for clean flat output.
    Replaces G-codes in GEOGRAPHY column with human-readable country names.
    Returns an empty DataFrame on any failure.
    """
    base_url = get_settings().undata.api_url
    url = (
        f"{base_url}/data/UNDATA,{series_id},1.0/all"
        f"?startPeriod={start_year}&endPeriod={end_year}"
        "&dimensionAtObservation=AllDimensions"
    )

    try:
        resp = requests.get(url, headers={"Accept": "text/csv"}, timeout=60)
        resp.raise_for_status()
        if not resp.text.strip():
            logger.info("Empty response for %s", series_id)
            return pd.DataFrame()
    except requests.exceptions.RequestException as exc:
        logger.warning("UN Data fetch failed for %s: %s", series_id, exc)
        return pd.DataFrame()

    try:
        df = pd.read_csv(StringIO(resp.text))
    except Exception as exc:
        logger.warning("CSV parse error for %s: %s", series_id, exc)
        return pd.DataFrame()

    if df.empty:
        return df

    # Filter to requested geo_codes in Python (URL-based filtering returns 422)
    if geo_codes and "GEOGRAPHY" in df.columns:
        df = df[df["GEOGRAPHY"].isin(geo_codes)].copy()

    if df.empty:
        return df

    # Resolve G-codes → country names using the codelist
    if "GEOGRAPHY" in df.columns:
        codelist = fetch_geography_codelist(series_id)
        if codelist:
            df["GEOGRAPHY"] = df["GEOGRAPHY"].map(codelist).fillna(df["GEOGRAPHY"])

    # Numeric OBS_VALUE
    if "OBS_VALUE" in df.columns:
        df["OBS_VALUE"] = pd.to_numeric(df["OBS_VALUE"], errors="coerce")

    # Numeric TIME_PERIOD
    if "TIME_PERIOD" in df.columns:
        df["TIME_PERIOD"] = pd.to_numeric(df["TIME_PERIOD"], errors="coerce").astype("Int64")

    # Drop high-noise metadata columns users rarely need
    _drop = {"DATAFLOW", "RELEASE_NAME", "TIME_DETAIL", "TIME_COVERAGE", "VALUE_TYPE"}
    df = df.drop(columns=[c for c in _drop if c in df.columns])

    return df


def get_display_columns(df: pd.DataFrame) -> list[str]:
    """Return a sensible column order for display: key dims first, then value, then extras."""
    priority = ["SERIES", "GEOGRAPHY", "TIME_PERIOD", "OBS_VALUE",
                "UNIT_MEASURE", "NATURE", "UPPER_BOUND", "LOWER_BOUND",
                "OBSERVATION_STATUS", "SOURCE", "FOOT_NOTE"]
    ordered = [c for c in priority if c in df.columns]
    rest = [c for c in df.columns if c not in ordered]
    return ordered + rest


# ===========================================================================
# data.un.org legacy SDMX API — UNESCO UIS Education + UN Energy
# ===========================================================================

_DATAUNORG_BASE = "https://data.un.org/ws/rest"


def _get_dataunorg_meta(dataflow_id: str) -> dict:
    """Fetch ``?detail=serieskeysonly`` JSON metadata for a data.un.org dataflow.

    Uses a 90s timeout — the UIS endpoint can take 35–40s to respond.
    """
    url = f"{_DATAUNORG_BASE}/data/{dataflow_id}"
    resp = requests.get(
        url,
        headers={"Accept": "text/json"},
        params={"detail": "serieskeysonly"},
        timeout=90,
    )
    resp.raise_for_status()
    return resp.json()


def _extract_dim(meta: dict, dim_id: str) -> dict[str, str]:
    """Extract ``{code: name}`` for a named dimension from metadata."""
    for dim in meta.get("structure", {}).get("dimensions", {}).get("series", []):
        if dim["id"] == dim_id:
            return {v["id"]: v["name"] for v in dim["values"]}
    return {}


# ---------------------------------------------------------------------------
# UNESCO UIS Education (DF_UNData_UIS)
# Key pattern: FREQ.SERIES.UNIT.LOCATION.AGE_GROUP.SEX.REF_AREA.SOURCE_TYPE
# Countries: ISO 3166-1 Alpha-3
# ---------------------------------------------------------------------------

@st.cache_data(ttl=86400, show_spinner=False)
def get_uis_series() -> dict[str, str]:
    """Return ``{series_code: series_name}`` for all 333 UNESCO UIS indicators.

    Falls back to a local ``content/uis_series.json`` cache when the API is
    unavailable, and persists a fresh response to that file on success.
    """
    _CACHE = Path(__file__).parent.parent.parent / "content" / "uis_series.json"
    try:
        series = _extract_dim(_get_dataunorg_meta("DF_UNData_UIS"), "SERIES")
        if series:
            try:
                _CACHE.write_text(json.dumps(series, ensure_ascii=False, indent=2))
            except Exception:
                pass
        return series
    except Exception as exc:
        logger.warning("Failed to fetch UIS series list from API: %s — trying local cache", exc)
        if _CACHE.exists():
            try:
                return json.loads(_CACHE.read_text())
            except Exception as cache_exc:
                logger.warning("Local UIS series cache unreadable: %s", cache_exc)
        return {}


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_uis_data(
    series_codes: tuple[str, ...],
    iso3_codes: tuple[str, ...],
    start_year: int,
    end_year: int,
) -> pd.DataFrame:
    """Fetch UNESCO UIS education data.

    Key: ``A.{series}.....{iso3_countries}.NA``
    Wildcards cover UNIT, LOCATION, AGE_GROUP, SEX (positions 2-5).
    """
    if not series_codes or not iso3_codes:
        return pd.DataFrame()
    key = f"A.{'+'.join(series_codes)}.....{'+'.join(iso3_codes)}.NA"
    url = f"{_DATAUNORG_BASE}/data/DF_UNData_UIS/{key}"
    try:
        resp = requests.get(
            url,
            headers={"Accept": "text/csv"},
            params={"startPeriod": start_year, "endPeriod": end_year},
            timeout=60,
        )
        resp.raise_for_status()
        if not resp.text.strip():
            return pd.DataFrame()
    except requests.exceptions.RequestException as exc:
        logger.warning("UIS fetch failed: %s", exc)
        return pd.DataFrame()

    try:
        df = pd.read_csv(StringIO(resp.text))
    except Exception as exc:
        logger.warning("UIS CSV parse error: %s", exc)
        return pd.DataFrame()

    if df.empty:
        return df

    if "OBS_VALUE" in df.columns:
        df["OBS_VALUE"] = pd.to_numeric(df["OBS_VALUE"], errors="coerce")
    if "TIME_PERIOD" in df.columns:
        df["TIME_PERIOD"] = pd.to_numeric(df["TIME_PERIOD"], errors="coerce").astype("Int64")

    # Add readable country name column next to REF_AREA
    iso_df = get_iso_reference_df()
    iso3_to_name = iso_df.dropna(subset=["iso3"]).set_index("iso3")["Country or Area"].to_dict()
    if "REF_AREA" in df.columns:
        loc = df.columns.get_loc("REF_AREA") + 1
        df.insert(loc, "COUNTRY", df["REF_AREA"].map(iso3_to_name).fillna(df["REF_AREA"]))

    _drop = {"DATAFLOW", "FREQ", "SOURCE_TYPE", "TIME_DETAIL", "UNIT_MULT"}
    return df.drop(columns=[c for c in _drop if c in df.columns])


# ---------------------------------------------------------------------------
# African country helpers (shared by Energy pages)
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def get_african_m49() -> dict[str, str]:
    """Return ``{m49_str: country_name}`` for African countries."""
    iso_df = get_iso_reference_df()
    africa = iso_df[iso_df["Region Name"] == "Africa"].dropna(subset=["m49"])
    return {
        str(int(float(row["m49"]))): row["Country or Area"]
        for _, row in africa.iterrows()
    }


@st.cache_data(show_spinner=False)
def get_all_m49() -> dict[str, str]:
    """Return ``{m49_str: country_name}`` for all countries in the ISO reference table."""
    iso_df = get_iso_reference_df()
    return {
        str(int(float(row["m49"]))): row["Country or Area"]
        for _, row in iso_df.dropna(subset=["m49"]).iterrows()
    }


# ---------------------------------------------------------------------------
# UN Energy Statistics (DF_UNDATA_ENERGY)
# Key pattern: FREQ.REF_AREA.COMMODITY.TRANSACTION
# Countries: UN M49 numeric
# ---------------------------------------------------------------------------

@st.cache_data(ttl=86400, show_spinner=False)
def get_energy_stats_codes() -> tuple[dict[str, str], dict[str, str]]:
    """Return ``(commodity_codes, transaction_codes)`` for DF_UNDATA_ENERGY."""
    try:
        meta = _get_dataunorg_meta("DF_UNDATA_ENERGY")
        return _extract_dim(meta, "COMMODITY"), _extract_dim(meta, "TRANSACTION")
    except Exception as exc:
        logger.warning("Failed to fetch Energy Stats codes: %s", exc)
        return {}, {}


def _fetch_energy_sdmx(
    dataflow: str,
    key: str,
    start_year: int,
    end_year: int,
    get_codes_fn,
    drop_cols: frozenset,
) -> pd.DataFrame:
    """Shared CSV-over-SDMX fetch logic for UN Energy dataflows.

    Fetches the dataflow URL, parses CSV, normalises OBS_VALUE and TIME_PERIOD,
    decodes M49 country codes and commodity/transaction codes, then drops
    internal metadata columns.  Both fetch_energy_stats and fetch_energy_balance
    are thin wrappers that set the key and codes function before calling this.
    """
    url = f"{_DATAUNORG_BASE}/data/{dataflow}/{key}"
    try:
        resp = requests.get(
            url,
            headers={"Accept": "text/csv"},
            params={"startPeriod": start_year, "endPeriod": end_year},
            timeout=120,
        )
        resp.raise_for_status()
        if not resp.text.strip():
            return pd.DataFrame()
    except requests.exceptions.RequestException as exc:
        logger.warning("%s fetch failed: %s", dataflow, exc)
        return pd.DataFrame()

    try:
        df = pd.read_csv(StringIO(resp.text))
    except Exception as exc:
        logger.warning("%s CSV parse error: %s", dataflow, exc)
        return pd.DataFrame()

    if df.empty:
        return df

    if "OBS_VALUE" in df.columns:
        df["OBS_VALUE"] = pd.to_numeric(df["OBS_VALUE"], errors="coerce")
    if "TIME_PERIOD" in df.columns:
        df["TIME_PERIOD"] = pd.to_numeric(df["TIME_PERIOD"], errors="coerce").astype("Int64")

    commodity_codes, transaction_codes = get_codes_fn()
    m49_map = get_all_m49()
    if "REF_AREA" in df.columns:
        df["REF_AREA"] = df["REF_AREA"].astype(str).map(m49_map).fillna(df["REF_AREA"].astype(str))
    if "COMMODITY" in df.columns and commodity_codes:
        df["COMMODITY"] = df["COMMODITY"].map(commodity_codes).fillna(df["COMMODITY"])
    if "TRANSACTION" in df.columns and transaction_codes:
        df["TRANSACTION"] = df["TRANSACTION"].map(transaction_codes).fillna(df["TRANSACTION"])

    return df.drop(columns=[c for c in drop_cols if c in df.columns])


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_energy_stats(
    m49_codes: tuple[str, ...],
    start_year: int,
    end_year: int,
) -> pd.DataFrame:
    """Fetch UN Energy Statistics for given M49 country codes (all commodities/transactions).

    Key: ``A.{m49_codes}..``  (wildcard COMMODITY and TRANSACTION)
    Codes are decoded to readable names post-fetch.
    """
    if not m49_codes:
        return pd.DataFrame()
    return _fetch_energy_sdmx(
        dataflow="DF_UNDATA_ENERGY",
        key=f"A.{'+'.join(m49_codes)}..",
        start_year=start_year,
        end_year=end_year,
        get_codes_fn=get_energy_stats_codes,
        drop_cols=frozenset({"DATAFLOW", "FREQ", "UNIT_MULT"}),
    )


# ---------------------------------------------------------------------------
# UN Energy Balance (DF_UNData_EnergyBalance)
# Key pattern: REF_AREA.COMMODITY.TRANSACTION.UNIT  (no FREQ dimension)
# Countries: UN M49 numeric
# ---------------------------------------------------------------------------

@st.cache_data(ttl=86400, show_spinner=False)
def get_energy_balance_codes() -> tuple[dict[str, str], dict[str, str]]:
    """Return ``(commodity_codes, transaction_codes)`` for DF_UNData_EnergyBalance."""
    try:
        meta = _get_dataunorg_meta("DF_UNData_EnergyBalance")
        return _extract_dim(meta, "COMMODITY"), _extract_dim(meta, "TRANSACTION")
    except Exception as exc:
        logger.warning("Failed to fetch Energy Balance codes: %s", exc)
        return {}, {}


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_energy_balance(
    m49_codes: tuple[str, ...],
    start_year: int,
    end_year: int,
) -> pd.DataFrame:
    """Fetch UN Energy Balance for given M49 country codes (all commodity groups/transactions).

    Key: ``{m49_codes}...``  (3 dots = wildcard COMMODITY, TRANSACTION, UNIT)
    """
    if not m49_codes:
        return pd.DataFrame()
    return _fetch_energy_sdmx(
        dataflow="DF_UNData_EnergyBalance",
        key=f"{'+'.join(m49_codes)}...",
        start_year=start_year,
        end_year=end_year,
        get_codes_fn=get_energy_balance_codes,
        drop_cols=frozenset({"DATAFLOW", "UNIT", "UNIT_MULT"}),
    )


# ===========================================================================
# Pre-built query suggestions
# ===========================================================================

#: Each entry: {"label": pill text, "query": NL query, "description": caption}
UNDATA_QUERY_SUGGESTIONS: list[dict] = [
    {
        "label": "🏥 Child Mortality",
        "query": "Under-5 and neonatal mortality rates for all African countries from 2010 to 2023",
        "description": "SDG 3 — child health outcomes tracked by mortality indicators across Africa.",
    },
    {
        "label": "💧 Water & Sanitation",
        "query": "Access to safely managed drinking water and sanitation across Africa 2015 to 2023",
        "description": "SDG 6 — WASH coverage and progress toward universal access.",
    },
    {
        "label": "⚡ Energy Access",
        "query": "Access to electricity and renewable energy share across Africa 2015 to 2022",
        "description": "SDG 7 — clean and affordable energy progress by country.",
    },
    {
        "label": "🎓 Education Quality",
        "query": "Minimum learning proficiency and school completion rates in East Africa 2015 to 2023",
        "description": "SDG 4 — education quality and outcome indicators.",
    },
    {
        "label": "🌱 CO₂ & Climate",
        "query": "CO2 emissions and climate finance indicators for Africa 2010 to 2022",
        "description": "SDG 13 — climate action tracking, emissions, and environmental protection.",
    },
    {
        "label": "👩 Gender Equality",
        "query": "Women in parliament and education gender parity index in Africa 2015 to 2023",
        "description": "SDG 5 — gender equality across education and political representation.",
    },
    {
        "label": "💼 Youth Employment",
        "query": "Youth unemployment and NEET rates for African countries 2015 to 2023",
        "description": "SDG 8 — youth labour market outcomes and decent work indicators.",
    },
    {
        "label": "🌿 Biodiversity",
        "query": "Protected terrestrial area and forest coverage trends in Africa 2000 to 2022",
        "description": "SDG 15 — land and biodiversity protection indicators.",
    },
]

UIS_QUERY_SUGGESTIONS: list[dict] = [
    {
        "label": "📖 Youth Literacy",
        "query": "Youth literacy rates (15-24) disaggregated by gender across Africa 2010 to 2023",
        "description": "UIS LR_AG15T24 — compare male/female literacy and gender gaps across Africa.",
    },
    {
        "label": "🏫 Primary Enrollment",
        "query": "Net enrolment rate in primary education for all African countries 2000 to 2023",
        "description": "UIS NERA_1 — share of school-age children actually enrolled in primary school.",
    },
    {
        "label": "🎓 Secondary Completion",
        "query": "Secondary school completion rates and gender parity index in East Africa 2010 to 2022",
        "description": "UIS CR_L2 — tracks secondary education access and gender equality.",
    },
    {
        "label": "📐 Learning Outcomes",
        "query": "Minimum proficiency in reading and math at end of primary school in sub-Saharan Africa 2015 to 2023",
        "description": "UIS LO_PRSE — SDG 4.1 proxy for education quality by country.",
    },
    {
        "label": "👩‍🏫 Teacher Quality",
        "query": "Percentage of trained teachers in primary education across West Africa 2015 to 2023",
        "description": "UIS TRTP — qualified teacher ratios by level and country.",
    },
    {
        "label": "💰 Education Spending",
        "query": "Government expenditure on education as a share of GDP in Africa 2010 to 2022",
        "description": "UIS XGDP_FSGOV — education investment compared across African economies.",
    },
    {
        "label": "🧒 Out-of-School Rate",
        "query": "Out-of-school children at primary and lower secondary level in Nigeria, Ethiopia, DRC 2010 to 2022",
        "description": "UIS OOSR — tracks exclusion from school by education level.",
    },
    {
        "label": "🌍 Adult Literacy",
        "query": "Adult literacy rate (15+) in North and West Africa from 2000 to 2022",
        "description": "UIS LR_AG15T99 — measures overall population literacy progress.",
    },
]

ENERGY_QUERY_SUGGESTIONS: list[dict] = [
    {
        "label": "🔌 Electricity Production",
        "query": "Electricity production from renewables and fossil fuels in Nigeria, South Africa and Kenya 2015 to 2022",
        "description": "Energy Stats — compare renewable vs fossil production in top African economies.",
    },
    {
        "label": "🌍 Africa Energy Mix",
        "query": "Total primary energy supply and renewable share for all African countries 2015 to 2022",
        "description": "Energy Balance — total supply and clean energy transition progress.",
    },
    {
        "label": "⛽ Oil & Gas Trade",
        "query": "Crude oil and natural gas exports and imports for major African producers 2010 to 2022",
        "description": "Energy Stats — fossil fuel trade flows for top African exporters and importers.",
    },
    {
        "label": "☀️ Solar & Wind Growth",
        "query": "Solar photovoltaic and wind energy production in North Africa and South Africa 2010 to 2022",
        "description": "Energy Stats — renewable energy production by country and fuel type.",
    },
    {
        "label": "🍳 Final Consumption",
        "query": "Final energy consumption by sector in Ethiopia, Tanzania, and Kenya 2015 to 2022",
        "description": "Energy Balance — consumption in industry, transport, and residential sectors.",
    },
    {
        "label": "🔥 Biomass & Coal",
        "query": "Solid biomass and coal consumption in Southern and Central Africa 2000 to 2022",
        "description": "Energy Stats — tracks traditional cooking fuel alongside coal in the energy mix.",
    },
    {
        "label": "🏭 Energy Losses",
        "query": "Energy transformation and distribution losses for East African countries 2015 to 2022",
        "description": "Energy Balance — measures conversion efficiency and system losses.",
    },
    {
        "label": "🌡️ Total Consumption",
        "query": "Total final energy consumption for all African countries 2010 to 2022",
        "description": "Energy Balance — overall energy intensity and consumption trends.",
    },
]


# ===========================================================================
# LLM query parsing
# ===========================================================================

def parse_undata_query_with_llm(user_query: str) -> Optional[dict]:
    """Parse a natural-language query into UN Data NSI SDMX fetch parameters.

    Returns a dict with keys: ``series_id``, ``series_name``, ``africa_only``,
    ``country_names``, ``start_year``, ``end_year``, ``explanation``.
    Returns ``None`` on failure.
    """
    from datetime import date

    catalogue = get_catalogue()
    if not catalogue:
        return None

    current_year = date.today().year

    # Build compact category → sample IDs summary (keeps prompt small)
    cat_to_ids: dict[str, list[str]] = {}
    for e in catalogue:
        cat_to_ids.setdefault(e["category_name"], []).append(e["id"])

    catalogue_summary = "\n".join(
        f"  {cat}: {', '.join(ids[:6])}{'…' if len(ids) > 6 else ''}"
        for cat, ids in sorted(cat_to_ids.items())
    )

    known_ids = {e["id"]: e["name"] for e in catalogue}

    system_prompt = (
        f"You are an expert at selecting UN SDG indicators from a catalogue.\n\n"
        f"TODAY'S YEAR: {current_year}\n\n"
        f"CATALOGUE (Category: sample IDs):\n{catalogue_summary}\n\n"
        "RULES:\n"
        "- Pick ONE series ID that best matches the query\n"
        "- Use an exact ID from the catalogue (e.g. SH_DYN_MORT, EG_ELC_ACCS, SI_POV_DAY1)\n"
        "- 'Africa' / no geography → AFRICA_ONLY: yes\n"
        "- Named countries → AFRICA_ONLY: no, COUNTRIES: list them\n"
        f"- No year → FROM_YEAR: {current_year - 10}, TO_YEAR: {current_year}\n"
        f"- 'latest' → FROM_YEAR: {current_year - 5}, TO_YEAR: {current_year}\n\n"
        "OUTPUT FORMAT (exactly 6 lines):\n"
        "SERIES_ID: <id>\n"
        "AFRICA_ONLY: yes/no\n"
        "COUNTRIES: NONE or Country1, Country2\n"
        "FROM_YEAR: <year>\n"
        "TO_YEAR: <year>\n"
        "EXPLANATION: <one sentence>"
    )

    try:
        from langchain_core.prompts import ChatPromptTemplate

        from app.services.llm_service import get_llm

        llm = get_llm()
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{query}"),
        ])
        response = llm.invoke(prompt.format_messages(query=user_query))
        content = (response.content if hasattr(response, "content") else str(response)).strip()

        parsed: dict = {
            "series_id": None, "series_name": "", "africa_only": True,
            "country_names": [], "start_year": current_year - 10,
            "end_year": current_year, "explanation": "",
        }
        for line in content.splitlines():
            line = line.strip()
            if not line or ":" not in line:
                continue
            key, _, value = line.partition(":")
            key, value = key.strip().upper(), value.strip()
            if key == "SERIES_ID":
                parsed["series_id"] = value.upper()
            elif key == "AFRICA_ONLY":
                parsed["africa_only"] = value.lower() == "yes"
            elif key == "COUNTRIES" and value.upper() != "NONE":
                parsed["country_names"] = [c.strip() for c in value.split(",") if c.strip()]
            elif key == "FROM_YEAR" and value.upper() != "NONE":
                try:
                    parsed["start_year"] = int(value)
                except ValueError:
                    pass
            elif key == "TO_YEAR" and value.upper() != "NONE":
                try:
                    parsed["end_year"] = int(value)
                except ValueError:
                    pass
            elif key == "EXPLANATION":
                parsed["explanation"] = value

        if not parsed["series_id"] or parsed["series_id"] not in known_ids:
            logger.warning("LLM returned invalid/unknown series ID: %s", parsed["series_id"])
            return None

        parsed["series_name"] = known_ids[parsed["series_id"]]
        return parsed

    except Exception:
        logger.exception("Error parsing UN Data query with LLM")
        st.error("Could not parse your query. Please try rephrasing or use Manual Selection.")
        return None


def parse_uis_query_with_llm(
    user_query: str,
    uis_series: dict[str, str],
) -> Optional[dict]:
    """Parse a natural-language query into UIS Education fetch parameters.

    Returns a dict with keys: ``series_codes`` (tuple), ``iso3_codes`` (tuple),
    ``start_year``, ``end_year``, ``explanation``. Returns ``None`` on failure.
    """
    from datetime import date

    if not uis_series:
        return None

    current_year = date.today().year
    iso_df = get_iso_reference_df()
    africa_iso3 = iso_df.loc[iso_df["Region Name"] == "Africa"].dropna(subset=["iso3"])["iso3"].tolist()
    valid_iso3 = set(iso_df.dropna(subset=["iso3"])["iso3"].tolist())

    # Include up to 250 indicators for context (sorted alphabetically by name)
    series_lines = "\n".join(
        f"  {code}: {name}"
        for code, name in sorted(uis_series.items(), key=lambda x: x[1])[:250]
    )

    system_prompt = (
        f"You are an expert at selecting UNESCO UIS education indicators.\n\n"
        f"TODAY'S YEAR: {current_year}\n\n"
        f"AVAILABLE INDICATORS (code: description):\n{series_lines}\n\n"
        "KEY MAPPINGS:\n"
        "  literacy → LR_AG15T24 (youth 15-24), LR_AG15T99 (adult 15+)\n"
        "  primary enrollment → NERA_1, GERA_1\n"
        "  secondary enrollment → NERA_2 (lower), NERA_3 (upper)\n"
        "  completion → CR_L1 (primary), CR_L2 (lower sec), CR_L3 (upper sec)\n"
        "  gender parity → add _GPI suffix (e.g. NERA_1_GPI)\n"
        "  out-of-school → OOSR_1 (primary), OOSR_2 (lower secondary)\n"
        "  teachers trained → TRTP\n"
        "  education spending → XGDP_FSGOV\n"
        "  learning outcomes → LO_PRSE_MATH, LO_PRSE_REA\n\n"
        "GEOGRAPHY RULES:\n"
        "  'Africa' / no geography → ISO3_LIST: ALL_AFRICA\n"
        "  Named countries → ISO3_LIST: ISO3 codes (e.g. NGA, ETH, KEN)\n\n"
        f"DATE RULES:\n"
        f"  No year → FROM_YEAR: {current_year - 10}, TO_YEAR: {current_year}\n"
        f"  'latest' → FROM_YEAR: {current_year - 5}, TO_YEAR: {current_year}\n\n"
        "OUTPUT FORMAT (exactly 5 lines):\n"
        "SERIES_CODES: CODE1, CODE2, CODE3\n"
        "ISO3_LIST: ALL_AFRICA or ETH, KEN, NGA\n"
        "FROM_YEAR: <year>\n"
        "TO_YEAR: <year>\n"
        "EXPLANATION: <one sentence>"
    )

    try:
        from langchain_core.prompts import ChatPromptTemplate

        from app.services.llm_service import get_llm

        llm = get_llm()
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{query}"),
        ])
        response = llm.invoke(prompt.format_messages(query=user_query))
        content = (response.content if hasattr(response, "content") else str(response)).strip()

        parsed: dict = {
            "series_codes": [], "iso3_codes": tuple(africa_iso3),
            "start_year": current_year - 10, "end_year": current_year, "explanation": "",
        }
        for line in content.splitlines():
            line = line.strip()
            if not line or ":" not in line:
                continue
            key, _, value = line.partition(":")
            key, value = key.strip().upper(), value.strip()
            if key == "SERIES_CODES" and value.upper() != "NONE":
                parsed["series_codes"] = [c.strip() for c in value.split(",") if c.strip()]
            elif key == "ISO3_LIST" and value.upper() != "NONE":
                if value.strip().upper() == "ALL_AFRICA":
                    parsed["iso3_codes"] = tuple(africa_iso3)
                else:
                    codes = [c.strip().upper() for c in value.split(",") if c.strip()]
                    filtered = tuple(c for c in codes if c in valid_iso3)
                    parsed["iso3_codes"] = filtered if filtered else tuple(africa_iso3)
            elif key == "FROM_YEAR" and value.upper() != "NONE":
                try:
                    parsed["start_year"] = int(value)
                except ValueError:
                    pass
            elif key == "TO_YEAR" and value.upper() != "NONE":
                try:
                    parsed["end_year"] = int(value)
                except ValueError:
                    pass
            elif key == "EXPLANATION":
                parsed["explanation"] = value

        # Filter to known series codes only
        parsed["series_codes"] = tuple(c for c in parsed["series_codes"] if c in uis_series)
        if not parsed["series_codes"]:
            logger.warning("LLM returned no valid UIS series codes")
            return None

        return parsed

    except Exception:
        logger.exception("Error parsing UIS query with LLM")
        st.error("Could not parse your query. Please try rephrasing or use Manual Selection.")
        return None


def parse_energy_query_with_llm(user_query: str) -> Optional[dict]:
    """Parse a natural-language query into UN Energy fetch parameters.

    Returns a dict with keys: ``dataset`` ('stats'|'balance'|'both'),
    ``m49_codes`` (tuple), ``country_names`` (str), ``start_year``,
    ``end_year``, ``explanation``. Returns ``None`` on failure.
    """
    from datetime import date

    current_year = date.today().year
    m49_map = get_african_m49()
    country_list = ", ".join(sorted(m49_map.values()))
    name_to_m49 = {v.lower(): k for k, v in m49_map.items()}

    system_prompt = (
        f"You are an expert at interpreting UN energy data queries.\n\n"
        f"TODAY'S YEAR: {current_year}\n\n"
        f"AVAILABLE AFRICAN COUNTRIES: {country_list}\n\n"
        "DATASET SELECTION:\n"
        "  stats (DF_UNDATA_ENERGY) — 75 specific commodities: coal, crude oil, natural gas,\n"
        "    electricity, solar, wind, biofuels; production/imports/exports by commodity.\n"
        "    Use for: specific fuel types, commodity-level production or trade flows.\n"
        "  balance (DF_UNData_EnergyBalance) — 11 broad groups in Terajoules: total primary\n"
        "    supply, transformation, final consumption by sector (industry/transport/residential).\n"
        "    Use for: total energy mix, energy balance, consumption by sector.\n"
        "  both — use when the query is broad or covers both levels.\n\n"
        "GEOGRAPHY RULES:\n"
        "  'Africa' / no geography → COUNTRIES: ALL_AFRICA\n"
        "  Named countries → COUNTRIES: exact names from the list above\n\n"
        f"DATE RULES:\n"
        f"  No year → FROM_YEAR: {current_year - 10}, TO_YEAR: {current_year}\n"
        f"  'latest' → FROM_YEAR: {current_year - 5}, TO_YEAR: {current_year}\n\n"
        "OUTPUT FORMAT (exactly 5 lines):\n"
        "DATASET: stats / balance / both\n"
        "COUNTRIES: ALL_AFRICA or Nigeria, Kenya, Ethiopia\n"
        "FROM_YEAR: <year>\n"
        "TO_YEAR: <year>\n"
        "EXPLANATION: <one sentence>"
    )

    try:
        from langchain_core.prompts import ChatPromptTemplate

        from app.services.llm_service import get_llm

        llm = get_llm()
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{query}"),
        ])
        response = llm.invoke(prompt.format_messages(query=user_query))
        content = (response.content if hasattr(response, "content") else str(response)).strip()

        parsed: dict = {
            "dataset": "both",
            "m49_codes": tuple(m49_map.keys()),
            "country_names": "All Africa",
            "start_year": current_year - 10,
            "end_year": current_year,
            "explanation": "",
        }
        for line in content.splitlines():
            line = line.strip()
            if not line or ":" not in line:
                continue
            key, _, value = line.partition(":")
            key, value = key.strip().upper(), value.strip()
            if key == "DATASET":
                ds = value.lower().strip()
                if ds in ("stats", "balance", "both"):
                    parsed["dataset"] = ds
            elif key == "COUNTRIES" and value.upper() != "NONE":
                if value.strip().upper() == "ALL_AFRICA":
                    parsed["m49_codes"] = tuple(m49_map.keys())
                    parsed["country_names"] = "All Africa"
                else:
                    names = [c.strip() for c in value.split(",") if c.strip()]
                    matched_codes, matched_names = [], []
                    for name in names:
                        m49 = name_to_m49.get(name.lower())
                        if not m49:
                            fm = fuzzy_match_country(name, list(m49_map.values()))
                            if fm:
                                m49 = name_to_m49.get(fm.lower())
                        if m49:
                            matched_codes.append(m49)
                            matched_names.append(m49_map.get(m49, name))
                    if matched_codes:
                        parsed["m49_codes"] = tuple(matched_codes)
                        parsed["country_names"] = ", ".join(matched_names)
            elif key == "FROM_YEAR" and value.upper() != "NONE":
                try:
                    parsed["start_year"] = int(value)
                except ValueError:
                    pass
            elif key == "TO_YEAR" and value.upper() != "NONE":
                try:
                    parsed["end_year"] = int(value)
                except ValueError:
                    pass
            elif key == "EXPLANATION":
                parsed["explanation"] = value

        return parsed

    except Exception:
        logger.exception("Error parsing Energy query with LLM")
        st.error("Could not parse your query. Please try rephrasing or use Manual Selection.")
        return None


def generate_undata_suggestions(
    df: pd.DataFrame,
    dataset_name: str = "UN Data",
) -> tuple[list[str], list[str]]:
    """Return ``(analysis_questions, visualization_ideas)`` for a UN Data dataset."""
    import json
    import re

    if df is None or df.empty:
        return [], []

    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        from app.services.llm_service import get_llm

        llm = get_llm()
        columns = df.columns.tolist()
        sample_vals: dict = {}
        for col in ["SERIES", "GEOGRAPHY", "COMMODITY", "TRANSACTION", "REF_AREA", "COUNTRY"]:
            if col in df.columns:
                sample_vals[col] = df[col].dropna().unique()[:5].tolist()

        prompt = (
            f"Based on this {dataset_name} dataset ({len(df):,} rows, "
            f"columns: {', '.join(columns)}, sample values: {sample_vals}), generate:\n"
            "1. 5 specific analysis questions about the data\n"
            "2. 5 specific chart/visualization ideas\n\n"
            'Return JSON: {"analysis_questions": [...], "visualization_ideas": [...]}'
        )
        response = llm.invoke([
            SystemMessage(content=f"You are a data analyst specialising in {dataset_name}."),
            HumanMessage(content=prompt),
        ])
        content = (response.content if hasattr(response, "content") else str(response)).strip()
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            result = json.loads(match.group(0))
            return result.get("analysis_questions", [])[:5], result.get("visualization_ideas", [])[:5]
    except Exception:
        logger.debug("UN Data suggestion generation failed", exc_info=True)

    return (
        [
            "What trends are visible in the data over time?",
            "Which countries show the highest values?",
            "How does the data vary across regions?",
        ],
        [
            "Create a line chart showing trends over time",
            "Create a bar chart comparing countries",
            "Create a heatmap showing data availability by country and year",
        ],
    )
