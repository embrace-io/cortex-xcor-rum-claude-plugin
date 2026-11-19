"""Findings and the report that collects them."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Severity(Enum):
    FAIL = "FAIL"
    WARN = "WARN"


@dataclass(frozen=True)
class Issue:
    """What a check yields. The runner adds the check id to make a Finding."""

    path: str
    message: str
    severity: Severity = Severity.FAIL


@dataclass(frozen=True)
class Finding:
    check: str
    path: str
    message: str
    severity: Severity = Severity.FAIL
    # A baselined finding is a known failure that was downgraded to a warning.
    baselined: bool = False

    def __str__(self) -> str:
        suffix = " (baselined)" if self.baselined else ""
        return (
            f"{self.severity.value} [{self.check}] {self.path}: {self.message}{suffix}"
        )


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)

    @property
    def fails(self) -> list[Finding]:
        return [f for f in self.findings if f.severity is Severity.FAIL]

    @property
    def warns(self) -> list[Finding]:
        return [f for f in self.findings if f.severity is Severity.WARN]

    @property
    def exit_code(self) -> int:
        return 1 if self.fails else 0

    def render(self) -> str:
        """Returns warnings first so the failures that stop the build end the output."""
        lines = [str(f) for f in self.warns + self.fails]
        lines.append(f"{len(self.fails)} failure(s), {len(self.warns)} warning(s)")
        return "\n".join(lines)
