"""Facts: the only numbers a published research note is allowed to contain.

Every analysis pipeline writes a `facts.json` file. Each fact is one number
with an id, a unit, a plain-language description and a source. A source is
either `computed` (produced by a pipeline in this repo, with the output file
it came from) or `external` (a published statistic, with a URL). The number
verifier checks drafted prose against this file before a note can be merged.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

Unit = Literal["usd", "proportion", "percent", "ratio", "count", "years", "year", "number"]
SourceKind = Literal["computed", "external"]
UNITS: frozenset[str] = frozenset(Unit.__args__)  # type: ignore[attr-defined]

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class Source:
    kind: SourceKind
    ref: str
    """Output file (computed) or URL (external) the value came from."""
    retrieved: str | None = None
    """ISO date an external value was retrieved."""

    def __post_init__(self) -> None:
        if self.kind not in ("computed", "external"):
            raise ValueError(f"source kind must be 'computed' or 'external', got {self.kind!r}")
        if not self.ref:
            raise ValueError("source ref must not be empty")
        if self.kind == "external" and not self.ref.startswith(("http://", "https://")):
            raise ValueError(f"external source ref must be a URL, got {self.ref!r}")


@dataclass(frozen=True)
class Fact:
    id: str
    value: float
    unit: Unit
    description: str
    source: Source

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("fact id must not be empty")
        if self.unit not in UNITS:
            raise ValueError(f"fact {self.id}: unknown unit {self.unit!r}")
        if not isinstance(self.value, (int, float)) or not math.isfinite(self.value):
            raise ValueError(f"fact {self.id}: value must be a finite number, got {self.value!r}")


@dataclass
class FactSheet:
    study: str
    model_version: str
    facts: list[Fact] = field(default_factory=list)

    def add(self, fact: Fact) -> None:
        if any(f.id == fact.id for f in self.facts):
            raise ValueError(f"duplicate fact id: {fact.id}")
        self.facts.append(fact)

    def get(self, fact_id: str) -> Fact:
        for fact in self.facts:
            if fact.id == fact_id:
                return fact
        raise KeyError(fact_id)

    def to_dict(self) -> dict:
        return {
            "schema_version": SCHEMA_VERSION,
            "study": self.study,
            "model_version": self.model_version,
            "facts": [asdict(f) for f in self.facts],
        }

    def write(self, path: Path | str) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")

    @classmethod
    def from_dict(cls, data: dict) -> FactSheet:
        if data.get("schema_version") != SCHEMA_VERSION:
            raise ValueError(f"unsupported facts schema version: {data.get('schema_version')!r}")
        sheet = cls(study=data["study"], model_version=data["model_version"])
        for raw in data["facts"]:
            sheet.add(
                Fact(
                    id=raw["id"],
                    value=raw["value"],
                    unit=raw["unit"],
                    description=raw["description"],
                    source=Source(**raw["source"]),
                )
            )
        return sheet

    @classmethod
    def read(cls, path: Path | str) -> FactSheet:
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
