"""Note scaffolding and the CI note check."""

from datetime import date

from lpresearch import notes
from lpresearch.facts import Fact, FactSheet, Source

SRC = Source(kind="computed", ref="studies/x/outputs/model_results.json")
TODAY = date(2026, 11, 20)


def sheet(cost=7505.288836504436):
    s = FactSheet(study="x", model_version="0.1.0")
    s.add(Fact("cost", cost, "usd", "Program cost per person", SRC))
    s.add(Fact("bcr", 4.773971392337122, "ratio", "Societal benefit-cost ratio", SRC))
    return s


def write_body(folder, body):
    path = folder / "note.md"
    text = path.read_text()
    head = text[: text.index("# ")]
    path.write_text(head + body)
    notes.write_index(folder.parent.parent)


def test_new_note_creates_front_matter_and_snapshot(tmp_path):
    folder = notes.new_note(sheet(), "Training Pays Off", "Utah ROI", tmp_path, today=TODAY)
    assert folder == tmp_path / "x" / "2026-11-20-training-pays-off"
    text = (folder / "note.md").read_text()
    assert 'byline: "LaborPulse Research Desk"' in text and 'status: "draft"' in text
    assert FactSheet.read(folder / "facts.json") == sheet()


def test_placeholder_fails_the_check(tmp_path):
    notes.new_note(sheet(), "Training pays off", "Utah ROI", tmp_path, today=TODAY)
    notes.write_index(tmp_path)
    assert [p.message for p in notes.check_notes(tmp_path, {"x": sheet()})] == ["still has the new-note placeholder"]


def test_written_note_passes(tmp_path):
    folder = notes.new_note(sheet(), "Training pays off", "Utah ROI", tmp_path, today=TODAY)
    write_body(folder, "# Training pays off\n\nIt costs $7,505 per person and returns $4.77 per dollar.\n")
    assert notes.check_notes(tmp_path, {"x": sheet()}) == []


def test_unbacked_number_fails(tmp_path):
    folder = notes.new_note(sheet(), "Training pays off", "Utah ROI", tmp_path, today=TODAY)
    write_body(folder, "# Training pays off\n\nIt costs $7,600 per person.\n")
    assert [p.message for p in notes.check_notes(tmp_path, {"x": sheet()})] == ["'$7,600' is not backed by any fact"]


def test_snapshot_that_drifted_from_pipeline_fails(tmp_path):
    folder = notes.new_note(sheet(), "Training pays off", "Utah ROI", tmp_path, today=TODAY)
    write_body(folder, "# Training pays off\n\nIt returns $4.77 per dollar.\n")
    problems = notes.check_notes(tmp_path, {"x": sheet(cost=7600.0)})
    assert len(problems) == 1 and "fact cost" in problems[0].message


def test_front_matter_numbers_are_not_checked():
    assert notes.note_body('---\nrevisions: 3\ndate: "2026-11-20"\n---\nBody') == "Body"


def test_utah_facts_back_a_realistic_note(tmp_path):
    from lpresearch import studies

    facts = studies.get("utah-roi").compute_facts()
    folder = notes.new_note(facts, "What sector training could return in Utah", "Utah ROI", tmp_path, today=TODAY)
    write_body(
        folder,
        "# What sector training could return in Utah\n\n"
        "The program costs about $7,505 per person offered. Over a 10-year horizon, society gains "
        "$4.77 in compensation for each dollar spent, and net benefits were positive in 98% of 10,000 "
        "simulated draws. Utah's own budget recovers less: its benefit-cost ratio is 0.17. Society breaks "
        "even if the program keeps 21% of the earnings effect seen in the WorkAdvance trials, which ran "
        "from 2011.\n",
    )
    assert notes.check_notes(tmp_path, {"utah_roi": facts}) == []


def test_index_lists_notes_with_summary(tmp_path):
    folder = notes.new_note(sheet(), "Training pays off", "Utah ROI", tmp_path, today=TODAY)
    write_body(folder, "# Training pays off\n\nIt costs $7,505\nper person.\n\n## More\n\nDetail.\n")
    index = notes.build_index(tmp_path)
    assert index["notes"] == [
        {
            "study": "x",
            "slug": "2026-11-20-training-pays-off",
            "path": "x/2026-11-20-training-pays-off/note.md",
            "title": "Training pays off",
            "date": "2026-11-20",
            "byline": "LaborPulse Research Desk",
            "model_version": "0.1.0",
            "status": "draft",
            "summary": "It costs $7,505 per person.",
        }
    ]


def test_stale_index_fails(tmp_path):
    folder = notes.new_note(sheet(), "Training pays off", "Utah ROI", tmp_path, today=TODAY)
    write_body(folder, "# Training pays off\n\nIt returns $4.77 per dollar.\n")
    (folder / "note.md").write_text((folder / "note.md").read_text().replace('"draft"', '"published"'))
    problems = notes.check_notes(tmp_path, {"x": sheet()})
    assert [p.message for p in problems] == ["is out of date; run `lpresearch index-notes`"]


def test_unknown_status_fails(tmp_path):
    folder = notes.new_note(sheet(), "Training pays off", "Utah ROI", tmp_path, today=TODAY)
    write_body(folder, "# Training pays off\n\nIt returns $4.77 per dollar.\n")
    path = folder / "note.md"
    path.write_text(path.read_text().replace('"draft"', '"final"'))
    notes.write_index(tmp_path)
    assert [p.message for p in notes.check_notes(tmp_path, {"x": sheet()})] == [
        "status must be one of draft, published, not 'final'"
    ]
