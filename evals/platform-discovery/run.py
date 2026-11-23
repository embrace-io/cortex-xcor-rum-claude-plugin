"""Measure how accurately the platform-discovery skill detects a project's platform.

`corpus.json` lists public projects pinned to a commit, two synthetic projects built
from them, and cases: a project, a prompt and the expected answer. `fetch` downloads
the projects. `run` starts one headless Claude Code session per case with the plugin
loaded from this checkout, calls `/cortex-xcor-rum:platform-discovery` with the case's
prompt, and scores the `**Platform:**` line the skill writes as right, asked or wrong.

The sessions run without MCP servers and without the Skill tool, so they measure
detection from the repository alone and stop before any hand-off. They use an empty
Claude Code configuration directory, so the runner's own settings, memory and plugins
don't reach them.

Usage:
    python3 evals/platform-discovery/run.py fetch --corpus-dir DIR
    python3 evals/platform-discovery/run.py run --corpus-dir DIR [--model sonnet] [--jobs 4]
    python3 evals/platform-discovery/run.py rescore RESULTS.json
"""

import argparse
import concurrent.futures
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
PLUGIN_DIR = REPO_ROOT / "plugins" / "cortex-xcor-rum"
SKILL_COMMAND = "/cortex-xcor-rum:platform-discovery"

# Files that would change a session's behavior or run code: project settings and hooks,
# MCP servers, and instruction files written for other agents.
STRIPPED_NAMES = {".claude", ".cursor", ".mcp.json", ".git", "claude.md", "agents.md"}

PLATFORMS = {
    "react native": "react-native",
    "android": "android",
    "apple": "apple",
    "flutter": "flutter",
    "unity": "unity",
    "web": "web",
}


def load_corpus(path=HERE / "corpus.json"):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def case_id(case):
    parts = [case["project"]]
    if case.get("cwd"):
        parts.append(case["cwd"].replace("/", "-"))
    parts.append(case["prompt"])
    return "/".join(parts)


# --- fetch ---------------------------------------------------------------------------


def strip_tree(root):
    """Remove agent configuration, instruction files and symlinks from a fetched tree."""
    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        for name in list(dirnames) + filenames:
            path = Path(dirpath) / name
            if path.is_symlink():
                path.unlink()
            elif name.lower() in STRIPPED_NAMES:
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
        dirnames[:] = [d for d in dirnames if (Path(dirpath) / d).is_dir()]


def extract_subdir(archive, subdir, dest):
    """Extract the members of a GitHub tarball under `subdir` into `dest`.

    GitHub tarballs put everything under one top-level directory. Members outside
    `subdir`, links and anything that would leave `dest` are skipped.
    """
    dest = Path(dest).resolve()
    prefix = None
    with tarfile.open(fileobj=archive, mode="r|gz") as tar:
        for member in tar:
            top, _, rest = member.name.partition("/")
            if prefix is None:
                prefix = f"{subdir.strip('/')}/" if subdir else ""
            if not rest.startswith(prefix) or rest == prefix:
                continue
            rel = rest[len(prefix) :]
            target = (dest / rel).resolve()
            if not target.is_relative_to(dest):
                continue
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                target.parent.mkdir(parents=True, exist_ok=True)
                with tar.extractfile(member) as src, open(target, "wb") as out:
                    shutil.copyfileobj(src, out)


def init_repo(path):
    """Make `path` its own git repository, as a user's project is.

    ripgrep, which Claude Code's Grep and Glob tools use, applies the .gitignore files
    of every enclosing repository. Without its own repository a project inside an
    ignored directory (such as a checkout's scratch folder) is invisible below its
    top level, and the project's own .gitignore doesn't apply.
    """
    subprocess.run(["git", "init", "-q", str(path)], check=True)


def fetch_source(name, source, corpus_dir):
    dest = corpus_dir / name
    if dest.exists():
        return f"have {name}"
    url = f"https://codeload.github.com/{source['repo']}/tar.gz/{source['ref']}"
    tmp = Path(tempfile.mkdtemp(dir=corpus_dir, prefix=f".{name}-"))
    with urllib.request.urlopen(url) as resp:
        extract_subdir(io.BufferedReader(resp), source.get("subdir", ""), tmp)
    strip_tree(tmp)
    init_repo(tmp)
    tmp.rename(dest)
    return f"fetched {name}"


def build_synthetic(name, spec, corpus_dir):
    dest = corpus_dir / name
    if dest.exists():
        shutil.rmtree(dest)
    for rel, source_name in spec.get("copy", {}).items():
        shutil.copytree(
            corpus_dir / source_name,
            dest / rel,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".git"),
        )
    for rel, text in spec.get("files", {}).items():
        path = dest / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    init_repo(dest)
    return f"built {name}"


def fetch(corpus, corpus_dir):
    corpus_dir.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        jobs = [
            pool.submit(fetch_source, name, source, corpus_dir)
            for name, source in corpus["sources"].items()
        ]
        for job in concurrent.futures.as_completed(jobs):
            print(job.result())
    for name, spec in corpus["synthetic"].items():
        print(build_synthetic(name, spec, corpus_dir))


# --- scoring -------------------------------------------------------------------------


def parse_report(text):
    """Read the skill's `**Platform:**` line into its parts, or None if there is none."""
    match = re.search(r"\*\*Platform:\*\*\s*(.+)", text or "")
    if not match:
        return None
    line = match.group(1).strip()
    head = re.split(r"\s\(", line, maxsplit=1)[0].lower()
    # The claim ends where the evidence starts: the first parenthesis that quotes code
    # or the user. Earlier ones qualify the platform, as in "Web (React)" or "React
    # Native (Expo)". Only the claim is parsed, so evidence such as "you said nothing
    # about the Android side" can't change the answer.
    claim = re.split(r"\s\((?=[^)]*(?:`|\byou))", line, maxsplit=1)[0]
    lower = claim.lower()
    report = {"line": line, "platform": None, "side": None, "app": None}
    if "not detected" in head:
        report["platform"] = "ask"
    else:
        for label, platform in PLATFORMS.items():
            if head.startswith(label):
                report["platform"] = platform
                break
    if "side not known" in lower:
        report["side"] = "ask"
    elif re.search(r"\bandroid side\b", lower):
        report["side"] = "android"
    elif re.search(r"\b(apple|ios) side\b", lower):
        report["side"] = "apple"
    if "app not known" in lower:
        report["app"] = "ask"
    report["react"] = "(react)" in lower
    # The skill is told to write "no XCOR RUM SDK found", but models reword it ("no
    # Gradle `io.embrace` entry found"), so any "no ... found" clause before the
    # evidence counts.
    report["sdk"] = not re.search(r"\bno\b.*\bfound\b", claim, re.I)
    return report


def rescore(corpus, results_path, model):
    """Score a results file again, after a change to the parser or the corpus."""
    expected = {case_id(c): c["expect"] for c in corpus["cases"]}
    results = json.loads(results_path.read_text(encoding="utf-8"))
    kept = []
    for row in results:
        if row["case"] not in expected:
            print(f"skipping {row['case']}: no longer in the corpus")
            continue
        if not row.get("error"):
            report = parse_report(row["result"])
            row["report"] = report["line"] if report else None
            row["verdict"], row["notes"] = score(expected[row["case"]], report)
        kept.append(row)
    results = kept
    results_path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print_summary(results, model)


def score(expect, report):
    """Return (verdict, notes). The verdict is right, asked, wrong or no-report.

    A session that failed (see `run_case`) is scored "error" by the caller, not here.

    Asking when the expected answer was definite is "asked", which costs the user a
    question but sends nobody to the wrong skill. Any definite answer that differs
    from the expected one is "wrong", including a side or app given where the expected
    answer is to ask.
    """
    if report is None:
        return "no-report", []
    notes = []
    if expect.get("app") == "ask":
        if report["app"] == "ask":
            return "right", notes
        if report["platform"] == "ask":
            return "asked", ["asked for the platform, not which app"]
        return "wrong", [f"expected to ask which app, got {report['line']!r}"]
    if report["app"] == "ask" or report["platform"] == "ask":
        return "asked", notes
    if report["platform"] != expect["platform"]:
        return "wrong", [f"expected platform {expect['platform']}"]
    expected_side = expect.get("side")
    if expected_side == "ask":
        if report["side"] not in (None, "ask"):
            return "wrong", [f"guessed the {report['side']} side"]
        if report["side"] is None:
            notes.append("named no side and asked nothing")
            return "wrong", notes
    elif expected_side:
        if report["side"] == "ask":
            return "asked", notes
        if report["side"] != expected_side:
            return "wrong", [f"expected the {expected_side} side, got {report['side']}"]
    if "sdk" in expect and report["sdk"] != expect["sdk"]:
        notes.append(f"sdk expected {expect['sdk']}, reported {report['sdk']}")
    if "react" in expect and report["react"] != expect["react"]:
        notes.append(f"react expected {expect['react']}, reported {report['react']}")
    return "right", notes


# --- run -----------------------------------------------------------------------------


def run_case(case, prompt, corpus_dir, model, config_dir, timeout):
    cwd = corpus_dir / case["project"] / case.get("cwd", "")
    cmd = [
        "claude",
        "-p",
        f"{SKILL_COMMAND} {prompt}",
        "--plugin-dir",
        str(PLUGIN_DIR),
        "--strict-mcp-config",
        "--setting-sources",
        "user",
        "--tools",
        "Read,Grep,Glob",
        "--model",
        model,
        "--no-session-persistence",
        "--output-format",
        "stream-json",
        "--verbose",
    ]
    env = dict(os.environ, CLAUDE_CONFIG_DIR=str(config_dir))
    try:
        proc = subprocess.run(
            cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired as err:
        return {"result": "", "error": f"timeout: {err}"[:300], "tools": []}
    tools, out = [], {}
    for line in proc.stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "result":
            out = event
        elif event.get("type") == "assistant":
            for block in event.get("message", {}).get("content", []):
                if block.get("type") == "tool_use":
                    tools.append({"tool": block["name"], "input": block.get("input")})
    error = None
    if proc.returncode != 0 or not out or out.get("is_error"):
        error = (
            f"exit {proc.returncode}: {(proc.stderr or out.get('result') or '')[-300:]}"
        )
    return {
        "error": error,
        "result": out.get("result", ""),
        "cost_usd": out.get("total_cost_usd"),
        "turns": out.get("num_turns"),
        "duration_s": round((out.get("duration_ms") or 0) / 1000, 1),
        "tools": tools,
    }


def run(corpus, corpus_dir, model, jobs, out_path, only, timeout):
    cases = [c for c in corpus["cases"] if not only or re.search(only, case_id(c))]
    config_dir = Path(tempfile.mkdtemp(prefix="platform-discovery-eval-"))
    (config_dir / "settings.json").write_text("{}", encoding="utf-8")
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = {
            pool.submit(
                run_case,
                case,
                corpus["prompts"][case["prompt"]],
                corpus_dir,
                model,
                config_dir,
                timeout,
            ): case
            for case in cases
        }
        for future in concurrent.futures.as_completed(futures):
            case = futures[future]
            outcome = future.result()
            report = parse_report(outcome["result"])
            if outcome.get("error"):
                verdict, notes = "error", [outcome["error"]]
            else:
                verdict, notes = score(case["expect"], report)
            row = {
                "case": case_id(case),
                "verdict": verdict,
                "notes": notes,
                "report": report["line"] if report else None,
                **outcome,
            }
            results.append(row)
            print(f"{verdict:9} {row['case']:45} {row['report']}", flush=True)
    shutil.rmtree(config_dir, ignore_errors=True)
    results.sort(key=lambda r: r["case"])
    out_path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print_summary(results, model)


def print_summary(results, model):
    counts = {}
    for row in results:
        counts[row["verdict"]] = counts.get(row["verdict"], 0) + 1
    cost = sum(r.get("cost_usd") or 0 for r in results)
    print(f"\nmodel {model}, {len(results)} cases, ${cost:.2f}")
    for verdict in ("right", "asked", "wrong", "no-report", "error"):
        print(f"  {verdict:9} {counts.get(verdict, 0)}")
    for row in results:
        if row["verdict"] != "right" or row["notes"]:
            print(f"  - {row['case']}: {row['verdict']} {'; '.join(row['notes'])}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("fetch", "run"):
        p = sub.add_parser(name)
        p.add_argument("--corpus-dir", type=Path, required=True)
    rescore_parser = sub.add_parser("rescore")
    rescore_parser.add_argument("results", type=Path)
    rescore_parser.add_argument("--model", default="")
    run_parser = sub.choices["run"]
    run_parser.add_argument("--model", default="sonnet")
    run_parser.add_argument("--jobs", type=int, default=4)
    run_parser.add_argument("--only", help="regex over case ids")
    run_parser.add_argument("--timeout", type=int, default=600)
    run_parser.add_argument(
        "--out", type=Path, default=Path("platform-discovery-results.json")
    )
    args = parser.parse_args(argv)
    corpus = load_corpus()
    if args.command == "rescore":
        return rescore(corpus, args.results, args.model)
    corpus_dir = args.corpus_dir.resolve()
    if args.command == "fetch":
        fetch(corpus, corpus_dir)
    else:
        run(
            corpus, corpus_dir, args.model, args.jobs, args.out, args.only, args.timeout
        )


if __name__ == "__main__":
    sys.exit(main())
