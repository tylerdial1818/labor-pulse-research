"""Sensitivity and report analyses for the Utah Workforce ROI model.

Python port of the original `build_report_analysis.mjs` (v0.1.0). Each
function returns a list of rows for one output table:

- one-way sensitivity (tornado chart)
- funding-share scenarios and fiscal incidence
- break-even frontier (effect retention by program cost)
- benefit composition by year and component
- results for each WorkAdvance provider
- uncertainty screening for the Monte Carlo
- occupation rank stability across targeting scenarios
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

from lpresearch.io import format_value
from lpresearch.pipelines.utah_roi import model

Rows = list[dict[str, Any]]


def load_report_scenarios(study_dir: Path) -> dict[str, Any]:
    return json.loads((study_dir / "model" / "report_scenarios.json").read_text(encoding="utf-8"))


def _mean(values: list[float]) -> float:
    return model._sum(values) / len(values)


def _variance(values: list[float]) -> float:
    m = _mean(values)
    return model._sum([(x - m) ** 2 for x in values]) / len(values)


def _provider_evaluation(inputs, evidence, reference_scenario, provider: str) -> dict[str, Any]:
    """Evaluate the model with one provider's observed effect path and cost."""
    return model.evaluate_scenario(
        inputs,
        evidence,
        reference_scenario,
        {
            "effectPath": evidence["sitePaths"][provider],
            "programCost": evidence["siteCosts2025"][provider],
        },
    )


def one_way_sensitivity(inputs, evidence, reference_scenario, reference, report: dict[str, Any]) -> Rows:
    """Swing each input to its low and high value, holding everything else at Reference."""

    def evaluate(spec: dict[str, Any], side: str) -> dict[str, Any]:
        if spec["kind"] == "parameter":
            overrides = {spec["parameter_id"]: spec[side]}
        elif spec["kind"] == "completion_composite":
            overrides = {
                "UTAH_COMPLETION": spec[f"{side}_completion"],
                "COMPLETION_OUTCOME_ELASTICITY": spec[f"{side}_outcome_elasticity"],
            }
        else:
            raise ValueError(f"Unsupported sensitivity kind: {spec['kind']}")
        return model.evaluate_scenario(inputs, evidence, reference_scenario, overrides)

    def composite_label(spec: dict[str, Any], side: str) -> str:
        return (
            f"{spec[f'{side}_completion'] * 100:.0f}% completion, "
            f"{spec[f'{side}_outcome_elasticity']:.2f} outcome elasticity"
        )

    rows = []
    for spec in report["one_way_sensitivity"]:
        low_value: Any = ""
        high_value: Any = ""
        if spec["kind"] == "empirical_sites":
            ranked = sorted(
                ((p, _provider_evaluation(inputs, evidence, reference_scenario, p)) for p in evidence["providers"]),
                key=lambda pe: pe[1]["perspectives"]["Societal"]["npv_per_person"],
            )
            (low_label, low), (high_label, high) = ranked[0], ranked[-1]
        else:
            low, high = evaluate(spec, "low"), evaluate(spec, "high")
            if spec["kind"] == "completion_composite":
                low_label, high_label = composite_label(spec, "low"), composite_label(spec, "high")
                low_value, high_value = spec["low_completion"], spec["high_completion"]
            else:
                low_label, high_label = format_value(spec["low"]), format_value(spec["high"])
                low_value, high_value = spec["low"], spec["high"]
        for perspective, base in reference["perspectives"].items():
            lo, hi = low["perspectives"][perspective], high["perspectives"][perspective]
            rows.append(
                {
                    "sensitivity_id": spec["sensitivity_id"],
                    "label": spec["label"],
                    "perspective": perspective,
                    "unit": spec.get("unit", "empirical provider"),
                    "low_label": low_label,
                    "low_value": low_value,
                    "high_label": high_label,
                    "high_value": high_value,
                    "base_npv_per_person": base["npv_per_person"],
                    "low_npv_per_person": lo["npv_per_person"],
                    "high_npv_per_person": hi["npv_per_person"],
                    "low_change_from_base": lo["npv_per_person"] - base["npv_per_person"],
                    "high_change_from_base": hi["npv_per_person"] - base["npv_per_person"],
                    "base_bcr": base["benefit_cost_ratio"],
                    "low_bcr": lo["benefit_cost_ratio"],
                    "high_bcr": hi["benefit_cost_ratio"],
                    "source_basis": spec["source_basis"],
                    "model_version": report["version"],
                }
            )
    return rows


def _pv_employer_payroll(reference: dict[str, Any]) -> float:
    return model._sum([r["employer_payroll_tax_cohort"] * r["discount_factor"] for r in reference["annual_cash_flows"]])


def funding_share_scenarios(reference: dict[str, Any], report: dict[str, Any]) -> Rows:
    """Who pays changes each government's return, but not the program's cost to society."""
    n = reference["parameters"]["COHORT_SIZE"]
    total_cost = reference["program_cost_cohort"]
    utah_revenue = reference["perspectives"]["Utah Government"]["pv_benefits_cohort"]
    combined_revenue = reference["perspectives"]["Combined Government"]["pv_benefits_cohort"]
    federal_revenue = combined_revenue - utah_revenue
    employer_payroll = _pv_employer_payroll(reference)
    rows = []
    for s in report["funding_share_scenarios"]:
        utah_cost = total_cost * s["utah_share"]
        federal_cost = total_cost * s["federal_share"]
        public_cost = utah_cost + federal_cost
        rows.append(
            {
                "scenario_id": s["scenario_id"],
                "label": s["label"],
                "utah_share": s["utah_share"],
                "federal_share": s["federal_share"],
                "employer_share": s["employer_share"],
                "philanthropic_share": s["philanthropic_share"],
                "total_program_cost_per_person": total_cost / n,
                "utah_cost_per_person": utah_cost / n,
                "federal_cost_per_person": federal_cost / n,
                "employer_cost_per_person": total_cost * s["employer_share"] / n,
                "philanthropic_cost_per_person": total_cost * s["philanthropic_share"] / n,
                "utah_revenue_per_person": utah_revenue / n,
                "federal_revenue_per_person": federal_revenue / n,
                "combined_revenue_per_person": combined_revenue / n,
                "employer_payroll_revenue_per_person": employer_payroll / n,
                "utah_npv_per_person": (utah_revenue - utah_cost) / n,
                "federal_npv_per_person": (federal_revenue - federal_cost) / n,
                "combined_government_npv_per_person": (combined_revenue - public_cost) / n,
                "combined_government_npv_excluding_employer_payroll_per_person": (
                    combined_revenue - employer_payroll - public_cost
                )
                / n,
                "utah_bcr": utah_revenue / utah_cost if utah_cost > 0 else "",
                "federal_bcr": federal_revenue / federal_cost if federal_cost > 0 else "",
                "combined_government_bcr": combined_revenue / public_cost if public_cost > 0 else "",
                "combined_government_bcr_excluding_employer_payroll": (combined_revenue - employer_payroll)
                / public_cost
                if public_cost > 0
                else "",
                "societal_npv_per_person": reference["perspectives"]["Societal"]["npv_per_person"],
                "note": "Funding allocation changes fiscal incidence. It does not change program resource cost or "
                "societal NPV.",
            }
        )
    return rows


def fiscal_incidence_sensitivity(reference: dict[str, Any]) -> Rows:
    n = reference["parameters"]["COHORT_SIZE"]
    total_cost = reference["program_cost_cohort"]
    combined = reference["perspectives"]["Combined Government"]
    combined_revenue = combined["pv_benefits_cohort"]
    employer_payroll = _pv_employer_payroll(reference)
    return [
        {
            "case": "Reference incidence",
            "combined_government_revenue_per_person": combined_revenue / n,
            "combined_government_npv_per_person": combined["npv_per_person"],
            "combined_government_bcr": combined["benefit_cost_ratio"],
            "employer_payroll_revenue_per_person": employer_payroll / n,
            "incidence_rule": "Employer payroll is deducted from participant compensation and credited to government",
        },
        {
            "case": "Exclude employer payroll revenue",
            "combined_government_revenue_per_person": (combined_revenue - employer_payroll) / n,
            "combined_government_npv_per_person": (combined_revenue - employer_payroll - total_cost) / n,
            "combined_government_bcr": (combined_revenue - employer_payroll) / total_cost,
            "employer_payroll_revenue_per_person": 0,
            "incidence_rule": "Diagnostic fiscal case that removes employer-side payroll revenue",
        },
    ]


def break_even_frontier(reference: dict[str, Any], conservative: dict[str, Any], report: dict[str, Any]) -> Rows:
    """Societal NPV over a grid of retained effect (share of Reference) and program cost."""
    grid = report["break_even_grid"]
    n = reference["parameters"]["COHORT_SIZE"]
    reference_benefits = reference["perspectives"]["Societal"]["pv_benefits_cohort"] / n
    conservative_retention = (
        conservative["perspectives"]["Societal"]["pv_benefits_cohort"]
        / reference["perspectives"]["Societal"]["pv_benefits_cohort"]
    )
    conservative_cost = (
        conservative["perspectives"]["Societal"]["pv_costs_cohort"] / conservative["parameters"]["COHORT_SIZE"]
    )
    rows = []
    # Accumulate the step the same way the original does so grid points match exactly.
    retention = grid["effect_retention_min"]
    while retention <= grid["effect_retention_max"] + 1e-9:
        rounded = round(retention, 4)
        cost = grid["program_cost_min"]
        while cost <= grid["program_cost_max"] + 1e-9:
            npv = reference_benefits * rounded - cost
            rows.append(
                {
                    "effect_retention": rounded,
                    "program_cost_per_person": cost,
                    "societal_npv_per_person": npv,
                    "positive_net_benefits": 1 if npv > 0 else 0,
                    "break_even_program_cost": reference_benefits * rounded,
                    "reference_effect_retention": 1,
                    "reference_program_cost": reference["program_cost_per_person"],
                    "conservative_equivalent_effect_retention": conservative_retention,
                    "conservative_program_and_time_cost": conservative_cost,
                    "model_version": report["version"],
                }
            )
            cost += grid["program_cost_step"]
        retention += grid["effect_retention_step"]
    return rows


_COMPONENTS = (
    ("Incremental earnings", "incremental_earnings_cohort", "resource benefit"),
    ("Fringe benefits", "fringe_cohort", "resource benefit"),
    ("Federal income tax", "federal_income_tax_cohort", "fiscal transfer"),
    ("Utah income tax", "utah_income_tax_cohort", "fiscal transfer"),
    ("Employee payroll tax", "employee_payroll_tax_cohort", "fiscal transfer"),
    ("Employer payroll tax", "employer_payroll_tax_cohort", "fiscal transfer"),
    ("Transfer offset", "transfer_offset_cohort", "fiscal transfer"),
    ("Program cost", "program_cost_cohort", "resource cost"),
    ("Participant time", "participant_time_cost_cohort", "resource cost"),
)


def benefit_composition(reference: dict[str, Any]) -> Rows:
    n = reference["parameters"]["COHORT_SIZE"]
    rows = []
    for component, key, classification in _COMPONENTS:
        total_cash = 0.0
        total_pv = 0.0
        for r in reference["annual_cash_flows"]:
            per_person = r[key] / n
            pv_per_person = per_person * r["discount_factor"]
            total_cash += per_person
            total_pv += pv_per_person
            rows.append(
                {
                    "period": r["year"],
                    "component": component,
                    "classification": classification,
                    "cash_flow_per_person": per_person,
                    "discount_factor": r["discount_factor"],
                    "pv_per_person": pv_per_person,
                    "price_year": 2025,
                    "scenario": "Reference",
                }
            )
        rows.append(
            {
                "period": "Total",
                "component": component,
                "classification": classification,
                "cash_flow_per_person": total_cash,
                "discount_factor": "",
                "pv_per_person": total_pv,
                "price_year": 2025,
                "scenario": "Reference",
            }
        )
    return rows


def provider_scenario_results(inputs, evidence, reference_scenario, report: dict[str, Any]) -> Rows:
    rows = []
    for provider in evidence["providers"]:
        ev = _provider_evaluation(inputs, evidence, reference_scenario, provider)
        n = ev["parameters"]["COHORT_SIZE"]
        for perspective, m in ev["perspectives"].items():
            rows.append(
                {
                    "provider": provider,
                    "perspective": perspective,
                    "program_cost_per_person": ev["program_cost_per_person"],
                    "undiscounted_earnings_effect_per_person": model._sum(ev["effect_path"]),
                    "npv_per_person": m["npv_per_person"],
                    "benefit_cost_ratio": m["benefit_cost_ratio"],
                    "pv_benefits_per_person": m["pv_benefits_cohort"] / n,
                    "pv_costs_per_person": m["pv_costs_cohort"] / n,
                    "model_version": report["version"],
                }
            )
    return rows


_FACTORS = (
    ("provider_environment", "Provider environment", "categorical_eta_squared"),
    ("early_effect_multiplier", "Years 1 through 6 effect multiplier", "univariate_r_squared"),
    ("long_term_common_z", "Shared long-term effect shock", "univariate_r_squared"),
    ("long_term_idiosyncratic_mean_z", "Idiosyncratic long-term effect shock", "univariate_r_squared"),
    ("completion_rate", "Completion rate", "univariate_r_squared"),
    ("discount_rate", "Real discount rate", "univariate_r_squared"),
    ("fringe_rate", "Fringe benefit rate", "univariate_r_squared"),
    ("program_cost_shock_ratio", "Program cost shock", "univariate_r_squared"),
    ("federal_income_tax_rate", "Federal income-tax rate", "univariate_r_squared"),
)


def _correlation_squared(x: list[float], y: list[float]) -> float:
    mx, my = _mean(x), _mean(y)
    cov = model._sum([(a - mx) * (b - my) for a, b in zip(x, y, strict=True)]) / len(x)
    denominator = math.sqrt(_variance(x) * _variance(y))
    return (cov / denominator) ** 2 if denominator > 0 else 0


def _provider_eta_squared(draws: Rows, y: list[float]) -> float:
    """Share of outcome variance explained by which provider was drawn (between-group / total)."""
    overall = _mean(y)
    groups: dict[str, list[float]] = {}
    for row, value in zip(draws, y, strict=True):
        groups.setdefault(row["provider"], []).append(value)
    between = model._sum([len(v) * (_mean(v) - overall) ** 2 for v in groups.values()])
    total = model._sum([(v - overall) ** 2 for v in y])
    return between / total if total > 0 else 0


def uncertainty_contributions(draws: Rows, report: dict[str, Any]) -> Rows:
    """Rank Monte Carlo inputs by how much of the societal NPV variance each one explains alone."""
    outcome = [r["societal_npv_per_person"] for r in draws]
    rows = []
    for key, label, method in _FACTORS:
        if method == "categorical_eta_squared":
            share = _provider_eta_squared(draws, outcome)
        else:
            share = _correlation_squared([r[key] for r in draws], outcome)
        rows.append(
            {
                "factor_id": key,
                "label": label,
                "method": method,
                "diagnostic_share_of_variance": share,
                "outcome": "societal_npv_per_person",
                "additive_decomposition": 0,
                "note": "This is a univariate screening diagnostic. Values are not additive because model inputs "
                "interact and some sampled values are correlated.",
                "model_version": report["version"],
            }
        )
    rows.sort(key=lambda r: r["diagnostic_share_of_variance"], reverse=True)
    return [{"rank": i + 1, **r} for i, r in enumerate(rows)]


def _js_number(text: str) -> float:
    """JavaScript Number(): blank becomes 0, unparseable becomes NaN."""
    text = text.strip()
    if text == "":
        return 0.0
    try:
        return float(text)
    except ValueError:
        return math.nan


def occupation_rank_stability(study_dir: Path) -> Rows:
    """How much each target occupation's rank moves across the four targeting scenarios."""
    with (study_dir / "data" / "processed" / "utah_target_occupations.csv").open(newline="", encoding="utf-8") as f:
        targets = list(csv.DictReader(f))
    rows = []
    for r in targets:
        ranks = [float(r[k]) for k in ("referenceRank", "demandHeavyRank", "mobilityAccessRank", "aiTransitionRank")]
        rank_mean = _mean(ranks)
        rank_sd = math.sqrt(model._sum([(v - rank_mean) ** 2 for v in ranks]) / len(ranks))
        top_ten = sum(1 for v in ranks if v <= 10)
        rank_range = max(ranks) - min(ranks)
        if top_ten >= 3:
            stability = "Stable top tier"
        elif rank_range >= 20:
            stability = "Scenario-sensitive"
        else:
            stability = "Broadly stable"
        rows.append(
            {
                "soc": r["soc"],
                "title": r["title"],
                "reference_rank": ranks[0],
                "demand_heavy_rank": ranks[1],
                "mobility_access_rank": ranks[2],
                "ai_transition_rank": ranks[3],
                "mean_rank": rank_mean,
                "rank_standard_deviation": rank_sd,
                "rank_range": rank_range,
                "top_ten_scenario_count": top_ten,
                "stability_class": stability,
                "median_wage_2025": _js_number(r["medianWage2025"]),
                "annual_openings": _js_number(r["annualOpenings"]),
                "annual_growth_pct": _js_number(r["annualGrowthPct"]),
                "ai_exposure_gamma": _js_number(r["aiExposureGamma"]),
            }
        )
    rows.sort(key=lambda row: row["mean_rank"])
    return rows


def build_report_tables(study_dir: Path, inputs, evidence, draws: Rows) -> dict[str, Rows]:
    """All report tables, keyed by output file name."""
    report = load_report_scenarios(study_dir)
    scenarios = {s["scenario"]: s for s in inputs.scenarios}
    reference_scenario = scenarios["Reference"]
    reference = model.evaluate_scenario(inputs, evidence, reference_scenario)
    conservative = model.evaluate_scenario(inputs, evidence, scenarios["Conservative"])
    return {
        "one_way_sensitivity.csv": one_way_sensitivity(inputs, evidence, reference_scenario, reference, report),
        "funding_share_scenarios.csv": funding_share_scenarios(reference, report),
        "fiscal_incidence_sensitivity.csv": fiscal_incidence_sensitivity(reference),
        "break_even_frontier.csv": break_even_frontier(reference, conservative, report),
        "benefit_composition.csv": benefit_composition(reference),
        "provider_scenario_results.csv": provider_scenario_results(inputs, evidence, reference_scenario, report),
        "uncertainty_contributions.csv": uncertainty_contributions(draws, report),
        "occupation_rank_stability.csv": occupation_rank_stability(study_dir),
    }
