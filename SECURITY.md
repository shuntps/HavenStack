# Security Policy

HavenStack is a reference homelab deployment. Its security-relevant surface
includes the Compose files, Traefik and Authelia configuration, the
documented exposure boundaries, and the guidance in the documentation.

## Reporting a vulnerability

Please do not open a public issue for a vulnerability.

Report it privately through
[GitHub private vulnerability reporting](https://github.com/shuntps/HavenStack/security/advisories/new).

Include:

- the affected file, service, or documentation page;
- the deployment context in which the problem applies;
- reproduction steps or a configuration excerpt, with all secrets,
  tokens, real domains, and IP addresses removed;
- the impact you expect, for example exposure of a service that the
  [exposure matrix](docs/security/exposure-matrix.md) documents as private.

You should receive an acknowledgement within a few days. Coordinated
disclosure is appreciated: please allow a fix to be published before
sharing details publicly.

## Scope

In scope:

- configuration in this repository that exposes a service more widely than
  the [exposure matrix](docs/security/exposure-matrix.md) documents;
- authentication or middleware gaps in the tracked Traefik and Authelia
  configuration;
- documentation that instructs users to do something unsafe;
- CI workflows that could leak secrets or run untrusted code.

Out of scope:

- vulnerabilities in upstream projects (Traefik, Authelia, Nextcloud,
  Vaultwarden, Plex, and the other containerized services); report those upstream;
- issues that only occur after a user deviates from the documented
  configuration;
- the security of any individual's private deployment.

## Hardening guidance

The documentation describes the intended boundaries and safe operation:

- [Exposure matrix](docs/security/exposure-matrix.md)
- [Secrets and credentials](docs/security/secrets.md)
- [First-run checklist](docs/getting-started/first-run-checklist.md)

Keep images updated through the weekly Dependabot pull requests and review
upstream release notes before deploying.
