"""Check that every number in a drafted note is backed by a fact.

A number in prose passes when some fact, shown in a plausible display form,
rounds to exactly what was written. For example a fact of 0.98077 with unit
"proportion" backs "98%", "98.1%" and "98 percent"; a fact of 7505.29 with
unit "usd" backs "$7,505", "$7.5k" and "$7,505.29". Signs are ignored, so a
fact of -6241.69 backs "a net cost of $6,242". A benefit-cost ratio may be
written in dollars ("$4.77 per dollar").

Calendar years (1900-2100 written without a currency sign, decimals or a
suffix) are skipped, because dates are checked in review rather than here.
Everything else must match, which keeps the rule simple to explain: no fact,
no number.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from lpresearch.facts import Fact, FactSheet

_SCALES = {
    "k": 1e3,
    "thousand": 1e3,
    "m": 1e6,
    "mn": 1e6,
    "million": 1e6,
    "b": 1e9,
    "bn": 1e9,
    "billion": 1e9,
    "t": 1e12,
    "trillion": 1e12,
}

_NUMBER = re.compile(
    r"""
    (?P<currency>\$)?
    (?P<number>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+)
    (?:\s?(?P<percent>%|percent\b|per\ cent\b|percentage\ points?\b|pp\b))?
    (?:\s?(?P<scale>thousand|million|billion|trillion|mn|bn|[kKmMbBtT])\b)?
    """,
    re.VERBOSE,
)


@dataclass(frozen=True)
class NumberMention:
    text: str
    start: int
    value: float
    decimals: int
    is_percent: bool
    is_currency: bool
    scale: float


@dataclass(frozen=True)
class Finding:
    mention: NumberMention
    matched: Fact | None

    @property
    def ok(self) -> bool:
        return self.matched is not None


def extract_numbers(text: str) -> list[NumberMention]:
    mentions = []
    for m in _NUMBER.finditer(text):
        start = m.start()
        if not m.group("currency") and _inside_word(text, start):
            continue
        raw = m.group("number").replace(",", "")
        decimals = len(raw.split(".")[1]) if "." in raw else 0
        scale_word = (m.group("scale") or "").lower()
        mention = NumberMention(
            text=m.group(0).strip(),
            start=start,
            value=float(raw),
            decimals=decimals,
            is_percent=m.group("percent") is not None,
            is_currency=m.group("currency") is not None,
            scale=_SCALES.get(scale_word, 1.0),
        )
        if _is_calendar_year(mention):
            continue
        mentions.append(mention)
    return mentions


def _inside_word(text: str, start: int) -> bool:
    """True for digits that belong to an identifier, e.g. "H1B", "v0.1" or "COVID-19"."""
    prev = text[start - 1] if start >= 1 else ""
    prev2 = text[start - 2] if start >= 2 else ""
    return prev.isalnum() or prev in "_." or (prev == "-" and prev2.isalnum())


def _is_calendar_year(m: NumberMention) -> bool:
    return not m.is_currency and not m.is_percent and m.scale == 1.0 and m.decimals == 0 and 1900 <= m.value <= 2100


def _display_candidates(fact: Fact, mention: NumberMention) -> list[float]:
    """Values the fact could legitimately be written as, given how the mention is written."""
    value = abs(fact.value)
    if mention.is_percent:
        if fact.unit == "proportion":
            return [value * 100]
        if fact.unit == "percent":
            return [value]
        return []
    if mention.is_currency and fact.unit not in ("usd", "ratio"):
        return []  # a ratio may be written per dollar, e.g. "returns $4.77 per $1 spent"
    candidates = [value / mention.scale]
    if mention.scale == 1.0 and fact.unit == "proportion":
        candidates.append(value)  # e.g. "a 0.98 probability"
    return candidates


def _rounds_to(candidate: float, mention: NumberMention) -> bool:
    if not math.isfinite(candidate):
        return False
    quantum = Decimal(1).scaleb(-mention.decimals)
    rounded = Decimal(repr(candidate)).quantize(quantum, rounding=ROUND_HALF_UP)
    return rounded == Decimal(repr(mention.value)).quantize(quantum)


def match(mention: NumberMention, facts: FactSheet) -> Fact | None:
    for fact in facts.facts:
        if any(_rounds_to(c, mention) for c in _display_candidates(fact, mention)):
            return fact
    return None


def verify_text(text: str, facts: FactSheet) -> list[Finding]:
    return [Finding(mention=m, matched=match(m, facts)) for m in extract_numbers(text)]


def unverified(text: str, facts: FactSheet) -> list[NumberMention]:
    return [f.mention for f in verify_text(text, facts) if not f.ok]
