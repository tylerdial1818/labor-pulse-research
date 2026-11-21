"""Registry of studies: how to run each one and what background a note writer gets."""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from lpresearch.facts import FactSheet

REPO = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Study:
    name: str
    """Folder name under studies/ and notes/, also the facts.json `study` value."""
    run: Callable[[Path | None], object]
    """Runs the pipeline, writing outputs (including facts.json) to the given folder."""
    context_docs: tuple[str, ...]
    """Docs (relative to the study folder) given to the note writer as background."""

    @property
    def folder(self) -> Path:
        return REPO / "studies" / self.name

    def context(self) -> str:
        return "\n\n".join((self.folder / doc).read_text(encoding="utf-8") for doc in self.context_docs)

    def compute_facts(self) -> FactSheet:
        """Run the pipeline into a scratch folder and return the facts it produces."""
        with tempfile.TemporaryDirectory() as tmp:
            self.run(Path(tmp))
            return FactSheet.read(Path(tmp) / "facts.json")


def _run_utah_roi(out_dir: Path | None) -> object:
    from lpresearch.pipelines.utah_roi import run

    return run.run(out_dir=out_dir)


def _run_state_roi(out_dir: Path | None) -> object:
    from lpresearch.pipelines.state_roi import run

    return run.run(out_dir=out_dir)


STUDIES: dict[str, Study] = {
    "utah_roi": Study(
        name="utah_roi",
        run=_run_utah_roi,
        context_docs=("docs/model_card.md", "docs/analysis_protocol.md"),
    ),
    "state_roi": Study(
        name="state_roi",
        run=_run_state_roi,
        context_docs=("docs/README.md",),
    ),
}


def get(name: str) -> Study:
    key = name.replace("-", "_")
    if key not in STUDIES:
        raise SystemExit(f"unknown study {name!r}; known: {', '.join(STUDIES)}")
    return STUDIES[key]
