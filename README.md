# LaborPulse Research

Reproducible analyses behind [LaborPulse](https://www.laborpulse.org) research notes, published by the LaborPulse Research Desk.

Each study is a Python pipeline that reads versioned inputs and writes its outputs plus a `facts.json`. A research note may only quote numbers that appear in a `facts.json` (computed here) or in a cited external source. `lpresearch verify` enforces that rule, and every note goes through a pull request as its editorial review.

## Layout

```
src/lpresearch/
  facts.py              facts.json schema: id, value, unit, description, source
  verify_numbers.py     checks every number in a note against the facts
  notes.py              drafts notes with Claude and checks them against their facts
  studies.py            registry of studies and the background docs a note writer gets
  cli.py                `lpresearch run | verify | draft | check-notes`
  pipelines/utah_roi/   Utah Workforce ROI benefit-cost model
studies/utah_roi/
  model/                parameter registry and scenario definitions
  evidence/             evidence registry (WorkAdvance RCT estimates)
  data/                 processed Utah labor-market and CPI inputs
  docs/                 protocol, model card, data dictionary, citation
  reference/node-v0.1.0 outputs of the original Node.js model, used as the parity baseline
notes/<study>/<date>-<slug>/
  note.md               the note, with front matter (byline, status, model version)
  facts.json            the facts snapshot it was written from
tests/                  model invariants, Node parity, sensitivity, verifier, note drafting
```

## Quick start

```bash
python -m pip install -e ".[dev]"
lpresearch run utah-roi                       # writes studies/utah_roi/outputs/
lpresearch verify --facts studies/utah_roi/outputs/facts.json note.md
pytest
```

The pipelines use only the Python standard library. Drafting notes needs the `draft` extra (`pip install -e ".[draft]"`) and an `ANTHROPIC_API_KEY`.

## Writing a note

1. Run the **Draft research note** workflow in GitHub Actions, choose a study and describe the topic.
2. The workflow runs the pipeline, Claude drafts the note from its `facts.json`, and the number check runs. If a number has no matching fact, the draft goes back to Claude with the list, up to two times.
3. A pull request opens with the note and its facts snapshot. Review the interpretation, caveats and tone, edit freely, and merge to publish.

CI runs `lpresearch check-notes` on every pull request: each note must pass the number check against its snapshot, and every snapshot value must still equal what the pipeline computes today. Changing the model therefore flags every note whose numbers moved.

Locally: `lpresearch draft utah-roi --topic "What Utah gets back from sector training"`.

## Studies

### Utah Workforce ROI (v0.1.0)

A benefit-cost model of WorkAdvance-style sector training for a Utah cohort, from participant, Utah government, combined government and societal perspectives. Values are intent-to-treat per person offered, in 2025 dollars, over a 10-year horizon at a 3% real discount rate, with a seeded 10,000-draw Monte Carlo. See `studies/utah_roi/docs/` for the protocol and model card. Besides the core results, the pipeline writes the report tables: one-way sensitivity, funding-share scenarios, fiscal incidence, the break-even frontier, benefit composition, provider results, Monte Carlo uncertainty screening and occupation rank stability.

The Python model is a direct port of the original Node.js `model_core.mjs`. `tests/test_utah_roi_parity.py` reruns all of it, including every simulation draw, and requires agreement with the Node outputs to within 1e-9 relative. The random number generator (Mulberry32) and the inverse-normal approximation are reimplemented exactly rather than swapped for NumPy or SciPy so that the seeded draws stay identical.

## How the number check works

A number in prose passes when some fact rounds to exactly what was written in a normal display form. A fact of 0.9808 (proportion) backs "98%" and "98.1 percent". A fact of 7505.29 (usd) backs "$7,505" and "$7.5k". Signs are ignored so a negative NPV can be written as "a net cost of $6,242". Calendar years are skipped. Anything else without a matching fact fails the check.
