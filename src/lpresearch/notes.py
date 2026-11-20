"""Draft research notes with Claude and hold them to the facts.

A note lives in its own folder, `notes/<study>/<slug>/`, with two files:

- `note.md`: front matter plus the prose
- `facts.json`: a snapshot of the facts the note was written from

`draft_note` asks Claude for a draft, runs the number verifier, and sends the
draft back for revision (up to `max_revisions` times) while any number lacks a
matching fact. A draft that still fails is written anyway, marked
`status: needs-numbers-fixed`, so a reviewer can see what went wrong.

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
from typing import Any, Protocol

from lpresearch.facts import FactSheet
from lpresearch.verify_numbers import NumberMention, unverified

MODEL = "claude-opus-5-5"
BYLINE = "LaborPulse Research Desk"

SYSTEM_PROMPT = f"""\
You write research notes for LaborPulse, a public labor-market research site. Notes appear under the \
byline "{BYLINE}" and are read by policy staff, journalists, workforce boards and researchers.

Write like a careful applied economist explaining results to an informed general reader:
- Lead with the finding and what it means for a decision maker, then explain how it was estimated.
- Use plain language. Define a benefit-cost ratio or net present value the first time you use it.
- Say what the analysis does not show as clearly as what it does: name the main assumptions, the \
evidence they rest on and where results are sensitive.
- Write in the institutional voice ("this analysis", "the model"), never "I".
- Aim for 600 to 900 words with a title line starting "# " and three to five "## " section headings.

Every number you write must come from the facts you are given, rounded however reads best \
("$7,505", "$7.5k", "98%"). Do not compute new numbers from them, such as differences, sums or \
percentages of a ratio, and do not bring in numbers from memory. Calendar years are fine. If a point \
needs a number that is not in the facts, make the point without the number. Spell out small counts \
in words ("four sites") unless the count is itself a fact.

Reply with the note in Markdown and nothing else."""


class MessagesClient(Protocol):
    """The slice of `anthropic.Anthropic` this module uses, so tests can pass a fake."""

    @property
    def beta(self) -> Any: ...


@dataclass
class DraftResult:
    markdown: str
    unverified: list[NumberMention]
    revisions: int

    @property
    def ok(self) -> bool:
        return not self.unverified


def _facts_block(facts: FactSheet) -> str:
    rows = [{"id": f.id, "value": f.value, "unit": f.unit, "description": f.description} for f in facts.facts]
    return json.dumps(rows, indent=1)


def _first_prompt(facts: FactSheet, topic: str, context: str) -> str:
    return (
        f"<study_context>\n{context}\n</study_context>\n\n"
        f'<facts study="{facts.study}" model_version="{facts.model_version}">\n{_facts_block(facts)}\n</facts>\n\n'
        f"Write a research note on this topic: {topic}"
    )


def _revision_prompt(bad: list[NumberMention]) -> str:
    listed = "\n".join(f"- {m.text!r}" for m in bad)
    return (
        "The number check found figures in your draft that do not match any fact:\n"
        f"{listed}\n\n"
        "Rewrite the note so that every number matches a fact (rounding is fine), or drop the figure "
        "and keep the point in words. Reply with the full revised note only."
    )


def _call(client: MessagesClient, messages: list[dict[str, Any]]) -> Any:
    with client.beta.messages.stream(
        model=MODEL,
        max_tokens=32000,
        system=SYSTEM_PROMPT,
        thinking={"type": "adaptive"},
        output_config={"effort": "high"},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=messages,
    ) as stream:
        response = stream.get_final_message()
    if response.stop_reason == "refusal":
        raise RuntimeError("Claude declined to draft this note; try rewording the topic.")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("The draft hit the output limit before finishing.")
    return response


def _text(response: Any) -> str:
    return "".join(block.text for block in response.content if block.type == "text").strip()


def draft_note(
    client: MessagesClient,
    facts: FactSheet,
    topic: str,
    context: str = "",
    max_revisions: int = 2,
) -> DraftResult:
    """Draft a note, then revise until every number is backed by a fact or revisions run out."""
    messages: list[dict[str, Any]] = [{"role": "user", "content": _first_prompt(facts, topic, context)}]
    response = _call(client, messages)
    markdown = _text(response)
    bad = unverified(markdown, facts)
    revisions = 0
    while bad and revisions < max_revisions:
        # Append the whole response (thinking blocks included) so the conversation stays append-only.
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": _revision_prompt(bad)})
        response = _call(client, messages)
        markdown = _text(response)
        bad = unverified(markdown, facts)
        revisions += 1
    return DraftResult(markdown=markdown, unverified=bad, revisions=revisions)


# --------------------------------------------------------------------------- note files


_FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "note"


def _title(markdown: str, fallback: str) -> str:
    for line in markdown.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def write_note(result: DraftResult, facts: FactSheet, topic: str, notes_dir: Path, today: date | None = None) -> Path:
    """Write note.md and its facts snapshot. Returns the note folder."""
    today = today or date.today()
    title = _title(result.markdown, topic)
    folder = notes_dir / facts.study / f"{today.isoformat()}-{slugify(title)}"
    folder.mkdir(parents=True, exist_ok=False)
    status = "draft" if result.ok else "needs-numbers-fixed"
    front = {
        "title": title,
        "byline": BYLINE,
        "date": today.isoformat(),
        "study": facts.study,
        "model_version": facts.model_version,
        "status": status,
        "topic": topic,
        "drafted_with": MODEL,
        "revisions": result.revisions,
    }
    lines = ["---", *(f"{k}: {json.dumps(v)}" for k, v in front.items()), "---", ""]
    (folder / "note.md").write_text("\n".join(lines) + result.markdown.rstrip() + "\n", encoding="utf-8")
    facts.write(folder / "facts.json")
    return folder


def note_body(text: str) -> str:
    """The prose of a note, without its front matter (which holds dates and counts that aren't claims)."""
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
        snapshot_path = note.parent / "facts.json"
        if not snapshot_path.exists():
            problems.append(NoteProblem(note, "missing facts.json snapshot"))
            continue
        snapshot = FactSheet.read(snapshot_path)
        for mention in unverified(note_body(note.read_text(encoding="utf-8")), snapshot):
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
