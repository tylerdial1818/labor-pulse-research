"""Run the Utah Workforce ROI model and write its outputs and facts.json.

Outputs mirror the original Node.js `run_model.mjs` file for file, so the two
can be compared directly, plus a `facts.json` for the research-note verifier.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from lpresearch.facts import Fact, FactSheet, Source
from lpresearch.io import write_csv
from lpresearch.pipelines.utah_roi import model, sensitivity

MODEL_VERSION = "0.1.0"
STUDY = "utah_roi"
STUDY_DIR = Path(__file__).resolve().parents[4] / "studies" / STUDY


def run(study_dir: Path = STUDY_DIR, out_dir: Path | None = None, draws: int | None = None) -> dict[str, Any]:
    """Run the full model. Returns the serialisable results written to model_results.json."""
    out_dir = out_dir or study_dir / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)

    inputs = model.load_model_inputs(study_dir)
    evidence = model.build_evidence_model(inputs)
    scenarios = model.deterministic_results(inputs, evidence)
    reference = next(r for r in scenarios if r["scenario"] == "Reference")
    simulation = model.simulate_reference(inputs, evidence, draws)

    effect_rows = [
        {
            "year": i + 1,
            "reference_effect_per_person_2025": value,
            "source_stage": (
                "Sample-weighted four-site RCT; source 3% discount undone"
                if i < 6
                else "Published pooled four-site RCT"
            ),
            "source_price_year_proxy": 2018 if i < 6 else 2020 + (i - 6),
        }
        for i, value in enumerate(reference["effect_path"])
    ]
    provider_rows = [
        {
            "provider": provider,
            "year": i + 1,
            "effect_per_person_2025": value,
            "standard_error_2025": evidence["siteSEs"][provider][i] or "",
        }
        for provider in evidence["providers"]
        for i, value in enumerate(evidence["sitePaths"][provider])
    ]

    write_csv(out_dir / "effect_path.csv", effect_rows)
    write_csv(out_dir / "provider_effect_paths.csv", provider_rows)
    write_csv(out_dir / "scenario_results.csv", model.flatten_scenario_results(scenarios))
    write_csv(out_dir / "annual_cash_flows_reference.csv", reference["annual_cash_flows"])
    write_csv(out_dir / "simulation_draws_reference.csv", simulation["draws"])
    write_csv(out_dir / "simulation_summary.csv", simulation["summary"])
    report_tables = sensitivity.build_report_tables(study_dir, inputs, evidence, simulation["draws"])
    for name, rows in report_tables.items():
        write_csv(out_dir / name, rows)

    summary = {row["perspective"]: row for row in simulation["summary"]}
    per = reference["perspectives"]
    results = {
        "model_version": MODEL_VERSION,
        "generated_at": datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "price_year": 2025,
        "horizon_years": 10,
        "cohort_size": reference["parameters"]["COHORT_SIZE"],
        "evidence_model": evidence,
        "deterministic_scenarios": scenarios,
        "simulation_summary": simulation["summary"],
        "simulation_draws": len(simulation["draws"]),
        "headline": {
            "participant_npv_per_person": per["Participant"]["npv_per_person"],
            "participant_bcr": per["Participant"]["benefit_cost_ratio"],
            "combined_government_npv_per_person": per["Combined Government"]["npv_per_person"],
            "combined_government_bcr": per["Combined Government"]["benefit_cost_ratio"],
            "societal_npv_per_person": per["Societal"]["npv_per_person"],
            "societal_bcr": per["Societal"]["benefit_cost_ratio"],
            "probability_societal_net_positive": summary["Societal"]["probability_net_benefits_positive"],
            "utah_government_npv_per_person": per["Utah Government"]["npv_per_person"],
            "utah_government_bcr": per["Utah Government"]["benefit_cost_ratio"],
            "probability_utah_government_net_positive": summary["Utah Government"]["probability_net_benefits_positive"],
            "program_cost_per_person": reference["program_cost_per_person"],
            "break_even_effect_scalar": reference["break_even"]["effect_scalar"],
            "perspective_additivity_gap_per_person": reference["accounting"]["perspective_additivity_gap_per_person"],
        },
    }
    (out_dir / "model_results.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    build_facts(results, reference, summary, report_tables).write(out_dir / "facts.json")
    return results


_PERSPECTIVE_SLUGS = {
    "Participant": "participant",
    "Utah Government": "utah_government",
    "Combined Government": "combined_government",
    "Societal": "societal",
}


def _slug(text: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in text.lower()).strip("_").replace("__", "_")


def build_facts(
    results: dict[str, Any],
    reference: dict[str, Any],
    summary: dict[str, dict],
    report_tables: dict[str, list[dict[str, Any]]],
) -> FactSheet:
    """Every number a Utah ROI research note may quote, with where it came from."""
    sheet = FactSheet(study=STUDY, model_version=MODEL_VERSION)
    det = Source(kind="computed", ref=f"studies/{STUDY}/outputs/model_results.json")
    sim = Source(kind="computed", ref=f"studies/{STUDY}/outputs/simulation_summary.csv")
    p = reference["parameters"]

    def add(fact_id: str, value: float, unit: str, description: str, source: Source = det) -> None:
        sheet.add(Fact(id=fact_id, value=float(value), unit=unit, description=description, source=source))

    add("horizon_years", results["horizon_years"], "years", "Years after enrollment in the core model")
    add("cohort_size", results["cohort_size"], "count", "Illustrative cohort offered the program")
    add("simulation_draws", results["simulation_draws"], "count", "Monte Carlo draws")
    add("discount_rate", p["DISCOUNT_RATE"], "proportion", "Reference real discount rate")
    add(
        "program_cost_per_person",
        reference["program_cost_per_person"],
        "usd",
        "Reference net program cost per person offered, 2025 dollars",
    )
    add(
        "break_even_effect_scalar",
        reference["break_even"]["effect_scalar"],
        "proportion",
        "Share of the reference earnings effect needed for societal break-even",
    )
    for name, m in reference["perspectives"].items():
        slug = _PERSPECTIVE_SLUGS[name]
        add(
            f"{slug}_npv_per_person",
            m["npv_per_person"],
            "usd",
            f"{name} net present value per person offered, Reference scenario, 2025 dollars",
        )
        if m["benefit_cost_ratio"] is not None:
            add(f"{slug}_bcr", m["benefit_cost_ratio"], "ratio", f"{name} benefit-cost ratio, Reference scenario")
        s = summary[name]
        add(
            f"{slug}_probability_npv_positive",
            s["probability_net_benefits_positive"],
            "proportion",
            f"Share of Monte Carlo draws with positive {name.lower()} net benefits",
            sim,
        )
        for stat in ("p05", "median", "p95"):
            add(
                f"{slug}_npv_{stat}",
                s[f"{stat}_npv_per_person"],
                "usd",
                f"{name} NPV per person, Monte Carlo {stat}",
                sim,
            )
    for row in results["deterministic_scenarios"]:
        if row["scenario"] == "Reference":
            continue
        scen = row["scenario"].lower().replace(" ", "_")
        for name, m in row["perspectives"].items():
            slug = _PERSPECTIVE_SLUGS[name]
            add(
                f"{scen}_{slug}_npv_per_person",
                m["npv_per_person"],
                "usd",
                f"{name} NPV per person, {row['scenario']} scenario, 2025 dollars",
            )
            if m["benefit_cost_ratio"] is not None:
                add(
                    f"{scen}_{slug}_bcr",
                    m["benefit_cost_ratio"],
                    "ratio",
                    f"{name} benefit-cost ratio, {row['scenario']} scenario",
                )
    _add_report_facts(add, reference, report_tables)
    return sheet


def _add_report_facts(add, reference: dict[str, Any], tables: dict[str, list[dict[str, Any]]]) -> None:
    """Facts from the sensitivity and report tables, limited to what a note is likely to quote."""

    def src(name: str) -> Source:
        return Source(kind="computed", ref=f"studies/{STUDY}/outputs/{name}")

    add(
        "break_even_program_cost_per_person",
        reference["break_even"]["societal_program_cost_per_person"],
        "usd",
        "Highest program cost per person at which societal NPV stays positive, Reference effects",
    )
    for row in tables["one_way_sensitivity.csv"]:
        if row["perspective"] not in ("Societal", "Utah Government"):
            continue
        base = f"sens_{row['sensitivity_id']}_{_PERSPECTIVE_SLUGS[row['perspective']]}"
        for side in ("low", "high"):
            add(
                f"{base}_{side}_npv_per_person",
                row[f"{side}_npv_per_person"],
                "usd",
                f"{row['perspective']} NPV per person when {row['label'].lower()} is set to its {side} value "
                f"({row[f'{side}_label']})",
                src("one_way_sensitivity.csv"),
            )
            if row[f"{side}_bcr"] is not None:
                add(
                    f"{base}_{side}_bcr",
                    row[f"{side}_bcr"],
                    "ratio",
                    f"{row['perspective']} benefit-cost ratio when {row['label'].lower()} is at its {side} value",
                    src("one_way_sensitivity.csv"),
                )
    for row in tables["provider_scenario_results.csv"]:
        if row["perspective"] != "Societal":
            continue
        slug = _slug(row["provider"])
        add(
            f"provider_{slug}_program_cost_per_person",
            row["program_cost_per_person"],
            "usd",
            f"{row['provider']} net program cost per person, 2025 dollars",
            src("provider_scenario_results.csv"),
        )
        add(
            f"provider_{slug}_societal_npv_per_person",
            row["npv_per_person"],
            "usd",
            f"Societal NPV per person using {row['provider']}'s own effects and cost",
            src("provider_scenario_results.csv"),
        )
        add(
            f"provider_{slug}_societal_bcr",
            row["benefit_cost_ratio"],
            "ratio",
            f"Societal benefit-cost ratio using {row['provider']}'s own effects and cost",
            src("provider_scenario_results.csv"),
        )
    for row in tables["funding_share_scenarios.csv"]:
        sid = row["scenario_id"]
        for key, unit, what in (
            ("utah_npv_per_person", "usd", "Utah government NPV per person"),
            ("federal_npv_per_person", "usd", "Federal government NPV per person"),
            ("utah_bcr", "ratio", "Utah government benefit-cost ratio"),
            ("federal_bcr", "ratio", "Federal government benefit-cost ratio"),
        ):
            if row[key] != "":
                add(
                    f"funding_{sid}_{key}",
                    row[key],
                    unit,
                    f"{what} when {row['label'][0].lower()}{row['label'][1:]}",
                    src("funding_share_scenarios.csv"),
                )
    for row in tables["uncertainty_contributions.csv"]:
        add(
            f"uncertainty_{row['factor_id']}_share",
            row["diagnostic_share_of_variance"],
            "proportion",
            f"Share of societal NPV variance explained by {row['label'].lower()} alone (screening diagnostic)",
            src("uncertainty_contributions.csv"),
        )
