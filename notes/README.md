# Research notes

Each note lives in `notes/<study>/<date>-<slug>/` with `note.md` and the `facts.json` snapshot it was written from. CI runs `lpresearch check-notes`: every number in a note must match a fact in its snapshot, and every snapshot value must still match what the pipeline computes.
