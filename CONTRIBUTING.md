# Contributing to HavenStack

Thank you for considering a contribution. HavenStack is a reference
deployment: changes must keep the Compose files, the documentation, and the
security boundaries consistent with each other.

## Before you start

- Read the [documentation](docs/README.md), especially the
  [architecture overview](docs/architecture/overview.md) and the
  [exposure matrix](docs/security/exposure-matrix.md).
- Search existing issues and pull requests before opening a new one.
- For a security problem, follow [SECURITY.md](SECURITY.md) instead of
  opening a public issue.

## Never commit secrets or private infrastructure details

- No populated `.env` files, tokens, passwords, VPN profiles, private keys,
  or `users.yml`. The `.gitignore` rules help, but they are not a guarantee.
- Screenshots must be sanitized before they are added: use `example.com`
  hostnames, documentation IP addresses such as `192.0.2.10` (RFC 5737),
  and generic account or tunnel names.
- Issue reports and logs must have passwords, tokens, cookies, and API keys
  removed without exception.

## How to propose a change

1. Fork the repository and create a topic branch from `main`.
2. Make focused commits using the repository's Conventional Commits style:
   `feat:`, `fix:`, `docs:`, `ci:`, or `chore:`.
3. Open a pull request against `main` and fill in the template.

Dependabot proposes image updates on Mondays. When an image tag changes,
update the documentation pages that mention the old version in the same pull
request; the documentation CI fails otherwise.

## Validate locally before pushing

Compose models (repeat for each stack you touched):

```bash
docker compose --env-file unraid/.env.example \
  -f unraid/edge/compose.yml config --quiet
```

Documentation links and anchors:

```bash
docker run --rm -v "$PWD:/input" -w /input lycheeverse/lychee:latest \
  --offline --include-fragments --no-progress --root-dir /input '**/*.md'
```

GitHub Actions workflows:

```bash
docker run --rm -v "$PWD:/repo" -w /repo rhysd/actionlint:latest -color
```

## Documentation conventions

- Documentation is written in English.
- Compose files are named `compose.yml`.
- Pinned image versions mentioned in the documentation must match the
  Compose files; CI enforces this.
- Use uppercase placeholders such as `ENVIRONMENT_FILE` in shell blocks,
  never `<angle-bracket>` placeholders that a shell would parse as
  redirections.
- Files use LF line endings; `.gitattributes` enforces this on commit.

## What is unlikely to be merged

- Changes that publish additional host ports or weaken authentication
  boundaries without a documented, reviewed reason.
- New services without a matching stack guide, exposure-matrix entry, and
  backup guidance.
- Screenshots or examples containing real domains, IPs, or credentials.
