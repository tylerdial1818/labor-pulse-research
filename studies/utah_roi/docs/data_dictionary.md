# Data Dictionary

## `model/parameter_registry.csv`

One row per swappable model parameter. Key fields include the parameter ID; reference, conservative, and evidence-extension values; unit; price year; geography; perspective; probability distribution; source; transformation; evidence tier; version; update date; and notes.

## `evidence/evidence_registry.csv`

One row per extracted program estimate. `estimand` distinguishes intent-to-treat from descriptive program-group measures. `outcome` identifies annual earnings, net program cost, completion, or cumulative earnings. `effect_unit` and `price_year` prevent dollar-basis ambiguity. `source_location` permits direct source verification. `uncertainty_method` states whether a standard error was reported, derived, or unavailable.

## `data/processed/utah_labor_market.csv`

Merged six-digit SOC file containing Utah projections, May 2025 OEWS employment and wages, task-level AI exposure, and derived scores.

## `data/processed/utah_target_occupations.csv`

Occupations passing the reference accessibility, growth, openings, and wage gates. The reference score weights demand at 35 percent, wage mobility at 35 percent, and credential accessibility at 30 percent. AI task exposure receives zero reference weight. The file also contains demand-heavy, mobility/access, and named AI-transition sensitivity rankings.

## `data/processed/utah_source_occupations.csv`

Modeled outreach occupations ranked on AI task exposure, Utah employment scale, and low-wage position. AI task exposure enters as a transition-planning signal.

## `outputs/data/effect_path.csv`

The pooled annual causal earnings path per eligible adult offered the program in 2025 dollars, with source construction and price-year proxy.

## `outputs/data/annual_cash_flows_reference.csv`

Reference annual cohort flows for earnings, fringe benefits, taxes, transfers, program cost, participant time, and four perspective-specific net benefits. Employer payroll tax is deducted from participant compensation under standard long-run incidence and credited to combined government. Participant plus combined-government net benefit equals societal net benefit.

## `outputs/data/scenario_results.csv`

Scenario-by-perspective NPV, present-value benefits, present-value costs, benefit-cost ratio, and program cost.

## `outputs/data/simulation_draws_reference.csv`

All 10,000 seeded reference draws. Each row records sampled provider, completion, discount, fringe, federal tax, program cost, and NPV/BCR for each perspective.

## `outputs/data/simulation_summary.csv`

Mean, 5th percentile, median, 95th percentile, probability of positive net benefits, and BCR distribution by perspective.
