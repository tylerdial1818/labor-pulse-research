# Model Card

## Intended use

This package publishes a reproducible benefit-cost model for sector-based workforce training in Utah. It supports public research, methodological discussion, sensitivity analysis, funding design, and development of a production evaluation.

The current version establishes an evidence-based prior using WorkAdvance and Utah economic data. Future versions can incorporate Utah administrative, provider, participant-time, cost-sharing, and implementation data through the registered replacement path.

## Core contract

- Estimand: intent-to-treat, per eligible adult offered the program.
- Cohort: 1,000 modeled offers.
- Price year: 2025 dollars.
- Horizon: observed years 1–10; no terminal value.
- Perspectives: participant, Utah government, combined government, societal.
- Accounting identity: participant NPV plus combined-government NPV equals societal NPV.
- Employer payroll incidence: deducted from participant compensation and credited to combined government under the reference incidence assumption.
- Causal anchor: four-site WorkAdvance randomized controlled trial.
- Uncertainty: 10,000 seeded Monte Carlo draws plus structural scenarios.
- Seed: 20260716.

## Headline reference result

- Program cost: $7,505 per person offered.
- Societal NPV: $28,325 per person.
- Societal benefit-cost ratio: 4.77.
- Probability of positive societal net benefits: 98.1%.
- Combined-government benefit-cost ratio: 1.04; probability of positive net benefits: 41.5%.
- Utah-government benefit-cost ratio: 0.17 when Utah bears the full cost.

The result implies strong value creation but a mismatch between the entity paying for the program and the governments capturing fiscal returns.

## Model boundaries

- External validity to Utah remains uncertain.
- The tax module is reduced-form rather than a tax-unit microsimulation.
- Transfer savings are set to zero pending credible linkage evidence.
- Participant time is a structural sensitivity pending measured attendance and forgone work.
- AI exposure represents task content. It receives zero weight in the reference destination score, remains visible as a diagnostic overlay, and enters only a named AI-transition sensitivity.
- Occupational rankings are screening outputs and require employer/provider validation.
- October 2025 is missing from the retrieved FRED CPI series; the 2025 annual average uses 11 nonmissing observations.

## Reproducibility

Run `npm run model && npm test` to regenerate the model results from committed processed data. See `README.md`, `analysis_protocol.md`, `model/parameter_registry.csv`, `evidence/evidence_registry.csv`, and `data/source_manifest.csv` for the complete audit trail.
