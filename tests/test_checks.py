"""One test per way a check can fail, plus the cases that must keep passing.

MUTATIONS is the table of failures: each entry breaks the good tree in one way
and names the only check that should then fail. Asserting on the exact set of
failing ids catches a check that starts reporting another check's problem.
"""

from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from scripts.check_plugin.checks import CHECKS
from scripts.check_plugin.config import PLUGIN, PLUGIN_REL
from scripts.check_plugin.repo import Repo
from scripts.check_plugin.runner import run_checks

from .fixtures import (
    MANIFEST,
    MARKETPLACE,
    MCP,
    NOTES,
    PLUGIN_README,
    SKILL,
    Tree,
    build_good_tree,
    manifest,
    marketplace_entry,
    rename_skill,
)


@dataclass(frozen=True)
class Mutation:
    name: str
    check: str
    mutate: Callable[[Tree], None]
    # The version check diffs two commits, so its cases need a git history.
    base: str | None = None
    tag: bool = False
    # Other checks that fail on the same edit because they read the same text.
    also: frozenset[str] = frozenset()


def _skill(old: str, new: str) -> Callable[[Tree], None]:
    return lambda tree: tree.edit(SKILL, lambda text: text.replace(old, new))


def _skill_append(extra: str) -> Callable[[Tree], None]:
    return lambda tree: tree.edit(SKILL, lambda text: text + extra)


def _rename_skill(name: str) -> Callable[[Tree], None]:
    return lambda tree: rename_skill(tree, name)


def _mcp(servers: dict) -> Callable[[Tree], None]:
    return lambda tree: tree.write_json(MCP, {"mcpServers": servers})


def _write(rel: str, content: str | bytes) -> Callable[[Tree], None]:
    return lambda tree: tree.write(rel, content)


def _second_plugin(tree: Tree) -> None:
    tree.write_json(
        MARKETPLACE,
        {
            "name": PLUGIN,
            "plugins": [
                marketplace_entry(PLUGIN, f"./{PLUGIN_REL}"),
                marketplace_entry("other", "./plugins/other"),
            ],
        },
    )


def _http_server(**extra: object) -> dict:
    return {"s": {"type": "http", "url": "https://x.example.com", **extra}}


# Built at run time so this file doesn't hold a string that looks like a key.
FAKE_API_KEY = "sk-" + "a1B2c3D4e5F6g7H8i9J0k1L2"

MUTATIONS = (
    Mutation("layout_second_plugin", "layout", _second_plugin),
    Mutation(
        "layout_name_mismatch",
        "layout",
        lambda t: t.edit(
            MANIFEST, lambda s: s.replace(f'"name": "{PLUGIN}"', '"name": "renamed"')
        ),
    ),
    Mutation(
        "layout_bad_version",
        "layout",
        lambda t: t.write_json(MANIFEST, manifest("one")),
        also=frozenset({"docs"}),
    ),
    Mutation("skills_name_mismatch", "skills", _skill("name: demo", "name: other")),
    Mutation(
        "skills_empty_description",
        "skills",
        _skill("description: Use when the user asks about the demo.", "description:"),
    ),
    Mutation("skills_long_description", "skills", _skill("the demo.", "x" * 1600)),
    Mutation(
        "skills_unquoted_colon",
        "skills",
        _skill("about the demo.", "about this: the demo."),
    ),
    Mutation("skill_names_ios_suffix", "skill-names", _rename_skill("doctor-ios")),
    Mutation("skill_names_ios_prefix", "skill-names", _rename_skill("ios-doctor")),
    Mutation("skill_names_tvos", "skill-names", _rename_skill("tvos-doctor")),
    Mutation(
        "skill_names_platform_suffix",
        "skill-names",
        _rename_skill("doctor-android"),
    ),
    Mutation("skill_names_uppercase", "skill-names", _rename_skill("iOS-doctor")),
    Mutation("skill_names_underscore", "skill-names", _rename_skill("doctor_ios")),
    Mutation(
        "skill_names_two_platforms",
        "skill-names",
        _rename_skill("android-apple-bridge"),
    ),
    Mutation(
        "skill_names_framework_suffix",
        "skill-names",
        _rename_skill("doctor-flutter"),
    ),
    Mutation("skill_names_rn_alias", "skill-names", _rename_skill("rn-doctor")),
    Mutation("skill_names_web_and_native", "skill-names", _rename_skill("web-android")),
    Mutation(
        "skill_names_native_side_not_after_prefix",
        "skill-names",
        _rename_skill("react-native-linking-android"),
    ),
    Mutation(
        "skill_names_framework_with_two_native_sides",
        "skill-names",
        _rename_skill("unity-apple-android-build"),
    ),
    Mutation("skill_refs_missing_file", "skill-refs", _skill("notes.md", "gone.md")),
    Mutation(
        "secrets_rule_missing",
        "secrets-rule",
        _skill("Never reproduce secrets", "Be careful"),
    ),
    Mutation(
        "mcp_http_url",
        "mcp",
        _mcp({"s": {"type": "http", "url": "http://mcp.example.com"}}),
    ),
    Mutation(
        "mcp_env_header",
        "mcp",
        _mcp(_http_server(headers={"Authorization": "Bearer ${SOME_TOKEN}"})),
        also=frozenset({"credentials"}),
    ),
    Mutation(
        "mcp_literal_header",
        "mcp",
        _mcp(_http_server(headers={"X-Api-Key": "abc"})),
    ),
    Mutation(
        "mcp_unpinned_npx",
        "mcp",
        _mcp({"s": {"command": "npx", "args": ["-y", "some-server@latest"]}}),
    ),
    Mutation(
        "credentials_env_bearer",
        "credentials",
        _write("notes.txt", "curl -H 'Authorization: Bearer ${MY_TOKEN}' x\n"),
    ),
    Mutation(
        "credentials_literal_key",
        "credentials",
        _write("notes.txt", f"key {FAKE_API_KEY}\n"),
    ),
    Mutation(
        "naming_formerly_twice",
        "naming",
        _skill_append("\nCortex (formerly Embrace). Again, formerly Embrace.\n"),
    ),
    Mutation(
        "denylist_internal_channel",
        "denylist",
        _skill_append("\nPost it in #tech-support.\n"),
    ),
    Mutation(
        "denylist_promise",
        "denylist",
        _skill_append("\nWe’re tracking this.\n"),
    ),
    Mutation("files_junk", "files", _write(f"{PLUGIN_REL}/skills/demo/.DS_Store", "x")),
    Mutation(
        "files_too_big",
        "files",
        _write(f"{PLUGIN_REL}/skills/demo/big.yaml", "a: b\n" * 60000),
    ),
    Mutation(
        "files_binary",
        "files",
        _write(f"{PLUGIN_REL}/skills/demo/x.zip", b"PK\x03\x04\x00\x00"),
    ),
    Mutation(
        "files_symlink",
        "files",
        lambda t: t.symlink(f"{PLUGIN_REL}/skills/demo/link.md", "notes.md"),
    ),
    Mutation(
        "files_short_readme",
        "files",
        _write(PLUGIN_README, f"# Demo\n\n`/{PLUGIN}:demo` is short.\n"),
    ),
    Mutation(
        "files_license_missing",
        "files",
        lambda t: t.write_json(MANIFEST, {"name": PLUGIN, "version": "1.0.0"}),
    ),
    Mutation("docs_skill_not_in_readme", "docs", _write("README.md", "no table\n")),
    Mutation("docs_no_changelog_entry", "docs", _write("CHANGELOG.md", "## [0.9.0]\n")),
    Mutation(
        "version_not_bumped_after_release",
        "version",
        lambda t: t.edit(NOTES, lambda s: s + "more\n"),
        base="base",
        tag=True,
    ),
)


def _run(tree: Tree, base: str | None = None):
    return run_checks(Repo(tree.root, base))


class GoodTreeTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tree = build_good_tree(Path(tmp.name))

    def test_good_tree_has_no_findings(self) -> None:
        self.assertEqual(_run(self.tree).findings, [])

    def test_user_config_header_and_pinned_npx_pass(self) -> None:
        self.tree.write_json(
            MCP,
            {
                "mcpServers": {
                    "s": {
                        "type": "http",
                        "url": "https://x.example.com",
                        "headers": {"Authorization": "Bearer ${user_config.TOKEN}"},
                    },
                    "l": {"command": "npx", "args": ["-y", "some-server@1.2.3"]},
                }
            },
        )
        self.assertEqual(_run(self.tree).findings, [])

    def test_unreleased_version_warns_instead_of_failing(self) -> None:
        self.tree.init_git()
        self.tree.edit(NOTES, lambda s: s + "more\n")
        self.tree.commit_changes()
        report = _run(self.tree, "base")
        self.assertEqual(report.fails, [])
        self.assertEqual([w.check for w in report.warns], ["version"])

    def test_real_version_bump_passes(self) -> None:
        self.tree.init_git(tag=True)
        self.tree.write(NOTES, "changed\n")
        self.tree.write_json(MANIFEST, manifest("1.0.1"))
        self.tree.write("CHANGELOG.md", "## [1.0.1]\n")
        self.tree.commit_changes()
        self.assertEqual(_run(self.tree, "base").findings, [])

    def test_unknown_base_ref_warns_and_skips_the_version_check(self) -> None:
        self.tree.init_git()
        report = _run(self.tree, "no-such-ref")
        self.assertEqual(report.fails, [])
        self.assertEqual([w.check for w in report.warns], ["version"])

    def test_changes_outside_the_plugin_need_no_bump(self) -> None:
        self.tree.init_git(tag=True)
        self.tree.write("CONTRIBUTING.md", "docs\n")
        self.tree.commit_changes()
        self.assertEqual(_run(self.tree, "base").findings, [])

    def test_formerly_embrace_twice_outside_shipped_files_passes(self) -> None:
        self.tree.write(
            "CHANGELOG.md", "## [1.0.0]\nformerly Embrace. formerly Embrace.\n"
        )
        self.assertEqual(_run(self.tree).findings, [])

    def test_platform_prefixed_and_platform_free_skill_names_pass(self) -> None:
        for name in (
            "apple-doctor",
            "android-doctor",
            "flutter-doctor",
            "react-native-doctor",
            "unity-doctor",
            "web-doctor",
            "react-native-android-linking",
            "flutter-apple-build",
            "doctor",
            "scenarios",
            "native-crash",
            "webview-crash",
        ):
            with self.subTest(name=name):
                tmp = tempfile.TemporaryDirectory()
                self.addCleanup(tmp.cleanup)
                tree = build_good_tree(Path(tmp.name))
                rename_skill(tree, name)
                self.assertEqual(_run(tree).findings, [])

    def test_skill_name_finding_suggests_the_prefixed_name(self) -> None:
        rename_skill(self.tree, "doctor-ios")
        [finding] = _run(self.tree).findings
        self.assertIn("'apple-doctor'", finding.message)

    def test_skill_name_with_apple_prefix_and_os_suggests_dropping_the_os(
        self,
    ) -> None:
        rename_skill(self.tree, "apple-ios-bridge")
        [finding] = _run(self.tree).findings
        self.assertIn("'apple-bridge'", finding.message)

    def test_skill_name_with_two_native_platforms_has_no_suggestion(self) -> None:
        rename_skill(self.tree, "android-apple-bridge")
        [finding] = _run(self.tree).findings
        self.assertIn("more than one platform", finding.message)
        self.assertNotIn("as in", finding.message)

    def test_framework_skill_name_suggestions_keep_the_native_side(self) -> None:
        cases = {
            "android-react-native-linking": "'react-native-android-linking'",
            "react-native-ios-build": "'react-native-apple-build'",
            "rn-doctor": "'react-native-doctor'",
        }
        for name, suggestion in cases.items():
            with self.subTest(name=name):
                tmp = tempfile.TemporaryDirectory()
                self.addCleanup(tmp.cleanup)
                tree = build_good_tree(Path(tmp.name))
                rename_skill(tree, name)
                [finding] = _run(tree).findings
                self.assertIn(suggestion, finding.message)

    def test_reworded_secrets_rule_passes(self) -> None:
        self.tree.edit(
            SKILL,
            lambda s: s.replace(
                "Never reproduce secrets", "Keep secrets out of answers"
            ),
        )
        self.assertEqual(_run(self.tree).findings, [])

    def test_skill_missing_from_plugin_readme_only_warns(self) -> None:
        self.tree.edit(PLUGIN_README, lambda s: s.replace(f"/{PLUGIN}:demo", "demo"))
        report = _run(self.tree)
        self.assertEqual(report.fails, [])
        self.assertEqual([w.check for w in report.warns], ["docs"])

    def test_missing_manifest_is_one_layout_failure(self) -> None:
        (self.tree.root / MANIFEST).unlink()
        report = _run(self.tree)
        self.assertEqual({f.check for f in report.fails}, {"layout"})


class FailingCaseTests(unittest.TestCase):
    """Test methods are generated from MUTATIONS below."""

    def check_mutation(self, mutation: Mutation) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tree = build_good_tree(Path(tmp))
            if mutation.base:
                tree.init_git(tag=mutation.tag)
            mutation.mutate(tree)
            if mutation.base:
                tree.commit_changes()
            report = _run(tree, mutation.base)
        self.assertEqual(
            {f.check for f in report.fails},
            {mutation.check} | mutation.also,
            "\n" + report.render(),
        )


def _add_mutation_test(mutation: Mutation) -> None:
    def test(self: FailingCaseTests) -> None:
        self.check_mutation(mutation)

    test.__name__ = f"test_{mutation.name}"
    setattr(FailingCaseTests, test.__name__, test)


for _mutation in MUTATIONS:
    _add_mutation_test(_mutation)


class RegistryTests(unittest.TestCase):
    def test_check_ids_are_unique(self) -> None:
        ids = [check.id for check in CHECKS]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_check_has_a_failing_case(self) -> None:
        self.assertEqual({m.check for m in MUTATIONS}, {c.id for c in CHECKS})

    def test_mutation_names_are_unique(self) -> None:
        names = [m.name for m in MUTATIONS]
        self.assertEqual(len(names), len(set(names)))


if __name__ == "__main__":
    unittest.main()
