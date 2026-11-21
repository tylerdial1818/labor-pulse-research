"""Utah Workforce ROI benefit-cost model (Python port of model_core.mjs v0.1.0).

The model values a WorkAdvance-style sector training program offered to a Utah
cohort from four perspectives: participant, Utah government, combined
government and society. All values are intent-to-treat per person offered, in
2025 dollars, over a 10-year horizon.

This is a line-for-line port of the original Node.js model so that results can
be checked against the published reference outputs. Function and field names
follow the original to keep that comparison easy.
"""

from __future__ import annotations

import csv
import json
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROVIDERS = ("Per Scholas", "St. Nicks Alliance", "Madison Strategies Group", "Towards Employment")
LONG_TERM_PRICE_YEARS = {7: 2020, 8: 2021, 9: 2022, 10: 2023}
SCENARIO_FILES = ("reference.json", "conservative.json", "evidence_extension.json")
PERSPECTIVES = ("Participant", "Utah Government", "Combined Government", "Societal")

SCENARIO_PARAMETER_IDS = (
    "COHORT_SIZE",
    "HORIZON_YEARS",
    "DISCOUNT_RATE",
    "SIMULATION_DRAWS",
    "SIMULATION_SEED",
    "REFERENCE_COMPLETION",
    "UTAH_COMPLETION",
    "COMPLETION_COST_ELASTICITY",
    "COMPLETION_OUTCOME_ELASTICITY",
    "COST_MULTIPLIER",
    "TRAINING_COST_SHARE",
    "WAGE_TRANSLATION_FACTOR",
    "EARLY_EFFECT_CV",
    "ANNUAL_EFFECT_CORRELATION",
    "FRINGE_RATE",
    "FEDERAL_INCOME_TAX_RATE",
    "UTAH_INCOME_TAX_RATE",
    "EMPLOYEE_PAYROLL_TAX_RATE",
    "EMPLOYER_PAYROLL_TAX_RATE",
    "TRANSFER_OFFSET_RATE",
    "PARTICIPANT_TIME_COST",
    "UTAH_COST_SHARE",
)

Params = dict[str, float]
Rng = Callable[[], float]


# --------------------------------------------------------------------------- inputs


@dataclass(frozen=True)
class ModelInputs:
    root: Path
    registry: dict[str, dict[str, Any]]
    evidence: list[dict[str, Any]]
    scenarios: list[dict[str, Any]]


def _number_or_text(value: str) -> float | str | None:
    if value == "":
        return None
    try:
        number = float(value)
    except ValueError:
        return value
    return number if math.isfinite(number) else value


def _optional_float(value: str) -> float | None:
    return None if value == "" else float(value)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [row for row in csv.DictReader(handle) if any(v != "" for v in row.values())]


def load_model_inputs(root: Path | str) -> ModelInputs:
    """Read the parameter registry, evidence registry and scenarios from a study folder."""
    root = Path(root)
    registry: dict[str, dict[str, Any]] = {}
    for row in _read_csv(root / "model" / "parameter_registry.csv"):
        entry: dict[str, Any] = dict(row)
        for key in (
            "base_value",
            "conservative_value",
            "evidence_extension_value",
            "dist_min",
            "dist_mode",
            "dist_max",
        ):
            entry[key] = _number_or_text(row[key])
        registry[row["parameter_id"]] = entry

    evidence = []
    for row in _read_csv(root / "evidence" / "evidence_registry.csv"):
        entry = dict(row)
        entry["followup_year"] = int(row["followup_year"])
        entry["effect_value"] = float(row["effect_value"])
        for key in ("p_value", "standard_error", "program_n", "control_n"):
            entry[key] = _optional_float(row[key])
        evidence.append(entry)

    scenarios = [
        json.loads((root / "model" / "scenarios" / name).read_text(encoding="utf-8")) for name in SCENARIO_FILES
    ]
    return ModelInputs(root=root, registry=registry, evidence=evidence, scenarios=scenarios)


def _param(registry: dict[str, dict[str, Any]], parameter_id: str, column: str = "base_value") -> Any:
    if parameter_id not in registry:
        raise KeyError(f"Unknown parameter: {parameter_id}")
    return registry[parameter_id][column]


def cpi_factor(registry: dict[str, dict[str, Any]], from_year: int) -> float:
    """Multiplier that converts dollars from `from_year` into 2025 dollars."""
    return _param(registry, "CPI_2025") / _param(registry, f"CPI_{from_year}")


# --------------------------------------------------------------------------- evidence


def build_evidence_model(inputs: ModelInputs) -> dict[str, Any]:
    """Turn the evidence registry into per-site and reference earnings-effect paths (2025 $)."""
    registry = inputs.registry
    earnings = [r for r in inputs.evidence if r["outcome"] == "annual_earnings"]
    site_paths: dict[str, list[float]] = {}
    site_ses: dict[str, list[float]] = {}
    for provider in PROVIDERS:
        site_paths[provider] = [0.0] * 10
        site_ses[provider] = [0.0] * 10
        for r in (row for row in earnings if row["provider"] == provider):
            year = r["followup_year"]
            if year <= 6:
                # MDRC reports years 1-6 as 2018-dollar present values discounted at 3%.
                # Undo that discount so the model applies its own rate exactly once.
                site_paths[provider][year - 1] = r["effect_value"] * (1.03 ** (year - 1)) * cpi_factor(registry, 2018)
            else:
                price_year = LONG_TERM_PRICE_YEARS[year]
                factor = cpi_factor(registry, price_year)
                site_paths[provider][year - 1] = r["effect_value"] * factor
                site_ses[provider][year - 1] = derive_se(r["effect_value"], r["p_value"]) * factor

    sample_by_provider = {}
    for provider in PROVIDERS:
        row = next(r for r in earnings if r["provider"] == provider)
        sample_by_provider[provider] = (row["program_n"] or 0) + (row["control_n"] or 0)
    sample_total = sum(sample_by_provider.values())

    reference_path = [0.0] * 10
    for year in range(1, 7):
        total = 0.0
        for provider in PROVIDERS:
            total += site_paths[provider][year - 1] * sample_by_provider[provider] / sample_total
        reference_path[year - 1] = total
    for year in range(7, 11):
        pooled = next(r for r in earnings if r["provider"] == "Pooled four-site" and r["followup_year"] == year)
        reference_path[year - 1] = pooled["effect_value"] * cpi_factor(registry, LONG_TERM_PRICE_YEARS[year])

    costs = [r for r in inputs.evidence if r["outcome"] == "net_program_cost"]
    site_costs_2025 = {}
    for provider in PROVIDERS:
        row = next(r for r in costs if r["provider"] == provider)
        site_costs_2025[provider] = row["effect_value"] * cpi_factor(registry, 2018)
    weighted_cost = 0.0
    for provider in PROVIDERS:
        weighted_cost += site_costs_2025[provider] * sample_by_provider[provider] / sample_total

    return {
        "providers": list(PROVIDERS),
        "sitePaths": site_paths,
        "siteSEs": site_ses,
        "referencePath": reference_path,
        "siteCosts2025": site_costs_2025,
        "weightedCost2025": weighted_cost,
        "sampleByProvider": sample_by_provider,
    }


# --------------------------------------------------------------------------- deterministic model


def scenario_parameters(inputs: ModelInputs, scenario: dict[str, Any]) -> Params:
    column = scenario["column"]
    return {pid: float(_param(inputs.registry, pid, column)) for pid in SCENARIO_PARAMETER_IDS}


def _completion_ratio(p: Params) -> float:
    return max(p["UTAH_COMPLETION"], 1e-9) / p["REFERENCE_COMPLETION"]


def cost_for_completion(base_cost: float, p: Params) -> float:
    """Scale the training share of cost with Utah's completion rate relative to the benchmark."""
    training_factor = _completion_ratio(p) ** p["COMPLETION_COST_ELASTICITY"]
    share = p["TRAINING_COST_SHARE"]
    return base_cost * p["COST_MULTIPLIER"] * ((1 - share) + share * training_factor)


def effect_for_completion(effect: float, p: Params) -> float:
    """Scale an earnings effect for wage translation and Utah's completion rate."""
    return effect * p["WAGE_TRANSLATION_FACTOR"] * (_completion_ratio(p) ** p["COMPLETION_OUTCOME_ELASTICITY"])


def evaluate_scenario(
    inputs: ModelInputs,
    evidence_model: dict[str, Any],
    scenario: dict[str, Any],
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate one scenario. `overrides` may replace any parameter, `effectPath` or `programCost`."""
    overrides = overrides or {}
    p: dict[str, Any] = {**scenario_parameters(inputs, scenario), **overrides}
    base_path = overrides.get("effectPath", evidence_model["referencePath"])
    path_2025 = [effect_for_completion(x, p) for x in base_path]
    program_cost = overrides.get("programCost")
    if program_cost is None:
        program_cost = cost_for_completion(evidence_model["weightedCost2025"], p)
    return evaluate_cash_flows(path_2025, program_cost, p, scenario["scenario"])


def _sum(values: Sequence[float]) -> float:
    """Left-to-right float sum, matching JavaScript's reduce order exactly."""
    total = 0.0
    for v in values:
        total += v
    return total


def evaluate_cash_flows(
    effect_path: Sequence[float],
    program_cost_per_person: float,
    p: dict[str, Any],
    scenario_name: str = "Custom",
) -> dict[str, Any]:
    """Build annual cohort cash flows and present values for the four perspectives."""
    cohort = p["COHORT_SIZE"]
    horizon = int(p["HORIZON_YEARS"])
    rows: list[dict[str, Any]] = [
        {
            "year": 0,
            "discount_factor": 1,
            "incremental_earnings_per_person": 0,
            "incremental_earnings_cohort": 0,
            "fringe_cohort": 0,
            "federal_income_tax_cohort": 0,
            "utah_income_tax_cohort": 0,
            "employee_payroll_tax_cohort": 0,
            "employer_payroll_tax_cohort": 0,
            "transfer_offset_cohort": 0,
            "program_cost_cohort": program_cost_per_person * cohort,
            "participant_time_cost_cohort": p["PARTICIPANT_TIME_COST"] * cohort,
        }
    ]
    for year in range(1, horizon + 1):
        effect = effect_path[year - 1] if year - 1 < len(effect_path) else 0
        earnings = effect * cohort
        rows.append(
            {
                "year": year,
                "discount_factor": 1 / ((1 + p["DISCOUNT_RATE"]) ** year),
                "incremental_earnings_per_person": effect,
                "incremental_earnings_cohort": earnings,
                "fringe_cohort": earnings * p["FRINGE_RATE"],
                "federal_income_tax_cohort": earnings * p["FEDERAL_INCOME_TAX_RATE"],
                "utah_income_tax_cohort": earnings * p["UTAH_INCOME_TAX_RATE"],
                "employee_payroll_tax_cohort": earnings * p["EMPLOYEE_PAYROLL_TAX_RATE"],
                "employer_payroll_tax_cohort": earnings * p["EMPLOYER_PAYROLL_TAX_RATE"],
                "transfer_offset_cohort": earnings * p["TRANSFER_OFFSET_RATE"],
                "program_cost_cohort": 0,
                "participant_time_cost_cohort": 0,
            }
        )
    for r in rows:
        r["participant_net_cohort"] = (
            r["incremental_earnings_cohort"]
            + r["fringe_cohort"]
            - r["federal_income_tax_cohort"]
            - r["utah_income_tax_cohort"]
            - r["employee_payroll_tax_cohort"]
            - r["employer_payroll_tax_cohort"]
            - r["participant_time_cost_cohort"]
        )
        r["utah_government_net_cohort"] = (
            r["utah_income_tax_cohort"] + r["transfer_offset_cohort"] - r["program_cost_cohort"] * p["UTAH_COST_SHARE"]
        )
        r["combined_government_net_cohort"] = (
            r["federal_income_tax_cohort"]
            + r["utah_income_tax_cohort"]
            + r["employee_payroll_tax_cohort"]
            + r["employer_payroll_tax_cohort"]
            + r["transfer_offset_cohort"]
            - r["program_cost_cohort"]
        )
        r["societal_net_cohort"] = (
            r["incremental_earnings_cohort"]
            + r["fringe_cohort"]
            - r["program_cost_cohort"]
            - r["participant_time_cost_cohort"]
        )

    def pv(selector: Callable[[dict[str, Any]], float]) -> float:
        return _sum([selector(r) * r["discount_factor"] for r in rows])

    earnings_pv = pv(lambda r: r["incremental_earnings_cohort"])
    fringe_pv = pv(lambda r: r["fringe_cohort"])
    # Long-run incidence assigns the employer-side payroll tax to worker compensation.
    # Debiting it from participants and crediting it to government keeps the
    # stakeholder accounts additive while preserving ECEC fringe compensation.
    tax_participant_pv = pv(
        lambda r: (
            r["federal_income_tax_cohort"]
            + r["utah_income_tax_cohort"]
            + r["employee_payroll_tax_cohort"]
            + r["employer_payroll_tax_cohort"]
        )
    )
    state_tax_pv = pv(lambda r: r["utah_income_tax_cohort"] + r["transfer_offset_cohort"])
    all_tax_pv = pv(
        lambda r: (
            r["federal_income_tax_cohort"]
            + r["utah_income_tax_cohort"]
            + r["employee_payroll_tax_cohort"]
            + r["employer_payroll_tax_cohort"]
            + r["transfer_offset_cohort"]
        )
    )
    cost_pv = program_cost_per_person * cohort
    time_pv = p["PARTICIPANT_TIME_COST"] * cohort
    utah_cost = cost_pv * p["UTAH_COST_SHARE"]
    perspectives = {
        "Participant": _metric(
            earnings_pv + fringe_pv - tax_participant_pv - time_pv,
            earnings_pv + fringe_pv,
            tax_participant_pv + time_pv,
            cohort,
        ),
        "Utah Government": _metric(state_tax_pv - utah_cost, state_tax_pv, utah_cost, cohort),
        "Combined Government": _metric(all_tax_pv - cost_pv, all_tax_pv, cost_pv, cohort),
        "Societal": _metric(
            earnings_pv + fringe_pv - cost_pv - time_pv, earnings_pv + fringe_pv, cost_pv + time_pv, cohort
        ),
    }
    gap = (
        perspectives["Participant"]["npv_cohort"]
        + perspectives["Combined Government"]["npv_cohort"]
        - perspectives["Societal"]["npv_cohort"]
    )
    return {
        "scenario": scenario_name,
        "parameters": p,
        "program_cost_per_person": program_cost_per_person,
        "program_cost_cohort": cost_pv,
        "effect_path": list(effect_path[:horizon]),
        "annual_cash_flows": rows,
        "perspectives": perspectives,
        "accounting": {
            "employer_payroll_tax_incidence": "participant",
            "perspective_additivity_gap_cohort": gap,
            "perspective_additivity_gap_per_person": gap / cohort,
        },
        "break_even": {
            "societal_program_cost_per_person": (earnings_pv + fringe_pv - time_pv) / cohort,
            "effect_scalar": (cost_pv + time_pv) / max(earnings_pv + fringe_pv, 1e-9),
        },
    }


def _metric(npv: float, benefits: float, costs: float, cohort: float) -> dict[str, float | None]:
    return {
        "npv_cohort": npv,
        "npv_per_person": npv / cohort,
        "pv_benefits_cohort": benefits,
        "pv_costs_cohort": costs,
        "benefit_cost_ratio": benefits / costs if costs > 0 else None,
    }


def deterministic_results(inputs: ModelInputs, evidence_model: dict[str, Any]) -> list[dict[str, Any]]:
    return [evaluate_scenario(inputs, evidence_model, s) for s in inputs.scenarios]


def flatten_scenario_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "scenario": r["scenario"],
            "perspective": perspective,
            "npv_per_person": m["npv_per_person"],
            "npv_cohort": m["npv_cohort"],
            "pv_benefits_cohort": m["pv_benefits_cohort"],
            "pv_costs_cohort": m["pv_costs_cohort"],
            "benefit_cost_ratio": m["benefit_cost_ratio"],
            "program_cost_per_person": r["program_cost_per_person"],
        }
        for r in results
        for perspective, m in r["perspectives"].items()
    ]


# --------------------------------------------------------------------------- statistics helpers


def derive_se(effect: float, p_value: float | None) -> float:
    """Back out a standard error from a two-sided p-value (fallback: 75% of |effect|, min $1,000)."""
    if not p_value or p_value <= 0 or p_value >= 1:
        return max(abs(effect) * 0.75, 1000)
    z = abs(inv_norm(1 - p_value / 2))
    return abs(effect) / max(z, 0.01)


_A = (
    -39.69683028665376,
    220.9460984245205,
    -275.9285104469687,
    138.357751867269,
    -30.66479806614716,
    2.506628277459239,
)
_B = (-54.47609879822406, 161.5858368580409, -155.6989798598866, 66.80131188771972, -13.28068155288572)
_C = (
    -0.007784894002430293,
    -0.3223964580411365,
    -2.400758277161838,
    -2.549732539343734,
    4.374664141464968,
    2.938163982698783,
)
_D = (0.007784695709041462, 0.3224671290700398, 2.445134137142996, 3.754408661907416)


def inv_norm(p: float) -> float:
    """Peter J. Acklam's inverse-normal approximation (kept instead of scipy for exact parity)."""
    lo, hi = 0.02425, 1 - 0.02425
    a, b, c, d = _A, _B, _C, _D
    if p < lo:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1
        )
    if p > hi:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(
            (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5])
            / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
        )
    q = p - 0.5
    r = q * q
    return (
        (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5])
        * q
        / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)
    )


_U32 = 0xFFFFFFFF


def mulberry32(seed: int) -> Rng:
    """Mulberry32 PRNG, bit-identical to the JavaScript version used by the original model."""
    state = int(seed) & _U32

    def imul(x: int, y: int) -> int:
        return (x * y) & _U32

    def rng() -> float:
        nonlocal state
        state = (state + 0x6D2B79F5) & _U32
        t = state
        t = imul(t ^ (t >> 15), t | 1)
        t = (t ^ ((t + imul(t ^ (t >> 7), t | 61)) & _U32)) & _U32
        return (t ^ (t >> 14)) / 4294967296

    return rng


_EPSILON = 2.220446049250313e-16  # JavaScript Number.EPSILON


def normal(rng: Rng) -> float:
    """Standard normal draw by Box-Muller (consumes two uniforms)."""
    u = max(rng(), _EPSILON)
    v = rng()
    return math.sqrt(-2 * math.log(u)) * math.cos(2 * math.pi * v)


def triangular(rng: Rng, low: float, mode: float, high: float) -> float:
    u = rng()
    f = (mode - low) / (high - low)
    if u < f:
        return low + math.sqrt(u * (high - low) * (mode - low))
    return high - math.sqrt((1 - u) * (high - low) * (high - mode))


def lognormal_mean_cv(rng: Rng, mean: float, cv: float) -> float:
    """Lognormal draw parameterised by its mean and coefficient of variation."""
    sigma2 = math.log(1 + cv * cv)
    mu = math.log(mean) - sigma2 / 2
    return math.exp(mu + math.sqrt(sigma2) * normal(rng))


def quantile(values: Sequence[float], q: float) -> float:
    """Linear-interpolation quantile (same as numpy's default 'linear' method)."""
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    low, high = math.floor(pos), math.ceil(pos)
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (pos - low)


# --------------------------------------------------------------------------- Monte Carlo


def simulate_reference(
    inputs: ModelInputs,
    evidence_model: dict[str, Any],
    draws: int | None = None,
    overrides: Params | None = None,
) -> dict[str, Any]:
    """Seeded Monte Carlo around the Reference scenario.

    `overrides` replaces fixed Reference parameters before the draws (the
    50-state model uses it for each state's income tax rate). Parameters that
    are drawn (completion, discount, fringe and federal tax rates) are still
    drawn, so the same seed gives every state the same random draws.

    Each draw picks one WorkAdvance site, then samples completion, discount,
    fringe and federal tax rates, an early-effect multiplier, correlated
    long-run effect shocks and a lognormal cost shock. The order of random
    draws matches the original model exactly; changing it changes every result.
    """
    scenario = next(s for s in inputs.scenarios if s["scenario"] == "Reference")
    base = {**scenario_parameters(inputs, scenario), **(overrides or {})}
    n_draws = int(base["SIMULATION_DRAWS"]) if draws is None else draws
    rng = mulberry32(int(base["SIMULATION_SEED"]))
    registry = inputs.registry
    providers = evidence_model["providers"]

    def tri(parameter_id: str) -> float:
        entry = registry[parameter_id]
        return triangular(rng, entry["dist_min"], entry["dist_mode"], entry["dist_max"])

    rho = base["ANNUAL_EFFECT_CORRELATION"]
    results = []
    for draw in range(1, n_draws + 1):
        provider = providers[math.floor(rng() * len(providers))]
        p = dict(base)
        p["UTAH_COMPLETION"] = tri("UTAH_COMPLETION")
        p["DISCOUNT_RATE"] = tri("DISCOUNT_RATE")
        p["FRINGE_RATE"] = tri("FRINGE_RATE")
        p["FEDERAL_INCOME_TAX_RATE"] = tri("FEDERAL_INCOME_TAX_RATE")

        early_multiplier = 1 + base["EARLY_EFFECT_CV"] * normal(rng)
        common_long = normal(rng)
        idiosyncratic_long = []
        effect_path = []
        for i, mean in enumerate(evidence_model["sitePaths"][provider]):
            if i < 6:
                effect_path.append(mean * early_multiplier)
                continue
            idiosyncratic = normal(rng)
            idiosyncratic_long.append(idiosyncratic)
            z = math.sqrt(rho) * common_long + math.sqrt(1 - rho) * idiosyncratic
            effect_path.append(mean + evidence_model["siteSEs"][provider][i] * z)

        adjusted_path = [effect_for_completion(x, p) for x in effect_path]
        mean_cost = cost_for_completion(evidence_model["siteCosts2025"][provider], p)
        program_cost = lognormal_mean_cv(rng, mean_cost, registry["COST_MULTIPLIER"]["dist_max"])
        ev = evaluate_cash_flows(adjusted_path, program_cost, p, "Reference Monte Carlo")
        per = ev["perspectives"]
        results.append(
            {
                "draw": draw,
                "provider": provider,
                "early_effect_multiplier": early_multiplier,
                "long_term_common_z": common_long,
                "long_term_idiosyncratic_mean_z": _sum(idiosyncratic_long) / len(idiosyncratic_long),
                "completion_rate": p["UTAH_COMPLETION"],
                "discount_rate": p["DISCOUNT_RATE"],
                "fringe_rate": p["FRINGE_RATE"],
                "federal_income_tax_rate": p["FEDERAL_INCOME_TAX_RATE"],
                "mean_program_cost_before_shock": mean_cost,
                "program_cost_shock_ratio": program_cost / mean_cost,
                "program_cost_per_person": program_cost,
                "pv_compensation_benefits_per_person": per["Societal"]["pv_benefits_cohort"] / p["COHORT_SIZE"],
                "participant_npv_per_person": per["Participant"]["npv_per_person"],
                "participant_bcr": per["Participant"]["benefit_cost_ratio"],
                "utah_government_npv_per_person": per["Utah Government"]["npv_per_person"],
                "utah_government_bcr": per["Utah Government"]["benefit_cost_ratio"],
                "combined_government_npv_per_person": per["Combined Government"]["npv_per_person"],
                "combined_government_bcr": per["Combined Government"]["benefit_cost_ratio"],
                "societal_npv_per_person": per["Societal"]["npv_per_person"],
                "societal_bcr": per["Societal"]["benefit_cost_ratio"],
            }
        )
    return {"draws": results, "summary": summarize_draws(results)}


def summarize_draws(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    specs = (
        ("Participant", "participant_npv_per_person", "participant_bcr"),
        ("Utah Government", "utah_government_npv_per_person", "utah_government_bcr"),
        ("Combined Government", "combined_government_npv_per_person", "combined_government_bcr"),
        ("Societal", "societal_npv_per_person", "societal_bcr"),
    )
    summary = []
    for perspective, npv_key, bcr_key in specs:
        npvs = [r[npv_key] for r in rows]
        bcrs = [r[bcr_key] for r in rows if r[bcr_key] is not None and math.isfinite(r[bcr_key])]
        summary.append(
            {
                "perspective": perspective,
                "mean_npv_per_person": _sum(npvs) / len(npvs),
                "p05_npv_per_person": quantile(npvs, 0.05),
                "median_npv_per_person": quantile(npvs, 0.50),
                "p95_npv_per_person": quantile(npvs, 0.95),
                "probability_net_benefits_positive": sum(1 for x in npvs if x > 0) / len(npvs),
                "mean_bcr": _sum(bcrs) / len(bcrs),
                "p05_bcr": quantile(bcrs, 0.05),
                "median_bcr": quantile(bcrs, 0.50),
                "p95_bcr": quantile(bcrs, 0.95),
            }
        )
    return summary
