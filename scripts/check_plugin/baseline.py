"""The baseline: known failures that predate a check.

The file has one `<check-id> <path>` per line and `#` comments. A baselined
failure is reported as a warning, so adding a check doesn't block the build on
old content. A line that no longer matches a finding is reported too, because
a stale line would silently hide the same problem if it came back.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from .report import Finding, Severity


@dataclass(frozen=True)
class Baseline:
    entries: frozenset[tuple[str, str]] = frozenset()
    name: str = "the baseline file"

    @classmethod
    def load(cls, path: Path) -> "Baseline":
        """Reads a baseline file. A missing file is an empty baseline."""
        if not path.is_file():
            return cls(name=path.name)
        entries = set()
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.split("#", 1)[0].strip()
            if line:
                check, _, rel = line.partition(" ")
                entries.add((check, rel.strip()))
        return cls(frozenset(entries), path.name)

    def apply(self, findings: list[Finding]) -> list[Finding]:
        """Downgrades baselined failures to warnings and flags unused lines."""
        used: set[tuple[str, str]] = set()
        result = []
        for finding in findings:
            key = (finding.check, finding.path)
            if finding.severity is Severity.FAIL and key in self.entries:
                used.add(key)
                finding = replace(finding, severity=Severity.WARN, baselined=True)
            result.append(finding)
        for check, path in sorted(self.entries - used):
            result.append(
                Finding(
                    check,
                    path,
                    "baseline line no longer matches a finding; "
                    f"delete it from {self.name}",
                    Severity.WARN,
                )
            )
        return result
