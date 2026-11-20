"""The command line: parses arguments, runs the checks and prints the report."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from .baseline import Baseline
from .config import DEFAULT_BASELINE, REPO_ROOT
from .repo import Repo
from .runner import run_checks


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m scripts.check_plugin",
        description=(
            "Checks that the repository follows the standards in AGENTS.md. "
            "Prints one FAIL or WARN line per finding and exits 1 if there is "
            "at least one FAIL."
        ),
    )
    parser.add_argument(
        "root",
        nargs="?",
        type=Path,
        default=REPO_ROOT,
        help="repository root to check (default: this repository)",
    )
    parser.add_argument(
        "--base",
        help="base ref for the version-bump check, such as origin/main",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=DEFAULT_BASELINE,
        help="baseline file (default: scripts/check-plugin-baseline.txt)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo = Repo(args.root.resolve(), args.base)
    report = run_checks(repo, Baseline.load(args.baseline))
    print(report.render())
    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
