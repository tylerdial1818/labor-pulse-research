"""The Python port must reproduce the original Node.js v0.1.0 outputs.

Tolerance is 1e-9 relative. In practice the largest gap is about 3e-13, from
last-digit differences between the two runtimes' log/exp/cos functions.
"""

import csv
import gzip
import json
import math

import pytest

from lpresearch.pipelines.utah_roi import run as runner

from .conftest import NODE_REFERENCE, UTAH

REL_TOL = 1e-9


@pytest.fixture(scope="module")
def outputs(tmp_path_factory):
    out = tmp_path_factory.mktemp("utah_roi")
    runner.run(study_dir=UTAH, out_dir=out)
    return out


def read_csv(path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def assert_cells_match(actual, expected, where):
    if expected == "" or actual == "":
        assert actual == expected, where
        return
    try:
        e, a = float(expected), float(actual)
    except ValueError:
        assert actual == expected, where
        return
    assert math.isclose(a, e, rel_tol=REL_TOL, abs_tol=1e-9), f"{where}: {a} != {e}"


@pytest.mark.parametrize(
    "name",
    [
        "effect_path.csv",
        "provider_effect_paths.csv",
        "scenario_results.csv",
        "annual_cash_flows_reference.csv",
        "simulation_summary.csv",
        "simulation_draws_reference.csv",
        "one_way_sensitivity.csv",
        "funding_share_scenarios.csv",
        "fiscal_incidence_sensitivity.csv",
        "break_even_frontier.csv",
        "benefit_composition.csv",
        "provider_scenario_results.csv",
        "uncertainty_contributions.csv",
        "occupation_rank_stability.csv",
    ],
)
def test_csv_outputs_match_node(outputs, name):
    expected_path = NODE_REFERENCE / name
    if not expected_path.exists():
        expected_path = expected_path.with_name(name + ".gz")
    expected, actual = read_csv(expected_path), read_csv(outputs / name)
    assert len(actual) == len(expected)
    assert list(actual[0].keys()) == list(expected[0].keys())
    for i, (a_row, e_row) in enumerate(zip(actual, expected, strict=True)):
        for column in e_row:
            assert_cells_match(a_row[column], e_row[column], f"{name} row {i + 1} {column}")


def _walk(actual, expected, where="$"):
    if isinstance(expected, dict):
        assert set(actual) == set(expected), where
        for key in expected:
            _walk(actual[key], expected[key], f"{where}.{key}")
    elif isinstance(expected, list):
        assert len(actual) == len(expected), where
        for i, (a, e) in enumerate(zip(actual, expected, strict=True)):
            _walk(a, e, f"{where}[{i}]")
    elif isinstance(expected, (int, float)) and not isinstance(expected, bool):
        assert math.isclose(actual, expected, rel_tol=REL_TOL, abs_tol=1e-9), f"{where}: {actual} != {expected}"
    else:
        assert actual == expected, where


def test_model_results_json_matches_node(outputs):
    expected = json.loads((NODE_REFERENCE / "model_results.json").read_text())
    actual = json.loads((outputs / "model_results.json").read_text())
    expected.pop("generated_at")
    actual.pop("generated_at")
    _walk(actual, expected)


def test_headline_numbers(outputs):
    h = json.loads((outputs / "model_results.json").read_text())["headline"]
    assert round(h["program_cost_per_person"]) == 7505
    assert round(h["societal_bcr"], 2) == 4.77
    assert round(h["utah_government_bcr"], 2) == 0.17
    assert round(h["combined_government_bcr"], 2) == 1.04
    assert h["probability_societal_net_positive"] == 0.9808


def test_facts_file_is_written_and_valid(outputs):
    from lpresearch.facts import FactSheet

    sheet = FactSheet.read(outputs / "facts.json")
    assert sheet.get("societal_bcr").value == pytest.approx(4.773971392337122)
    assert sheet.get("simulation_draws").value == 10000
