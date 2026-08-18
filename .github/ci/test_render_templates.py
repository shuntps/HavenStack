#!/usr/bin/env python3
"""Self-test for render_templates.py.

Runs before the Traefik reference check so the validator is itself validated on
every CI run. The two accepted forms below are the exhaustive inventory of what
appears in this repository today; the rejection cases are what stop a future
unsupported construct from being silently rendered away.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from render_templates import TemplateError, render  # noqa: E402

ENV = {"DOMAIN": "example.com", "NAS_IP": "192.168.1.10"}

ACCEPTED = [
    ("simple form", '{{ env "DOMAIN" }}', "example.com"),
    ("pipe replace", r'{{ env "DOMAIN" | replace "." "\\." }}', r"example\.com"),
    ("no inner spacing", '{{env "DOMAIN"}}', "example.com"),
    ("wide inner spacing", '{{    env     "DOMAIN"    }}', "example.com"),
    ("two tokens on one line", '{{ env "DOMAIN" }}:{{ env "NAS_IP" }}', "example.com:192.168.1.10"),
    ("token inside surrounding text", 'Host(`traefik.{{ env "DOMAIN" }}`)', "Host(`traefik.example.com`)"),
    (
        "real middlewares.yml line",
        r"""regex: '^https?://www\.{{ env "DOMAIN" | replace "." "\\." }}/(.*)'""",
        r"""regex: '^https?://www\.example\.com/(.*)'""",
    ),
]

REJECTED = [
    ("unknown pipe function", '{{ env "DOMAIN" | upper }}', "unsupported template construct"),
    ("conditional construct", '{{ if eq .X "y" }}', "unsupported template construct"),
    ("dot field access", "{{ .Values.domain }}", "unsupported template construct"),
    ("bare function", "{{ printf \"%s\" \"x\" }}", "unsupported template construct"),
    ("undefined variable", '{{ env "ABSENT" }}', 'undefined variable "ABSENT"'),
    ("unbalanced opening", '{{ env "DOMAIN" }', "unbalanced template delimiter"),
    ("unbalanced closing", 'value }} tail', "unbalanced template delimiter"),
]

failures: list[str] = []

for name, template, expected in ACCEPTED:
    try:
        got = render(template, ENV, source="test")
    except TemplateError as exc:
        failures.append(f"ACCEPT {name}: raised unexpectedly: {exc}")
        continue
    if got != expected:
        failures.append(f"ACCEPT {name}: expected {expected!r}, got {got!r}")
    else:
        print(f"  ok   accept  {name}")

for name, template, fragment in REJECTED:
    try:
        got = render(template, ENV, source="test")
    except TemplateError as exc:
        if fragment not in str(exc):
            failures.append(f"REJECT {name}: wrong message: {exc}")
        else:
            print(f"  ok   reject  {name}")
        continue
    failures.append(f"REJECT {name}: should have raised, returned {got!r}")

if failures:
    print("\nrenderer self-test FAILED:", file=sys.stderr)
    for failure in failures:
        print(f"  - {failure}", file=sys.stderr)
    sys.exit(1)

print(f"\nrenderer self-test passed: {len(ACCEPTED)} accepted, {len(REJECTED)} rejected")
