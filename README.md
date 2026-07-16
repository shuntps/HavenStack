# HavenStack

**Your services. Your data. Your digital haven.**

HavenStack is a security-first, modular homelab built by [Shunt](https://github.com/shuntps). It uses Docker Compose to run media automation, private cloud services, secure remote access, and monitoring across Unraid and NAS infrastructure.

## Features

- Secure ingress with Traefik, Authelia, and Cloudflare Tunnel
- Media streaming and automation with Plex and the Servarr ecosystem
- Private cloud and password management with Nextcloud and Vaultwarden
- Monitoring and dashboards with Prometheus, Grafana, and Blackbox Exporter
- Isolated Docker networks, health checks, resource limits, and hardened containers
- Modular Compose stacks that can be deployed and maintained independently

## Included services

| Stack | Services |
| --- | --- |
| Edge | Traefik, Authelia, Cloudflare Tunnel, Cloudflare DDNS, Docker Socket Proxy |
| Apps | Homepage, Vaultwarden, Nextcloud AIO |
| Media | Plex, qBittorrent, Prowlarr, Radarr, Sonarr, Seerr, Profilarr |
| Monitoring | Prometheus, Grafana, Blackbox Exporter |
| Management | Arcane |

## Repository structure

```text
HavenStack/
├── unraid/
│   ├── edge/
│   ├── apps/
│   ├── servarr/
│   └── monitoring/
└── nas/
    ├── plex/
    └── arcane/
```

## Getting started

1. Clone the repository:

   ```bash
   git clone https://github.com/shuntps/HavenStack.git
   cd HavenStack
   ```

2. Create your local environment file, then configure your domain, paths, user IDs, and secrets:

   ```bash
   cp .env.example .env
   ```

3. Start the edge stack first, followed by the stacks you want to deploy:

   ```bash
   docker compose -f unraid/edge/compose.yml up -d
   docker compose -f unraid/apps/compose.yml up -d
   docker compose -f unraid/monitoring/compose.yml up -d
   docker compose -f unraid/servarr/compose.yml up -d
   ```

> [!IMPORTANT]
> Review all paths, credentials, network ranges, and domain settings before deployment. Never commit secrets or populated environment files.

## License

This project is available under the terms of the [LICENSE](LICENSE) file.

---

Created and maintained by [Shunt](https://github.com/shuntps).
