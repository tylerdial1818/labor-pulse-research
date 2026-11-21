# 50-State Workforce ROI (v0.1.0)

The Utah Workforce ROI model, run for every state and DC. It asks the same question for each state: if a state offers WorkAdvance-style sector training, what does society get back, and how much of that comes back to the state government that pays for it?

## How it works

The engine is the Utah model in `src/lpresearch/pipelines/utah_roi/model.py`, unchanged. The 50-state pipeline (`src/lpresearch/pipelines/state_roi/`) reads the Utah study's parameter registry, WorkAdvance evidence and scenarios, then evaluates the Reference scenario once per state with that state's income tax rate. Everything else is held fixed:

- the earnings effects from the four-site WorkAdvance randomized trial (10 years)
- the net program cost per person offered
- national parameters: CPI, payroll tax, fringe rate, federal tax rate, 3% real discounting
- the 10,000-draw Monte Carlo with the same seed, so every state sees the same random draws

The Utah model's "Utah Government" perspective becomes each state's government. In the Reference case the state pays the whole program cost.

## What varies by state

| Input | Source | How it is used |
|---|---|---|
| State income tax rate | Tax Foundation, State Individual Income Tax Rates and Brackets, 2025 (single filer, as of January 1, 2025) | Statutory marginal rate at $30,000 of taxable income, a rough level for a WorkAdvance participant. Credits that lower what people actually owe are not modeled. |
| Median annual wage, all occupations | BLS OEWS, May 2025 state estimates | Sensitivities only. Divided by the sample-weighted median of the WorkAdvance site states (New York for Per Scholas and St. Nicks Alliance, Oklahoma for Madison Strategies Group, Ohio for Towards Employment). |

One sourced override: the January 1 table shows Utah at 4.55%, but Utah cut its rate to 4.5% for tax year 2025, which is the rate the Utah study uses. Overrides live in `model/settings.json` with their source.

## Outputs

`lpresearch run state-roi` writes `studies/state_roi/outputs/`:

- `state_results.csv`: one row per state (columns below)
- `model_results.json`: the same rows plus a cross-state summary
- `facts.json`: the numbers a research note may quote

| Column | Meaning |
|---|---|
| `state_income_tax_rate` | Rate used in the Reference case |
| `state_income_tax_rate_alt_income` | Marginal rate at $50,000 of taxable income |
| `median_annual_wage`, `wage_ratio_to_workadvance_sites` | OEWS median and its ratio to the WorkAdvance site states |
| `program_cost_per_person` | Net program cost per person offered (2025 dollars, same everywhere) |
| `participant_npv_per_person`, `societal_npv_per_person`, `societal_bcr` | Reference results |
| `combined_government_npv_per_person`, `combined_government_bcr` | Federal plus state, including payroll taxes |
| `state_government_npv_per_person`, `state_government_bcr` | The state's own account when it pays the full cost |
| `state_revenue_pv_per_person` | Present value of extra state income tax per person offered |
| `federal_npv_per_person` | Federal account when the state pays the full cost |
| `probability_*_positive` | Share of Monte Carlo draws with positive net benefits |
| `alt_income_state_government_bcr` | State BCR at the $50,000 marginal rate |
| `wage_scaled_*` | Earnings effects scaled by the state's wage ratio, cost unchanged |
| `wage_scaled_with_costs_*` | Effects and program cost both scaled by the wage ratio |

The state government benefit-cost ratio has a second reading: it is the share of the program cost the state could pay and still break even, with the rest paid by federal or other funders.

## What to expect in the results

- **The societal return is identical in every state in the Reference case.** The effects come from one trial, and the Reference case does not scale them by local wages (the same choice the Utah study made). Taxes are transfers, so they cancel out of the societal account.
- **The state's own return tracks its income tax rate.** States with no tax on wages at this income recover nothing through income tax.
- **The federal gain is the same everywhere**, because federal and payroll tax rates are national.
- **The wage sensitivities are where states differ on value.** If effects scale with local wages, high-wage states show larger societal returns. If program costs scale too, the ratio returns to the Reference value and only dollar amounts change.

## Limitations

- One causal anchor (WorkAdvance in New York City, Tulsa and Cleveland). How well it transfers to each state is unknown.
- The state tax is a statutory marginal rate, not a tax-unit microsimulation. Credits, deductions and local income taxes (for example in Maryland, New York City and Ohio cities) are excluded.
- Sales, excise and property taxes are excluded, which understates what states without an income tax recover.
- Transfer savings (for example Medicaid or SNAP) are set to zero, as in the Utah study.
- Rate changes enacted after January 1, 2025 are not reflected unless registered as an override.
- Statewide medians are a coarse proxy for local labor markets, and DC is a single city compared against whole states.
- Occupational targeting by state (the Utah study's shortlist) is not yet generalized; it needs each state's long-term occupational projections.

## Reproducing

```bash
python -m pip install -e ".[dev]"
lpresearch run state-roi            # about 30 seconds, 51 x 10,000 draws
pytest tests/test_state_roi.py
```

The OEWS extract in `data/raw/` was made with `scripts/extract_oews_state_medians.py`, which needs `openpyxl`, from the same BLS zip the Utah study used (sha256 in `data/source_manifest.csv`). The tax brackets were transcribed from the Tax Foundation table.
