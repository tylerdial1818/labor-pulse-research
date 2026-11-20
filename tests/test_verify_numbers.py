import pytest

from lpresearch.facts import Fact, FactSheet, Source
from lpresearch.verify_numbers import extract_numbers, unverified

SRC = Source(kind="computed", ref="studies/x/outputs/model_results.json")


@pytest.fixture
def facts():
    sheet = FactSheet(study="x", model_version="0")
    sheet.add(Fact("cost", 7505.288836504436, "usd", "cost", SRC))
    sheet.add(Fact("bcr", 4.773971392337122, "ratio", "bcr", SRC))
    sheet.add(Fact("p_pos", 0.9808, "proportion", "prob", SRC))
    sheet.add(Fact("utah_npv", -6241.6904518246, "usd", "utah", SRC))
    sheet.add(Fact("horizon", 10, "years", "horizon", SRC))
    sheet.add(Fact("big", 28324745.36, "usd", "cohort npv", SRC))
    return sheet


@pytest.mark.parametrize(
    "text",
    [
        "The program costs $7,505 per person.",
        "It costs about $7.5k.",
        "Each dollar returns $4.77.",
        "A benefit-cost ratio of 4.8.",
        "Net benefits are positive in 98% of draws.",
        "Net benefits are positive in 98.1 percent of draws.",
        "Utah's budget takes a net cost of $6,242 per person.",
        "Over a 10-year horizon.",
        "Cohort net benefits reach $28.3 million.",
        "In 2025 dollars, using WorkAdvance data from COVID-19 era follow-ups.",
    ],
)
def test_backed_numbers_pass(facts, text):
    assert unverified(text, facts) == []


@pytest.mark.parametrize(
    "text, bad",
    [
        ("The program costs $7,600 per person.", "$7,600"),
        ("A benefit-cost ratio of 4.78.", "4.78"),
        ("Positive in 99% of draws.", "99%"),
        ("Over a 12-year horizon.", "12"),
        ("Each dollar returns $4.77, or 477%.", "477%"),
    ],
)
def test_unbacked_numbers_fail(facts, text, bad):
    assert [m.text for m in unverified(text, facts)] == [bad]


def test_currency_does_not_match_proportion(facts):
    assert [m.text for m in unverified("It costs $0.98.", facts)] == ["$0.98"]


def test_extract_skips_identifiers_but_keeps_negatives():
    values = [m.value for m in extract_numbers("H1B v0.1 COVID-19 net -6,242 and 3.5%")]
    assert values == [6242.0, 3.5]


def test_fact_rejects_bad_external_source():
    with pytest.raises(ValueError):
        Source(kind="external", ref="not a url")


def test_factsheet_rejects_duplicates(facts):
    with pytest.raises(ValueError):
        facts.add(Fact("cost", 1, "usd", "dup", SRC))


def test_factsheet_round_trip(facts, tmp_path):
    path = tmp_path / "facts.json"
    facts.write(path)
    assert FactSheet.read(path) == facts
