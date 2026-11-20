import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from scripts.check_plugin.baseline import Baseline
from scripts.check_plugin.cli import main
from scripts.check_plugin.report import Finding, Report, Severity

from .fixtures import SKILL, build_good_tree

FAIL = Finding("skills", "a/SKILL.md", "broken")


class BaselineTests(unittest.TestCase):
    def load(self, text: str) -> Baseline:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "baseline.txt"
            path.write_text(text, encoding="utf-8")
            return Baseline.load(path)

    def test_parses_entries_and_ignores_comments_and_blank_lines(self) -> None:
        baseline = self.load("# header\n\nskills a/SKILL.md  # why\n")
        self.assertEqual(baseline.entries, {("skills", "a/SKILL.md")})

    def test_missing_file_is_an_empty_baseline(self) -> None:
        self.assertEqual(
            Baseline.load(Path("/nonexistent/baseline.txt")).entries, frozenset()
        )

    def test_baselined_failure_becomes_a_warning(self) -> None:
        (result,) = self.load("skills a/SKILL.md\n").apply([FAIL])
        self.assertEqual((result.severity, result.baselined), (Severity.WARN, True))
        self.assertTrue(str(result).endswith("broken (baselined)"))

    def test_unmatched_failure_stays_a_failure(self) -> None:
        (result,) = self.load("skills other/SKILL.md\n").apply([FAIL])[:1]
        self.assertEqual(result.severity, Severity.FAIL)

    def test_warning_is_not_baselined(self) -> None:
        warn = Finding("version", "plugin.json", "w", Severity.WARN)
        (result,) = self.load("version plugin.json\n").apply([warn])[:1]
        self.assertFalse(result.baselined)

    def test_unused_line_is_reported_as_stale(self) -> None:
        baseline = self.load("skills gone/SKILL.md\n")
        (stale,) = baseline.apply([])
        self.assertEqual(
            (stale.check, stale.path, stale.severity),
            ("skills", "gone/SKILL.md", Severity.WARN),
        )
        self.assertIn("delete it from baseline.txt", stale.message)


class ReportTests(unittest.TestCase):
    def test_warnings_print_before_failures_and_failures_set_the_exit_code(
        self,
    ) -> None:
        warn = Finding("version", "p", "w", Severity.WARN)
        report = Report([FAIL, warn])
        self.assertEqual(
            report.render().splitlines(),
            [
                "WARN [version] p: w",
                "FAIL [skills] a/SKILL.md: broken",
                "1 failure(s), 1 warning(s)",
            ],
        )
        self.assertEqual(report.exit_code, 1)

    def test_warnings_alone_exit_zero(self) -> None:
        self.assertEqual(Report([Finding("v", "p", "w", Severity.WARN)]).exit_code, 0)


class CliTests(unittest.TestCase):
    def run_cli(self, *argv: str) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(list(argv))
        return code, out.getvalue()

    def test_good_tree_exits_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            build_good_tree(Path(tmp))
            code, out = self.run_cli(tmp, "--baseline", str(Path(tmp) / "none.txt"))
        self.assertEqual((code, out), (0, "0 failure(s), 0 warning(s)\n"))

    def test_failure_exits_one_and_prints_the_finding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tree = build_good_tree(Path(tmp))
            tree.edit(SKILL, lambda s: s.replace("name: demo", "name: other"))
            code, out = self.run_cli(tmp, "--baseline", str(Path(tmp) / "none.txt"))
        self.assertEqual(code, 1)
        self.assertIn(
            "FAIL [skills] plugins/cortex-xcor-rum/skills/demo/SKILL.md:", out
        )
        self.assertIn("1 failure(s), 0 warning(s)", out)

    def test_baseline_file_downgrades_the_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tree = build_good_tree(Path(tmp))
            tree.edit(SKILL, lambda s: s.replace("name: demo", "name: other"))
            baseline = Path(tmp) / "baseline.txt"
            baseline.write_text(f"skills {SKILL}\n", encoding="utf-8")
            code, out = self.run_cli(tmp, "--baseline", str(baseline))
        self.assertEqual(code, 0)
        self.assertIn("(baselined)", out)


if __name__ == "__main__":
    unittest.main()
