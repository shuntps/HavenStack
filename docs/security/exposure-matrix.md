# Exposure matrix

This page describes the network and host-access boundaries created by the current repository. It separates four different ideas that are easy to confuse:

- **Public via Tunnel**: reachable from the Internet through Cloudflare, `cloudflared`, and a matching Traefik router.
- **LAN-published**: bound directly to a NAS or host network interface.
- **Docker-internal**: reachable only from containers attached to a suitable Docker network, unless another proxy route exists.
- **Host resource access**: access to a socket, device, or filesystem rather than a TCP port.

A Cloudflare Tunnel route provides connectivity, not authentication. Authelia applies only to a Traefik router that explicitly includes the `authelia@file` middleware.

## On this page

- [Public request boundary](#public-request-boundary)
- [Public routes through Cloudflare Tunnel](#public-routes-through-cloudflare-tunnel)
- [Direct LAN and host exposure](#direct-lan-and-host-exposure)
- [Container and internal endpoint inventory](#container-and-internal-endpoint-inventory)
- [Host resources and elevated capabilities](#host-resources-and-elevated-capabilities)
- [Authentication boundaries to remember](#authentication-boundaries-to-remember)
- [Verify the real deployment](#verify-the-real-deployment)
- [Environment-specific uncertainties](#environment-specific-uncertainties)

## Public request boundary

The documented Cloudflare Tunnel publishes the apex domain and wildcard domain to:

```text
http://traefik:8080
```

Cloudflare terminates visitor HTTPS. The connector-to-Traefik and Traefik-to-application hops use HTTP on Docker or LAN networks in the current configuration. Traefik port `8080` is not published on the Unraid host, and the repository requires no inbound router forwarding for ports `80` or `443`.

The apex and wildcard routes make only hostnames with a matching Traefik router useful. An arbitrary subdomain receives a Traefik `404`; the Tunnel does not automatically publish every container.

## Public routes through Cloudflare Tunnel

Replace `DOMAIN` with the configured domain.

| Public route | Backend | Traefik middleware | Authentication in the repository | Important note |
| --- | --- | --- | --- | --- |
| `https://DOMAIN` | Homepage at `homepage:3000` | Rate limit and security headers | None | Public landing page; review all rendered metadata |
| `https://www.DOMAIN` | Redirect to the apex | Redirect only | None | No application content is served by this router |
| `https://auth.DOMAIN` | Authelia at `authelia:9091` | Rate limit and security headers | The router deliberately has no forward-auth middleware; Authelia handles its own login, and its rules also declare this hostname `bypass` | This is the authentication portal, not an unprotected admin dashboard |
| `https://traefik.DOMAIN` | Traefik dashboard | Rate limit, security headers, Authelia | Explicit `admins` group plus Authelia two-factor authentication | Traefik has no separate dashboard password in this configuration |
| `https://vault.DOMAIN` | Vaultwarden at `vaultwarden:8080` | Rate limit and security headers | Vaultwarden's native account authentication; no Authelia middleware | Required for Bitwarden-compatible clients; sign-ups and invitations are disabled in Compose |
| `https://vault.DOMAIN/admin` | Vaultwarden admin interface | Rate limit, security headers, Authelia | Explicit `admins` group plus Authelia two-factor authentication, then the Vaultwarden admin token | Two independent checks protect this path |
| `https://cloud.DOMAIN` | Nextcloud Apache at `nextcloud-aio-apache:11000` | Security headers | Nextcloud's native authentication; no Authelia middleware | Preserves WebDAV and client compatibility |
| `https://grafana.DOMAIN` | Grafana at `grafana:3000` | Rate limit, security headers, Authelia | Explicit `admins` group plus Authelia two-factor authentication, then Grafana login | Authelia is not configured as Grafana SSO |
| `https://qbittorrent.DOMAIN` | qBittorrent at `qbittorrent:8090` | Rate limit, security headers, Authelia | Explicit `admins` group plus Authelia two-factor authentication, then qBittorrent login | VPN status must still be verified separately |
| `https://prowlarr.DOMAIN` | Prowlarr at `prowlarr:9696` | Rate limit, security headers, Authelia | Explicit `admins` group plus Authelia two-factor authentication; native application auth is runtime configuration | Protect API keys even when browser access uses Authelia |
| `https://radarr.DOMAIN` | Radarr at `radarr:7878` | Rate limit, security headers, Authelia | Explicit `admins` group plus Authelia two-factor authentication; native application auth is runtime configuration | Internal API clients bypass the public route |
| `https://sonarr.DOMAIN` | Sonarr at `sonarr:8989` | Rate limit, security headers, Authelia | Explicit `admins` group plus Authelia two-factor authentication; native application auth is runtime configuration | Internal API clients bypass the public route |
| `https://profilarr.DOMAIN` | Profilarr at `profilarr:6868` | Rate limit, security headers, Authelia | Explicit `admins` group plus Authelia two-factor authentication; native application auth is runtime configuration | Review profile changes before applying them |
| `https://seerr.DOMAIN` | Seerr at `seerr:5055` | Rate limit, security headers, Authelia | Falls through to Authelia's wildcard `one_factor` policy, then Seerr's own authentication | This is intentionally weaker than the administrator-only routes; review the allowed audience |

## Direct LAN and host exposure

| Service | Direct endpoint | Protection | Boundary |
| --- | --- | --- | --- |
| Plex | NAS host networking; primary Web UI at `http://NAS_IP:32400/web` | Plex native authentication and NAS firewall | No Traefik or Authelia route. Host networking may expose additional Plex listeners selected by Plex itself; inspect the running host |

No Unraid Compose service declares a `ports:` mapping. qBittorrent, Prowlarr, Radarr, Sonarr, Seerr, Profilarr, Homepage, Vaultwarden, Nextcloud, Traefik, Authelia, Prometheus, Blackbox Exporter, and Grafana are therefore not directly published on an Unraid LAN address by these Compose files.

Plex's `network_mode: host` is broader than a single Docker port mapping: every listener opened by Plex uses the NAS network namespace. The repository confirms the health endpoint on `32400`, but the complete set of active Plex discovery or streaming listeners depends on the installed Plex version and settings.

## Container and internal endpoint inventory

These endpoints are not host port mappings. They are reachable only where Docker network membership or a proxy path permits it.

| Stack and service | Internal endpoint or behavior | Reachability in the current design |
| --- | --- | --- |
| Edge: cloudflared | Metrics/readiness on `cloudflared:2000`; outbound Tunnel connection | Metrics on `monitoring_backend`; public requests return through the established outbound tunnel |
| Edge: Traefik | HTTP ingress `8080`, health `8082`, metrics `8084`, internal dashboard service | `8080` from cloudflared; health/metrics from monitoring; selected dashboard exposed only through its public router |
| Edge: Authelia | Web/forward-auth `9091`, metrics `9959` | Forward-auth from Traefik, metrics/health from monitoring, portal through `auth.DOMAIN` |
| Apps: Homepage | `homepage:3000` | Traefik and Blackbox Exporter through `homepage_backend`; public apex router |
| Apps: Vaultwarden | `vaultwarden:8080` | Traefik and Blackbox Exporter through `apps_backend`; public vault routers |
| Nextcloud: Apache | `nextcloud-aio-apache:11000` | Traefik and Blackbox Exporter through `apps_backend`; public `cloud.DOMAIN` router |
| Nextcloud: PostgreSQL | PostgreSQL `5432` | Only `nextcloud_backend`, which is an internal Docker network |
| Nextcloud: Redis | Redis `6379` | Only `nextcloud_backend`, which is an internal Docker network |
| Nextcloud: application | Internal PHP/application service managed by the AIO images | `nextcloud_backend`; separate `nextcloud_egress` supplies outbound access, no host port |
| Nextcloud: Notify Push | Internal notify-push service | `nextcloud_backend`, no host port or direct Traefik router |
| Servarr: qBittorrent | Web UI `8090`; Privoxy `8118`; VPN egress | `servarr_backend`; Web UI has a public Traefik router, Privoxy remains internal, transfer traffic should leave through the VPN |
| Servarr: Prowlarr | `prowlarr:9696` | `servarr_backend`, public Traefik router, and internal API clients |
| Servarr: Radarr | `radarr:7878` | `servarr_backend`, public Traefik router, and internal API clients |
| Servarr: Sonarr | `sonarr:8989` | `servarr_backend`, public Traefik router, and internal API clients |
| Servarr: Seerr | `seerr:5055` | `servarr_backend`, public Traefik router, and internal API clients |
| Servarr: Profilarr | `profilarr:6868` | `servarr_backend`, public Traefik router, and internal API clients |
| Monitoring: Prometheus | `prometheus:9090` | `monitoring_backend` only; no public router |
| Monitoring: Blackbox Exporter | `blackbox-exporter:9115` | Monitoring plus application probe networks; no public router |
| Monitoring: Grafana | `grafana:3000` | `monitoring_backend`; public Traefik router with Authelia |
| NAS: Plex | Host network rather than an internal Docker endpoint | Direct NAS/LAN boundary described above; probed by Blackbox Exporter at `NAS_IP:32400` |

Docker network isolation is not authentication. Any compromised container attached to a shared backend can attempt to reach peers on that backend. The `auth_backend`, `homepage_backend`, `monitoring_backend`, and `nextcloud_backend` networks have Docker's `internal` flag; other networks provide the egress required by their services.

## Host resources and elevated capabilities

| Service | Host access | Risk and control |
| --- | --- | --- |
| Plex | `/dev/dri:/dev/dri` | Grants access to host graphics devices for transcoding. Restrict device permissions and remove the mapping deliberately when it is not needed |
| qBittorrent VPN | Linux `NET_ADMIN` capability | Required for the VPN interface and firewall. A compromise has greater network-control capability inside this container than a normal unprivileged service |
| Traefik and applications | Bind-mounted configuration and persistent data | A compromised service can read or modify whatever its container user and mount mode permit; `:ro` configuration mounts reduce this scope |
| Servarr and Nextcloud | NAS-backed bind mounts using `rslave` | A compromised writable service can alter shared media or cloud data. Mount availability and UID/GID permissions are part of the security boundary |

`no-new-privileges`, dropped capabilities, read-only root filesystems, and internal Docker networks reduce risk where configured. They do not replace application patching, authentication, least-privilege file ownership, host firewalling, or backups.

## Authentication boundaries to remember

- Cloudflare Tunnel is transport, not user authentication.
- Traefik rate limiting and security headers are useful controls, not login mechanisms.
- Authelia policies apply only to routers with the forward-auth middleware.
- Homepage, normal Vaultwarden, and Nextcloud routes do not use Authelia in the current configuration.
- Service-to-service calls on Docker networks do not pass through Authelia; they rely on application API keys or other native credentials.
- LAN access to Plex does not pass through Authelia.
- The Authelia wildcard `one_factor` rule applies to unmatched domains only when their Traefik router invokes Authelia. It does not globally protect every wildcard hostname.

## Verify the real deployment

Repository review cannot see host firewalls, router forwards, Cloudflare Access policies, unexpected containers, or services installed directly on the hosts. Audit both machines after every material network change.

List Docker-published ports and networks:

```bash
docker ps --format 'table {{.Names}}\t{{.Ports}}\t{{.Networks}}'
```

List listening host sockets with the tool available on the platform, for example:

```bash
ss -lntup
```

Review the output for listeners on `0.0.0.0`, `::`, and `NAS_IP`. Confirm the Cloudflare dashboard contains only the intended apex and wildcard Tunnel routes plus the final `http_status:404` catch-all. Check the router for unexpected port forwards and verify the NAS and Unraid firewall rules.

Perform functional tests from three places:

1. an external network, to verify only intended Tunnel hostnames respond;
2. the trusted LAN, to verify the direct Plex boundary;
3. an untrusted or guest LAN, to confirm firewall isolation.

## Environment-specific uncertainties

The following cannot be proven from this repository:

- whether host firewalls restrict Plex;
- whether the router has unrelated inbound port forwards;
- whether Cloudflare Access, WAF rules, or account-level controls add protection beyond the repository;
- the native authentication settings selected during first-run setup for Servarr applications, Seerr, and Plex;
- Plex's complete listener set under host networking;
- whether a running container or local override publishes additional ports.

Record the verified answers in a private deployment inventory. Recheck this matrix after changes to Compose files, Traefik routers, Authelia policies, Cloudflare routes, host networking, or firewall rules.

See [Secrets and credentials](secrets.md) for the values that protect these boundaries.
