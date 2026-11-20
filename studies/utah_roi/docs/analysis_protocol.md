# Analysis Protocol

## Project

**Title:** Translating Evidence into State Policy: A Utah ROI and Budget-Impact Model for Sector-Based Workforce Training

**Version:** 0.1.0-protocol  
**Protocol frozen:** 2026-07-16  
**Analyst:** Tyler Dial  
**Status:** Open research protocol

## Decision Question

What participant, Utah-government, combined-government, and societal returns might result if Utah offered a WorkAdvance-like sectoral training program to 1,000 eligible adults, given Utah labor-market conditions and the uncertainty observed in the causal evidence?

## Estimand and Unit of Analysis

- Primary estimand: intent-to-treat (ITT) incremental benefit and cost per eligible adult offered the program.
- Modeled cohort: 1,000 eligible adults offered the program.
- Program: assessment, sector-focused skills training, credential support, placement assistance, and post-placement coaching.
- Primary monetary outcome: incremental annual earnings relative to services-as-usual.
- The model interprets AI occupational exposure as a transition-planning measure.

## Perspectives

1. Participant: after-tax compensation, transfer changes, and participant-paid costs. Employer payroll tax is deducted from total compensation under standard long-run incidence.
2. Utah government: Utah tax revenue and Utah-funded program costs or documented transfer changes.
3. Combined government: federal and state tax revenue, public program costs, and causally supported transfer changes.
4. Societal: incremental labor compensation and real resource costs; taxes and cash transfers are excluded as transfers.

## Time, Prices, and Discounting

- Base price year: 2025 dollars.
- Core horizon: 10 years following program offer.
- Core post-Year-10 benefits: zero.
- Base real discount rate: 3 percent.
- Sensitivity discount rates: 0 percent and 7 percent.
- Costs and benefits are timed explicitly by model year.

## Evidence Rules

- Primary causal anchor: WorkAdvance multisite randomized controlled trial.
- Use ITT estimates for the offer cohort; do not multiply ITT outcomes by completion a second time.
- Extract site, follow-up period, outcome definition, effect estimate, uncertainty, sample, and design information into the evidence registry.
- Pool estimates only when intervention, outcome, sample, estimand, and follow-up are sufficiently comparable.
- Prefer the evaluation's prespecified pooled estimate. If a new pooled estimate is justified, use inverse-variance random effects with small-sample uncertainty.
- Do not select a favorable provider as the base case.
- Weaker designs may inform external validity or sensitivity cases but will not displace randomized evidence in the core estimate.

## Translation Rules

- Absolute dollar effects are converted to 2025 dollars but are not proportionally wage-scaled in the reference case.
- Relative or log-earnings effects may be applied to the Utah counterfactual when reported in that form.
- A proportional Utah wage-translation case is reported separately.
- Completion affects stage-specific costs. Outcome adjustments for completion appear only in explicit implementation-fidelity scenarios.
- Observed long-term effects are used through Year 10. No terminal value appears in the reference case.
- Provider heterogeneity is preserved through site-specific results and empirical provider-mix scenarios.

## Fiscal and Societal Accounting Rules

- Effective tax rates are used rather than top statutory rates.
- Federal income, payroll, and Utah income taxes may enter combined-government results.
- Sales-tax feedback is excluded from the reference case.
- Transfer changes enter fiscal results only when supported by credible causal evidence.
- Taxes and cash transfers are not net societal benefits.
- Marginal employer-paid fringe benefits are included as a separate societal line and removed in a wages-only sensitivity case.
- Employer payroll tax is credited to combined government and deducted from participant compensation. This treatment reflects standard long-run incidence and prevents legally required benefits in ECEC compensation from being counted twice.
- The model must satisfy the accounting identity `Participant NPV + Combined Government NPV = Societal NPV` when no separate employer surplus account is modeled.
- Participant time is not added at full wages when short-run earnings effects already capture foregone work; a separately identified nonmarket-time sensitivity is allowed.

## Occupational Targeting Rules

- Prioritize transitions from exposed or underemployed source occupations into accessible Utah destination occupations.
- Destination occupations must pass configurable demand, wage, credential-duration, and placement-capacity gates.
- Reference score weights: Utah demand 35 percent, wage uplift 35 percent, and credential accessibility 30 percent.
- AI task exposure receives zero weight in the reference score. It remains visible as a diagnostic overlay and enters only a named AI-transition sensitivity.
- Report rank stability under alternative weights and do not treat AI exposure as a forecast of job loss.

## Uncertainty

- Run 10,000 seeded Monte Carlo draws.
- Preserve correlation in annual effect paths where covariance information is available; otherwise use transparent block-level draws.
- Sampling uncertainty, provider heterogeneity, cost uncertainty, and parameter uncertainty are recorded separately.
- Structural choices without defensible probabilities are reported as separate scenarios, not hidden inside one probability-weighted result.
- Primary risk metric: probability net present value exceeds zero.

## Reproducibility Standard

- All parameters use stable IDs and reside in `model/parameter_registry.csv`.
- All evidence records reside in `evidence/evidence_registry.csv`.
- All external sources, retrieval dates, local snapshots, and SHA-256 hashes reside in `data/source_manifest.csv`.
- Scenario files change parameter selections; formulas are not edited to run a case.
- The workbook is formula-driven for deterministic calculations and references the parameter registry.
- The simulation uses an explicit random seed and writes machine-readable results.
- The reproducibility manifest records the Git commit, environment, input hashes, model version, and seed.
- Automated tests verify perspective additivity and equal treatment of employer payroll tax as a participant debit and government credit.
- Acceptance criterion: the same commit, inputs, scenario, and seed reproduce the same outputs.

## Prespecified Outputs

- Net present value and benefit-cost ratio by perspective.
- Benefit and cost streams by year and category.
- 5th, 50th, and 95th percentile results.
- Probability benefits exceed costs by perspective.
- Break-even effect and break-even cost.
- Provider/site scenario comparison.
- Occupational transition shortlist and rank-stability analysis.
