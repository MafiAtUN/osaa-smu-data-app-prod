"""Tests for app.services.geo_service."""


from app.services.geo_service import (
    fuzzy_match_country,
    fuzzy_match_event_type,
    fuzzy_match_region,
)

COUNTRIES = [
    "Nigeria", "Kenya", "South Africa", "Democratic Republic of the Congo",
    "Republic of the Congo", "Côte d'Ivoire", "United States",
]

REGIONS = ["Western Africa", "Eastern Africa", "Southern Africa", "Northern Africa"]

EVENTS = ["Armed clash", "Peaceful protest", "Air/drone strike", "Sexual violence"]


class TestFuzzyMatchCountry:
    def test_exact_match(self):
        assert fuzzy_match_country("Nigeria", COUNTRIES) == "Nigeria"

    def test_alias_drc(self):
        assert fuzzy_match_country("DRC", COUNTRIES) == "Democratic Republic of the Congo"

    def test_alias_ivory_coast(self):
        assert fuzzy_match_country("Ivory Coast", COUNTRIES) == "Côte d'Ivoire"

    def test_case_insensitive(self):
        assert fuzzy_match_country("kenya", COUNTRIES) == "Kenya"

    def test_partial_match(self):
        assert fuzzy_match_country("South", COUNTRIES) == "South Africa"

    def test_no_match(self):
        assert fuzzy_match_country("Narnia", COUNTRIES) is None

    def test_empty(self):
        assert fuzzy_match_country("", COUNTRIES) is None

    def test_none(self):
        assert fuzzy_match_country(None, COUNTRIES) is None


class TestFuzzyMatchRegion:
    def test_exact(self):
        assert fuzzy_match_region("Western Africa", REGIONS) == "Western Africa"

    def test_case(self):
        assert fuzzy_match_region("eastern africa", REGIONS) == "Eastern Africa"

    def test_partial(self):
        assert fuzzy_match_region("Northern", REGIONS) == "Northern Africa"


class TestFuzzyMatchEventType:
    def test_exact(self):
        assert fuzzy_match_event_type("Armed clash", EVENTS) == "Armed clash"

    def test_case(self):
        assert fuzzy_match_event_type("armed clash", EVENTS) == "Armed clash"
