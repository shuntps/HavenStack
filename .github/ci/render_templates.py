"""Renderer for the Go template forms used by the Traefik and Authelia configs.

Both services read their configuration through Go's text/template — Traefik via
its file provider, Authelia via `--config.experimental.filters template`. Only
two forms appear anywhere in this repository:

    {{ env "VAR" }}
    {{ env "VAR" | replace "OLD" "NEW" }}

This module renders exactly those two and refuses everything else. Refusing is
the entire point: an unsupported construct that rendered to an empty string
would still produce parseable YAML, and the mistake would only surface at
deployment time. An undefined variable is likewise an error rather than an
empty string.
"""

from __future__ import annotations

import re
from pathlib import Path

TOKEN = re.compile(r"\{\{(.*?)\}\}", re.DOTALL)

_IDENT = r"[A-Za-z_][A-Za-z0-9_]*"
_GOSTR = r'"(?:[^"\\]|\\.)*"'

ENV_SIMPLE = re.compile(rf'^\s*env\s+"({_IDENT})"\s*$')
ENV_REPLACE = re.compile(
    rf'^\s*env\s+"({_IDENT})"\s*\|\s*replace\s+({_GOSTR})\s+({_GOSTR})\s*$'
)

_ESCAPES = {"\\": "\\", '"': '"', "n": "\n", "t": "\t", "r": "\r"}


class TemplateError(Exception):
    """Raised for an unsupported construct, an undefined variable, or a residue."""


def _unquote(literal: str) -> str:
    """Interpret a Go double-quoted string literal."""
    body = literal[1:-1]
    out, i = [], 0
    while i < len(body):
        char = body[i]
        if char == "\\" and i + 1 < len(body):
            nxt = body[i + 1]
            if nxt not in _ESCAPES:
                raise TemplateError(f'unsupported escape "\\{nxt}" in {literal}')
            out.append(_ESCAPES[nxt])
            i += 2
            continue
        out.append(char)
        i += 1
    return "".join(out)


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1].strip()
    return value


def load_env(path: str | Path) -> dict[str, str]:
    """Read a KEY=VALUE template such as unraid/.env.example."""
    env: dict[str, str] = {}
    for raw in Path(path).read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if re.fullmatch(_IDENT, key):
            env[key] = _strip_quotes(value)
    return env


def render(text: str, env: dict[str, str], source: str = "<string>") -> str:
    """Render the supported template forms, raising TemplateError otherwise."""

    def line_of(offset: int) -> int:
        return text.count("\n", 0, offset) + 1

    def lookup(name: str, line: int) -> str:
        if name not in env:
            raise TemplateError(f'{source}:{line}: undefined variable "{name}"')
        return env[name]

    def substitute(match: re.Match[str]) -> str:
        inner, line = match.group(1), line_of(match.start())

        simple = ENV_SIMPLE.match(inner)
        if simple:
            return lookup(simple.group(1), line)

        replaced = ENV_REPLACE.match(inner)
        if replaced:
            value = lookup(replaced.group(1), line)
            return value.replace(_unquote(replaced.group(2)), _unquote(replaced.group(3)))

        raise TemplateError(
            f"{source}:{line}: unsupported template construct {{{{{inner}}}}}. "
            'Only {{ env "VAR" }} and {{ env "VAR" | replace "OLD" "NEW" }} are supported.'
        )

    rendered = TOKEN.sub(substitute, text)

    # Residue is detected on the original text with every valid token removed, so
    # that braces occurring inside a substituted *value* cannot raise a false
    # positive. What remains can only be an unbalanced or malformed delimiter.
    residue = TOKEN.sub("", text)
    for delimiter in ("{{", "}}"):
        index = residue.find(delimiter)
        if index != -1:
            raise TemplateError(
                f'{source}:{residue.count(chr(10), 0, index) + 1}: '
                f'unbalanced template delimiter "{delimiter}"'
            )

    return rendered


def render_file(path: str | Path, env: dict[str, str]) -> str:
    path = Path(path)
    return render(path.read_text(), env, source=str(path))
