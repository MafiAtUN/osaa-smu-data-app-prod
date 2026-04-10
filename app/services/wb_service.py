"""World Bank data access via the ``wbgapi`` package.

Wraps the World Bank Open Data API to search indicators, fetch time-series
data for African countries, and convert natural-language questions into
``wbgapi`` query parameters via LLM.  Key exports: ``fetch_wb_data``,
``search_wb_indicators``, ``parse_wb_query_with_llm``, and
``WB_QUERY_SUGGESTIONS`` for pre-built UI pill prompts.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

import pandas as pd
import streamlit as st
import wbgapi as wb

from app.core.logging import get_logger
from app.services.geo_service import fuzzy_match_country, get_iso_reference_df

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Curated indicator catalogue (used in AI prompt to avoid hallucinations)
# ---------------------------------------------------------------------------

_WB_INDICATOR_CATALOGUE = {
    # ── Population & Demographics ──────────────────────────────────────────
    "SP.POP.TOTL":          "Population, total",
    "SP.POP.GROW":          "Population growth (annual %)",
    "SP.URB.TOTL.IN.ZS":   "Urban population (% of total population)",
    "SP.URB.GROW":          "Urban population growth (annual %)",
    "SP.DYN.TFRT.IN":      "Fertility rate, total (births per woman)",
    "SP.DYN.CBRT.IN":      "Birth rate, crude (per 1,000 people)",
    "SP.DYN.CDRT.IN":      "Death rate, crude (per 1,000 people)",
    "SP.POP.0014.TO.ZS":   "Population ages 0-14 (% of total population)",
    "SP.POP.1564.TO.ZS":   "Population ages 15-64 (% of total population)",
    "SP.POP.65UP.TO.ZS":   "Population ages 65 and above (% of total population)",
    "SM.POP.NETM":          "Net migration",
    "SP.POP.DPND":          "Age dependency ratio (% of working-age population)",
    "SP.POP.DPND.YG":      "Age dependency ratio, young (% of working-age population)",

    # ── Economy & Income ──────────────────────────────────────────────────
    "NY.GDP.MKTP.CD":      "GDP (current US$)",
    "NY.GDP.MKTP.KD.ZG":   "GDP growth (annual %)",
    "NY.GDP.PCAP.CD":      "GDP per capita (current US$)",
    "NY.GDP.PCAP.KD.ZG":   "GDP per capita growth (annual %)",
    "NY.GNP.PCAP.CD":      "GNI per capita, Atlas method (current US$)",
    "NY.GNP.PCAP.PP.CD":   "GNI per capita, PPP (current international $)",
    "NY.GDP.MKTP.PP.CD":   "GDP, PPP (current international $)",
    "NE.EXP.GNFS.ZS":      "Exports of goods and services (% of GDP)",
    "NE.IMP.GNFS.ZS":      "Imports of goods and services (% of GDP)",
    "NE.TRD.GNFS.ZS":      "Trade (% of GDP)",
    "BX.KLT.DINV.WD.GD.ZS": "Foreign direct investment, net inflows (% of GDP)",
    "BX.KLT.DINV.CD.WD":   "Foreign direct investment, net inflows (BoP, current US$)",
    "GC.TAX.TOTL.GD.ZS":   "Tax revenue (% of GDP)",
    "GC.XPN.TOTL.GD.ZS":   "Expenditure, total (% of GDP)",
    "NE.GDI.TOTL.ZS":      "Gross capital formation (% of GDP)",
    "NY.ADJ.NNTY.PC.KD.ZG": "Adjusted net national income per capita (annual % growth)",
    "NE.CON.GOVT.ZS":      "General government final consumption expenditure (% of GDP)",
    "FP.CPI.TOTL.ZG":      "Inflation, consumer prices (annual %)",

    # ── Poverty & Inequality ──────────────────────────────────────────────
    "SI.POV.DDAY":          "Poverty headcount ratio at $2.15 a day, 2017 PPP (% of population)",
    "SI.POV.LMIC":          "Poverty headcount ratio at $3.65 a day, 2017 PPP (% of population)",
    "SI.POV.UMIC":          "Poverty headcount ratio at $6.85 a day, 2017 PPP (% of population)",
    "SI.POV.NAHC":          "Poverty headcount ratio at national poverty lines (% of population)",
    "SI.POV.GAPS":          "Poverty gap at $2.15 a day, 2017 PPP (%)",
    "SI.POV.GINI":          "Gini index (World Bank estimate)",
    "SI.DST.FRST.20":       "Income share held by lowest 20%",
    "SI.DST.10TH.10":       "Income share held by highest 10%",
    "SI.DST.04TH.20":       "Income share held by fourth 20%",
    "SI.SPR.PC40.ZG":       "Growth rate of expenditure or income per capita of bottom 40% (%)",

    # ── Health ────────────────────────────────────────────────────────────
    "SH.DYN.MORT":          "Mortality rate, under-5 (per 1,000 live births)",
    "SH.DYN.NMRT":          "Mortality rate, neonatal (per 1,000 live births)",
    "SP.DYN.IMRT.IN":       "Mortality rate, infant (per 1,000 live births)",
    "SH.STA.MMRT":          "Maternal mortality ratio (modeled estimate, per 100,000 live births)",
    "SP.DYN.LE00.IN":       "Life expectancy at birth, total (years)",
    "SP.DYN.LE00.FE.IN":    "Life expectancy at birth, female (years)",
    "SP.DYN.LE00.MA.IN":    "Life expectancy at birth, male (years)",
    "SH.MED.PHYS.ZS":       "Physicians (per 1,000 people)",
    "SH.MED.BEDS.ZS":       "Hospital beds (per 1,000 people)",
    "SH.H2O.BASW.ZS":       "People using safely managed drinking water services (% of population)",
    "SH.STA.HYGN.ZS":       "People with basic handwashing facilities including soap and water (% of population)",
    "SH.HIV.INCD.ZS":       "Incidence of HIV (per 1,000 uninfected population ages 15-49)",
    "SH.TBS.INCD":          "Incidence of tuberculosis (per 100,000 people)",
    "SH.MLR.INCD.P3":       "Incidence of malaria (per 1,000 population at risk)",
    "SH.XPD.CHEX.GD.ZS":   "Current health expenditure (% of GDP)",
    "SH.XPD.OOPC.CH.ZS":   "Out-of-pocket expenditure (% of current health expenditure)",

    # ── Education ────────────────────────────────────────────────────────
    "SE.PRM.ENRR":          "School enrollment, primary (% gross)",
    "SE.SEC.ENRR":          "School enrollment, secondary (% gross)",
    "SE.TER.ENRR":          "School enrollment, tertiary (% gross)",
    "SE.ADT.LITR.ZS":       "Literacy rate, adult total (% of people ages 15 and above)",
    "SE.ADT.1524.LT.ZS":    "Literacy rate, youth total (% of people ages 15-24)",
    "SE.PRM.CMPT.ZS":       "Primary completion rate, total (% of relevant age group)",
    "SE.PRM.NENR":          "School enrollment, primary (% net)",
    "SE.PRM.ENRR.FE":       "School enrollment, primary, female (% gross)",
    "SE.SEC.ENRR.FE":       "School enrollment, secondary, female (% gross)",
    "SE.ENR.PRSC.FM.ZS":    "School enrollment, primary and secondary (gross), gender parity index (GPI)",
    "SE.XPD.TOTL.GD.ZS":   "Government expenditure on education, total (% of GDP)",
    "SE.XPD.TOTL.GB.ZS":   "Government expenditure on education (% of government expenditure)",

    # ── Gender ────────────────────────────────────────────────────────────
    "SG.GEN.PARL.ZS":       "Proportion of seats held by women in national parliaments (%)",
    "SL.TLF.ACTI.FE.ZS":   "Labor force participation rate, female (% of female population ages 15+)",
    "SL.TLF.ACTI.MA.ZS":   "Labor force participation rate, male (% of male population ages 15+)",
    "SP.ADO.TFRT":          "Adolescent fertility rate (births per 1,000 women ages 15-19)",
    "SH.PRG.ANEM":          "Prevalence of anemia among pregnant women (%)",

    # ── Labor & Employment ────────────────────────────────────────────────
    "SL.UEM.TOTL.ZS":       "Unemployment, total (% of total labor force) (modeled ILO estimate)",
    "SL.UEM.1524.ZS":       "Unemployment, youth total (% of total labor force ages 15-24)",
    "SL.UEM.TOTL.FE.ZS":   "Unemployment, female (% of female labor force)",
    "SL.TLF.ACTI.ZS":      "Labor force participation rate, total (% of total population ages 15+)",
    "SL.AGR.EMPL.ZS":       "Employment in agriculture (% of total employment) (modeled ILO estimate)",
    "SL.IND.EMPL.ZS":       "Employment in industry (% of total employment) (modeled ILO estimate)",
    "SL.SRV.EMPL.ZS":       "Employment in services (% of total employment) (modeled ILO estimate)",
    "SL.EMP.VULN.ZS":       "Vulnerable employment, total (% of total employment) (modeled ILO estimate)",

    # ── Infrastructure & Technology ───────────────────────────────────────
    "EG.ELC.ACCS.ZS":       "Access to electricity (% of population)",
    "EG.ELC.ACCS.RU.ZS":   "Access to electricity, rural (% of rural population)",
    "EG.ELC.RNEW.ZS":       "Renewable electricity output (% of total electricity output)",
    "EG.FEC.RNEW.ZS":       "Renewable energy consumption (% of total final energy consumption)",
    "EG.USE.PCAP.KG.OE":    "Energy use (kg of oil equivalent per capita)",
    "IT.NET.USER.ZS":        "Individuals using the Internet (% of population)",
    "IT.CEL.SETS.P2":        "Mobile cellular subscriptions (per 100 people)",
    "IT.MLT.MAIN.P2":        "Fixed telephone subscriptions (per 100 people)",
    "IS.ROD.PAVE.ZS":        "Roads, paved (% of total roads)",

    # ── Environment & Climate ─────────────────────────────────────────────
    "EN.ATM.CO2E.PC":        "CO2 emissions (metric tons per capita)",
    "EN.ATM.CO2E.KT":        "CO2 emissions (kt)",
    "EN.ATM.GHGT.KT.CE":     "Total greenhouse gas emissions (kt of CO2 equivalent)",
    "AG.LND.FRST.ZS":        "Forest area (% of land area)",
    "AG.LND.FRST.K2":        "Forest area (sq. km)",
    "ER.H2O.FWTL.ZS":        "Annual freshwater withdrawals, total (% of internal resources)",
    "AG.LND.ARBL.ZS":        "Arable land (% of land area)",

    # ── Agriculture & Food Security ───────────────────────────────────────
    "AG.YLD.CREL.KG":        "Cereal yield (kg per hectare)",
    "SN.ITK.DEFC.ZS":        "Prevalence of undernourishment (% of population)",
    "SH.STA.STNT.ZS":        "Prevalence of stunting, height for age (% of children under 5)",
    "SH.STA.WAST.ZS":        "Prevalence of wasting, weight for height (% of children under 5)",
    "AG.PRD.FOOD.XD":        "Food production index (2014-2016 = 100)",

    # ── Finance, Aid & Debt ───────────────────────────────────────────────
    "DT.ODA.ALLD.CD":        "Net official development assistance and official aid received (current US$)",
    "DT.ODA.ODAT.PC.ZS":    "Net ODA received per capita (current US$)",
    "DT.DOD.DECT.GN.ZS":    "External debt stocks, total (% of GNI)",
    "DT.DOD.DECT.CD":        "External debt stocks, total (current US$)",
    "DT.TDS.DECT.GN.ZS":    "Debt service, total (% of GNI)",
    "DT.TDS.DECT.EX.ZS":    "Debt service (% of exports of goods, services and primary income)",
    "GC.DOD.TOTL.GD.ZS":    "Central government debt, total (% of GDP)",
    "FS.AST.PRVT.GD.ZS":    "Domestic credit to private sector (% of GDP)",
    "BX.TRF.PWKR.DT.GD.ZS": "Personal remittances, received (% of GDP)",

    # ── Governance & Institutions ─────────────────────────────────────────
    "CC.EST":                "Control of Corruption: Estimate (Worldwide Governance Indicators)",
    "GE.EST":                "Government Effectiveness: Estimate (Worldwide Governance Indicators)",
    "RQ.EST":                "Regulatory Quality: Estimate (Worldwide Governance Indicators)",
    "RL.EST":                "Rule of Law: Estimate (Worldwide Governance Indicators)",
    "PV.EST":                "Political Stability and Absence of Violence/Terrorism: Estimate (WGI)",
    "VA.EST":                "Voice and Accountability: Estimate (Worldwide Governance Indicators)",
    "IQ.CPA.PROP.XQ":        "CPIA property rights and rule-based governance rating (1=low to 6=high)",
    "IQ.CPA.PUBS.XQ":        "CPIA quality of budgetary and financial management rating (1=low to 6=high)",
}

# ---------------------------------------------------------------------------
# Cached helpers
# ---------------------------------------------------------------------------

@st.cache_data
def get_databases() -> list[tuple[int, str]] | Exception:
    try:
        return [(db["id"], db["name"]) for db in wb.source.list()]
    except Exception as exc:
        return exc


@st.cache_data
def get_indicators() -> list[dict[str, Any]] | Exception:
    try:
        return list(wb.series.list())
    except Exception as exc:
        return exc


@st.cache_data
def get_countries() -> list[dict[str, Any]] | Exception:
    try:
        return list(wb.economy.list())
    except Exception as exc:
        return exc


@st.cache_data
def get_wb_data(
    indicators: list[str],
    countries: list[str],
    time_range: list[int],
) -> pd.DataFrame:
    return wb.data.DataFrame(indicators, countries, time_range).reset_index()


def set_database(db_id: int) -> None:
    """Set the active World Bank database for subsequent API calls."""
    wb.db = db_id


def enrich_wb_dataframe(
    df: pd.DataFrame,
    selected_indicators: list[str],
    selected_iso3_codes: list[str],
    indicators: list[dict[str, Any]],
) -> pd.DataFrame:
    """Merge WB raw output with ISO reference, melt year columns, and clean up."""
    iso3_df = get_iso_reference_df()

    if "economy" not in df.columns:
        df["economy"] = selected_iso3_codes[0] if selected_iso3_codes else ""
    if "series" not in df.columns:
        df["series"] = selected_indicators[0] if selected_indicators else ""

    merge_cols = [
        "Country or Area", "Region Name", "Sub-region Name",
        "Intermediate Region Name", "iso2", "iso3", "m49",
    ]
    df = df.merge(
        iso3_df[[c for c in merge_cols if c in iso3_df.columns]],
        left_on="economy", right_on="iso3", how="left",
    )
    df.drop(columns=["iso3"], inplace=True, errors="ignore")
    df = df.rename(columns={"series": "Indicator", "economy": "iso3"})

    code_desc = {d["id"]: d["value"] for d in indicators}
    df["Indicator Description"] = df["Indicator"].map(code_desc)

    id_cols = [c for c in df.columns if not c.startswith("YR")]
    df = df.melt(id_vars=id_cols, var_name="Year", value_name="Value")
    df["Year"] = df["Year"].str.extract(r"(\d{4})").astype(int)

    return df


# ---------------------------------------------------------------------------
# AI query parsing
# ---------------------------------------------------------------------------

def parse_wb_query_with_llm(user_query: str) -> Optional[dict[str, Any]]:
    """Use the LLM to extract World Bank API parameters from a natural-language query."""
    from datetime import date

    from app.services.llm_service import get_llm

    iso3_df = get_iso_reference_df()
    regions_list = iso3_df["Region Name"].dropna().unique().tolist()
    current_year = date.today().year

    catalogue_block = "\n".join(
        f"  {code}: {desc}" for code, desc in _WB_INDICATOR_CATALOGUE.items()
    )
    regions_block = "\n".join(f"  - {r}" for r in regions_list)

    system_prompt = f"""You are an expert at extracting structured parameters from natural language queries about World Bank development data.

TODAY'S YEAR: {current_year}

CURATED INDICATOR CATALOGUE (preferred — use exact codes from this list when possible):
{catalogue_block}

If the user asks for something NOT in the catalogue, output a short search term in SEARCH_TERMS instead of an indicator code.

AVAILABLE REGIONS (use exact names):
{regions_block}

CONCEPT → INDICATOR MAPPINGS (quick reference):
  "population" → SP.POP.TOTL
  "GDP" / "economic growth" / "economy" → NY.GDP.MKTP.CD, NY.GDP.MKTP.KD.ZG
  "GDP per capita" / "income per person" → NY.GDP.PCAP.CD
  "poverty" → SI.POV.DDAY, SI.POV.NAHC
  "inequality" / "gini" → SI.POV.GINI
  "child mortality" / "under-5 mortality" → SH.DYN.MORT
  "infant mortality" → SP.DYN.IMRT.IN
  "maternal mortality" → SH.STA.MMRT
  "life expectancy" → SP.DYN.LE00.IN
  "HIV" / "AIDS" → SH.HIV.INCD.ZS
  "tuberculosis" / "TB" → SH.TBS.INCD
  "malaria" → SH.MLR.INCD.P3
  "education" / "school enrollment" → SE.PRM.ENRR, SE.SEC.ENRR
  "literacy" → SE.ADT.LITR.ZS
  "gender parity" / "gender equality" → SG.GEN.PARL.ZS, SE.ENR.PRSC.FM.ZS
  "unemployment" → SL.UEM.TOTL.ZS
  "youth unemployment" → SL.UEM.1524.ZS
  "electricity" / "energy access" → EG.ELC.ACCS.ZS
  "renewable energy" → EG.ELC.RNEW.ZS
  "internet" / "digital" → IT.NET.USER.ZS
  "CO2" / "carbon emissions" / "climate" → EN.ATM.CO2E.PC
  "deforestation" / "forest" → AG.LND.FRST.ZS
  "trade" / "exports" / "imports" → NE.TRD.GNFS.ZS
  "FDI" / "foreign investment" → BX.KLT.DINV.WD.GD.ZS
  "inflation" → FP.CPI.TOTL.ZG
  "debt" / "external debt" → DT.DOD.DECT.GN.ZS
  "ODA" / "aid" / "development assistance" → DT.ODA.ALLD.CD
  "corruption" / "governance" → CC.EST, GE.EST

REGION CONCEPT MAPPINGS:
  "Africa" / "African countries" → Eastern Africa, Middle Africa, Northern Africa, Southern Africa, Western Africa
  "sub-Saharan Africa"           → Eastern Africa, Middle Africa, Southern Africa, Western Africa
  "East Africa"                  → Eastern Africa
  "West Africa"                  → Western Africa
  "Southern Africa"              → Southern Africa
  "North Africa"                 → Northern Africa

DATE RULES:
  - "current" / "now" / "latest" → TO_YEAR: {current_year}
  - "from [year]" with no end → FROM_YEAR: [year], TO_YEAR: {current_year}
  - "last 10 years" → FROM_YEAR: {current_year - 10}, TO_YEAR: {current_year}
  - "last 5 years" → FROM_YEAR: {current_year - 5}, TO_YEAR: {current_year}
  - "in 2020" → FROM_YEAR: 2020, TO_YEAR: 2020
  - "2010 to 2020" → FROM_YEAR: 2010, TO_YEAR: 2020

OUTPUT FORMAT — return EXACTLY 8 lines, no extra text:
INDICATORS: code1, code2 (exact codes from catalogue, or NONE)
SEARCH_TERMS: term1, term2 (free-text search if no exact code, or NONE)
COUNTRIES: Country1, Country2 (exact UN country names, or NONE)
REGIONS: Region1, Region2 (exact region names, or NONE)
FROM_YEAR: 2010 (4-digit year, or NONE)
TO_YEAR: 2023 (4-digit year, or NONE)
LIMIT: 50 (max countries to include; default 50, or ALL for all countries)
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
            "indicators": [], "search_terms": [], "countries": [],
            "regions": [], "from_year": None, "to_year": None,
            "limit": 50, "explanation": "",
        }

        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            upper = line.upper()
            value = line.split(":", 1)[1].strip() if ":" in line else ""
            if upper.startswith("INDICATORS:") and value.upper() != "NONE":
                parsed["indicators"] = [i.strip() for i in value.split(",") if i.strip()]
            elif upper.startswith("SEARCH_TERMS:") and value.upper() != "NONE":
                parsed["search_terms"] = [s.strip() for s in value.split(",") if s.strip()]
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
            elif upper.startswith("LIMIT:") and value.upper() != "ALL":
                try:
                    parsed["limit"] = int(value)
                except ValueError:
                    pass
            elif upper.startswith("EXPLANATION:"):
                parsed["explanation"] = value

        if not any([parsed["indicators"], parsed["search_terms"], parsed["countries"], parsed["regions"]]):
            return None

        # Resolve country names to ISO3 codes
        iso3_df_local = get_iso_reference_df()
        iso3_candidates = iso3_df_local["Country or Area"].tolist()
        resolved_countries: list[str] = []
        for name in parsed["countries"]:
            matched = fuzzy_match_country(name, iso3_candidates)
            if matched:
                row = iso3_df_local.loc[iso3_df_local["Country or Area"] == matched]
                if not row.empty:
                    iso3 = row.iloc[0]["iso3"]
                    if isinstance(iso3, str) and iso3:
                        resolved_countries.append(iso3)
        parsed["country_codes"] = resolved_countries

        # Resolve region names → ISO3 codes
        region_iso3: list[str] = []
        for region in parsed["regions"]:
            codes = iso3_df_local.loc[iso3_df_local["Region Name"] == region, "iso3"].tolist()
            region_iso3.extend(c for c in codes if isinstance(c, str) and c)
        parsed["region_codes"] = list(set(region_iso3))

        # Validate indicator codes against catalogue (filter out hallucinations)
        valid_indicators = [i for i in parsed["indicators"] if i in _WB_INDICATOR_CATALOGUE]
        unknown_indicators = [i for i in parsed["indicators"] if i not in _WB_INDICATOR_CATALOGUE]
        parsed["indicators"] = valid_indicators
        if unknown_indicators:
            parsed["search_terms"].extend(unknown_indicators)

        return parsed

    except Exception as exc:
        logger.exception("Error parsing WB query with LLM")
        st.error("Could not interpret the World Bank query. Please rephrase it.")
        return None


def search_wb_indicators(search_terms: list[str], max_results: int = 5) -> list[str]:
    """Search WB series for *search_terms* and return up to *max_results* indicator codes."""
    found: list[str] = []
    for term in search_terms:
        try:
            for item in wb.series.list(q=term):
                code = item.get("id") or item.get("code", "")
                if code and code not in found:
                    found.append(code)
                if len(found) >= max_results:
                    break
        except Exception:
            logger.debug("WB indicator search failed for term: %s", term, exc_info=True)
    return found[:max_results]


def fetch_wb_data_ai(parsed: dict[str, Any]) -> tuple[Optional[pd.DataFrame], Optional[str]]:
    """Fetch World Bank data for AI-parsed parameters and return ``(df, error)``."""
    from datetime import date

    current_year = date.today().year

    # Resolve indicators
    indicator_codes = list(parsed.get("indicators", []))
    search_terms = parsed.get("search_terms", [])
    if search_terms and not indicator_codes:
        indicator_codes = search_wb_indicators(search_terms)
    if not indicator_codes:
        return None, "No indicators could be resolved. Please refine your query."

    # Resolve countries
    country_codes: list[str] = list(parsed.get("country_codes", []))
    if not country_codes:
        region_codes = parsed.get("region_codes", [])
        if region_codes:
            country_codes = region_codes
    if not country_codes:
        country_codes = ["all"]  # wbgapi "all" = all economies

    # Year range
    from_year = parsed.get("from_year") or (current_year - 10)
    to_year = parsed.get("to_year") or current_year
    try:
        from_year, to_year = int(from_year), int(to_year)
    except (ValueError, TypeError):
        return None, f"Invalid year range: {from_year}–{to_year}"
    if from_year > to_year:
        return None, f"from_year ({from_year}) is after to_year ({to_year})"

    try:
        raw = wb.data.DataFrame(
            indicator_codes,
            country_codes,
            list(range(from_year, to_year + 1)),
        ).reset_index()
        if raw.empty:
            return None, "No data returned for the selected parameters."

        # Build a minimal indicator lookup from catalogue
        catalogue_lookup = [{"id": k, "value": v} for k, v in _WB_INDICATOR_CATALOGUE.items()]
        df = enrich_wb_dataframe(raw, indicator_codes, country_codes, catalogue_lookup)
        return df, None

    except Exception as exc:
        logger.exception("Error fetching WB data")
        return None, f"Error fetching data: {exc}"


def generate_wb_suggestions(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    """Return ``(analysis_questions, visualization_ideas)`` for a WB dataset."""
    if df is None or df.empty:
        return [], []
    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        from app.services.llm_service import get_llm

        llm = get_llm()
        columns = df.columns.tolist()
        indicators = df["Indicator"].unique().tolist()[:5] if "Indicator" in df.columns else []
        countries = df["Country or Area"].unique().tolist()[:5] if "Country or Area" in df.columns else []

        prompt_text = f"""Based on this World Bank dataset ({len(df)} rows):
Indicators: {', '.join(indicators)}
Countries (sample): {', '.join(countries)}
Columns: {', '.join(columns)}

Generate:
1. 5-7 specific analysis questions about development trends
2. 5-7 specific visualization ideas

Return JSON: {{"analysis_questions": [...], "visualization_ideas": [...]}}"""

        response = llm.invoke([
            SystemMessage(content="You are a World Bank development data analyst specializing in African development."),
            HumanMessage(content=prompt_text),
        ])
        content = (response.content if hasattr(response, "content") else str(response)).strip()
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            result = json.loads(match.group(0))
            return result.get("analysis_questions", [])[:7], result.get("visualization_ideas", [])[:7]
    except Exception:
        logger.debug("WB suggestion generation failed", exc_info=True)

    return (
        ["How has GDP per capita changed over time?",
         "Which countries show the fastest poverty reduction?",
         "Compare education enrollment rates across regions",
         "Analyze health indicator trends"],
        ["Line chart of GDP growth over time",
         "Bar chart comparing countries",
         "Scatter plot of GDP vs life expectancy",
         "Heatmap of indicator values by country"],
    )


# ---------------------------------------------------------------------------
# Pre-built query suggestions (displayed as clickable pills on the AI page)
# ---------------------------------------------------------------------------

#: Each entry: {"label": short pill text, "query": NL query, "description": caption}
WB_QUERY_SUGGESTIONS: list[dict] = [
    {
        "label": "📈 GDP Per Capita, Africa",
        "query": "Show GDP per capita for all African countries from 2010 to 2023",
        "description": "Economic development overview across the entire African continent — a great starting point.",
    },
    {
        "label": "👶 Child & Maternal Mortality",
        "query": "Compare child mortality and maternal mortality trends in West Africa from 2000 to 2022",
        "description": "SDG 3 health system performance — Africa has 70% of global maternal deaths.",
    },
    {
        "label": "📱 Internet & Mobile Access",
        "query": "Internet access and mobile subscriptions in sub-Saharan Africa over the last 15 years",
        "description": "Digital inclusion and leapfrogging analysis — mobile is the primary gateway in Africa.",
    },
    {
        "label": "💸 Poverty & Inequality",
        "query": "Poverty headcount at $2.15 per day and Gini inequality for East African countries from 2005 to 2020",
        "description": "SDG 1 and SDG 10 — poverty and inequality trends in East Africa.",
    },
    {
        "label": "⚡ Rural Electricity Access",
        "query": "Electricity access for rural and urban populations in Nigeria, Ethiopia, and DRC from 2010 to 2023",
        "description": "Energy access gap between urban and rural areas — SDG 7.",
    },
    {
        "label": "👨‍💼 Youth Unemployment",
        "query": "Youth unemployment and labor force participation rates across Southern Africa from 2000 to 2022",
        "description": "Youth employment crisis and SDG 8 decent work analysis in Southern Africa.",
    },
    {
        "label": "🏦 Debt & Aid Flows",
        "query": "External debt as a percentage of GNI and ODA received for fragile African states from 2010 to 2023",
        "description": "Debt sustainability and development finance analysis for fragile and conflict-affected states.",
    },
    {
        "label": "🌿 CO2 & Forest Cover",
        "query": "CO2 emissions per capita and forest area for Central African countries from 1990 to 2020",
        "description": "Climate and environment tracking — SDG 13 and SDG 15 for the Congo Basin region.",
    },
    {
        "label": "🏫 Education & Literacy",
        "query": "Primary school enrollment and female literacy rates across the Sahel from 2000 to 2022",
        "description": "Education access and gender parity in Sahel LDCs — SDG 4.",
    },
    {
        "label": "🏛️ Governance Quality",
        "query": "Government effectiveness and corruption control scores for African regions from 2015 to 2022",
        "description": "Worldwide Governance Indicators — institutional capacity and SDG 16 progress across Africa.",
    },
]
