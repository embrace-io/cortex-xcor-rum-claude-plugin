#!/usr/bin/env python3
"""Checks that the repository follows the standards in AGENTS.md.

Usage:
    scripts/check-plugin.py [ROOT] [--base REF]
    scripts/check-plugin.py --self-test [--scratch DIR] [-v]

ROOT defaults to the repository that contains this script. The script uses only
the Python standard library. It prints one FAIL or WARN line per finding and
exits 1 if there is at least one FAIL.

Known failures that predate a check are listed in check-plugin-baseline.txt
next to this script, one "<check-id> <relative path>" per line. A baselined
finding is reported as a warning and doesn't fail the run. A baseline line that
no longer matches a finding is also reported, so the line gets deleted and the
list only shrinks.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

PLUGIN = "cortex-xcor-rum"
PLUGIN_REL = f"plugins/{PLUGIN}"
TAG_GLOB = f"{PLUGIN}--v*"
DESCRIPTION_CAP = 1536
TEXT_CAP = 256 * 1024
FILE_CAP = 5 * 1024 * 1024
MAX_FILES = 512
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
FONT_EXT = {".woff", ".woff2", ".ttf", ".otf"}
JUNK_NAMES = {".ds_store", "thumbs.db", "desktop.ini", "__macosx"}
SKIP_DIRS = {".git", ".agentd", "node_modules"}
# This file holds credential-shaped test strings, so the content checks skip it.
SELF = "scripts/check-plugin.py"
SECRETS_PHRASE = "Never reproduce secrets"
DENYLIST = [
    "#tech-support",
    "#guild-",
    "we'll flip",
    "we're tracking",
    "professional services",
]
SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
USER_CONFIG = re.compile(r"\$\{user_config\.[A-Za-z0-9_]+\}")
ENV_REF = re.compile(r"\$\{?(?!user_config\.)[A-Za-z_]")
SECRET_PATTERNS = [
    (re.compile(r"Bearer\s+\$\{?(?!user_config\.)[A-Za-z_]"), "an Authorization header that reads an environment variable"),
    (re.compile(r"[?&](?:api[_-]?key|token|access[_-]?token|key|secret)=\$\{?(?!user_config\.)[A-Za-z_]", re.I), "a URL that reads an environment variable into a credential parameter"),
    (re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{24,}"), "a literal bearer token"),
    (re.compile(r"\b(?:sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|AKIA[0-9A-Z]{16}|xox[abpr]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{35})"), "a literal API key"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}"), "a literal JWT"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "a private key"),
]


class Report:
    def __init__(self, baseline):
        self.baseline = baseline
        self.fails = []
        self.warns = []
        self.used = set()

    def fail(self, check, path, msg):
        if (check, path) in self.baseline:
            self.used.add((check, path))
            self.warns.append((check, path, f"{msg} (baselined)"))
        else:
            self.fails.append((check, path, msg))

    def warn(self, check, path, msg):
        self.warns.append((check, path, msg))

    def finish(self):
        for check, path in sorted(self.baseline - self.used):
            self.warns.append((check, path, "baseline line no longer matches a finding; delete it from check-plugin-baseline.txt"))


def load_baseline(path):
    entries = set()
    if not os.path.isfile(path):
        return entries
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.split("#", 1)[0].strip()
            if line:
                check, _, rel = line.partition(" ")
                entries.add((check, rel.strip()))
    return entries


def read_json(root, rel, rep, check):
    path = os.path.join(root, rel)
    if not os.path.isfile(path):
        rep.fail(check, rel, "file is missing")
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (ValueError, OSError) as e:
        rep.fail(check, rel, f"can't parse as JSON: {e}")
        return None


def walk(root, sub=""):
    """Yields (relative path, absolute path) for every file under root/sub."""
    base = os.path.join(root, sub)
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            abs_path = os.path.join(dirpath, name)
            yield os.path.relpath(abs_path, root), abs_path


def read_text(path):
    """Returns the file's text, or None if it isn't UTF-8 text."""
    try:
        with open(path, "rb") as f:
            data = f.read()
        if b"\x00" in data:
            return None
        return data.decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def parse_frontmatter(text):
    """Parses the top-level keys of a SKILL.md frontmatter block.

    Returns (dict, error). It handles scalars, quoted scalars and block scalars,
    which is what skills use, and rejects a plain scalar that YAML would fail on.
    """
    lines = text.split("\n")
    if not lines or lines[0].rstrip() != "---":
        return None, "file doesn't start with a '---' frontmatter block"
    end = None
    for i in range(1, len(lines)):
        if lines[i].rstrip() == "---":
            end = i
            break
    if end is None:
        return None, "frontmatter has no closing '---'"
    fm = {}
    body = lines[1:end]
    idx = 0
    while idx < len(body):
        line = body[idx]
        idx += 1
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = re.match(r"^([A-Za-z0-9_.-]+):(?:\s+(.*))?$", line)
        if not m:
            return None, f"frontmatter line {idx + 1} isn't a 'key: value' pair: {line[:60]!r}"
        key, val = m.group(1), (m.group(2) or "").strip()
        cont = []
        while idx < len(body) and (body[idx].startswith((" ", "\t")) or not body[idx].strip()):
            cont.append(body[idx].strip())
            idx += 1
        if re.match(r"^[>|][+-]?$", val):
            joiner = " " if val.startswith(">") else "\n"
            val = joiner.join(c for c in cont if c)
        elif val[:1] in ("'", '"'):
            if len(val) < 2 or val[-1] != val[0]:
                return None, f"frontmatter key {key!r} has an unterminated quoted string"
            val = val[1:-1]
        elif val:
            val = " ".join([val] + [c for c in cont if c])
            if ": " in val or " #" in val:
                return None, f"frontmatter key {key!r} is a plain scalar with ': ' or ' #' in it, which YAML can't parse; wrap it in quotes"
        fm[key] = val
    return fm, None


def check_layout(root, rep):
    mkt = read_json(root, ".claude-plugin/marketplace.json", rep, "layout")
    plugins_dir = os.path.join(root, "plugins")
    dirs = sorted(os.listdir(plugins_dir)) if os.path.isdir(plugins_dir) else []
    if dirs != [PLUGIN]:
        rep.fail("layout", "plugins", f"expected exactly one plugin directory named {PLUGIN}, found {dirs or 'none'}")
    mkt_rel = ".claude-plugin/marketplace.json"
    if mkt is not None:
        if mkt.get("name") != PLUGIN:
            rep.fail("layout", mkt_rel, f"marketplace name is {mkt.get('name')!r}, expected {PLUGIN!r}")
        entries = mkt.get("plugins")
        if not isinstance(entries, list) or len(entries) != 1:
            rep.fail("layout", mkt_rel, "the marketplace must list exactly one plugin")
        else:
            e = entries[0]
            if e.get("name") != PLUGIN:
                rep.fail("layout", mkt_rel, f"plugin entry name is {e.get('name')!r}, expected {PLUGIN!r}")
            if e.get("source") != f"./{PLUGIN_REL}":
                rep.fail("layout", mkt_rel, f"plugin entry source is {e.get('source')!r}, expected './{PLUGIN_REL}'")
    pj_rel = f"{PLUGIN_REL}/.claude-plugin/plugin.json"
    pj = read_json(root, pj_rel, rep, "layout")
    if pj is not None:
        if pj.get("name") != PLUGIN:
            rep.fail("layout", pj_rel, f"plugin name is {pj.get('name')!r}, expected {PLUGIN!r}")
        version = pj.get("version")
        if not isinstance(version, str) or not SEMVER.match(version):
            rep.fail("layout", pj_rel, f"version {version!r} isn't a semantic version")
        if not pj.get("license"):
            rep.fail("files", pj_rel, "license is not set")
    return pj


def check_skills(root, rep):
    skills_root = os.path.join(root, PLUGIN_REL, "skills")
    names = []
    if not os.path.isdir(skills_root):
        rep.fail("skills", f"{PLUGIN_REL}/skills", "directory is missing")
        return names
    for entry in sorted(os.listdir(skills_root)):
        rel = f"{PLUGIN_REL}/skills/{entry}"
        if not os.path.isdir(os.path.join(skills_root, entry)):
            rep.fail("skills", rel, "skills/ holds only skill directories")
            continue
        names.append(entry)
        skill_md = f"{rel}/SKILL.md"
        text = read_text(os.path.join(root, skill_md))
        if text is None:
            rep.fail("skills", skill_md, "SKILL.md is missing or isn't UTF-8 text")
            continue
        if SECRETS_PHRASE not in text:
            rep.fail("secrets-rule", skill_md, f"missing the hard rule that starts '{SECRETS_PHRASE}'")
        refs = {m.group(1).rstrip(".,;:") for m in re.finditer(r"\$\{CLAUDE_SKILL_DIR\}/([^\s`'\"<>)\]]+)", text)}
        for ref in sorted(refs):
            if not os.path.isfile(os.path.join(skills_root, entry, ref)):
                rep.fail("skill-refs", skill_md, f"references ${{CLAUDE_SKILL_DIR}}/{ref}, which isn't in {rel}/")
        fm, err = parse_frontmatter(text)
        if err:
            rep.fail("skills", skill_md, err)
            continue
        if fm.get("name") != entry:
            rep.fail("skills", skill_md, f"frontmatter name is {fm.get('name')!r}, expected the directory name {entry!r}")
        desc = fm.get("description", "")
        if not desc.strip():
            rep.fail("skills", skill_md, "frontmatter description is missing or empty")
        elif len(desc) > DESCRIPTION_CAP:
            rep.fail("skills", skill_md, f"description is {len(desc)} characters, over the {DESCRIPTION_CAP} cap")
    return names


def check_mcp(root, rep):
    rel = f"{PLUGIN_REL}/.mcp.json"
    if not os.path.isfile(os.path.join(root, rel)):
        return
    data = read_json(root, rel, rep, "mcp")
    if data is None:
        return
    servers = data.get("mcpServers", data) if isinstance(data, dict) else None
    if not isinstance(servers, dict):
        rep.fail("mcp", rel, "expected an object of servers")
        return
    for name, s in servers.items():
        where = f"server {name!r}"
        if not isinstance(s, dict):
            rep.fail("mcp", rel, f"{where} isn't an object")
            continue
        env = s.get("env") or {}
        if isinstance(env, dict):
            for k, v in env.items():
                if ENV_REF.search(str(v)):
                    rep.fail("mcp", rel, f"{where} env {k!r} reads from the user's environment")
        if "command" in s:
            check_launcher(rep, rel, where, s)
            continue
        if s.get("type") not in ("http", "sse", "ws"):
            rep.fail("mcp", rel, f"{where} has type {s.get('type')!r}, expected http, sse or ws")
        url = s.get("url")
        if not isinstance(url, str) or not (re.match(r"^(https|wss)://[^\s/$]", url) or USER_CONFIG.fullmatch(url) or url == ""):
            rep.fail("mcp", rel, f"{where} url {url!r} must be an absolute https:// or wss:// URL")
        elif ENV_REF.search(url):
            rep.fail("mcp", rel, f"{where} url reads an environment variable")
        headers = s.get("headers") or {}
        if not isinstance(headers, dict):
            rep.fail("mcp", rel, f"{where} headers isn't an object")
            continue
        for h, v in headers.items():
            v = str(v)
            if ENV_REF.search(v):
                rep.fail("mcp", rel, f"{where} header {h!r} reads an environment variable; use a userConfig entry with sensitive: true")
            elif not USER_CONFIG.search(v) and re.search(r"auth|token|key|secret|cookie|password", h, re.I):
                rep.fail("mcp", rel, f"{where} header {h!r} holds a literal value; use a userConfig entry with sensitive: true")


def check_launcher(rep, rel, where, s):
    cmd = os.path.basename(str(s.get("command")))
    args = [str(a) for a in s.get("args", [])]
    runners = {"npx": "@", "bunx": "@", "uvx": "==", "pipx": "==", "pnpm": "@", "yarn": "@", "uv": "=="}
    if cmd not in runners:
        return
    if cmd in ("pnpm", "yarn"):
        if not args or args[0] != "dlx":
            return
        args = args[1:]
    elif cmd == "pipx":
        if not args or args[0] != "run":
            return
        args = args[1:]
    elif cmd == "uv":
        if not args or args[0] != "run":
            return
        if "--locked" not in args and "--frozen" not in args:
            rep.fail("mcp", rel, f"{where} runs uv run without --locked or --frozen")
        return
    pkg = next((a for a in args if not a.startswith("-")), None)
    sep = runners[cmd]
    if pkg is None or not re.search(re.escape(sep) + r"\d+\.\d+\.\d+", pkg.lstrip("@")):
        rep.fail("mcp", rel, f"{where} runs {cmd} with {pkg!r}; pin the package to an exact version such as name{sep}1.2.3")


def check_content(root, rep):
    for rel, path in walk(root):
        if rel == SELF:
            continue
        text = read_text(path)
        if text is None:
            continue
        for rx, what in SECRET_PATTERNS:
            if rx.search(text):
                rep.fail("credentials", rel, f"contains {what}")
        count = len(re.findall(r"formerly\s+embrace", text, re.I))
        if count > 1:
            rep.fail("naming", rel, f"says 'formerly Embrace' {count} times; once per file at most")
        if rel.startswith(PLUGIN_REL + "/"):
            low = text.lower().replace("’", "'")
            for term in DENYLIST:
                if term in low:
                    rep.fail("denylist", rel, f"contains {term!r}, which doesn't belong in shipped content")


def check_files(root, rep):
    plugin_dir = os.path.join(root, PLUGIN_REL)
    count = 0
    for rel, path in walk(root, PLUGIN_REL):
        count += 1
        name = os.path.basename(rel)
        ext = os.path.splitext(name)[1].lower()
        if name.lower() in JUNK_NAMES or "__MACOSX" in rel.split("/"):
            rep.fail("files", rel, "OS junk file")
        if re.search(r'[:<>"|?*]|[. ]$', name):
            rep.fail("files", rel, "file name isn't valid on Windows")
        if os.path.islink(path):
            rep.fail("files", rel, "symlink; commit a regular file")
            continue
        size = os.path.getsize(path)
        if size > FILE_CAP:
            rep.fail("files", rel, f"{size} bytes, over the 5 MiB limit")
        if ext in IMAGE_EXT or ext in FONT_EXT:
            continue
        if size >= TEXT_CAP:
            rep.fail("files", rel, f"{size} bytes, at or over the 256 KiB limit for non-image files")
        text = read_text(path)
        if text is None:
            rep.fail("files", rel, "binary file; only PNG, JPEG, GIF, WebP, SVG and font files are allowed")
        elif text.startswith("version https://git-lfs.github.com/spec"):
            rep.fail("files", rel, "Git LFS pointer file")
    if count > MAX_FILES:
        rep.fail("files", PLUGIN_REL, f"{count} files, over the {MAX_FILES} file limit")
    for rel, path in walk(root):
        if os.path.basename(rel) == ".gitattributes":
            text = read_text(path) or ""
            if re.search(r"export-ignore|export-subst|\bfilter=", text):
                rep.fail("files", rel, "uses export-ignore, export-subst or filter (including Git LFS)")
    readme = read_text(os.path.join(plugin_dir, "README.md"))
    if readme is None:
        rep.fail("files", f"{PLUGIN_REL}/README.md", "plugin README is missing")
    else:
        prose = re.sub(r"```.*?```", "", readme, flags=re.S)
        words = len(prose.split())
        if words < 40:
            rep.fail("files", f"{PLUGIN_REL}/README.md", f"{words} words outside code blocks, need at least 40")


def check_docs(root, rep, pj, skills):
    root_readme = read_text(os.path.join(root, "README.md")) or ""
    plugin_readme = read_text(os.path.join(root, PLUGIN_REL, "README.md")) or ""
    for s in skills:
        if f"/{PLUGIN}:{s}" not in root_readme:
            rep.fail("docs", "README.md", f"skill table doesn't list /{PLUGIN}:{s}")
        if f"/{PLUGIN}:{s}" not in plugin_readme:
            rep.fail("docs", f"{PLUGIN_REL}/README.md", f"skill list doesn't mention /{PLUGIN}:{s}")
    version = (pj or {}).get("version")
    changelog = read_text(os.path.join(root, "CHANGELOG.md"))
    if changelog is None:
        rep.fail("docs", "CHANGELOG.md", "file is missing")
    elif version and not re.search(r"^## \[" + re.escape(version) + r"\]", changelog, re.M):
        rep.fail("docs", "CHANGELOG.md", f"no '## [{version}]' entry for the version in plugin.json")


def vcs(root, *args):
    r = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True)
    return r.returncode, r.stdout.strip()


def check_version(root, rep, base):
    if not base:
        return
    manifest = f"{PLUGIN_REL}/.claude-plugin/plugin.json"
    code, out = vcs(root, "diff", "--name-only", f"{base}...HEAD", "--", PLUGIN_REL)
    if code != 0:
        rep.warn("version", base, "can't diff against the base ref (fetch full history with fetch-depth: 0); skipping the version check")
        return
    if not out:
        return
    code, old = vcs(root, "show", f"{base}:{manifest}")
    try:
        old_version = json.loads(old).get("version") if code == 0 else None
    except ValueError:
        old_version = None
    with open(os.path.join(root, manifest), encoding="utf-8") as f:
        new_version = json.load(f).get("version")
    if old_version != new_version:
        return
    _, tags = vcs(root, "tag", "-l", TAG_GLOB)
    msg = f"files under {PLUGIN_REL}/ changed against {base} but version is still {new_version}"
    if tags:
        rep.fail("version", manifest, msg + "; bump it")
    else:
        rep.warn("version", manifest, msg + f" (not enforced: no {TAG_GLOB} tag exists, so the version hasn't shipped)")


def run_checks(root, base, baseline):
    rep = Report(baseline)
    pj = check_layout(root, rep)
    skills = check_skills(root, rep)
    check_mcp(root, rep)
    check_content(root, rep)
    check_files(root, rep)
    check_docs(root, rep, pj, skills)
    check_version(root, rep, base)
    rep.finish()
    return rep


def print_report(rep, out=sys.stdout):
    for check, path, msg in rep.warns:
        print(f"WARN [{check}] {path}: {msg}", file=out)
    for check, path, msg in rep.fails:
        print(f"FAIL [{check}] {path}: {msg}", file=out)
    print(f"{len(rep.fails)} failure(s), {len(rep.warns)} warning(s)", file=out)


# ---- self test -----------------------------------------------------------

GOOD_SKILL = """---
name: demo
description: Use when the user asks about the demo.
---

# Demo

Read ${CLAUDE_SKILL_DIR}/notes.md first.

## Hard rules

- **Never reproduce secrets.** Replace credentials with `<redacted>`.
"""


def write(root, rel, text, mode="w"):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, mode) as f:
        f.write(text)


def read(root, rel):
    with open(os.path.join(root, rel), encoding="utf-8") as f:
        return f.read()


def build_fixture(root):
    p = PLUGIN_REL
    write(root, ".claude-plugin/marketplace.json", json.dumps({"name": PLUGIN, "plugins": [{"name": PLUGIN, "source": f"./{p}"}]}))
    write(root, f"{p}/.claude-plugin/plugin.json", json.dumps({"name": PLUGIN, "version": "1.0.0", "license": "Apache-2.0"}))
    write(root, f"{p}/.mcp.json", json.dumps({"mcpServers": {"embrace": {"type": "http", "url": "https://mcp.example.com/mcp"}}}))
    write(root, f"{p}/README.md", f"# Demo\n\nSkill `/{PLUGIN}:demo`. " + " ".join(["word"] * 50) + "\n")
    write(root, f"{p}/skills/demo/SKILL.md", GOOD_SKILL)
    write(root, f"{p}/skills/demo/notes.md", "notes\n")
    write(root, "README.md", f"| `/{PLUGIN}:demo` | demo |\n")
    write(root, "CHANGELOG.md", "## [1.0.0] - Unreleased\n")


def run_vcs(root, *args):
    subprocess.run(["git", "-C", root, *args], check=True, capture_output=True)


def self_test(scratch, verbose):
    base_dir = scratch or tempfile.mkdtemp(prefix="check-plugin-")
    os.makedirs(base_dir, exist_ok=True)
    failures = []

    def case(name, expect, mutate, base=None, tag=False, expect_warn=None):
        root = os.path.join(base_dir, name)
        shutil.rmtree(root, ignore_errors=True)
        build_fixture(root)
        if base:
            run_vcs(root, "init", "-q", "-b", "main")
            run_vcs(root, "config", "user.email", "t@example.com")
            run_vcs(root, "config", "user.name", "t")
            run_vcs(root, "add", "-A")
            run_vcs(root, "commit", "-q", "-m", "base")
            run_vcs(root, "branch", "base")
            if tag:
                run_vcs(root, "tag", f"{PLUGIN}--v1.0.0")
        mutate(root)
        if base:
            run_vcs(root, "add", "-A")
            run_vcs(root, "commit", "-q", "-m", "change")
        rep = run_checks(root, base, set())
        got = {c for c, _, _ in rep.fails}
        ok = (expect in got) if expect else not rep.fails
        if expect_warn:
            ok = ok and any(c == expect_warn for c, _, _ in rep.warns)
        print(f"{'ok  ' if ok else 'BAD '} {name} [{expect or 'pass'}]")
        if verbose or not ok:
            print_report(rep)
        if not ok:
            failures.append(name)

    def edit(rel, fn):
        return lambda root: write(root, rel, fn(read(root, rel)))

    p = PLUGIN_REL
    skill = f"{p}/skills/demo/SKILL.md"
    mcp = f"{p}/.mcp.json"
    notes = f"{p}/skills/demo/notes.md"

    def mcp_case(name, expect, servers):
        case(name, expect, lambda r: write(r, mcp, json.dumps({"mcpServers": servers})))

    def bump(r):
        write(r, notes, "changed\n")
        write(r, f"{p}/.claude-plugin/plugin.json", json.dumps({"name": PLUGIN, "version": "1.0.1", "license": "Apache-2.0"}))
        write(r, "CHANGELOG.md", "## [1.0.1]\n")

    case("good", None, lambda r: None)
    case("layout-second-plugin", "layout", lambda r: write(r, ".claude-plugin/marketplace.json", json.dumps({"name": PLUGIN, "plugins": [{"name": PLUGIN, "source": f"./{p}"}, {"name": "other", "source": "./plugins/other"}]})))
    case("layout-name-mismatch", "layout", edit(f"{p}/.claude-plugin/plugin.json", lambda t: t.replace(f'"name": "{PLUGIN}"', '"name": "renamed"')))
    case("skills-name-mismatch", "skills", edit(skill, lambda t: t.replace("name: demo", "name: other")))
    case("skills-empty-description", "skills", edit(skill, lambda t: t.replace("description: Use when the user asks about the demo.", "description:")))
    case("skills-long-description", "skills", edit(skill, lambda t: t.replace("the demo.", "x" * 1600)))
    case("skills-unquoted-colon", "skills", edit(skill, lambda t: t.replace("about the demo.", "about this: the demo.")))
    case("skill-refs-missing-file", "skill-refs", edit(skill, lambda t: t.replace("notes.md", "gone.md")))
    case("secrets-rule-missing", "secrets-rule", edit(skill, lambda t: t.replace("Never reproduce secrets", "Be careful")))
    mcp_case("mcp-http-url", "mcp", {"s": {"type": "http", "url": "http://mcp.example.com"}})
    mcp_case("mcp-env-header", "mcp", {"s": {"type": "http", "url": "https://x.example.com", "headers": {"Authorization": "Bearer ${SOME_TOKEN}"}}})
    mcp_case("mcp-literal-header", "mcp", {"s": {"type": "http", "url": "https://x.example.com", "headers": {"X-Api-Key": "abc"}}})
    mcp_case("mcp-unpinned-npx", "mcp", {"s": {"command": "npx", "args": ["-y", "some-server@latest"]}})
    mcp_case("mcp-user-config-and-pinned-ok", None, {"s": {"type": "http", "url": "https://x.example.com", "headers": {"Authorization": "Bearer ${user_config.TOKEN}"}}, "l": {"command": "npx", "args": ["-y", "some-server@1.2.3"]}})
    case("credentials-env-bearer", "credentials", lambda r: write(r, "notes.txt", "curl -H 'Authorization: Bearer ${MY_TOKEN}' x\n"))
    case("credentials-literal-key", "credentials", lambda r: write(r, "notes.txt", "key sk-" + "a1B2c3D4e5F6g7H8i9J0k1L2\n"))
    case("naming-formerly-twice", "naming", lambda r: write(r, "notes.txt", "Cortex (formerly Embrace). Again, formerly Embrace.\n"))
    case("denylist-internal-channel", "denylist", edit(skill, lambda t: t + "\nPost it in #tech-support.\n"))
    case("denylist-promise", "denylist", edit(skill, lambda t: t + "\nWe’re tracking this.\n"))
    case("files-junk", "files", lambda r: write(r, f"{p}/skills/demo/.DS_Store", "x"))
    case("files-too-big", "files", lambda r: write(r, f"{p}/skills/demo/big.yaml", "a: b\n" * 60000))
    case("files-binary", "files", lambda r: write(r, f"{p}/skills/demo/x.zip", b"PK\x03\x04\x00\x00", "wb"))
    case("files-symlink", "files", lambda r: os.symlink("notes.md", os.path.join(r, p, "skills/demo/link.md")))
    case("files-short-readme", "files", lambda r: write(r, f"{p}/README.md", f"# Demo\n\n`/{PLUGIN}:demo` is short.\n"))
    case("docs-skill-not-in-readme", "docs", lambda r: write(r, "README.md", "no table\n"))
    case("docs-no-changelog-entry", "docs", lambda r: write(r, "CHANGELOG.md", "## [0.9.0]\n"))
    case("version-not-bumped-after-release", "version", edit(notes, lambda t: t + "more\n"), base="base", tag=True)
    case("version-not-bumped-unreleased", None, edit(notes, lambda t: t + "more\n"), base="base", expect_warn="version")
    case("version-bumped", None, bump, base="base", tag=True)

    if not scratch:
        shutil.rmtree(base_dir, ignore_errors=True)
    if failures:
        print(f"self-test failed: {', '.join(failures)}")
        return 1
    print("self-test passed")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", help="repository root to check (default: this repository)")
    ap.add_argument("--base", help="base ref for the version-bump check, such as origin/main")
    ap.add_argument("--baseline", help="baseline file (default: check-plugin-baseline.txt beside this script)")
    ap.add_argument("--self-test", action="store_true", help="run the checks against built-in good and broken fixtures")
    ap.add_argument("--scratch", help="with --self-test, keep the fixtures in this directory")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    here = os.path.dirname(os.path.abspath(__file__))
    if args.self_test:
        return self_test(args.scratch, args.verbose)
    root = os.path.abspath(args.root or os.path.join(here, ".."))
    baseline = load_baseline(args.baseline or os.path.join(here, "check-plugin-baseline.txt"))
    rep = run_checks(root, args.base, baseline)
    print_report(rep)
    return 1 if rep.fails else 0


if __name__ == "__main__":
    sys.exit(main())
