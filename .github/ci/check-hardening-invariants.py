#!/usr/bin/env python3
"""Service hardening baseline, enforced across every stack.

CLAUDE.md and the README describe a hardening baseline and a short list of
services that cannot meet it. Prose drifts: a service added without a
healthcheck, or an exception that stops being necessary after an upstream fix,
both leave the documentation quietly wrong. These checks keep the list honest.

Services are read from `docker compose config`, not from the YAML source, so
anchors, merge keys and `.env.example` interpolation are resolved exactly as
they will be on the host.

  A. Waivable baseline
     Every service carries a healthcheck, a read-only root filesystem with
     `cap_drop: [ALL]`, and a pinned image tag — unless it is listed under the
     matching key in invariant-exceptions.yml.

  B. Unwaivable baseline
     Every service carries `mem_limit`, `restart: unless-stopped`,
     `security_opt: [no-new-privileges:true]` and the shared json-file logging
     anchor. These have no exception list on purpose.

  C. No stale waiver
     A service listed as an exception that now satisfies the invariant is an
     error, not a pass: the waiver has outlived its reason and the comment
     justifying it has become misleading. Same for a waiver naming a service
     that no longer exists.

The stack list is spelled out here on purpose, matching check-env-templates.sh;
dynamic discovery is a later change.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
EXCEPTIONS_FILE = ROOT / ".github/ci/invariant-exceptions.yml"

STACKS = [("unraid", "edge"), ("unraid", "apps"), ("unraid", "servarr"),
          ("nas", "plex"), ("nas", "arcane")]

errors: list[str] = []
waived: list[str] = []

exceptions = yaml.safe_load(EXCEPTIONS_FILE.read_text()) or {}
hardening = exceptions.get("hardening", {}) or {}


def waiver(key: str) -> set[str]:
    return set(hardening.get(key) or [])


def load_services() -> dict[str, dict]:
    """service name -> resolved definition, across every stack."""
    services: dict[str, dict] = {}
    for host, stack in STACKS:
        command = [
            "docker", "compose",
            "--env-file", str(ROOT / host / ".env.example"),
            "-f", str(ROOT / host / stack / "compose.yml"),
            "config", "--format", "json",
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            sys.exit(f"cannot render {host}/{stack}: {result.stderr.strip()}")
        for name, service in (json.loads(result.stdout).get("services") or {}).items():
            services[name] = service or {}
    return services


def is_pinned(image: str) -> bool:
    """A tag other than `latest`, or a digest, counts as pinned."""
    if "@sha256:" in image:
        return True
    last = image.rsplit("/", 1)[-1]          # strip any registry host:port
    if ":" not in last:
        return False                          # implicit :latest
    return last.rsplit(":", 1)[1] != "latest"


services = load_services()

CHECKS = {
    "no_healthcheck": (
        "healthcheck",
        lambda s: bool(s.get("healthcheck")),
    ),
    "writable_rootfs": (
        "read_only + cap_drop:[ALL]",
        lambda s: bool(s.get("read_only")) and "ALL" in (s.get("cap_drop") or []),
    ),
    "unpinned_image": (
        "pinned image tag",
        lambda s: is_pinned(str(s.get("image", ""))),
    ),
}

# ---------------------------------------------------------------- check A / C
for key, (label, satisfied) in CHECKS.items():
    allowed = waiver(key)
    for name in sorted(services):
        ok = satisfied(services[name])
        if not ok and name not in allowed:
            errors.append(f"A: service '{name}' has no {label} and is not listed under hardening.{key}")
        elif not ok:
            waived.append(f"  waived  {label:26} {name}")
    for name in sorted(allowed - set(services)):
        errors.append(f"C: hardening.{key} waives '{name}', which is not a service in any stack")
    for name in sorted(allowed & set(services)):
        if satisfied(services[name]):
            errors.append(
                f"C: hardening.{key} waives '{name}', but it now satisfies {label}; "
                f"remove the waiver so its justification stops being misleading"
            )

# ---------------------------------------------------------------- check B
UNWAIVABLE = {
    "mem_limit": lambda s: bool(s.get("mem_limit")),
    "restart: unless-stopped": lambda s: s.get("restart") == "unless-stopped",
    "security_opt: no-new-privileges:true":
        lambda s: "no-new-privileges:true" in (s.get("security_opt") or []),
    "logging driver json-file": lambda s: (s.get("logging") or {}).get("driver") == "json-file",
}
for label, satisfied in UNWAIVABLE.items():
    for name in sorted(services):
        if not satisfied(services[name]):
            errors.append(f"B: service '{name}' is missing {label} (no exception is accepted for this)")

for line in waived:
    print(line)

if errors:
    print("\nhardening invariants FAILED", file=sys.stderr)
    for error in errors:
        print(f"  - {error}", file=sys.stderr)
    sys.exit(1)

print(
    f"\nhardening invariants passed: {len(services)} service(s) across {len(STACKS)} stack(s), "
    f"{len(waived)} documented waiver(s), {len(UNWAIVABLE)} unwaivable property(ies) verified."
)
