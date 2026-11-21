"""State-specific inputs for the 50-state Workforce ROI model.

Two free public sources vary by state:

- state income tax brackets (Tax Foundation, 2025), turned into the statutory
  marginal rate a participant pays on an extra dollar of earnings
- all-occupation median annual wages (BLS OEWS, May 2025), used only in the
  local-wage sensitivities

Everything else comes from the Utah study unchanged.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Bracket:
    rate: float
    """Marginal rate as a proportion (0.045 for 4.5%)."""
    start: float
    """Taxable income, in dollars, above which this rate applies."""


@dataclass(frozen=True)
class State:
    abbr: str
    name: str
    brackets: tuple[Bracket, ...]
    median_wage: float
    employment: float


def marginal_rate(brackets: tuple[Bracket, ...] | list[Bracket], taxable_income: float) -> float:
    """Statutory marginal rate on the next dollar above `taxable_income`.

    Income below the first bracket's start is untaxed (for example North
    Dakota's first bracket starts at $48,475 for single filers).
    """
    rate = 0.0
    for bracket in sorted(brackets, key=lambda b: b.start):
        if taxable_income >= bracket.start:
            rate = bracket.rate
    return rate


def load_settings(study_dir: Path) -> dict[str, Any]:
    return json.loads((study_dir / "model" / "settings.json").read_text(encoding="utf-8"))


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_states(study_dir: Path) -> list[State]:
    """The 50 states and DC, sorted by name, with their tax brackets and OEWS wages."""
    raw = study_dir / "data" / "raw"
    brackets: dict[str, list[Bracket]] = {}
    names: dict[str, str] = {}
    for row in _read_csv(raw / "state_income_tax_brackets_2025.csv"):
        abbr = row["state_abbr"]
        names[abbr] = row["state_name"]
        brackets.setdefault(abbr, []).append(
            Bracket(rate=float(row["rate_percent"]) / 100, start=float(row["bracket_start_usd"]))
        )
    wages = {row["prim_state"]: row for row in _read_csv(raw / "oews_may2025_state_all_occupations.csv")}
    missing = sorted(set(brackets) - set(wages))
    if missing:
        raise ValueError(f"no OEWS wage row for: {', '.join(missing)}")
    states = [
        State(
            abbr=abbr,
            name=names[abbr],
            brackets=tuple(sorted(brackets[abbr], key=lambda b: b.start)),
            median_wage=float(wages[abbr]["a_median"]),
            employment=float(wages[abbr]["tot_emp"]),
        )
        for abbr in brackets
    ]
    return sorted(states, key=lambda s: s.name)


def state_tax_rate(state: State, settings: dict[str, Any], taxable_income: float | None = None) -> float:
    """Rate used in the model: the bracket lookup, unless settings register a sourced override.

    Overrides are flat-rate corrections (Utah's 2025 cut), so they apply at any income.
    """
    for override in settings.get("rate_overrides", []):
        if override["state_abbr"] == state.abbr:
            return float(override["rate"])
    income = settings["reference_taxable_income_usd"] if taxable_income is None else taxable_income
    return marginal_rate(state.brackets, income)


def site_weighted_median_wage(states: list[State], settings: dict[str, Any], sample_by_provider: dict) -> float:
    """Median wage of the WorkAdvance site states, weighted by each site's trial sample."""
    by_abbr = {s.abbr: s for s in states}
    site_states = settings["workadvance_site_states"]
    total = sum(sample_by_provider.values())
    return sum(by_abbr[site_states[p]].median_wage * n / total for p, n in sample_by_provider.items())
