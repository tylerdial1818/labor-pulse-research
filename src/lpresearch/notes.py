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

`notes/index.json` lists every note with its front matter and summary. The
LaborPulse site reads it (and each note.md) from this repo's main branch, so a
merged note with `status: "published"` appears on the site without a deploy.
`lpresearch index-notes` rewrites it, and CI fails when it is out of date.
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
STATUSES = ("draft", "published")
INDEX_FILE = "index.json"
INDEX_SCHEMA_VERSION = 1

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


def front_matter(text: str) -> dict:
    """The front matter as a dict. Each line is `key: <JSON value>`, as written by new_note."""
    match = _FRONT_MATTER.match(text)
    if not match:
        return {}
    fields = {}
    for line in match.group(1).splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = json.loads(value.strip())
    return fields


def summary(body: str) -> str:
    """The first paragraph of prose after the title, used as the note's summary."""
    for block in re.split(r"\n\s*\n", body.strip()):
        block = block.strip()
        if block and not block.startswith(("#", "<!--")):
            return " ".join(block.split())
    return ""


def build_index(notes_dir: Path) -> dict:
    """Every note's metadata, newest first, in the form the site reads."""
    entries = []
    for note in notes_dir.glob("*/*/note.md"):
        text = note.read_text(encoding="utf-8")
        meta = front_matter(text)
        entries.append(
            {
                "study": note.parent.parent.name,
                "slug": note.parent.name,
                "path": note.relative_to(notes_dir).as_posix(),
                "title": meta.get("title", ""),
                "date": meta.get("date", ""),
                "byline": meta.get("byline", ""),
                "model_version": meta.get("model_version", ""),
                "status": meta.get("status", ""),
                "summary": summary(note_body(text)),
            }
        )
    entries.sort(key=lambda e: (e["date"], e["slug"]), reverse=True)
    return {"schema_version": INDEX_SCHEMA_VERSION, "notes": entries}


def write_index(notes_dir: Path) -> Path:
    path = notes_dir / INDEX_FILE
    path.write_text(json.dumps(build_index(notes_dir), indent=2) + "\n", encoding="utf-8")
    return path


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
        status = front_matter(text).get("status")
        if status not in STATUSES:
            problems.append(NoteProblem(note, f"status must be one of {', '.join(STATUSES)}, not {status!r}"))
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
    index_path = notes_dir / INDEX_FILE
    if any(notes_dir.glob("*/*/note.md")):
        current_index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else None
        if current_index != build_index(notes_dir):
            problems.append(NoteProblem(index_path, "is out of date; run `lpresearch index-notes`"))
    return problems
