"""Collect candidate AI-and-labor research from open feeds.

`lpresearch feeds collect` runs weekly in GitHub Actions. It reads the sources
in ai_impact/feed_sources.json (RSS, Atom and the OpenAlex API, none needing a
key), keeps items that mention both AI and a labor-market topic, drops anything
already featured or already listed in an earlier candidates file, and writes
ai_impact/candidates/<date>.json ranked by a simple keyword score.

Nothing here is published. A monthly curation pass in a LaborPulse project
thread reads the candidates and opens a PR to featured.json (see
docs/curating-featured-research.md).
"""

from __future__ import annotations

import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path

from lpresearch.studies import REPO

AI_IMPACT_DIR = REPO / "ai_impact"
SOURCES_PATH = AI_IMPACT_DIR / "feed_sources.json"
CANDIDATES_DIR = AI_IMPACT_DIR / "candidates"
USER_AGENT = "LaborPulseResearchFeeds/1.0 (+https://github.com/tylerdial1818/labor-pulse-research)"
TIMEOUT_SECONDS = 30

AI_TERMS = re.compile(
    r"\b(artificial intelligence|generative ai|gen ?ai|large language models?|llms?|chatgpt|"
    r"ai exposure|ai adoption|ai)\b",
    re.IGNORECASE,
)
LABOR_TERMS = re.compile(
    r"\b(labou?r markets?|employment|unemployment|jobs?|wages?|earnings|workers?|workforce|hiring|occupations?|"
    r"productivity|displacement|entry[- ]level|early[- ]career|labou?r share)\b",
    re.IGNORECASE,
)

_ATOM = "{http://www.w3.org/2005/Atom}"


@dataclass
class Candidate:
    title: str
    url: str
    source: str
    published: str | None = None
    authors: str = ""
    abstract: str = ""
    score: int = 0
    matched_terms: list[str] = field(default_factory=list)


def _text(node: ET.Element | None) -> str:
    return re.sub(r"\s+", " ", "".join(node.itertext())).strip() if node is not None else ""


def _strip_html(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", value)).strip()


def _rss_date(value: str) -> str | None:
    try:
        return parsedate_to_datetime(value).date().isoformat()
    except (TypeError, ValueError, IndexError):
        return value[:10] if re.match(r"\d{4}-\d{2}-\d{2}", value or "") else None


def parse_rss(xml_text: str, source: str) -> list[Candidate]:
    root = ET.fromstring(xml_text)
    out = []
    for item in root.iter("item"):
        title = _text(item.find("title"))
        link = _text(item.find("link"))
        if not title or not link:
            continue
        creator = item.find("{http://purl.org/dc/elements/1.1/}creator")
        out.append(
            Candidate(
                title=title,
                url=link,
                source=source,
                published=_rss_date(_text(item.find("pubDate"))),
                authors=_text(creator),
                abstract=_strip_html(_text(item.find("description"))),
            )
        )
    return out


def parse_atom(xml_text: str, source: str) -> list[Candidate]:
    root = ET.fromstring(xml_text)
    out = []
    for entry in root.iter(f"{_ATOM}entry"):
        title = _text(entry.find(f"{_ATOM}title"))
        link = next(
            (
                link.get("href", "")
                for link in entry.findall(f"{_ATOM}link")
                if link.get("rel", "alternate") == "alternate"
            ),
            "",
        )
        link = link or _text(entry.find(f"{_ATOM}id"))
        if not title or not link:
            continue
        authors = ", ".join(_text(a.find(f"{_ATOM}name")) for a in entry.findall(f"{_ATOM}author"))
        published = _text(entry.find(f"{_ATOM}published")) or _text(entry.find(f"{_ATOM}updated"))
        out.append(
            Candidate(
                title=title,
                url=link,
                source=source,
                published=published[:10] or None,
                authors=authors,
                abstract=_text(entry.find(f"{_ATOM}summary")),
            )
        )
    return out


def _openalex_abstract(inverted: dict | None) -> str:
    if not inverted:
        return ""
    positions = sorted((pos, word) for word, places in inverted.items() for pos in places)
    return " ".join(word for _, word in positions)


def parse_openalex(json_text: str, source: str) -> list[Candidate]:
    out = []
    for work in json.loads(json_text).get("results", []):
        title = work.get("display_name") or work.get("title") or ""
        location = work.get("primary_location") or {}
        url = location.get("landing_page_url") or work.get("doi") or work.get("id") or ""
        if not title or not url:
            continue
        authors = ", ".join(
            (a.get("author") or {}).get("display_name", "") for a in work.get("authorships", [])[:6]
        ).strip(", ")
        out.append(
            Candidate(
                title=title,
                url=url,
                source=source,
                published=work.get("publication_date"),
                authors=authors,
                abstract=_openalex_abstract(work.get("abstract_inverted_index")),
            )
        )
    return out


PARSERS: dict[str, Callable[[str, str], list[Candidate]]] = {
    "rss": parse_rss,
    "atom": parse_atom,
    "openalex": parse_openalex,
}


def score(candidate: Candidate) -> Candidate:
    """Title matches count double. Both an AI term and a labor term are required (score 0 otherwise)."""
    title_ai, title_labor = AI_TERMS.findall(candidate.title), LABOR_TERMS.findall(candidate.title)
    body_ai, body_labor = AI_TERMS.findall(candidate.abstract), LABOR_TERMS.findall(candidate.abstract)
    has_ai, has_labor = bool(title_ai or body_ai), bool(title_labor or body_labor)
    candidate.matched_terms = sorted({t.lower() for t in [*title_ai, *title_labor, *body_ai, *body_labor]})
    candidate.score = (
        (2 * (len(title_ai) + len(title_labor)) + min(len(body_ai) + len(body_labor), 10))
        if has_ai and has_labor
        else 0
    )
    return candidate


def normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def known_keys(featured: dict, candidates_dir: Path) -> set[str]:
    """Normalized titles and URLs already featured or already listed as candidates."""
    keys: set[str] = set()
    for item in featured.get("items", []):
        keys.update({normalize_title(item.get("title", "")), item.get("url", "")})
    for path in candidates_dir.glob("*.json"):
        for item in json.loads(path.read_text(encoding="utf-8")).get("candidates", []):
            keys.update({normalize_title(item.get("title", "")), item.get("url", "")})
    keys.discard("")
    return keys


def fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return response.read().decode("utf-8", errors="replace")


def collect(
    sources: list[dict],
    *,
    today: date,
    since_days: int,
    exclude: set[str],
    fetch: Callable[[str], str] = fetch_text,
    limit: int = 40,
) -> dict:
    since = (today - timedelta(days=since_days)).isoformat()
    status, pool = [], {}
    for source in sources:
        url = source["url"].replace("{since}", since)
        try:
            items = PARSERS[source["kind"]](fetch(url), source["id"])
            status.append({"id": source["id"], "ok": True, "items": len(items)})
        except Exception as error:  # one dead feed must not stop the run
            status.append({"id": source["id"], "ok": False, "error": f"{type(error).__name__}: {error}"[:200]})
            continue
        for candidate in items:
            if candidate.published and candidate.published < since:
                continue
            key = normalize_title(candidate.title)
            if key in exclude or candidate.url in exclude or key in pool:
                continue
            if score(candidate).score > 0:
                pool[key] = candidate
    ranked = sorted(pool.values(), key=lambda c: (c.score, c.published or ""), reverse=True)[:limit]
    return {
        "schema_version": 1,
        "collected": today.isoformat(),
        "since": since,
        "sources": status,
        "candidates": [asdict(c) for c in ranked],
    }


def run_collect(*, today: date | None = None, since_days: int = 10, out_dir: Path = CANDIDATES_DIR) -> Path:
    from lpresearch.featured import read_featured

    today = today or date.today()
    sources = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))["sources"]
    out_dir.mkdir(parents=True, exist_ok=True)
    result = collect(sources, today=today, since_days=since_days, exclude=known_keys(read_featured(), out_dir))
    path = out_dir / f"{today.isoformat()}.json"
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
