"""Model invariants, ported one for one from the original tests/model_tests.mjs."""

import math

from lpresearch.pipelines.utah_roi import model


def npv(result, perspective):
    return result["perspectives"][perspective]["npv_per_person"]


def test_core_horizon_stops_at_year_ten(reference):
    assert len(reference["effect_path"]) == 10


def test_program_cost_is_positive(reference):
    assert reference["program_cost_per_person"] > 0


def test_societal_npv_is_finite(reference):
    assert math.isfinite(npv(reference, "Societal"))


def test_higher_cost_lowers_societal_npv(inputs, evidence, reference_scenario, reference):
    higher = model.evaluate_scenario(
        inputs, evidence, reference_scenario, {"programCost": reference["program_cost_per_person"] * 1.10}
    )
    assert npv(higher, "Societal") < npv(reference, "Societal")


def test_zero_effect_npv_equals_negative_cost(inputs, evidence, reference_scenario):
    zero = model.evaluate_scenario(inputs, evidence, reference_scenario, {"effectPath": [0] * 10})
    assert abs(npv(zero, "Societal") + zero["program_cost_per_person"]) < 1e-6


def test_taxes_cancel_from_societal_perspective(inputs, evidence, reference_scenario, reference):
    changed = model.evaluate_scenario(inputs, evidence, reference_scenario, {"FEDERAL_INCOME_TAX_RATE": 0.15})
    assert abs(npv(changed, "Societal") - npv(reference, "Societal")) < 1e-6


def test_participant_plus_government_equals_societal(reference):
    total = npv(reference, "Participant") + npv(reference, "Combined Government")
    assert abs(total - npv(reference, "Societal")) < 1e-6
    assert abs(reference["accounting"]["perspective_additivity_gap_per_person"]) < 1e-6


def test_employer_payroll_tax_is_symmetric_transfer(inputs, evidence, reference_scenario, reference):
    changed = model.evaluate_scenario(inputs, evidence, reference_scenario, {"EMPLOYER_PAYROLL_TAX_RATE": 0})
    participant_delta = npv(reference, "Participant") - npv(changed, "Participant")
    government_delta = npv(reference, "Combined Government") - npv(changed, "Combined Government")
    assert abs(participant_delta + government_delta) < 1e-6


def test_seeded_simulation_is_reproducible(inputs, evidence):
    a = model.simulate_reference(inputs, evidence, 100)
    b = model.simulate_reference(inputs, evidence, 100)
    assert a["summary"] == b["summary"]


def test_additivity_holds_in_every_draw(inputs, evidence):
    sim = model.simulate_reference(inputs, evidence, 100)
    for d in sim["draws"]:
        gap = d["participant_npv_per_person"] + d["combined_government_npv_per_person"] - d["societal_npv_per_person"]
        assert abs(gap) < 1e-6


def test_summary_statistics_are_finite(inputs, evidence):
    sim = model.simulate_reference(inputs, evidence, 100)
    for row in sim["summary"]:
        assert all(math.isfinite(v) for v in row.values() if isinstance(v, float))


def test_diagnostic_fields_present_and_finite(inputs, evidence):
    draw = model.simulate_reference(inputs, evidence, 100)["draws"][0]
    for field in (
        "early_effect_multiplier",
        "long_term_common_z",
        "long_term_idiosyncratic_mean_z",
        "mean_program_cost_before_shock",
        "program_cost_shock_ratio",
        "pv_compensation_benefits_per_person",
    ):
        assert math.isfinite(draw[field])


def test_target_weights_sum_to_one(inputs):
    ids = ("TARGET_DEMAND_WEIGHT", "TARGET_WAGE_WEIGHT", "TARGET_ACCESS_WEIGHT", "TARGET_AI_RESILIENCE_WEIGHT")
    assert abs(sum(inputs.registry[i]["base_value"] for i in ids) - 1) < 1e-12


def test_ai_exposure_is_unweighted_diagnostic(inputs):
    assert inputs.registry["TARGET_AI_RESILIENCE_WEIGHT"]["base_value"] == 0


def test_mulberry32_matches_javascript():
    # First values from the original JavaScript implementation (node, seed 20260716 and seed 1).
    rng = model.mulberry32(20260716)
    assert [rng() for _ in range(5)] == [
        0.6984757150057703,
        0.6530899936333299,
        0.7107332674786448,
        0.07608623383566737,
        0.9435331681743264,
    ]
    rng = model.mulberry32(1)
    assert [rng() for _ in range(3)] == [0.6270739405881613, 0.002735721180215478, 0.5274470399599522]


def test_inv_norm_is_accurate():
    assert abs(model.inv_norm(0.975) - 1.959963984540054) < 1e-8
    assert abs(model.inv_norm(0.5)) < 1e-15
    assert abs(model.inv_norm(0.01) + 2.326347874040841) < 1e-8
