#!/usr/bin/env bash
#
# Fails when a variable interpolated by a compose file is missing from its
# host's .env.example, or is present with an empty value.
#
# The list of required variables is produced by Compose itself: each stack is
# rendered against an empty env file, and Compose reports every variable it
# interpolates and cannot resolve. Deriving the list this way, rather than by
# grepping for ${...}, excludes three classes of false positive structurally:
#
#   * $$LITERAL escapes are never interpolated, so Compose stays silent
#   * ${VAR:-default} resolves, so Compose stays silent — correctly optional
#   * ${VAR} inside a YAML comment is dropped before interpolation happens
#
# Two implementation details matter and are easy to get wrong:
#
#   * Outside a TTY, Compose escapes the quotes in its warnings, emitting
#     The \"DOMAIN\" variable is not set. A pattern matching The "DOMAIN"
#     matches nothing in CI, which would leave this check permanently green.
#   * The runner's own environment can define a variable and suppress the
#     warning, hiding a genuinely missing key, so the probe runs under env -i.
#
# The stack list is spelled out here on purpose; dynamic discovery is a later
# change.

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../.."

UNRAID_STACKS=(edge apps servarr)
NAS_STACKS=(plex arcane)

ALLOWLIST_FILE='.github/ci/optional-vars.txt'
EMPTY_ENV="$(mktemp)"
trap 'rm -f "$EMPTY_ENV"' EXIT

# Every helper below tolerates an empty result: grep exits 1 when it matches
# nothing, which would abort the script under `set -e`.
allowlist() {
  { grep -vE '^[[:space:]]*(#|$)' "$ALLOWLIST_FILE" 2>/dev/null || true; } | tr -d '[:space:]'
}

# Normalise a newline-separated list into a sorted file, dropping blank lines.
to_file() {
  { printf '%s\n' "$1" | grep -v '^[[:space:]]*$' || true; } | sort -u > "$2"
}

count() { wc -l < "$1" | tr -d '[:space:]'; }

# Every variable Compose interpolates for the given stacks and cannot resolve.
required_vars() {
  local host="$1"; shift
  local stack
  for stack in "$@"; do
    env -i PATH="$PATH" HOME="$HOME" \
      docker compose --env-file "$EMPTY_ENV" -f "${host}/${stack}/compose.yml" config \
      2>&1 >/dev/null || true
  done | sed -nE 's/.*The \\?"([A-Za-z_][A-Za-z0-9_]*)\\?" variable is not set.*/\1/p' | sort -u
}

# KEY<TAB>VALUE, with surrounding whitespace and one layer of quotes removed,
# so that DOMAIN=, DOMAIN="" and DOMAIN='   ' are all seen as empty.
env_pairs() {
  awk '
    /^[[:space:]]*#/ { next }
    /^[[:space:]]*$/ { next }
    {
      eq = index($0, "=")
      if (eq == 0) next
      key = substr($0, 1, eq - 1)
      val = substr($0, eq + 1)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", key)
      if (key !~ /^[A-Za-z_][A-Za-z0-9_]*$/) next
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", val)
      if (length(val) >= 2) {
        first = substr(val, 1, 1)
        last  = substr(val, length(val), 1)
        if ((first == "\"" && last == "\"") || (first == "'\''" && last == "'\''")) {
          val = substr(val, 2, length(val) - 2)
          gsub(/^[[:space:]]+|[[:space:]]+$/, "", val)
        }
      }
      printf "%s\t%s\n", key, val
    }
  ' "$1"
}

defined_keys()  { env_pairs "$1" | cut -f1 | sort -u; }
non_empty_keys() { env_pairs "$1" | awk -F'\t' '$2 != "" { print $1 }' | sort -u; }

status=0
WORK="$(mktemp -d)"
trap 'rm -rf "$EMPTY_ENV" "$WORK"' EXIT
to_file "$(allowlist)" "$WORK/allowed"

check_host() {
  local host="$1"; shift
  local template="${host}/.env.example"

  to_file "$(required_vars "$host" "$@")" "$WORK/required"
  to_file "$(defined_keys "$template")" "$WORK/defined"
  to_file "$(non_empty_keys "$template")" "$WORK/non_empty"

  comm -23 "$WORK/required" "$WORK/defined" | comm -23 - "$WORK/allowed" > "$WORK/missing"
  comm -12 "$WORK/required" "$WORK/defined" \
    | comm -23 - "$WORK/non_empty" \
    | comm -23 - "$WORK/allowed" > "$WORK/empty"
  comm -13 "$WORK/required" "$WORK/defined" > "$WORK/orphan"

  printf '%s: %s variable(s) required across %s stack(s), %s defined\n' \
    "$template" "$(count "$WORK/required")" "$#" "$(count "$WORK/defined")"

  if [ -s "$WORK/missing" ]; then
    status=1
    printf '  ERROR missing from %s:\n' "$template"
    sed 's/^/    - /' "$WORK/missing"
  fi
  if [ -s "$WORK/empty" ]; then
    status=1
    printf '  ERROR present but empty in %s:\n' "$template"
    sed 's/^/    - /' "$WORK/empty"
  fi
  if [ -s "$WORK/orphan" ]; then
    printf '  notice: defined but never interpolated (not an error):\n'
    sed 's/^/    - /' "$WORK/orphan"
  fi
  if [ ! -s "$WORK/missing" ] && [ ! -s "$WORK/empty" ]; then
    printf '  ok: no missing or empty variable\n'
  fi
}

check_host unraid "${UNRAID_STACKS[@]}"
check_host nas "${NAS_STACKS[@]}"

exit "$status"
