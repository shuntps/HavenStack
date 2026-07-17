# HavenStack

<p align="center">
  <img src="docs/images/havenstack-banner.png" alt="HavenStack - Secure, private, self-hosted infrastructure" width="100%">
</p>

<p align="center">
  A modular, security-focused homelab built with Docker Compose across Unraid and NAS infrastructure.
</p>

<p align="center">
  <a href="https://github.com/shuntps/HavenStack/actions/workflows/validate-compose.yml"><img src="https://github.com/shuntps/HavenStack/actions/workflows/validate-compose.yml/badge.svg?branch=main" alt="Compose validation status"></a>
  <a href="https://github.com/shuntps/HavenStack/actions/workflows/validate-docs.yml"><img src="https://github.com/shuntps/HavenStack/actions/workflows/validate-docs.yml/badge.svg?branch=main" alt="Documentation validation status"></a>
  <a href="https://github.com/shuntps/HavenStack/releases/latest"><img src="https://img.shields.io/github/v/release/shuntps/HavenStack" alt="Latest release"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/shuntps/HavenStack" alt="License"></a>
</p>

## Overview

- Cloudflare Tunnel ingress through Traefik
- Central authentication and access policies with Authelia
- Private applications including Nextcloud and Vaultwarden
- Media automation with the Servarr ecosystem and VPN-protected qBittorrent
- Monitoring with Prometheus, Grafana, and Blackbox Exporter
- Segmented Docker networks, health checks, resource limits, and hardened containers

## Stacks

| Location | Stack | Services |
| --- | --- | --- |
| Unraid | Edge | Traefik, Authelia, Cloudflare Tunnel, Cloudflare DDNS |
| Unraid | Apps | Homepage, Vaultwarden |
| Unraid | Nextcloud | Apache, Nextcloud, PostgreSQL, Redis, Notify Push |
| Unraid | Servarr | qBittorrent VPN, Prowlarr, Radarr, Sonarr, Seerr, Profilarr |
| Unraid | Monitoring | Prometheus, Grafana, Blackbox Exporter |
| NAS | Media | Plex |
| NAS | Management | Arcane |

## Repository layout

```text
HavenStack/
├── docs/
│   ├── getting-started/
│   ├── architecture/
│   ├── stacks/
│   ├── operations/
│   └── security/
├── unraid/
│   ├── edge/
│   ├── apps/
│   ├── nextcloud/
│   ├── servarr/
│   └── monitoring/
└── nas/
    ├── plex/
    └── arcane/
```

## Documentation

For a complete first installation, follow the [HavenStack documentation](docs/README.md). It covers prerequisites, host preparation, environment configuration, Cloudflare Tunnel routing, deployment order, first-run verification, operations, and security boundaries.

Start with the [Quick start](docs/getting-started/quick-start.md) instead of running the deployment commands below immediately.

After deployment, use the [stack guides](docs/stacks/README.md) for service-specific configuration and verification.

Before an update or recovery operation, review the [operations guides](docs/README.md#operations). Use the [exposure matrix](docs/security/exposure-matrix.md) to understand which services are public, LAN-accessible, or internal.

## Deployment

The commands below are a compact reference for an already prepared environment. For a new installation, use the [step-by-step deployment guide](docs/getting-started/deployment.md).

Create and configure the environment files before starting any stack:

```bash
cp unraid/.env.example unraid/.env
cp nas/.env.example nas/.env
```

Deploy the Unraid stacks in order:

```bash
docker compose --env-file unraid/.env -f unraid/edge/compose.yml up -d
docker compose --env-file unraid/.env -f unraid/apps/compose.yml up -d
docker compose --env-file unraid/.env -f unraid/nextcloud/compose.yml up -d
docker compose --env-file unraid/.env -f unraid/servarr/compose.yml up -d
docker compose --env-file unraid/.env -f unraid/monitoring/compose.yml up -d
```

Deploy the required NAS stacks separately:

```bash
docker compose --env-file nas/.env -f nas/plex/compose.yml up -d
docker compose --env-file nas/.env -f nas/arcane/compose.yml up -d
```

Review all paths, user IDs, network ranges, domains, and secrets before deployment. Never commit populated environment files.

### Required local configuration

- Copy `unraid/edge/config/authelia/users.yml.example` to `users.yml` and replace the example password with an Argon2id hash.
- Place one provider-supplied OpenVPN profile and its certificates in the qBittorrent `/config/openvpn` directory.
- Ensure the configured Nextcloud data path exists and is writable before starting the stack.

These files and runtime data are intentionally excluded from Git.

## Contributing

Contributions are welcome. Read the [contributing guide](CONTRIBUTING.md) and the [code of conduct](CODE_OF_CONDUCT.md) first. Report vulnerabilities privately as described in the [security policy](SECURITY.md), never in a public issue.

## License

Licensed under the terms of the [LICENSE](LICENSE) file.
