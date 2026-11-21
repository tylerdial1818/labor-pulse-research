"""Run the 50-state Workforce ROI model and write its outputs and facts.json.

The model is the Utah benefit-cost engine (`pipelines/utah_roi/model.py`)
run once per state. The WorkAdvance evidence, national tax and price
parameters and the Monte Carlo design are unchanged; each state gets its own
income tax rate. The Utah model's "Utah Government" perspective is reported
here as the state government of each state.

Because the earnings effects come from one national trial, the reference
societal result is the same in every state. What differs is how much of the
return a state government recovers through its own income tax. Two
sensitivities let local wages scale the effects (and, in the second, program
costs) instead.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from lpresearch.facts import Fact, FactSheet, Source
from lpresearch.io import write_csv
from lpresearch.pipelines.state_roi import inputs as state_inputs
from lpresearch.pipelines.utah_roi import model

MODEL_VERSION = "0.1.0"
STUDY = "state_roi"
REPO = Path(__file__).resolve().parents[4]
STUDY_DIR = REPO / "studies" / STUDY
STATE_TAX = "UTAH_INCOME_TAX_RATE"
"""The Utah model's state income tax parameter, set to each state's rate here."""


def _per(result: dict[str, Any], perspective: str, key: str = "npv_per_person") -> float:
    return result["perspectives"][perspective][key]


def evaluate_state(
    mi: model.ModelInputs,
    evidence: dict[str, Any],
    scenario: dict[str, Any],
    state: state_inputs.State,
    settings: dict[str, Any],
    wage_ratio: float,
    draws: int | None = None,
) -> dict[str, Any]:
    """All results for one state, as one flat row."""
    rate = state_inputs.state_tax_rate(state, settings)
    alt_rate = state_inputs.state_tax_rate(state, settings, settings["alternative_taxable_income_usd"])
    ref = model.evaluate_scenario(mi, evidence, scenario, {STATE_TAX: rate})
    alt = model.evaluate_scenario(mi, evidence, scenario, {STATE_TAX: alt_rate})
    wage_effects = model.evaluate_scenario(
        mi, evidence, scenario, {STATE_TAX: rate, "WAGE_TRANSLATION_FACTOR": wage_ratio}
    )
    wage_both = model.evaluate_scenario(
        mi, evidence, scenario, {STATE_TAX: rate, "WAGE_TRANSLATION_FACTOR": wage_ratio, "COST_MULTIPLIER": wage_ratio}
    )
    sim = model.simulate_reference(mi, evidence, draws, {STATE_TAX: rate})
    summary = {row["perspective"]: row for row in sim["summary"]}

    state_npv = _per(ref, "Utah Government")
    combined_npv = _per(ref, "Combined Government")
    return {
        "state_abbr": state.abbr,
        "state_name": state.name,
        "state_income_tax_rate": rate,
        "state_income_tax_rate_alt_income": alt_rate,
        "median_annual_wage": state.median_wage,
        "wage_ratio_to_workadvance_sites": wage_ratio,
        "program_cost_per_person": ref["program_cost_per_person"],
        "participant_npv_per_person": _per(ref, "Participant"),
        "societal_npv_per_person": _per(ref, "Societal"),
        "societal_bcr": _per(ref, "Societal", "benefit_cost_ratio"),
        "combined_government_npv_per_person": combined_npv,
        "combined_government_bcr": _per(ref, "Combined Government", "benefit_cost_ratio"),
        "state_government_npv_per_person": state_npv,
        "state_government_bcr": _per(ref, "Utah Government", "benefit_cost_ratio"),
        "state_revenue_pv_per_person": ref["perspectives"]["Utah Government"]["pv_benefits_cohort"]
        / ref["parameters"]["COHORT_SIZE"],
        "federal_npv_per_person": combined_npv - state_npv,
        "probability_combined_government_positive": summary["Combined Government"]["probability_net_benefits_positive"],
        "probability_state_government_positive": summary["Utah Government"]["probability_net_benefits_positive"],
        "probability_societal_positive": summary["Societal"]["probability_net_benefits_positive"],
        "alt_income_state_government_bcr": _per(alt, "Utah Government", "benefit_cost_ratio"),
        "wage_scaled_societal_npv_per_person": _per(wage_effects, "Societal"),
        "wage_scaled_societal_bcr": _per(wage_effects, "Societal", "benefit_cost_ratio"),
        "wage_scaled_state_government_bcr": _per(wage_effects, "Utah Government", "benefit_cost_ratio"),
        "wage_scaled_with_costs_societal_npv_per_person": _per(wage_both, "Societal"),
        "wage_scaled_with_costs_societal_bcr": _per(wage_both, "Societal", "benefit_cost_ratio"),
    }


def run(study_dir: Path = STUDY_DIR, out_dir: Path | None = None, draws: int | None = None) -> dict[str, Any]:
    """Run every state. Returns the serialisable results written to model_results.json."""
    out_dir = out_dir or study_dir / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    settings = state_inputs.load_settings(study_dir)
    mi = model.load_model_inputs(REPO / "studies" / settings["evidence_study"])
    evidence = model.build_evidence_model(mi)
    scenario = next(s for s in mi.scenarios if s["scenario"] == "Reference")
    states = state_inputs.load_states(study_dir)
    site_wage = state_inputs.site_weighted_median_wage(states, settings, evidence["sampleByProvider"])

    rows = [evaluate_state(mi, evidence, scenario, s, settings, s.median_wage / site_wage, draws) for s in states]
    write_csv(out_dir / "state_results.csv", rows)
    results = {
        "model_version": MODEL_VERSION,
        "generated_at": datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "price_year": 2025,
        "reference_taxable_income_usd": settings["reference_taxable_income_usd"],
        "workadvance_site_weighted_median_wage": site_wage,
        "summary": summarize(rows),
        "states": rows,
    }
    (out_dir / "model_results.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    build_facts(results).write(out_dir / "facts.json")
    return results


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    mid = len(ordered) // 2
    return ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Cross-state summary: the range of what a state government gets back."""
    by_bcr = sorted(rows, key=lambda r: r["state_government_bcr"])
    bcrs = [r["state_government_bcr"] for r in rows]
    return {
        "state_count": len(rows),
        "zero_rate_state_count": sum(1 for r in rows if r["state_income_tax_rate"] == 0),
        "zero_rate_states": [r["state_abbr"] for r in rows if r["state_income_tax_rate"] == 0],
        "median_state_government_bcr": _median(bcrs),
        "max_state_government_bcr": by_bcr[-1]["state_government_bcr"],
        "max_state_government_bcr_state": by_bcr[-1]["state_abbr"],
        "min_nonzero_state_government_bcr": min(b for b in bcrs if b > 0),
        "societal_bcr_min": min(r["societal_bcr"] for r in rows),
        "societal_bcr_max": max(r["societal_bcr"] for r in rows),
        "wage_scaled_societal_bcr_min": min(r["wage_scaled_societal_bcr"] for r in rows),
        "wage_scaled_societal_bcr_max": max(r["wage_scaled_societal_bcr"] for r in rows),
        "max_probability_combined_government_positive": max(
            r["probability_combined_government_positive"] for r in rows
        ),
        "min_probability_combined_government_positive": min(
            r["probability_combined_government_positive"] for r in rows
        ),
    }


_STATE_FACTS = (
    ("state_income_tax_rate", "proportion", "State marginal income tax rate used for {name}"),
    ("median_annual_wage", "usd", "{name} all-occupation median annual wage, BLS OEWS May 2025"),
    ("wage_ratio_to_workadvance_sites", "ratio", "{name} median wage relative to the WorkAdvance site states"),
    ("state_government_npv_per_person", "usd", "{name} state government NPV per person offered, state pays all"),
    (
        "state_government_bcr",
        "ratio",
        "{name} state government benefit-cost ratio when the state pays all costs; also the share of costs "
        "{name} could pay and still break even",
    ),
    ("state_revenue_pv_per_person", "usd", "Present value of {name} income tax gained per person offered"),
    ("federal_npv_per_person", "usd", "Federal government NPV per person when {name} pays all costs"),
    ("combined_government_npv_per_person", "usd", "Combined government NPV per person in {name}"),
    ("combined_government_bcr", "ratio", "Combined government benefit-cost ratio in {name}"),
    (
        "probability_combined_government_positive",
        "proportion",
        "Share of Monte Carlo draws with positive combined government net benefits in {name}",
    ),
    ("wage_scaled_societal_npv_per_person", "usd", "{name} societal NPV per person if effects scale with wages"),
    ("wage_scaled_societal_bcr", "ratio", "{name} societal benefit-cost ratio if effects scale with local wages"),
)


def build_facts(results: dict[str, Any]) -> FactSheet:
    """Every number a 50-state ROI note may quote."""
    sheet = FactSheet(study=STUDY, model_version=MODEL_VERSION)
    src = Source(kind="computed", ref=f"studies/{STUDY}/outputs/state_results.csv")
    det = Source(kind="computed", ref=f"studies/{STUDY}/outputs/model_results.json")

    def add(fact_id: str, value: float, unit: str, description: str, source: Source = det) -> None:
        sheet.add(Fact(id=fact_id, value=float(value), unit=unit, description=description, source=source))

    s = results["summary"]
    rows = results["states"]
    first = rows[0]
    add("state_count", s["state_count"], "count", "States modeled, including DC")
    add("reference_taxable_income", results["reference_taxable_income_usd"], "usd", "Taxable income for state rates")
    add("program_cost_per_person", first["program_cost_per_person"], "usd", "Net program cost per person offered")
    add("societal_bcr", first["societal_bcr"], "ratio", "Societal benefit-cost ratio, same in every state")
    add("societal_npv_per_person", first["societal_npv_per_person"], "usd", "Societal NPV per person, every state")
    add("zero_rate_state_count", s["zero_rate_state_count"], "count", "States with no income tax at that income")
    add("median_state_government_bcr", s["median_state_government_bcr"], "ratio", "Median state government BCR")
    add("max_state_government_bcr", s["max_state_government_bcr"], "ratio", "Highest state government BCR")
    add("min_nonzero_state_government_bcr", s["min_nonzero_state_government_bcr"], "ratio", "Lowest nonzero BCR")
    add("wage_scaled_societal_bcr_min", s["wage_scaled_societal_bcr_min"], "ratio", "Lowest wage-scaled societal BCR")
    add("wage_scaled_societal_bcr_max", s["wage_scaled_societal_bcr_max"], "ratio", "Highest wage-scaled societal BCR")
    add(
        "workadvance_site_weighted_median_wage",
        results["workadvance_site_weighted_median_wage"],
        "usd",
        "Sample-weighted median wage of the WorkAdvance site states",
    )
    for row in rows:
        prefix = row["state_abbr"].lower()
        for key, unit, template in _STATE_FACTS:
            add(f"{prefix}_{key}", row[key], unit, template.format(name=row["state_name"]), src)
    return sheet
