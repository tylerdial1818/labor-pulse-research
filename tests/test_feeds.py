import json
from datetime import date

from lpresearch import feeds
from lpresearch.featured import check_featured, read_featured, unbacked_numbers

RSS = """<?xml version="1.0"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/"><channel>
<item><title>Generative AI and the Hiring of Young Workers</title><link>https://example.org/a</link>
<pubDate>Mon, 16 Nov 2026 10:00:00 GMT</pubDate><dc:creator>A. Author</dc:creator>
<description>&lt;p&gt;We study employment in exposed occupations.&lt;/p&gt;</description></item>
<item><title>Monetary policy and housing</title><link>https://example.org/b</link>
<pubDate>Mon, 16 Nov 2026 10:00:00 GMT</pubDate><description>Rates.</description></item>
</channel></rss>"""

ATOM = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<entry><id>http://arxiv.org/abs/2611.00001v1</id><title>Large Language Models and Wages</title>
<published>2026-11-15T00:00:00Z</published><summary>Effects of LLMs on wages of workers.</summary>
<author><name>B. Writer</name></author><author><name>C. Writer</name></author>
<link href="http://arxiv.org/abs/2611.00001v1" rel="alternate"/></entry>
<entry><id>http://arxiv.org/abs/2611.00002v1</id><title>Old AI labor paper</title>
<published>2026-01-01T00:00:00Z</published><summary>AI and jobs.</summary></entry>
</feed>"""

OPENALEX = json.dumps(
    {
        "results": [
            {
                "display_name": "AI Exposure and Unemployment",
                "publication_date": "2026-11-10",
                "primary_location": {"landing_page_url": "https://example.org/oa"},
                "authorships": [{"author": {"display_name": "D. Scholar"}}],
                "abstract_inverted_index": {"AI": [0], "raises": [1], "unemployment": [2]},
            }
        ]
    }
)


def test_parsers_read_title_link_date_and_authors():
    rss = feeds.parse_rss(RSS, "nber")
    assert rss[0].title == "Generative AI and the Hiring of Young Workers"
    assert rss[0].published == "2026-11-16"
    assert rss[0].authors == "A. Author"
    assert "<p>" not in rss[0].abstract

    atom = feeds.parse_atom(ATOM, "arxiv")
    assert atom[0].url == "http://arxiv.org/abs/2611.00001v1"
    assert atom[0].authors == "B. Writer, C. Writer"

    oa = feeds.parse_openalex(OPENALEX, "openalex")
    assert oa[0].abstract == "AI raises unemployment"
    assert oa[0].url == "https://example.org/oa"


def test_score_requires_both_an_ai_term_and_a_labor_term():
    assert feeds.score(feeds.Candidate(title="Monetary policy and jobs", url="u", source="s")).score == 0
    assert feeds.score(feeds.Candidate(title="Generative AI and jobs", url="u", source="s")).score > 0


def test_collect_filters_dedupes_and_reports_failing_sources():
    pages = {"rss": RSS, "atom": ATOM, "oa": OPENALEX}

    def fetch(url):
        if url == "dead":
            raise OSError("boom")
        return pages[url]

    sources = [
        {"id": "nber", "kind": "rss", "url": "rss"},
        {"id": "arxiv", "kind": "atom", "url": "atom"},
        {"id": "openalex", "kind": "openalex", "url": "oa"},
        {"id": "dead", "kind": "rss", "url": "dead"},
    ]
    exclude = {feeds.normalize_title("AI Exposure and Unemployment")}
    result = feeds.collect(sources, today=date(2026, 11, 21), since_days=10, exclude=exclude, fetch=fetch)

    titles = [c["title"] for c in result["candidates"]]
    assert "Generative AI and the Hiring of Young Workers" in titles
    assert "Large Language Models and Wages" in titles
    assert "Monetary policy and housing" not in titles  # no AI term
    assert "Old AI labor paper" not in titles  # older than the window
    assert "AI Exposure and Unemployment" not in titles  # already known
    assert {s["id"]: s["ok"] for s in result["sources"]} == {
        "nber": True,
        "arxiv": True,
        "openalex": True,
        "dead": False,
    }


def test_known_keys_include_featured_and_earlier_candidates(tmp_path):
    (tmp_path / "2026-11-14.json").write_text(
        json.dumps({"candidates": [{"title": "Earlier One", "url": "https://x"}]})
    )
    keys = feeds.known_keys({"items": [{"title": "Featured Paper", "url": "https://y"}]}, tmp_path)
    assert {"earlier one", "https://x", "featured paper", "https://y"} <= keys


def test_committed_featured_file_passes():
    assert check_featured(read_featured()) == []


def _item(**overrides):
    item = {
        "id": "x",
        "title": "T",
        "authors": "A",
        "publisher": "P",
        "published": "2026-11-01",
        "url": "https://example.org",
        "kind": "study",
        "data_access": "public",
        "summary": "No numbers here.",
        "evidence": [],
        "featured_on": "2026-11-21",
        "featured_until": "2027-02-19",
        "tags": [],
    }
    item.update(overrides)
    return {"schema_version": 1, "updated": "2026-11-21", "items": [item]}


def test_numbers_in_summaries_need_an_evidence_quote():
    assert unbacked_numbers("about 19% of workers", ["is about 19% below"]) == []
    assert unbacked_numbers("ages 22 to 25", ["ages 22-25"]) == []
    assert unbacked_numbers("rose 3%", ["rose 30%"]) == ["3%"]
    problems = check_featured(_item(summary="Hiring fell 12% in 2026."))
    assert [p.message for p in problems] == ["number '12%' in summary is not backed by an evidence quote"]


def test_check_featured_catches_bad_windows_and_fields():
    messages = [p.message for p in check_featured(_item(featured_until="2026-01-01", kind="blog", url="http://x"))]
    assert "featured_until is before featured_on" in messages
    assert any(m.startswith("kind must be") for m in messages)
    assert "url must start with https://" in messages
