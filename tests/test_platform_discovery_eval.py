"""Tests for the platform-discovery eval's report parser and scorer.

The eval's published numbers come from these two functions, so each verdict and
each way a model rewords the `**Platform:**` line has a case here. The eval lives in
a directory with a hyphen in its name, which isn't importable, so it's loaded by path.
"""

from __future__ import annotations

import importlib.util
import json
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

    def test_missing_report(self):
        self.assertEqual(verdict({"platform": "web"}, "no line here"), "no-report")

    def test_sdk_and_react_mismatches_are_notes_not_verdicts(self):
        expect = {"platform": "web", "react": True, "sdk": True}
        result, notes = run.score(
            expect, run.parse_report("**Platform:** Web, no XCOR RUM SDK found (`x`)")
        )
        self.assertEqual(result, "right")
        self.assertEqual(len(notes), 2)


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
