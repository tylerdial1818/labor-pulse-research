"""Research notes: scaffolding a note and holding every note to its facts.

A note lives in its own folder, `notes/<study>/<date>-<slug>/`, with two files:

- `note.md`: front matter plus the prose
- `facts.json`: a snapshot of the facts the note was written from

Notes are drafted by Claude in a LaborPulse project thread, not through the
API, so drafting has no per-call cost. The process is in `docs/writing-notes.md`:
`lpresearch new-note` sets up the folder, Claude writes the prose following
`docs/note-style.md`, `lpresearch verify` must pass, and the note opens as a
pull request for review.

`check_notes` is what CI runs: every note must pass the verifier against its
snapshot, and every snapshot value must still match what the pipeline
computes today, so a note can't drift from the model behind it.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from lpresearch.facts import FactSheet
from lpresearch.verify_numbers import unverified

BYLINE = "LaborPulse Research Desk"

_FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)

PLACEHOLDER = (
    "<!-- Write the note here, following docs/note-style.md. Every number must match a fact in the\n"
    "facts.json next to this file. Run `lpresearch verify --facts <this folder>/facts.json <this file>`\n"
    "before opening the pull request. Delete this comment. -->\n"
)


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "note"


def new_note(facts: FactSheet, title: str, topic: str, notes_dir: Path, today: date | None = None) -> Path:
    """Create a note folder with front matter, a placeholder body and the facts snapshot."""
    today = today or date.today()
    folder = notes_dir / facts.study / f"{today.isoformat()}-{slugify(title)}"
    folder.mkdir(parents=True, exist_ok=False)
    front = {
        "title": title,
        "byline": BYLINE,
        "date": today.isoformat(),
        "study": facts.study,
        "model_version": facts.model_version,
        "status": "draft",
        "topic": topic,
    }
    lines = ["---", *(f"{k}: {json.dumps(v)}" for k, v in front.items()), "---", ""]
    body = f"# {title}\n\n{PLACEHOLDER}"
    (folder / "note.md").write_text("\n".join(lines) + body, encoding="utf-8")
    facts.write(folder / "facts.json")
    return folder


def note_body(text: str) -> str:
    """The prose of a note, without its front matter (which holds dates that aren't claims)."""
    match = _FRONT_MATTER.match(text)
    return text[match.end() :] if match else text


@dataclass
class NoteProblem:
    note: Path
    message: str


def check_notes(notes_dir: Path, current: dict[str, FactSheet]) -> list[NoteProblem]:
    """Verify every note against its facts snapshot, and every snapshot against current pipeline facts."""
    problems = []
    for note in sorted(notes_dir.glob("*/*/note.md")):
        text = note.read_text(encoding="utf-8")
        if "<!-- Write the note here" in text:
            problems.append(NoteProblem(note, "still has the new-note placeholder"))
        snapshot_path = note.parent / "facts.json"
        if not snapshot_path.exists():
            problems.append(NoteProblem(note, "missing facts.json snapshot"))
            continue
        snapshot = FactSheet.read(snapshot_path)
        for mention in unverified(note_body(text), snapshot):
            problems.append(NoteProblem(note, f"{mention.text!r} is not backed by any fact"))
        live = current.get(snapshot.study)
        if live is None:
            problems.append(NoteProblem(note, f"no pipeline facts for study {snapshot.study!r}"))
            continue
        live_values = {f.id: f.value for f in live.facts}
        for fact in snapshot.facts:
            if fact.id not in live_values:
                problems.append(NoteProblem(note, f"fact {fact.id} no longer produced by the pipeline"))
            elif not math.isclose(fact.value, live_values[fact.id], rel_tol=1e-9, abs_tol=1e-9):
                problems.append(
                    NoteProblem(note, f"fact {fact.id} is {fact.value} in the snapshot but {live_values[fact.id]} now")
                )
    return problems
