#!/usr/bin/env python3
"""Cross-file authentication invariants between Traefik and Authelia.

Protecting a route takes an edit in two places, and doing only one of them fails
silently. These three checks make that failure loud.

  A. Pair integrity
     A two_factor rule carrying a `subject` must be IMMEDIATELY followed by a
     deny rule for the same domain and the same resources. Without the deny, the
     trailing `*.${DOMAIN}` one_factor catch-all matches instead and the admin
     surface is quietly downgraded to single-factor.

  B. No dead-letter policy
     Every domain named in access_control (bypass rules and the catch-all
     excluded) must be served by a Traefik router that attaches the
     authelia@file middleware. Without the middleware Authelia is never
     consulted: the policy exists on paper and the route is unauthenticated.

  C. No silent downgrade
     Every router that attaches authelia@file must have a dedicated
     access_control rule, otherwise it lands on the one_factor catch-all. Hosts
     for which that is intentional are declared in invariant-exceptions.yml.

Middlewares are read from the parsed YAML list. A substring search would be
wrong: `service: 'authelia@file'` contains that text without the router
carrying the middleware.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))

from render_templates import TemplateError, load_env, render_file  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DYNAMIC_DIR = ROOT / "unraid/edge/config/traefik/dynamic"
AUTHELIA_CONFIG = ROOT / "unraid/edge/config/authelia/configuration.yml"
EXCEPTIONS_FILE = ROOT / ".github/ci/invariant-exceptions.yml"
ENV_FILE = ROOT / "unraid/.env.example"

AUTH_MIDDLEWARE = "authelia@file"
HOST_MATCHER = re.compile(r"Host\(`([^`]+)`\)")

errors: list[str] = []
env = load_env(ENV_FILE)

exceptions = yaml.safe_load(EXCEPTIONS_FILE.read_text()) or {}
auth_exceptions = exceptions.get("auth", {}) or {}
intentional_one_factor = set(auth_exceptions.get("intentional_one_factor") or [])
allow_unpaired = set(auth_exceptions.get("allow_unpaired_two_factor") or [])

try:
    authelia = yaml.safe_load(render_file(AUTHELIA_CONFIG, env)) or {}
except (TemplateError, yaml.YAMLError) as exc:
    sys.exit(f"cannot read Authelia configuration: {exc}")

routers: dict[str, dict] = {}
for path in sorted(DYNAMIC_DIR.glob("*.yml")):
    try:
        document = yaml.safe_load(render_file(path, env)) or {}
    except (TemplateError, yaml.YAMLError) as exc:
        sys.exit(f"cannot read {path.relative_to(ROOT)}: {exc}")
    for name, router in ((document.get("http", {}) or {}).get("routers", {}) or {}).items():
        routers[name] = router or {}


def as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def rule_key(rule: dict) -> tuple:
    """Identity of a rule for pairing purposes: its domains and its resources."""
    return (
        tuple(sorted(as_list(rule.get("domain")))),
        tuple(sorted(as_list(rule.get("resources")))),
    )


def protected_hosts() -> dict[str, set[str]]:
    """Router name -> hosts it matches, for routers attaching authelia@file."""
    result: dict[str, set[str]] = {}
    for name, router in routers.items():
        middlewares = router.get("middlewares")
        if not isinstance(middlewares, list):
            continue
        if AUTH_MIDDLEWARE not in [str(item) for item in middlewares]:
            continue
        result[name] = set(HOST_MATCHER.findall(str(router.get("rule", ""))))
    return result


rules = ((authelia.get("access_control", {}) or {}).get("rules") or [])
protected = protected_hosts()
all_protected_hosts = {host for hosts in protected.values() for host in hosts}

# ---------------------------------------------------------------- check A
pairs_found = 0
for index, rule in enumerate(rules):
    if rule.get("policy") != "two_factor" or not rule.get("subject"):
        continue
    domains = as_list(rule.get("domain"))
    label = ", ".join(domains)
    if set(domains) & allow_unpaired:
        print(f"  waived  unpaired two_factor for {label}")
        continue
    following = rules[index + 1] if index + 1 < len(rules) else None
    if (
        following is None
        or following.get("policy") != "deny"
        or rule_key(following) != rule_key(rule)
        or following.get("subject")
    ):
        errors.append(
            f"A: two_factor rule for {label} is not immediately followed by an "
            f"equivalent deny rule; the one_factor catch-all will match instead"
        )
        continue
    pairs_found += 1
    print(f"  ok  pair    {label}")

# ---------------------------------------------------------------- check B
for rule in rules:
    if rule.get("policy") == "bypass":
        continue
    for domain in as_list(rule.get("domain")):
        if domain.startswith("*."):
            continue
        if domain not in all_protected_hosts:
            errors.append(
                f"B: access_control names {domain} but no Traefik router matching "
                f"that host attaches {AUTH_MIDDLEWARE}; the policy is never consulted"
            )

# ---------------------------------------------------------------- check C
dedicated_domains = {
    domain
    for rule in rules
    if rule.get("policy") != "bypass"
    for domain in as_list(rule.get("domain"))
    if not domain.startswith("*.")
}
for name, hosts in sorted(protected.items()):
    uncovered = sorted(host for host in hosts if host not in dedicated_domains)
    if not uncovered:
        continue
    if name in intentional_one_factor:
        print(f"  waived  one_factor for router '{name}' ({', '.join(uncovered)})")
        continue
    errors.append(
        f"C: router '{name}' attaches {AUTH_MIDDLEWARE} but {', '.join(uncovered)} "
        f"has no dedicated access_control rule, so it falls through to the "
        f"one_factor catch-all"
    )

if errors:
    print("\nauth invariants FAILED", file=sys.stderr)
    for error in errors:
        print(f"  - {error}", file=sys.stderr)
    sys.exit(1)

print(
    f"\nauth invariants passed: {pairs_found} two_factor/deny pair(s), "
    f"{len(protected)} protected router(s), {len(intentional_one_factor)} documented exception(s)."
)
