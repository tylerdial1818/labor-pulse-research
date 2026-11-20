"""Accounting checks on the report tables, independent of the Node baseline."""

import pytest

from lpresearch.pipelines.utah_roi import model, sensitivity

from .conftest import UTAH


@pytest.fixture(scope="module")
def tables(inputs, evidence):
    draws = model.simulate_reference(inputs, evidence, 500)["draws"]
    return sensitivity.build_report_tables(UTAH, inputs, evidence, draws)


def test_funding_shares_do_not_change_societal_npv(tables, reference):
    rows = tables["funding_share_scenarios.csv"]
    assert {r["societal_npv_per_person"] for r in rows} == {reference["perspectives"]["Societal"]["npv_per_person"]}
    for r in rows:
        shares = r["utah_share"] + r["federal_share"] + r["employer_share"] + r["philanthropic_share"]
        assert shares == pytest.approx(1)
        paid = (
            r["utah_cost_per_person"]
            + r["federal_cost_per_person"]
            + r["employer_cost_per_person"]
            + r["philanthropic_cost_per_person"]
        )
        assert paid == pytest.approx(r["total_program_cost_per_person"])


def test_utah_only_matches_reference_utah_perspective(tables, reference):
    utah_only = next(r for r in tables["funding_share_scenarios.csv"] if r["scenario_id"] == "utah_only")
    assert utah_only["utah_npv_per_person"] == pytest.approx(
        reference["perspectives"]["Utah Government"]["npv_per_person"]
    )


def test_frontier_breaks_even_at_reference_benefits(tables, reference):
    row = next(r for r in tables["break_even_frontier.csv"] if r["effect_retention"] == 1)
    assert row["break_even_program_cost"] == pytest.approx(reference["break_even"]["societal_program_cost_per_person"])
    for r in tables["break_even_frontier.csv"]:
        assert r["positive_net_benefits"] == (1 if r["program_cost_per_person"] < r["break_even_program_cost"] else 0)


def test_benefit_composition_totals_match_present_values(tables, reference):
    totals = {r["component"]: r["pv_per_person"] for r in tables["benefit_composition.csv"] if r["period"] == "Total"}
    societal = reference["perspectives"]["Societal"]
    benefits = totals["Incremental earnings"] + totals["Fringe benefits"]
    assert benefits * 1000 == pytest.approx(societal["pv_benefits_cohort"])
    assert totals["Program cost"] == pytest.approx(reference["program_cost_per_person"])


def test_parameter_sensitivity_moves_the_right_way(tables):
    rows = {(r["sensitivity_id"], r["perspective"]): r for r in tables["one_way_sensitivity.csv"]}
    cost = rows[("program_cost", "Societal")]
    assert cost["low_npv_per_person"] > cost["base_npv_per_person"] > cost["high_npv_per_person"]
    discount = rows[("discount_rate", "Societal")]
    assert discount["low_npv_per_person"] > discount["base_npv_per_person"] > discount["high_npv_per_person"]
    tax = rows[("federal_income_tax", "Societal")]
    assert tax["low_npv_per_person"] == pytest.approx(tax["high_npv_per_person"])


def test_uncertainty_shares_are_ranked_and_bounded(tables):
    rows = tables["uncertainty_contributions.csv"]
    shares = [r["diagnostic_share_of_variance"] for r in rows]
    assert shares == sorted(shares, reverse=True)
    assert all(0 <= s <= 1 for s in shares)
    assert [r["rank"] for r in rows] == list(range(1, len(rows) + 1))
