"""Runs the registered checks and builds the report."""

from __future__ import annotations

from typing import Sequence

from .baseline import Baseline
from .checks import CHECKS, Check
from .report import Finding, Report
from .repo import Repo


def run_checks(
    repo: Repo,
    baseline: Baseline | None = None,
    checks: Sequence[Check] = CHECKS,
) -> Report:
    findings = [
        Finding(check.id, issue.path, issue.message, issue.severity)
        for check in checks
        for issue in check.run(repo)
    ]
    return Report((baseline or Baseline()).apply(findings))
