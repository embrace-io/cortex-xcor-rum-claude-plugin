"""Tests for the platform-discovery eval's report parser and scorer.

The eval's published numbers come from these two functions, so each verdict and
each rewording of the `**Platform:**` line seen in a run has a case here. The
extraction tests cover the only code that handles downloaded archives. The eval lives in
a directory with a hyphen in its name, which isn't importable, so it's loaded by path.
"""

from __future__ import annotations

import importlib.util
import io
import json
import shutil
import tarfile
import tempfile
import time
import unittest
from pathlib import Path

RUN_PY = (
    Path(__file__).resolve().parent.parent / "evals" / "platform-discovery" / "run.py"
)
_spec = importlib.util.spec_from_file_location("platform_discovery_run", RUN_PY)
run = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run)


def verdict(expect, text):
    return run.score(expect, run.parse_report(text))[0]


class ParseReportTests(unittest.TestCase):
    def test_native_platform_with_evidence(self):
        report = run.parse_report(
            "**Platform:** Android (`gradle/libs.versions.toml:96` applies `io.embrace.gradle`)"
        )
        self.assertEqual(report["platform"], "android")
        self.assertIsNone(report["side"])
        self.assertTrue(report["sdk"])

    def test_cross_platform_side_and_missing_sdk(self):
        report = run.parse_report(
            "**Platform:** React Native (Expo), Apple side, no XCOR RUM SDK found "
            '(`package.json:58` has `expo`, and you said "iPhone app")'
        )
        self.assertEqual(report["platform"], "react-native")
        self.assertEqual(report["side"], "apple")
        self.assertFalse(report["sdk"])

    def test_react_qualifier_is_not_evidence(self):
        report = run.parse_report(
            "**Platform:** Web (React), no XCOR RUM SDK found (`package.json:13` has `react`)"
        )
        self.assertEqual(report["platform"], "web")
        self.assertTrue(report["react"])
        self.assertFalse(report["sdk"])

    def test_no_react_is_not_react(self):
        report = run.parse_report(
            "**Platform:** Web (no React) (`src/main.mjs:2` imports the SDK)"
        )
        self.assertFalse(report["react"])

    def test_reworded_missing_sdk(self):
        report = run.parse_report(
            "**Platform:** Android, no Gradle `io.embrace` entry found (`app/build.gradle.kts`)"
        )
        self.assertFalse(report["sdk"])

    def test_a_missing_sdk_inside_the_evidence_does_not_count(self):
        report = run.parse_report(
            "**Platform:** Android (`app/build.gradle.kts:11` applies the plugin, and no "
            "other Gradle file was found)"
        )
        self.assertTrue(report["sdk"])

    def test_unknowns(self):
        self.assertEqual(
            run.parse_report("**Platform:** not detected")["platform"], "ask"
        )
        self.assertEqual(
            run.parse_report("**Platform:** Unity, side not known")["side"], "ask"
        )
        self.assertEqual(
            run.parse_report("**Platform:** app not known (two apps)")["app"], "ask"
        )

    def test_evidence_does_not_change_the_side(self):
        report = run.parse_report(
            "**Platform:** React Native, Apple side "
            '(you said "iPhone", and nothing about the Android side)'
        )
        self.assertEqual(report["side"], "apple")

    def test_evidence_without_backticks_does_not_change_the_side(self):
        report = run.parse_report(
            "**Platform:** Flutter, Apple side (pubspec.yaml:12 has embrace; the user "
            "said iPhone, nothing about the Android side)"
        )
        self.assertEqual(report["side"], "apple")

    def test_evidence_without_backticks_does_not_hide_the_sdk(self):
        report = run.parse_report(
            "**Platform:** Android (app/build.gradle:11 applies io.embrace.gradle, no "
            "cross-platform manifest found)"
        )
        self.assertTrue(report["sdk"])

    def test_not_detected_counts_only_at_the_start(self):
        report = run.parse_report(
            "**Platform:** Android, React Native not detected (`app/build.gradle:3`)"
        )
        self.assertEqual(report["platform"], "android")

    def test_platform_qualifiers_are_part_of_the_claim(self):
        report = run.parse_report("**Platform:** Apple (tvOS) (`project.pbxproj:11`)")
        self.assertEqual(report["platform"], "apple")
        self.assertTrue(report["sdk"])

    def test_an_empty_line_does_not_read_the_next_paragraph(self):
        report = run.parse_report("**Platform:**\nThis is an Android app.")
        self.assertIsNone(report)

    def test_qualifiers_with_versions_are_part_of_the_claim(self):
        report = run.parse_report(
            "**Platform:** React Native (Expo SDK 52), Android side (`package.json:58`)"
        )
        self.assertEqual(report["platform"], "react-native")
        self.assertEqual(report["side"], "android")
        report = run.parse_report(
            "**Platform:** Web (React 18), no XCOR RUM SDK found (`package.json:13`)"
        )
        self.assertTrue(report["react"])
        self.assertFalse(report["sdk"])

    def test_a_file_reference_in_parentheses_ends_the_claim(self):
        report = run.parse_report(
            "**Platform:** Flutter (pubspec.yaml:3), Android side"
        )
        self.assertEqual(report["platform"], "flutter")

    def test_evidence_after_a_dash_does_not_change_the_side(self):
        report = run.parse_report(
            "**Platform:** Flutter, Apple side - you said iPhone, nothing about the "
            "Android side"
        )
        self.assertEqual(report["side"], "apple")

    def test_hyphenated_and_prefixed_spellings(self):
        self.assertEqual(
            run.parse_report("**Platform:** React-Native, side not known")["platform"],
            "react-native",
        )
        self.assertEqual(
            run.parse_report("**Platform:** platform not detected")["platform"], "ask"
        )

    def test_no_report(self):
        self.assertIsNone(run.parse_report("Which platform is your app on?"))


class ScoreTests(unittest.TestCase):
    def test_right(self):
        self.assertEqual(
            verdict({"platform": "apple"}, "**Platform:** Apple (`Podfile:9`)"), "right"
        )

    def test_wrong_platform(self):
        self.assertEqual(
            verdict({"platform": "apple"}, "**Platform:** Android (`x`)"), "wrong"
        )

    def test_asking_a_definite_case_is_asked(self):
        self.assertEqual(
            verdict({"platform": "apple"}, "**Platform:** not detected"), "asked"
        )
        expect = {"platform": "react-native", "side": "android"}
        self.assertEqual(
            verdict(expect, "**Platform:** React Native, side not known"), "asked"
        )

    def test_guessing_a_side_is_wrong(self):
        expect = {"platform": "flutter", "side": "ask"}
        self.assertEqual(
            verdict(expect, "**Platform:** Flutter, Android side (`x`)"), "wrong"
        )
        self.assertEqual(
            verdict(expect, "**Platform:** Flutter (`pubspec.yaml`)"), "wrong"
        )
        self.assertEqual(
            verdict(expect, "**Platform:** Flutter, side not known"), "right"
        )

    def test_picking_one_app_is_wrong(self):
        expect = {"app": "ask"}
        self.assertEqual(
            verdict(expect, "**Platform:** Apple (`apps/ios/Podfile`)"), "wrong"
        )
        self.assertEqual(
            verdict(expect, "**Platform:** app not known (two apps)"), "right"
        )

    def test_asking_the_platform_in_a_multi_app_repo_is_asked(self):
        self.assertEqual(verdict({"app": "ask"}, "**Platform:** not detected"), "asked")

    def test_missing_report(self):
        self.assertEqual(verdict({"platform": "web"}, "no line here"), "no-report")

    def test_sdk_and_react_mismatches_are_notes_not_verdicts(self):
        expect = {"platform": "web", "react": True, "sdk": True}
        result, notes = run.score(
            expect, run.parse_report("**Platform:** Web, no XCOR RUM SDK found (`x`)")
        )
        self.assertEqual(result, "right")
        self.assertEqual(len(notes), 2)


def tarball(members):
    """Build a gzipped tarball in memory from (name, kind, payload) tuples."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, kind, payload in members:
            info = tarfile.TarInfo(name)
            if kind == "file":
                data = payload.encode()
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
            elif kind == "symlink":
                info.type = tarfile.SYMTYPE
                info.linkname = payload
                tar.addfile(info)
    buf.seek(0)
    return buf


class ExtractTests(unittest.TestCase):
    def extract(self, members, subdir=""):
        dest = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(dest, ignore_errors=True))
        run.extract_subdir(tarball(members), subdir, dest)
        return dest

    def test_extracts_only_the_subdirectory(self):
        dest = self.extract(
            [
                ("repo-abc/README.md", "file", "top"),
                ("repo-abc/examples/app/build.gradle", "file", "gradle"),
            ],
            subdir="examples/app",
        )
        self.assertEqual((dest / "build.gradle").read_text(), "gradle")
        self.assertFalse((dest / "README.md").exists())

    def test_skips_names_that_leave_the_destination(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        dest = root / "a" / "b" / "dest"
        dest.mkdir(parents=True)
        outside = root / "outside.txt"
        run.extract_subdir(
            tarball(
                [
                    ("repo-abc/ok.txt", "file", "ok"),
                    ("repo-abc/../../escape.txt", "file", "bad"),
                    ("repo-abc/../../../../outside.txt", "file", "bad"),
                    (f"repo-abc/{outside}", "file", "bad"),
                ]
            ),
            "",
            dest,
        )
        files = sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())
        self.assertEqual(files, [str(Path("a/b/dest/ok.txt"))])

    def test_skips_links(self):
        dest = self.extract([("repo-abc/link", "symlink", "/etc/passwd")])
        self.assertFalse((dest / "link").exists())
        self.assertFalse((dest / "link").is_symlink())

    def test_strip_tree_removes_agent_files_and_links(self):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        (root / ".claude").mkdir()
        (root / ".claude" / "settings.json").write_text("{}")
        (root / "CLAUDE.md").write_text("x")
        (root / "sub").mkdir()
        (root / "sub" / "agents.md").write_text("x")
        (root / "app.txt").write_text("keep")
        (root / "link").symlink_to(root / "app.txt")
        run.strip_tree(root)
        self.assertEqual(sorted(p.name for p in root.rglob("*")), ["app.txt", "sub"])


class InterruptTests(unittest.TestCase):
    def test_a_failure_cancels_the_sessions_still_queued(self):
        started = []

        def fake_run_case(case, prompt, corpus_dir, model, config_dir, timeout):
            started.append(case["project"])
            if case["project"] == "p0":
                raise KeyboardInterrupt
            time.sleep(0.05)
            return {"result": "", "error": None, "tools": []}

        cases = [
            {"project": f"p{i}", "prompt": "generic", "expect": {"platform": "web"}}
            for i in range(6)
        ]
        corpus = {"prompts": {"generic": "x"}}
        original = run.run_case
        run.run_case = fake_run_case
        self.addCleanup(setattr, run, "run_case", original)
        with self.assertRaises(KeyboardInterrupt):
            run.run_cases(corpus, cases, Path("."), "m", 1, Path("."), 1, [])
        self.assertLess(len(started), len(cases))


class CorpusTests(unittest.TestCase):
    def test_every_case_names_a_known_project_and_prompt(self):
        corpus = json.loads((RUN_PY.parent / "corpus.json").read_text(encoding="utf-8"))
        projects = set(corpus["sources"]) | set(corpus["synthetic"])
        platforms = set(run.PLATFORMS.values())
        for case in corpus["cases"]:
            with self.subTest(case=run.case_id(case)):
                self.assertIn(case["project"], projects)
                self.assertIn(case["prompt"], corpus["prompts"])
                expect = case["expect"]
                if "app" not in expect:
                    self.assertIn(expect["platform"], platforms)
                self.assertIn(expect.get("side"), (None, "android", "apple", "ask"))
        for name, spec in corpus["synthetic"].items():
            for source in spec.get("copy", {}).values():
                self.assertIn(source, corpus["sources"], name)


if __name__ == "__main__":
    unittest.main()
