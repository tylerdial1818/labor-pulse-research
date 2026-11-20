"""Command line entry point: `lpresearch run utah-roi` and `lpresearch verify`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from lpresearch.facts import FactSheet
from lpresearch.verify_numbers import verify_text


def _run(args: argparse.Namespace) -> int:
    if args.study == "utah-roi":
        from lpresearch.pipelines.utah_roi import run

        results = run.run(out_dir=Path(args.out) if args.out else None, draws=args.draws)
        for key, value in results["headline"].items():
            print(f"{key}: {value}")
        return 0
    raise SystemExit(f"unknown study: {args.study}")


def _verify(args: argparse.Namespace) -> int:
    facts = FactSheet.read(args.facts)
    failures = 0
    for path in args.notes:
        text = Path(path).read_text(encoding="utf-8")
        for finding in verify_text(text, facts):
            line = text.count("\n", 0, finding.mention.start) + 1
            if finding.ok:
                if args.verbose:
                    print(f"{path}:{line}: ok   {finding.mention.text!r} = {finding.matched.id}")
            else:
                failures += 1
                print(f"{path}:{line}: FAIL {finding.mention.text!r} is not backed by any fact")
    print(f"{failures} unverified number(s)")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lpresearch", description="LaborPulse research pipelines")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="run an analysis pipeline")
    run_p.add_argument("study", choices=["utah-roi"])
    run_p.add_argument("--out", help="output folder (default: studies/<study>/outputs)")
    run_p.add_argument("--draws", type=int, help="override the number of Monte Carlo draws")
    run_p.set_defaults(func=_run)

    ver_p = sub.add_parser("verify", help="check that every number in a note is backed by facts.json")
    ver_p.add_argument("--facts", required=True)
    ver_p.add_argument("notes", nargs="+")
    ver_p.add_argument("-v", "--verbose", action="store_true")
    ver_p.set_defaults(func=_verify)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
