"""The AI Impact page's featured research list (ai_impact/featured.json).

The LaborPulse site reads this file from the main branch, so it is published
the moment a PR merges. `check_featured` is what CI runs on it:

- the file has the shape the site's parser expects (schema_version 1);
- ids are unique, dates are ISO dates and the feature window is sensible;
- every number in a summary is backed by an `evidence` quote copied from the
  source, so a reviewer can check it against the linked page. This applies the
  repo's "no fact, no number" rule to outside research.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from lpresearch.studies import REPO
from lpresearch.verify_numbers import extract_numbers

FEATURED_PATH = REPO / "ai_impact" / "featured.json"
KINDS = {"study", "tracker", "report", "survey"}
DATA_ACCESS = {"public", "restricted"}
MAX_FEATURE_DAYS = 120
_ID = re.compile(r"^[a-z0-9-]+$")
_REQUIRED = (
    "id",
    "title",
    "authors",
    "publisher",
    "published",
    "url",
    "kind",
    "data_access",
    "summary",
    "featured_on",
    "featured_until",
)


@dataclass(frozen=True)
class Problem:
    item: str
    message: str


def _iso(value: object) -> date | None:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _backed(number_text: str, value: float, is_percent: bool, quotes: list[str]) -> bool:
    """A number is backed when a quote contains the same value (and % sense) or the same literal digits."""
    literal = re.compile(rf"(?<![\d.]){re.escape(number_text.replace(',', ''))}(?![\d])")
    for quote in quotes:
        if any(m.value == value and m.is_percent == is_percent for m in extract_numbers(quote)):
            return True
        if literal.search(quote.replace(",", "")):
            return True
    return False


def unbacked_numbers(summary: str, quotes: list[str]) -> list[str]:
    missing = []
    for mention in extract_numbers(summary):
        digits = re.match(r"\$?([\d,.]+)", mention.text)
        number_text = digits.group(1) if digits else mention.text
        if not _backed(number_text, mention.value, mention.is_percent, quotes):
            missing.append(mention.text)
    return missing


def check_featured(payload: dict) -> list[Problem]:
    problems: list[Problem] = []
    if payload.get("schema_version") != 1:
        return [Problem("file", "schema_version must be 1")]
    if _iso(payload.get("updated")) is None:
        problems.append(Problem("file", "updated must be a YYYY-MM-DD date"))
    items = payload.get("items")
    if not isinstance(items, list):
        return [*problems, Problem("file", "items must be a list")]

    seen: set[str] = set()
    for raw in items:
        item_id = str(raw.get("id", "?")) if isinstance(raw, dict) else "?"
        if not isinstance(raw, dict):
            problems.append(Problem(item_id, "item must be an object"))
            continue
        for key in _REQUIRED:
            if not isinstance(raw.get(key), str) or not raw[key].strip():
                problems.append(Problem(item_id, f"{key} is required"))
        if not _ID.match(item_id):
            problems.append(Problem(item_id, "id must be lowercase letters, digits and hyphens"))
        if item_id in seen:
            problems.append(Problem(item_id, "duplicate id"))
        seen.add(item_id)
        if not str(raw.get("url", "")).startswith("https://"):
            problems.append(Problem(item_id, "url must start with https://"))
        if raw.get("kind") not in KINDS:
            problems.append(Problem(item_id, f"kind must be one of {sorted(KINDS)}"))
        if raw.get("data_access") not in DATA_ACCESS:
            problems.append(Problem(item_id, f"data_access must be one of {sorted(DATA_ACCESS)}"))

        published, start, end = (_iso(raw.get(k)) for k in ("published", "featured_on", "featured_until"))
        for key, parsed in (("published", published), ("featured_on", start), ("featured_until", end)):
            if parsed is None:
                problems.append(Problem(item_id, f"{key} must be a YYYY-MM-DD date"))
        if start and end:
            if end < start:
                problems.append(Problem(item_id, "featured_until is before featured_on"))
            elif (end - start).days > MAX_FEATURE_DAYS:
                problems.append(Problem(item_id, f"feature window is longer than {MAX_FEATURE_DAYS} days"))

        evidence = raw.get("evidence", [])
        if not isinstance(evidence, list) or any(
            not isinstance(e, dict) or not e.get("quote") or not str(e.get("url", "")).startswith("https://")
            for e in evidence
        ):
            problems.append(Problem(item_id, "evidence must be a list of {quote, url} with https URLs"))
            evidence = []
        quotes = [str(e["quote"]) for e in evidence]
        for number in unbacked_numbers(str(raw.get("summary", "")), quotes):
            problems.append(Problem(item_id, f"number {number!r} in summary is not backed by an evidence quote"))
    return problems


def read_featured(path: Path = FEATURED_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
