"""Command line entry point.

lpresearch run utah-roi | state-roi     run a pipeline
lpresearch verify --facts F note.md     check numbers in any Markdown file
lpresearch new-note utah-roi --title "..." set up a note folder with its facts snapshot
lpresearch index-notes                  rewrite notes/index.json, which the site reads
lpresearch check-notes                  what CI runs on notes/
lpresearch feeds collect                gather candidate AI research from open feeds (weekly Action)
lpresearch check-featured               what CI runs on ai_impact/featured.json
"""

from __future__ import annotations

import argparse
import json
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
    if args.study.replace("-", "_") == "state_roi":
        from lpresearch.pipelines.state_roi import run

        results = run.run(out_dir=Path(args.out) if args.out else None, draws=args.draws)
        for key, value in results["summary"].items():
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


def _new_note(args: argparse.Namespace) -> int:
    from lpresearch import notes

    study = studies.get(args.study)
    folder = notes.new_note(study.compute_facts(), args.title, args.topic or args.title, Path(args.notes_dir))
    print(folder)
    return 0


def _facts(args: argparse.Namespace) -> int:
    """Print a study's facts as a readable table, for whoever is writing a note."""
    for fact in studies.get(args.study).compute_facts().facts:
        print(f"{fact.id:<60} {fact.value:>18.6g}  {fact.unit:<10} {fact.description}")
    return 0


def _index_notes(args: argparse.Namespace) -> int:
    from lpresearch import notes

    print(notes.write_index(Path(args.notes_dir)))
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


def _feeds_collect(args: argparse.Namespace) -> int:
    from lpresearch import feeds

    path = feeds.run_collect(since_days=args.since_days)
    result = json.loads(path.read_text(encoding="utf-8"))
    for source in result["sources"]:
        state = f"{source['items']} item(s)" if source["ok"] else f"FAILED {source['error']}"
        print(f"{source['id']:<22} {state}")
    print(f"{len(result['candidates'])} new candidate(s) -> {path}")
    return 0


def _check_featured(args: argparse.Namespace) -> int:
    from lpresearch import featured

    problems = featured.check_featured(featured.read_featured(Path(args.path)))
    for p in problems:
        print(f"{p.item}: {p.message}")
    print(f"featured.json: {len(problems)} problem(s)")
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

    new_p = sub.add_parser("new-note", help="set up a note folder with its facts snapshot")
    new_p.add_argument("study")
    new_p.add_argument("--title", required=True)
    new_p.add_argument("--topic", help="what the note should explain (default: the title)")
    new_p.add_argument("--notes-dir", default=str(studies.REPO / "notes"))
    new_p.set_defaults(func=_new_note)

    facts_p = sub.add_parser("facts", help="list the facts a study produces")
    facts_p.add_argument("study")
    facts_p.set_defaults(func=_facts)

    index_p = sub.add_parser("index-notes", help="rewrite notes/index.json, which the LaborPulse site reads")
    index_p.add_argument("--notes-dir", default=str(studies.REPO / "notes"))
    index_p.set_defaults(func=_index_notes)

    check_p = sub.add_parser("check-notes", help="verify every note and its facts snapshot")
    check_p.add_argument("--notes-dir", default=str(studies.REPO / "notes"))
    check_p.set_defaults(func=_check_notes)

    feeds_p = sub.add_parser("feeds", help="research feed tools for the AI Impact page")
    feeds_sub = feeds_p.add_subparsers(dest="feeds_command", required=True)
    collect_p = feeds_sub.add_parser("collect", help="write ai_impact/candidates/<today>.json")
    collect_p.add_argument(
        "--since-days", type=int, default=10, help="ignore items published before this many days ago"
    )
    collect_p.set_defaults(func=_feeds_collect)

    featured_p = sub.add_parser("check-featured", help="validate ai_impact/featured.json")
    featured_p.add_argument("--path", default=str(studies.REPO / "ai_impact" / "featured.json"))
    featured_p.set_defaults(func=_check_featured)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
