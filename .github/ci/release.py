#!/usr/bin/env python3
"""Cut a release from whatever landed on main since the last tag.

This repository is driven by Dependabot: most of what reaches main is an image
bump. A release here is therefore not an artefact anybody installs — it is a
named, deployable state of the fleet, and its notes have exactly one job: tell
the operator what changed on the hosts and what has to be redeployed.

Three decisions are made here, in order.

  1. Is a release warranted?
     Only if something DEPLOYABLE changed. The gate is the path: files under
     unraid/ and nas/ are the ones that end up on a host, everything else
     (workflows, CI scripts, README) is not. A docs-only or CI-only commit
     therefore produces no version, because it changes nothing you could
     deploy. Path is the honest test; a commit-type test would call a `ci:`
     commit that edits a compose file non-deployable, which is false.

  2. How big is the bump?
     Read from Conventional Commits, but with the semantics that matter to an
     operator rather than to an API consumer:

       major  a `!` marker or a BREAKING CHANGE footer -> deploying needs a
              manual step first (new variable, network recreation, data move)
       minor  a `feat:` -> a new service or capability
       patch  everything else, which is what a Dependabot batch is

  3. What do the notes say?
     The image table comes first, because on a Dependabot release it is the
     entire content of the change. Then the stacks that need redeploying,
     derived from the same paths as decision 1, so the note doubles as a
     deployment checklist.

Images are read straight from the `image:` lines rather than through
`docker compose config`: every image in this repository is a literal, no
interpolation is involved, and this way the script needs neither Docker nor the
env templates to describe a tag that is already in the past.

Usage:
    release.py --dry-run            decide and print, touch nothing
    release.py --dry-run --since X  same, but pretend the last tag was X
    release.py --emit DIR           write notes to DIR and print the version
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Only these trees are deployed to a host. Everything else is repository
# machinery and must not, on its own, produce a version.
DEPLOYED_TREES = ("unraid/", "nas/")

STACK_OF_PATH = re.compile(r"^((?:unraid|nas)/[a-z0-9-]+)/")
IMAGE_LINE = re.compile(r"^\s*image:\s*(\S+)\s*$")
VERSION_TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
CONVENTIONAL = re.compile(r"^(?P<type>[a-z]+)(?:\((?P<scope>[^)]*)\))?(?P<bang>!)?:\s*(?P<desc>.+)$")

# Conventional-commit type -> heading in the notes. Order is the display order.
SECTIONS = [
    ("feat", "New capabilities"),
    ("fix", "Fixes"),
    ("perf", "Performance"),
    ("refactor", "Refactoring"),
    ("chore", "Dependencies and chores"),
    ("docs", "Documentation"),
    ("ci", "CI"),
    ("style", "Style"),
    ("test", "Tests"),
]


def git(*args: str) -> str:
    result = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def last_tag() -> str | None:
    """Highest v<major>.<minor>.<patch> tag, by version rather than by date."""
    tags = []
    for line in git("tag", "--list", "v*").splitlines():
        match = VERSION_TAG.match(line.strip())
        if match:
            tags.append((tuple(int(p) for p in match.groups()), line.strip()))
    return max(tags)[1] if tags else None


def commits_since(ref: str | None) -> list[dict]:
    """Subject and body of every commit after `ref`, oldest first."""
    span = f"{ref}..HEAD" if ref else "HEAD"
    raw = git("log", "--reverse", "--format=%H%x00%s%x00%b%x1e", span)
    commits = []
    for record in raw.split("\x1e"):
        record = record.strip("\n")
        if not record:
            continue
        sha, subject, body = record.split("\x00")
        # A release commit is bookkeeping this script wrote itself; it must not
        # show up as a change in the next release's notes.
        if subject.startswith("chore(release)"):
            continue
        parsed = CONVENTIONAL.match(subject)
        commits.append({
            "sha": sha[:7],
            "subject": subject,
            "type": parsed.group("type") if parsed else None,
            "scope": parsed.group("scope") if parsed else None,
            "desc": parsed.group("desc") if parsed else subject,
            "breaking": bool(parsed and parsed.group("bang")) or "BREAKING CHANGE:" in body,
        })
    return commits


def changed_paths(ref: str | None) -> list[str]:
    span = f"{ref}..HEAD" if ref else "HEAD"
    return [p for p in git("diff", "--name-only", span).splitlines() if p]


def images_at(ref: str) -> dict[str, tuple[str, str]]:
    """image repository -> (tag, stack), as pinned at `ref`."""
    found: dict[str, tuple[str, str]] = {}
    for path in git("ls-tree", "-r", "--name-only", ref).splitlines():
        if not path.endswith("compose.yml"):
            continue
        stack = path.rsplit("/", 1)[0]
        for line in git("show", f"{ref}:{path}").splitlines():
            match = IMAGE_LINE.match(line)
            if not match:
                continue
            reference = match.group(1)
            repository, _, tag = reference.rpartition(":")
            if not repository:                     # no tag at all
                repository, tag = reference, "latest"
            found[repository] = (tag, stack)
    return found


def bump(commits: list[dict]) -> str:
    if any(c["breaking"] for c in commits):
        return "major"
    if any(c["type"] == "feat" for c in commits):
        return "minor"
    return "patch"


def next_version(tag: str | None, level: str) -> str:
    # An unparseable ref counts as no previous version. Only --since can produce
    # one, but a release must never crash on a malformed or missing tag.
    match = VERSION_TAG.match(tag) if tag else None
    major, minor, patch = (int(p) for p in match.groups()) if match else (0, 0, 0)
    if level == "major":
        return f"v{major + 1}.0.0"
    if level == "minor":
        return f"v{major}.{minor + 1}.0"
    return f"v{major}.{minor}.{patch + 1}"


def render(version: str, previous: str | None, commits: list[dict], paths: list[str]) -> str:
    lines: list[str] = []

    # --- images first: on a Dependabot release this is the whole story
    before = images_at(previous) if previous else {}
    after = images_at("HEAD")
    moved = sorted(r for r in after if r in before and before[r][0] != after[r][0])
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))

    if moved or added or removed:
        lines += ["## Images", "", "| Stack | Image | From | To |", "| --- | --- | --- | --- |"]
        for repository in moved:
            lines.append(f"| `{after[repository][1]}` | `{repository}` | `{before[repository][0]}` | `{after[repository][0]}` |")
        for repository in added:
            lines.append(f"| `{after[repository][1]}` | `{repository}` | — | `{after[repository][0]}` |")
        for repository in removed:
            lines.append(f"| `{before[repository][1]}` | `{repository}` | `{before[repository][0]}` | removed |")
        lines.append("")
    else:
        lines += ["## Images", "", "No image changed in this release.", ""]

    # --- the note doubles as a deployment checklist
    stacks = sorted({m.group(1) for p in paths if (m := STACK_OF_PATH.match(p))})
    lines += ["## Redeploy", ""]
    if stacks:
        # edge owns the shared networks, so it always goes first when involved.
        ordered = sorted(stacks, key=lambda s: (s != "unraid/edge", s))
        # One block, in dependency order, so the whole thing is a single paste.
        lines.append("```bash")
        for stack in ordered:
            host = stack.split("/")[0]
            lines.append(f"docker compose --env-file {host}/.env -f {stack}/compose.yml up -d")
        lines.append("```")
        if "unraid/edge" in stacks:
            lines += ["", "`unraid/edge` is listed first because it is the only stack that defines the shared networks."]
    else:
        lines.append("Nothing to redeploy.")
    lines.append("")

    # --- changes, grouped
    lines += ["## Changes", ""]
    breaking = [c for c in commits if c["breaking"]]
    if breaking:
        lines += ["### Breaking — a manual step is required before deploying", ""]
        lines += [f"- {c['desc']} ({c['sha']})" for c in breaking]
        lines.append("")
    for kind, heading in SECTIONS:
        listed = [c for c in commits if c["type"] == kind and not c["breaking"]]
        if not listed:
            continue
        lines += [f"### {heading}", ""]
        for c in listed:
            scope = f"**{c['scope']}**: " if c["scope"] else ""
            lines.append(f"- {scope}{c['desc']} ({c['sha']})")
        lines.append("")

    other = [c for c in commits if c["type"] not in {k for k, _ in SECTIONS} and not c["breaking"]]
    if other:
        lines += ["### Other", ""] + [f"- {c['subject']} ({c['sha']})" for c in other] + [""]

    if previous:
        repo = git("config", "--get", "remote.origin.url").strip()
        slug = re.sub(r"^.*[:/]([^/]+/[^/]+?)(?:\.git)?$", r"\1", repo)
        lines.append(f"**Full diff**: https://github.com/{slug}/compare/{previous}...{version}")

    return "\n".join(lines).rstrip() + "\n"


def prepend_changelog(version: str, notes: str) -> None:
    """Insert the entry at the TOP: a changelog is read newest first."""
    path = ROOT / "CHANGELOG.md"
    header = (
        "# Changelog\n"
        "\n"
        "Every entry is a deployable state of the fleet. Releases are cut automatically\n"
        "when something under `unraid/` or `nas/` changes; documentation and CI changes\n"
        "do not produce a version because they change nothing you could deploy.\n"
    )
    date = git("log", "-1", "--format=%ad", "--date=short").strip()
    # The notes are written for a release page, where they start at level 2.
    # Nested under a version heading they have to move down one level.
    nested = re.sub(r"^(#{2,})", r"#\1", notes, flags=re.M)
    entry = f"## {version} — {date}\n\n{nested.rstrip()}\n"

    existing = path.read_text() if path.exists() else header
    # Anchor on a version heading specifically: the entry body also contains
    # "## " headings, and splitting on those would nest a release inside another.
    match = re.search(r"^## v\d", existing, flags=re.M)
    preamble = existing[: match.start()] if match else existing
    rest = existing[match.start():] if match else ""
    path.write_text(f"{preamble.rstrip()}\n\n{entry}\n{rest}".rstrip() + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--since", help="pretend this is the last tag (testing only)")
    parser.add_argument("--emit", help="directory to write NOTES.md into")
    args = parser.parse_args()

    previous = args.since or last_tag()
    commits = commits_since(previous)
    paths = changed_paths(previous)
    deployable = [p for p in paths if p.startswith(DEPLOYED_TREES)]

    print(f"previous tag : {previous or '(none)'}")
    print(f"commits      : {len(commits)}")
    print(f"changed files: {len(paths)} ({len(deployable)} deployable)")

    if not commits:
        print("decision     : no release — nothing landed since the last tag")
        return 0
    if not deployable:
        print("decision     : no release — nothing under unraid/ or nas/ changed")
        for p in paths:
            print(f"               untouched by deploy: {p}")
        return 0

    level = bump(commits)
    version = next_version(previous, level)
    print(f"decision     : release {version} ({level})")

    notes = render(version, previous, commits, paths)
    if args.dry_run:
        print("\n" + "=" * 70 + "\n" + notes)
        return 0

    prepend_changelog(version, notes)
    if args.emit:
        # VERSION exists only when a release was decided; the workflow keys the
        # whole tag-and-publish sequence off its presence.
        out = Path(args.emit)
        out.mkdir(parents=True, exist_ok=True)
        (out / "NOTES.md").write_text(notes)
        (out / "VERSION").write_text(version)
    print(f"::notice::released {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
