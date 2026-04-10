"""Geographic reference data: ISO codes, regions, and fuzzy matching.

Provides helper functions for resolving country names to ISO-2/ISO-3 codes,
grouping countries by UN region, and performing fuzzy country-name lookups.
Key exports: ``get_african_countries``, ``iso2_to_iso3``, ``fuzzy_match_country``.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd
import streamlit as st

from app.core.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# ISO-3166 / M49 reference data
# ---------------------------------------------------------------------------

@st.cache_data
def get_iso_reference_df() -> pd.DataFrame:
    """Load the ISO-3166 / M49 country reference CSV (cached)."""
    df = pd.read_csv("content/iso3_country_reference.csv")
    df["m49"] = df["m49"].astype(str)
    return df


def get_countries_by_region(region: str, code_column: str = "m49") -> list[str]:
    """Return a list of country codes for the given *region*."""
    df = get_iso_reference_df()
    return df.loc[df["Region Name"] == region, code_column].tolist()


def get_acled_region_countries(region: str) -> list[str]:
    """Return country names from the ISO reference for an ACLED region name.

    ACLED regions map to UN M49 sub-regions or intermediate regions
    (e.g. "Western Africa", "Eastern Africa") and occasionally to top-level
    region names (e.g. "Europe").  We check all three columns so a single
    lookup handles every case.
    """
    df = get_iso_reference_df()
    mask = (
        (df["Sub-region Name"] == region)
        | (df["Intermediate Region Name"] == region)
        | (df["Region Name"] == region)
    )
    return df.loc[mask, "Country or Area"].dropna().tolist()


# ---------------------------------------------------------------------------
# ACLED region mapping
# ---------------------------------------------------------------------------

ACLED_REGION_MAPPING: dict[str, int] = {
    "Western Africa": 1,
    "Middle Africa": 2,
    "Eastern Africa": 3,
    "Southern Africa": 4,
    "Northern Africa": 5,
    "South Asia": 7,
    "Southeast Asia": 9,
    "Middle East": 11,
    "Europe": 12,
    "Caucasus and Central Asia": 13,
    "Central America": 14,
    "South America": 15,
    "Caribbean": 16,
    "East Asia": 17,
    "North America": 18,
    "Oceania": 19,
    "Antarctica": 20,
}

# ---------------------------------------------------------------------------
# ACLED sub-event types
# ---------------------------------------------------------------------------

ACLED_SUB_EVENT_TYPES: list[str] = [
    "Government regains territory",
    "Non-state actor overtakes territory",
    "Armed clash",
    "Excessive force against protesters",
    "Protest with intervention",
    "Peaceful protest",
    "Violent demonstration",
    "Mob violence",
    "Chemical weapon",
    "Air/drone strike",
    "Suicide bomb",
    "Shelling/artillery/missile attack",
    "Remote explosive/landmine/IED",
    "Grenade",
    "Sexual violence",
    "Attack",
    "Abduction/forced disappearance",
    "Agreement",
    "Arrests",
    "Change to group/activity",
    "Disrupted weapons use",
    "Headquarters or base established",
    "Looting/property destruction",
    "Non-violent transfer of territory",
    "Other",
]

# ---------------------------------------------------------------------------
# Fuzzy matching helpers
# ---------------------------------------------------------------------------

_COUNTRY_ALIASES: dict[str, str] = {
    # Central / West Africa
    "DRC": "Democratic Republic of the Congo",
    "Congo-Kinshasa": "Democratic Republic of the Congo",
    "Congo (DRC)": "Democratic Republic of the Congo",
    "Congo": "Republic of the Congo",
    "Congo-Brazzaville": "Republic of the Congo",
    "CAR": "Central African Republic",
    "Ivory Coast": "Côte d'Ivoire",
    "Cote d'Ivoire": "Côte d'Ivoire",
    # East / Horn of Africa
    "Tanzania": "United Republic of Tanzania",
    "Tanzania, United Republic of": "United Republic of Tanzania",
    # Americas
    "Bolivia": "Bolivia (Plurinational State of)",
    "Venezuela": "Venezuela (Bolivarian Republic of)",
    "USA": "United States of America",
    "US": "United States of America",
    "United States": "United States of America",
    # Europe / Asia
    "Burma": "Myanmar",
    "UK": "United Kingdom",
    "UAE": "United Arab Emirates",
    "Iran": "Iran (Islamic Republic of)",
    "North Korea": "Democratic People's Republic of Korea",
    "South Korea": "Republic of Korea",
    "Russia": "Russian Federation",
    "Syria": "Syrian Arab Republic",
    "Laos": "Lao People's Democratic Republic",
    "Vietnam": "Viet Nam",
    "Palestine": "State of Palestine",
}


def fuzzy_match_country(name: str, candidates: list[str]) -> Optional[str]:
    """Best-effort match of *name* against *candidates*."""
    if not name or not isinstance(name, str):
        return None
    name = name.strip()

    if name in candidates:
        return name

    if name in _COUNTRY_ALIASES:
        alias = _COUNTRY_ALIASES[name]
        if alias in candidates:
            return alias

    lower = name.lower()
    for c in candidates:
        if lower == c.lower():
            return c

    for c in candidates:
        if lower in c.lower() or c.lower() in lower:
            return c

    words = set(lower.split())
    for c in candidates:
        ref_words = set(c.lower().split())
        if len(words) >= 2 and len(ref_words) >= 2:
            if len(words & ref_words) >= min(2, len(words) - 1):
                return c

    return None


def fuzzy_match_region(name: str, candidates: list[str]) -> Optional[str]:
    """Best-effort match of *name* against region *candidates*."""
    if not name or not isinstance(name, str):
        return None
    name = name.strip()

    if name in candidates:
        return name

    lower = name.lower()
    for c in candidates:
        if lower == c.lower():
            return c

    for c in candidates:
        if lower in c.lower() or c.lower() in lower:
            return c

    return None


def fuzzy_match_event_type(name: str, candidates: list[str]) -> Optional[str]:
    """Best-effort match of *name* against event-type *candidates*."""
    if not name or not isinstance(name, str):
        return None
    name = name.strip()

    if name in candidates:
        return name

    lower = name.lower()
    for c in candidates:
        if lower == c.lower():
            return c

    for c in candidates:
        words = set(lower.split())
        ref_words = set(c.lower().split())
        common = words & ref_words
        if len(common) >= 2 or (len(common) >= 1 and len(words) <= 3):
            return c

    return None
