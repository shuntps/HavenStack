# Stack guides

These guides explain the purpose, dependencies, storage, networking, first configuration, verification, and maintenance boundaries of each HavenStack Compose stack.

Complete the [getting-started installation path](../README.md#installation-path) before using a stack guide. The stack pages assume that the environment files and required local configuration already exist.

## Unraid stacks

Deploy the Unraid stacks in this order because the edge stack creates the shared Docker networks used by the others.

| Order | Stack | Main services | Guide |
| ---: | --- | --- | --- |
| 1 | Edge | cloudflared, Cloudflare DDNS, Traefik, Authelia | [Edge](edge.md) |
| 2 | Apps | Homepage, Vaultwarden | [Apps](apps.md) |
| 3 | Nextcloud | Apache, Nextcloud, PostgreSQL, Redis, Notify Push | [Nextcloud](nextcloud.md) |
| 4 | Servarr | qBittorrent VPN, Prowlarr, Radarr, Sonarr, Seerr, Profilarr | [Servarr](servarr.md) |
| 5 | Monitoring | Prometheus, Grafana, Blackbox Exporter | [Monitoring](monitoring.md) |

You may omit a stack you do not need. Keep `edge` running while any dependent Unraid stack is running.

## NAS stacks

The NAS stacks are independent of the Unraid Docker networks and can be deployed separately.

| Stack | Main service | Guide |
| --- | --- | --- |
| Plex | Media server | [Plex](plex.md) |
| Arcane | Docker management interface | [Arcane](arcane.md) |

## Reading a stack guide

Each guide distinguishes between three types of verification:

- **Compose validation** checks YAML, interpolation, and the resulting Compose model.
- **Container health** checks whether the process responds to its configured health check.
- **Functional testing** confirms that authentication, storage, networking, and application integrations actually work.

A successful Compose validation or green health check does not replace functional testing or a tested backup.

After deployment, use the [operations guides](../README.md#operations) for backup, updates, rollback, and troubleshooting. Review [Secrets and credentials](../security/secrets.md) and the [Exposure matrix](../security/exposure-matrix.md) before publishing or changing a service.
