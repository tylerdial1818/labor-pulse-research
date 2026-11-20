"""Note drafting loop and the CI note check, with a fake Claude client (no network)."""

from contextlib import contextmanager
from datetime import date
from types import SimpleNamespace

import pytest

from lpresearch import notes
from lpresearch.facts import Fact, FactSheet, Source

SRC = Source(kind="computed", ref="studies/x/outputs/model_results.json")


def sheet(cost=7505.288836504436):
    s = FactSheet(study="x", model_version="0.1.0")
    s.add(Fact("cost", cost, "usd", "Program cost per person", SRC))
    s.add(Fact("bcr", 4.773971392337122, "ratio", "Societal benefit-cost ratio", SRC))
    return s


class FakeClient:
    """Returns the queued replies in order and records every request."""

    def __init__(self, *replies, stop_reason="end_turn"):
        self.replies = list(replies)
        self.requests = []
        self.stop_reason = stop_reason
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

    @contextmanager
    def _stream(self, **kwargs):
        self.requests.append({**kwargs, "messages": list(kwargs["messages"])})
        text = self.replies.pop(0)
        message = SimpleNamespace(
            content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)],
            stop_reason=self.stop_reason,
        )
        yield SimpleNamespace(get_final_message=lambda: message)


GOOD = "# Training pays off\n\nIt costs $7,505 per person and returns $4.77 per dollar."
BAD = "# Training pays off\n\nIt costs $7,600 per person and returns $4.77 per dollar."


def test_clean_draft_needs_no_revision():
    client = FakeClient(GOOD)
    result = notes.draft_note(client, sheet(), "Utah ROI")
    assert result.ok and result.revisions == 0
    request = client.requests[0]
    assert request["model"] == "claude-opus-5-5"
    assert request["thinking"] == {"type": "adaptive"}
    assert request["fallbacks"] == "default"
    assert "cost" in request["messages"][0]["content"]


def test_bad_number_triggers_revision_with_append_only_history():
    client = FakeClient(BAD, GOOD)
    result = notes.draft_note(client, sheet(), "Utah ROI")
    assert result.ok and result.revisions == 1
    first, second = client.requests
    assert second["messages"][: len(first["messages"])] == first["messages"]
    assert second["messages"][1]["role"] == "assistant"
    assert second["messages"][1]["content"][0].type == "thinking"
    assert "'$7,600'" in second["messages"][2]["content"]


def test_gives_up_after_max_revisions():
    client = FakeClient(BAD, BAD, BAD)
    result = notes.draft_note(client, sheet(), "Utah ROI", max_revisions=2)
    assert not result.ok
    assert [m.text for m in result.unverified] == ["$7,600"]
    assert len(client.requests) == 3


def test_refusal_raises():
    with pytest.raises(RuntimeError, match="declined"):
        notes.draft_note(FakeClient(GOOD, stop_reason="refusal"), sheet(), "Utah ROI")


def test_write_note_and_check_passes(tmp_path):
    result = notes.draft_note(FakeClient(GOOD), sheet(), "Utah ROI")
    folder = notes.write_note(result, sheet(), "Utah ROI", tmp_path, today=date(2026, 11, 20))
    assert folder.name == "2026-11-20-training-pays-off"
    text = (folder / "note.md").read_text()
    assert 'status: "draft"' in text and 'byline: "LaborPulse Research Desk"' in text
    assert notes.check_notes(tmp_path, {"x": sheet()}) == []


def test_failed_draft_is_marked(tmp_path):
    result = notes.draft_note(FakeClient(BAD), sheet(), "Utah ROI", max_revisions=0)
    folder = notes.write_note(result, sheet(), "Utah ROI", tmp_path, today=date(2026, 11, 20))
    assert 'status: "needs-numbers-fixed"' in (folder / "note.md").read_text()
    problems = notes.check_notes(tmp_path, {"x": sheet()})
    assert [p.message for p in problems] == ["'$7,600' is not backed by any fact"]


def test_check_flags_snapshot_that_drifted_from_pipeline(tmp_path):
    result = notes.draft_note(FakeClient(GOOD), sheet(), "Utah ROI")
    notes.write_note(result, sheet(), "Utah ROI", tmp_path, today=date(2026, 11, 20))
    problems = notes.check_notes(tmp_path, {"x": sheet(cost=7600.0)})
    assert len(problems) == 1 and "fact cost" in problems[0].message


def test_front_matter_numbers_are_not_checked():
    assert notes.note_body('---\nrevisions: 3\ndate: "2026-11-20"\n---\nBody') == "Body"


def test_utah_facts_back_a_realistic_note(tmp_path):
    from lpresearch import studies

    facts = studies.get("utah-roi").compute_facts()
    text = (
        "# What sector training could return in Utah\n\n"
        "The program costs about $7,505 per person offered. Over a 10-year horizon, society gains "
        "$4.77 in compensation for each dollar spent, and net benefits were positive in 98% of 10,000 "
        "simulated draws. Utah's own budget recovers less: its benefit-cost ratio is 0.17. Society breaks "
        "even if the program keeps 21% of the earnings effect seen in the WorkAdvance trials, which ran "
        "from 2011."
    )
    result = notes.DraftResult(markdown=text, unverified=[], revisions=0)
    notes.write_note(result, facts, "Utah ROI", tmp_path, today=date(2026, 11, 20))
    assert notes.check_notes(tmp_path, {"utah_roi": facts}) == []
