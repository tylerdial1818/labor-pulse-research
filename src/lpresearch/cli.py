"""Command line entry point.

lpresearch run utah-roi                 run a pipeline
lpresearch verify --facts F note.md     check numbers in any Markdown file
lpresearch draft utah-roi --topic "..." draft a note with Claude (needs ANTHROPIC_API_KEY)
lpresearch check-notes                  what CI runs on notes/
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from lpresearch import studies
from lpresearch.facts import FactSheet
from lpresearch.verify_numbers import verify_text


def _run(args: argparse.Namespace) -> int:
    if args.study.replace("-", "_") == "utah_roi":
        from lpresearch.pipelines.utah_roi import run

        results = run.run(out_dir=Path(args.out) if args.out else None, draws=args.draws)
        for key, value in results["headline"].items():
            print(f"{key}: {value}")
        return 0
    studies.get(args.study)
    return 1


def _verify(args: argparse.Namespace) -> int:
    from lpresearch.notes import note_body

    facts = FactSheet.read(args.facts)
    failures = 0
    for path in args.notes:
        text = Path(path).read_text(encoding="utf-8")
        body = note_body(text)
        offset = len(text) - len(body)
        for finding in verify_text(body, facts):
            line = text.count("\n", 0, offset + finding.mention.start) + 1
            if finding.ok:
                if args.verbose:
                    print(f"{path}:{line}: ok   {finding.mention.text!r} = {finding.matched.id}")
            else:
                failures += 1
                print(f"{path}:{line}: FAIL {finding.mention.text!r} is not backed by any fact")
    print(f"{failures} unverified number(s)")
    return 1 if failures else 0


def _draft(args: argparse.Namespace) -> int:
    import anthropic

    from lpresearch import notes

    study = studies.get(args.study)
    facts = study.compute_facts()
    result = notes.draft_note(
        anthropic.Anthropic(), facts, args.topic, study.context(), max_revisions=args.max_revisions
    )
    folder = notes.write_note(result, facts, args.topic, Path(args.notes_dir))
    print(folder)
    if not result.ok:
        print("Numbers still not backed by facts: " + ", ".join(m.text for m in result.unverified), file=sys.stderr)
        return 2
    return 0


def _check_notes(args: argparse.Namespace) -> int:
    from lpresearch import notes

    notes_dir = Path(args.notes_dir)
    names = sorted({p.parent.parent.name for p in notes_dir.glob("*/*/note.md")})
    current = {name: studies.get(name).compute_facts() for name in names}
    problems = notes.check_notes(notes_dir, current)
    for p in problems:
        print(f"{p.note}: {p.message}")
    count = len(list(notes_dir.glob("*/*/note.md")))
    print(f"{count} note(s) checked, {len(problems)} problem(s)")
    return 1 if problems else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lpresearch", description="LaborPulse research pipelines")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="run an analysis pipeline")
    run_p.add_argument("study", help="e.g. utah-roi")
    run_p.add_argument("--out", help="output folder (default: studies/<study>/outputs)")
    run_p.add_argument("--draws", type=int, help="override the number of Monte Carlo draws")
    run_p.set_defaults(func=_run)

    ver_p = sub.add_parser("verify", help="check that every number in a note is backed by facts.json")
    ver_p.add_argument("--facts", required=True)
    ver_p.add_argument("notes", nargs="+")
    ver_p.add_argument("-v", "--verbose", action="store_true")
    ver_p.set_defaults(func=_verify)

    draft_p = sub.add_parser("draft", help="draft a research note with Claude")
    draft_p.add_argument("study")
    draft_p.add_argument("--topic", required=True, help="what the note should explain")
    draft_p.add_argument("--max-revisions", type=int, default=2)
    draft_p.add_argument("--notes-dir", default=str(studies.REPO / "notes"))
    draft_p.set_defaults(func=_draft)

    check_p = sub.add_parser("check-notes", help="verify every note and its facts snapshot")
    check_p.add_argument("--notes-dir", default=str(studies.REPO / "notes"))
    check_p.set_defaults(func=_check_notes)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
