# LaborPulse Research

Reproducible analyses behind [LaborPulse](https://www.laborpulse.org) research notes, published by the LaborPulse Research Desk.

Each study is a Python pipeline that reads versioned inputs and writes its outputs plus a `facts.json`. A research note may only quote numbers that appear in a `facts.json` (computed here) or in a cited external source. `lpresearch verify` enforces that rule, and every note goes through a pull request as its editorial review.

## Layout

```
src/lpresearch/
  facts.py              facts.json schema: id, value, unit, description, source
  verify_numbers.py     checks every number in a note against the facts
  cli.py                `lpresearch run <study>` and `lpresearch verify`
  pipelines/utah_roi/   Utah Workforce ROI benefit-cost model
studies/utah_roi/
  model/                parameter registry and scenario definitions
  evidence/             evidence registry (WorkAdvance RCT estimates)
  data/                 processed Utah labor-market and CPI inputs
  docs/                 protocol, model card, data dictionary, citation
  reference/node-v0.1.0 outputs of the original Node.js model, used as the parity baseline
tests/                  model invariants, Node parity, number verifier
```

## Quick start

```bash
python -m pip install -e ".[dev]"
lpresearch run utah-roi                       # writes studies/utah_roi/outputs/
lpresearch verify --facts studies/utah_roi/outputs/facts.json note.md
pytest
```

The package uses only the Python standard library at runtime.

## Studies

### Utah Workforce ROI (v0.1.0)

A benefit-cost model of WorkAdvance-style sector training for a Utah cohort, from participant, Utah government, combined government and societal perspectives. Values are intent-to-treat per person offered, in 2025 dollars, over a 10-year horizon at a 3% real discount rate, with a seeded 10,000-draw Monte Carlo. See `studies/utah_roi/docs/` for the protocol and model card.

The Python model is a direct port of the original Node.js `model_core.mjs`. `tests/test_utah_roi_parity.py` reruns all of it, including every simulation draw, and requires agreement with the Node outputs to within 1e-9 relative. The random number generator (Mulberry32) and the inverse-normal approximation are reimplemented exactly rather than swapped for NumPy or SciPy so that the seeded draws stay identical.

## How the number check works

A number in prose passes when some fact rounds to exactly what was written in a normal display form. A fact of 0.9808 (proportion) backs "98%" and "98.1 percent". A fact of 7505.29 (usd) backs "$7,505" and "$7.5k". Signs are ignored so a negative NPV can be written as "a net cost of $6,242". Calendar years are skipped. Anything else without a matching fact fails the check.
