#!/usr/bin/env python3
"""Partial structural check of the Traefik dynamic configuration.

This is a PARTIAL STRUCTURAL CHECK, not a validation of Traefik configuration.
Traefik ships no configuration validator (its only subcommands are `healthcheck`
and `version`), so this script deliberately verifies a narrow, mechanical set of
properties and claims nothing beyond them.

What it checks:
  * every dynamic file renders with the supported template forms and parses as YAML
  * every router's `service` reference resolves to a service defined in these
    files, or to a built-in @internal provider
  * every entry of a router's `middlewares` LIST resolves to a defined middleware
  * every loadBalancer server `url` is a well-formed absolute http(s) URL

What it explicitly does NOT check:
  * the syntax or semantics of a router `rule` expression
  * whether middleware options are valid for their type
  * entryPoint names, TLS options, or anything in the static traefik.yml
  * that a backend is actually reachable

References are resolved by reading the parsed `middlewares` list as a list. A
substring search would be wrong: `service: 'authelia@file'` contains the text
`authelia@file` without the router carrying that middleware at all.
"""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlparse

import yaml

sys.path.insert(0, str(Path(__file__).parent))

from render_templates import TemplateError, load_env, render_file  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DYNAMIC_DIR = ROOT / "unraid/edge/config/traefik/dynamic"
ENV_FILE = ROOT / "unraid/.env.example"

BUILTIN_PROVIDERS = {"internal"}

errors: list[str] = []
documents: dict[Path, dict] = {}

env = load_env(ENV_FILE)

for path in sorted(DYNAMIC_DIR.glob("*.yml")):
    try:
        rendered = render_file(path, env)
    except TemplateError as exc:
        errors.append(f"template: {exc}")
        continue
    try:
        documents[path] = yaml.safe_load(rendered) or {}
    except yaml.YAMLError as exc:
        errors.append(f"yaml: {path.relative_to(ROOT)}: {exc}")

if errors:
    print("Traefik partial structural check FAILED", file=sys.stderr)
    for error in errors:
        print(f"  - {error}", file=sys.stderr)
    sys.exit(1)


def collect(section: str) -> dict[str, Path]:
    found: dict[str, Path] = {}
    for path, doc in documents.items():
        for name in (doc.get("http", {}) or {}).get(section, {}) or {}:
            found[name] = path
    return found


services = collect("services")
middlewares = collect("middlewares")
routers = collect("routers")


def resolve(reference: str, defined: dict[str, Path], kind: str, where: str) -> None:
    if "@" not in reference:
        errors.append(f"{where}: {kind} reference '{reference}' has no @provider suffix")
        return
    name, provider = reference.rsplit("@", 1)
    if provider in BUILTIN_PROVIDERS:
        return
    if provider != "file":
        errors.append(f"{where}: {kind} reference '{reference}' uses unknown provider '{provider}'")
        return
    if name not in defined:
        errors.append(f"{where}: {kind} '{reference}' is not defined in any dynamic file")


for path, doc in documents.items():
    rel = path.relative_to(ROOT)
    http = doc.get("http", {}) or {}

    for router_name, router in (http.get("routers", {}) or {}).items():
        where = f"{rel}: router '{router_name}'"
        if not isinstance(router, dict):
            errors.append(f"{where}: expected a mapping")
            continue

        service = router.get("service")
        if service is None:
            errors.append(f"{where}: has no 'service'")
        else:
            resolve(str(service), services, "service", where)

        router_middlewares = router.get("middlewares", [])
        if router_middlewares and not isinstance(router_middlewares, list):
            errors.append(f"{where}: 'middlewares' must be a list, got {type(router_middlewares).__name__}")
        else:
            for reference in router_middlewares or []:
                resolve(str(reference), middlewares, "middleware", where)

    for service_name, service in (http.get("services", {}) or {}).items():
        where = f"{rel}: service '{service_name}'"
        servers = ((service or {}).get("loadBalancer", {}) or {}).get("servers", []) or []
        if not servers:
            errors.append(f"{where}: loadBalancer has no servers")
        for server in servers:
            url = (server or {}).get("url")
            if not url:
                errors.append(f"{where}: a server entry has no 'url'")
                continue
            parsed = urlparse(str(url))
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                errors.append(f"{where}: malformed server url '{url}'")

if errors:
    print("Traefik partial structural check FAILED", file=sys.stderr)
    for error in errors:
        print(f"  - {error}", file=sys.stderr)
    sys.exit(1)

print(
    f"Traefik partial structural check passed: {len(documents)} file(s), "
    f"{len(routers)} router(s), {len(services)} service(s), {len(middlewares)} middleware(s)."
)
print("Scope: reference resolution and URL shape only; rule syntax and middleware")
print("options are not validated (Traefik ships no configuration validator).")
