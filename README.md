# LaborPulse Research

Reproducible analyses behind [LaborPulse](https://www.laborpulse.org) research notes, published by the LaborPulse Research Desk.

Each study is a Python pipeline that reads versioned inputs and writes its outputs plus a `facts.json`. A research note may only quote numbers that appear in a `facts.json` (computed here) or in a cited external source. `lpresearch verify` enforces that rule, and every note goes through a pull request as its editorial review.

## Layout

```
src/lpresearch/
  facts.py              facts.json schema: id, value, unit, description, source
  verify_numbers.py     checks every number in a note against the facts
  notes.py              sets up note folders and checks notes against their facts
  studies.py            registry of studies and their background docs
  cli.py                `lpresearch run | facts | verify | new-note | check-notes | feeds collect | check-featured`
  feeds.py              collects candidate AI-and-labor research from open feeds (weekly Action)
  featured.py           validates ai_impact/featured.json, the AI Impact page's featured research
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
ai_impact/
  featured.json         featured research shown on laborpulse.org/ai-impact (published on merge)
  feed_sources.json     open feeds the weekly collector reads
  candidates/           weekly candidate lists, input to the monthly curation PR
docs/                   how notes are written, the note style guide, and how featured research is curated
tests/                  model invariants, Node parity, sensitivity, verifier, note checks
```

## Quick start

```bash
python -m pip install -e ".[dev]"
lpresearch run utah-roi                       # writes studies/utah_roi/outputs/
lpresearch verify --facts studies/utah_roi/outputs/facts.json note.md
pytest
```

The package uses only the Python standard library at runtime.

## Writing a note

Notes are drafted by Claude in a LaborPulse project thread, with no API calls or API key. Each note gets its own folder with a snapshot of the facts it was written from, `lpresearch verify` must pass before the pull request opens, and the pull request is the editorial review. The full steps are in [docs/writing-notes.md](docs/writing-notes.md) and the house style is in [docs/note-style.md](docs/note-style.md).

CI runs `lpresearch check-notes` on every pull request: each note must pass the number check against its snapshot, and every snapshot value must still equal what the pipeline computes today. Changing the model therefore flags every note whose numbers moved.

## Featured AI research

The AI Impact page's rotating research list is curated here. A weekly Action collects candidates from open feeds, and a monthly PR picks the best ones. See [docs/curating-featured-research.md](docs/curating-featured-research.md).

## Studies

### Utah Workforce ROI (v0.1.0)

A benefit-cost model of WorkAdvance-style sector training for a Utah cohort, from participant, Utah government, combined government and societal perspectives. Values are intent-to-treat per person offered, in 2025 dollars, over a 10-year horizon at a 3% real discount rate, with a seeded 10,000-draw Monte Carlo. See `studies/utah_roi/docs/` for the protocol and model card. Besides the core results, the pipeline writes the report tables: one-way sensitivity, funding-share scenarios, fiscal incidence, the break-even frontier, benefit composition, provider results, Monte Carlo uncertainty screening and occupation rank stability.

The Python model is a direct port of the original Node.js `model_core.mjs`. `tests/test_utah_roi_parity.py` reruns all of it, including every simulation draw, and requires agreement with the Node outputs to within 1e-9 relative. The random number generator (Mulberry32) and the inverse-normal approximation are reimplemented exactly rather than swapped for NumPy or SciPy so that the seeded draws stay identical.

## How the number check works

A number in prose passes when some fact rounds to exactly what was written in a normal display form. A fact of 0.9808 (proportion) backs "98%" and "98.1 percent". A fact of 7505.29 (usd) backs "$7,505" and "$7.5k". Signs are ignored so a negative NPV can be written as "a net cost of $6,242". Calendar years are skipped. Anything else without a matching fact fails the check.
