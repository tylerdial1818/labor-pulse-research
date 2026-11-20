# Utah Workforce ROI Model

This repository contains an open research report and a complete, reproducible economic model of sector-based workforce investment in Utah. It combines ten-year randomized WorkAdvance evidence with Utah labor-market data, a documented cost and fiscal model, occupational targeting, structural scenarios, and seeded Monte Carlo risk analysis.

The policy-transfer model separates experimental evidence, Utah-specific economic inputs, and registered reference-case assumptions. Every result can be traced through the public evidence registry, parameter library, model code, and generated cash flows.

## Headline reference result

For a cohort of 1,000 eligible adults offered the program, in 2025 dollars:

- Program cost: **$7,505 per person offered**.
- Societal NPV: **$28,325 per person**.
- Societal benefit-cost ratio: **4.77**.
- Probability of positive societal net benefits: **98.1%** across 10,000 seeded draws.
- Combined-government benefit-cost ratio: **1.04**, with a **41.5%** probability of positive net benefits.
- Utah-government benefit-cost ratio: **0.17** when Utah bears the full cost.

The central strategic finding is a financing-incidence problem: the program creates substantial value, but Utah income-tax receipts alone do not repay a fully state-funded program within ten years. Federal/employer cost sharing and outcome-based procurement are therefore part of the economic design, not afterthoughts.

## Start here

- [Open research report](output/pdf/utah_workforce_roi_open_research_report.pdf) — 30-page publication with executive summary, evidence, methods, results, risk analysis, Utah occupational strategy, and technical documentation.
- [Editable Word report](output/docx/utah_workforce_roi_open_research_report.docx) — editable narrative and tables with high-resolution analytical exhibits.
- [Technical brief](outputs/pdf/utah_workforce_roi_technical_brief.pdf) — seven-page reviewer-facing methodology and findings.
- [Interactive audit workbook](outputs/workbook/utah_workforce_roi_model.xlsx) — formula-driven scenario selector, evidence and parameter registries, cash flows, Monte Carlo summaries, targets, and QA.
- [Copy-ready proposal methodology](proposal_methodology.md) — narrative language suitable for adapting into an RFP response.
- [Frozen analysis protocol](analysis_protocol.md) — decisions made before results.
- [Model card](model_card.md) — intended use, headline result, model boundaries, and reproducibility contract.
- [Parameter registry](model/parameter_registry.csv) — every assumption sourced, dated, versioned, and swappable.
- [Evidence registry](evidence/evidence_registry.csv) — one row per extracted estimate.
- [Source manifest](data/source_manifest.csv) — URLs, retrieval dates, local paths, roles, notes, and SHA-256 hashes.

## Reproduce the core model

Requirements: Node.js 20 or later. The core model uses only the Node standard library.

```bash
npm run build
```

This regenerates deterministic scenarios, the 10,000 Monte Carlo draws, summary CSVs, automated tests, and `reproducibility_manifest.json` from committed processed data. The random seed is `20260716`, so the draws reproduce exactly.

Useful commands:

```bash
npm run model        # deterministic model + Monte Carlo outputs
npm test             # economic-identity and reproducibility tests
npm run manifest     # refresh file hashes
```

## Refresh raw labor data or presentation artifacts

The upstream BLS workbook reader and Excel generator use OpenAI's bundled `@oai/artifact-tool` workspace dependency. The final workbook is committed so reviewers do not need that environment to inspect it. Within a compatible Codex workspace:

```bash
npm run refresh:workspace
```

The publication-quality PDF and editable Word report require Python 3, the report dependencies, and Poppler for exhibit rendering:

```bash
python3 -m pip install -r requirements-report.txt
npm run report:publication
```

## Model architecture

```text
raw sources + hashes
        ↓
processed Utah labor data     evidence registry
        ↓                           ↓
occupational portfolio       causal effect + cost paths
                  ↘          ↙
                  parameter registry
                         ↓
            deterministic cash-flow model
                         ↓
        structural scenarios + Monte Carlo risk
                         ↓
           CSVs, audit workbook, technical brief
```

The machine-readable files are the source of truth. The workbook is the human-readable audit layer; its selected scenario changes formulas on the effect, cost, cash-flow, and executive-summary sheets. Monte Carlo probabilities remain labeled as reference-case results.

## Primary analytical rules

- Intent-to-treat effects are reported per eligible adult offered the program.
- Years 1–6 pool WorkAdvance sites by randomized sample size; years 7–10 use published pooled effects.
- The source report's discounting is undone before the model applies its selected discount rate once.
- No effect or terminal value is assumed after observed year 10.
- Utah wage levels determine opportunity targeting and counterfactuals; they do not mechanically scale the causal effect in the reference case.
- Completion changes the training-related cost share but does not double-attenuate the reference ITT outcome.
- Taxes are fiscal benefits but cancel from the societal perspective.
- Unsupported transfer savings are zero.
- Provider heterogeneity is preserved in deployment-risk draws.
- AI task exposure informs transition portfolios as a task-based planning signal.

See [proposal_methodology.md](proposal_methodology.md) and the workbook's **Read Me** sheet for the full rationale and replacement path.

## Repository map

```text
analysis_protocol.md                   frozen design choices
proposal_methodology.md                copy-ready RFP language
model_card.md                          intended use and limits
data/source_manifest.csv               source provenance and hashes
data/raw/                               preserved source files
data/processed/                         model-ready Utah inputs
evidence/evidence_registry.csv          extracted causal and cost evidence
model/parameter_registry.csv            swappable assumption library
model/scenarios/                        structural scenario definitions
src/model_core.mjs                      economic identities and simulation
src/run_model.mjs                       output orchestration
tests/model_tests.mjs                   automated QA
outputs/data/                           cash flows, scenarios, and draws
outputs/workbook/                       Excel audit model
outputs/pdf/                            technical brief
output/pdf/                             publication-quality open research report
output/docx/                            editable Word report
report/                                 report brief, exhibit storyboard, design system, and brand assets
reproducibility_manifest.json           final hashes and build contract
```

## Model boundaries

External validity remains uncertain until Utah implementation data are observed. The tax module is reduced-form, transfer offsets are excluded pending linkage evidence, participant time lacks direct measurement, and the occupational portfolio requires employer and provider validation. Employer payroll tax is assigned to participants under standard long-run incidence and is shown separately because it determines whether combined government reaches break-even. AI task exposure receives zero weight in the reference destination score. October 2025 is missing from the retrieved FRED CPI series, so the 2025 annual average uses 11 nonmissing observations. These boundaries are surfaced in the registries, workbook, report, and model card.

## Citation

See `CITATION.cff`. Model version `0.1.0`, released under the MIT License.
