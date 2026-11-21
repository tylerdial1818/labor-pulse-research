"""50-state Workforce ROI: state inputs, the per-state model and its facts."""

import math

import pytest

from lpresearch.pipelines.state_roi import inputs as si
from lpresearch.pipelines.state_roi import run as state_run
from lpresearch.pipelines.utah_roi import model

STUDY = state_run.STUDY_DIR


@pytest.fixture(scope="module")
def settings():
    return si.load_settings(STUDY)


@pytest.fixture(scope="module")
def states():
    return si.load_states(STUDY)


@pytest.fixture(scope="module")
def results(tmp_path_factory):
    return state_run.run(out_dir=tmp_path_factory.mktemp("state_roi"), draws=500)


@pytest.fixture(scope="module")
def rows(results):
    return {r["state_abbr"]: r for r in results["states"]}


# --------------------------------------------------------------------------- tax brackets


def test_marginal_rate_picks_the_bracket_containing_income():
    brackets = [si.Bracket(0.02, 0), si.Bracket(0.04, 10_000), si.Bracket(0.06, 40_000)]
    assert si.marginal_rate(brackets, 5_000) == 0.02
    assert si.marginal_rate(brackets, 30_000) == 0.04
    assert si.marginal_rate(brackets, 40_000) == 0.06


def test_income_below_first_bracket_is_untaxed():
    assert si.marginal_rate([si.Bracket(0.0195, 48_475)], 30_000) == 0


def test_bracket_order_in_the_file_does_not_matter():
    brackets = [si.Bracket(0.06, 40_000), si.Bracket(0.02, 0)]
    assert si.marginal_rate(brackets, 50_000) == 0.06


# --------------------------------------------------------------------------- state inputs


def test_every_state_and_dc_is_loaded_once(states):
    abbrs = [s.abbr for s in states]
    assert len(abbrs) == 51
    assert len(set(abbrs)) == 51
    assert "DC" in abbrs
    assert not {"PR", "GU", "VI"} & set(abbrs)


def test_every_state_has_a_positive_median_wage(states):
    assert all(s.median_wage > 0 and s.employment > 0 for s in states)


def test_states_without_wage_tax_get_zero(states, settings):
    by_abbr = {s.abbr: s for s in states}
    for abbr in ("AK", "FL", "NV", "NH", "SD", "TN", "TX", "WA", "WY"):
        assert si.state_tax_rate(by_abbr[abbr], settings) == 0


def test_utah_override_matches_utah_study(states, settings):
    utah = next(s for s in states if s.abbr == "UT")
    registry = model.load_model_inputs(state_run.REPO / "studies" / "utah_roi").registry
    assert si.state_tax_rate(utah, settings) == registry["UTAH_INCOME_TAX_RATE"]["base_value"]
    assert si.state_tax_rate(utah, settings, 50_000) == registry["UTAH_INCOME_TAX_RATE"]["base_value"]


def test_site_weighted_wage_sits_between_site_states(states, settings):
    by_abbr = {s.abbr: s.median_wage for s in states}
    sample = {"Per Scholas": 1, "St. Nicks Alliance": 1, "Madison Strategies Group": 1, "Towards Employment": 1}
    wage = si.site_weighted_median_wage(states, settings, sample)
    assert min(by_abbr["NY"], by_abbr["OK"], by_abbr["OH"]) < wage < max(by_abbr["NY"], by_abbr["OK"], by_abbr["OH"])
    assert math.isclose(wage, (2 * by_abbr["NY"] + by_abbr["OK"] + by_abbr["OH"]) / 4)


# --------------------------------------------------------------------------- model results


def test_utah_row_reproduces_the_utah_study(rows, reference):
    ut = rows["UT"]
    per = reference["perspectives"]
    assert math.isclose(ut["state_government_npv_per_person"], per["Utah Government"]["npv_per_person"])
    assert math.isclose(ut["state_government_bcr"], per["Utah Government"]["benefit_cost_ratio"])
    assert math.isclose(ut["societal_bcr"], per["Societal"]["benefit_cost_ratio"])


def test_societal_result_is_the_same_everywhere_in_reference(rows):
    bcrs = {r["societal_bcr"] for r in rows.values()}
    assert max(bcrs) - min(bcrs) < 1e-12


def test_zero_tax_states_recover_nothing(rows):
    for r in rows.values():
        if r["state_income_tax_rate"] == 0:
            assert r["state_government_bcr"] == 0
            assert math.isclose(r["state_government_npv_per_person"], -r["program_cost_per_person"])


def test_state_return_rises_with_state_tax_rate(rows):
    ordered = sorted(rows.values(), key=lambda r: r["state_income_tax_rate"])
    bcrs = [r["state_government_bcr"] for r in ordered]
    assert bcrs == sorted(bcrs)


def test_federal_gain_does_not_depend_on_the_state(rows):
    federal = [r["federal_npv_per_person"] for r in rows.values()]
    assert max(federal) - min(federal) < 1e-6


def test_participant_plus_government_equals_societal_in_every_state(rows):
    for r in rows.values():
        total = r["participant_npv_per_person"] + r["combined_government_npv_per_person"]
        assert abs(total - r["societal_npv_per_person"]) < 1e-6


def test_scaling_effects_and_costs_together_keeps_the_ratio(rows):
    for r in rows.values():
        assert math.isclose(r["wage_scaled_with_costs_societal_bcr"], r["societal_bcr"], rel_tol=1e-12)


def test_wage_scaled_ratio_follows_local_wages(rows):
    for r in rows.values():
        expected = r["societal_bcr"] * r["wage_ratio_to_workadvance_sites"]
        assert math.isclose(r["wage_scaled_societal_bcr"], expected, rel_tol=1e-9)


def test_probabilities_are_proportions(rows):
    for r in rows.values():
        for key in ("probability_combined_government_positive", "probability_societal_positive"):
            assert 0 <= r[key] <= 1


# --------------------------------------------------------------------------- facts


def test_facts_cover_every_state(results):
    sheet = state_run.build_facts(results)
    ids = {f.id for f in sheet.facts}
    for abbr in ("ut", "tx", "dc", "or"):
        assert f"{abbr}_state_government_bcr" in ids
    assert "societal_bcr" in ids
