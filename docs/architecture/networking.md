# Networking

HavenStack uses separate Docker networks to limit which containers can communicate. Docker networking exists independently on the Unraid and NAS hosts; a Docker network never spans both machines.

For the high-level system diagram, start with [Architecture overview](overview.md).

## Public web request flow

```text
Browser
  -> HTTPS to Cloudflare
  -> encrypted Cloudflare Tunnel
  -> cloudflared on Unraid
  -> HTTP to traefik:8080 on edge_ingress
  -> optional Authelia ForwardAuth check
  -> application on its backend Docker network
```

The home router does not need inbound forwarding for ports `80` or `443`. `cloudflared` initiates outbound connections, and no Unraid Compose service publishes Traefik to a host port.

Cloudflare terminates the visitor's TLS connection. The Cloudflare-to-cloudflared Tunnel is encrypted; only the short `cloudflared` to Traefik hop uses HTTP inside `edge_ingress`.

## Tunnel DNS and DDNS

The two mechanisms have different purposes:

| Name | Owner | Destination | Purpose |
| --- | --- | --- | --- |
| `example.com` | Cloudflare Tunnel route | `http://traefik:8080` | Homepage at the apex domain |
| `*.example.com` | Cloudflare Tunnel route | `http://traefik:8080` | First-level HavenStack subdomains |
| `ddns.example.com` | cloudflare-ddns | Current home public IPv4 address | Separate direct-DNS use outside the Tunnel request path |

The wildcard does not match the apex, so both Tunnel routes are required. A final `http_status:404` Tunnel rule rejects unmatched published routes.

`CLOUDFLARE_DDNS_DOMAINS` is intentionally set to `ddns.example.com`. Do not change it to the apex or wildcard names. The DDNS container sets `IP6_PROVIDER=none`, so it updates IPv4 only. The DDNS record may reveal the home public IP and must not be treated as protected by the Tunnel or Authelia.

See [Configure the Cloudflare Tunnel](../getting-started/cloudflare-tunnel.md) for the dashboard procedure.

## Unraid Docker networks

The edge stack creates seven networks with fixed subnets. Other stacks declare several of them as external, which is why `unraid/edge/compose.yml` must start first.

| Network | Subnet | Internal | Members in the repository | Purpose |
| --- | --- | --- | --- | --- |
| `edge_ingress` | `10.88.10.0/24` | No | cloudflared, Traefik | Tunnel connector to reverse proxy |
| `auth_backend` | `10.88.20.0/24` | Yes | Traefik, Authelia | Forward-auth requests |
| `apps_backend` | `10.88.30.0/24` | No | Traefik, Vaultwarden, Nextcloud Apache, Blackbox Exporter | Application proxying and probes |
| `servarr_backend` | `10.88.40.0/24` | No | Traefik, all Servarr services, Blackbox Exporter | Media automation proxying and probes |
| `homepage_backend` | `10.88.50.0/24` | Yes | Traefik, Homepage, Blackbox Exporter | Homepage proxying and probes |
| `monitoring_backend` | `10.88.60.0/24` | Yes | cloudflared, Traefik, Authelia, Prometheus, Blackbox Exporter, Grafana | Metrics and monitoring communication |
| `ddns_egress` | `10.88.70.0/24` | No | cloudflare-ddns | Outbound DNS update traffic |

An internal Docker network does not provide normal external connectivity. A container can still communicate with other members of that network and may also have another non-internal network.

Traefik trusts forwarded headers only from `10.88.10.0/24`. If you change `edge_ingress`, update `trustedIPs` in `unraid/edge/config/traefik/traefik.yml` as part of the same reviewed change.

qBittorrent also needs the Servarr subnet in `LAN_NETWORK`. The example value is:

```dotenv
LAN_NETWORK=192.168.1.0/24,10.88.40.0/24
```

If you change `servarr_backend`, update this value or the qBittorrent web interface may reject traffic from Traefik and the other Servarr containers.

## Nextcloud-only networks

The Nextcloud stack creates two additional bridge networks. Docker chooses their subnets because the Compose file does not set IPAM ranges.

| Network | Internal | Members | Purpose |
| --- | --- | --- | --- |
| `nextcloud_backend` | Yes | Apache, PostgreSQL, Redis, Nextcloud, Notify Push | Private communication between Nextcloud components |
| `nextcloud_egress` | No | Nextcloud application | Outbound access for the application |

Nextcloud Apache also joins `apps_backend`, allowing Traefik and Blackbox Exporter to reach it. PostgreSQL and Redis remain only on `nextcloud_backend`.

## NAS networking

The NAS runs a separate Docker Engine:

- Plex uses `network_mode: host`. It shares the NAS network namespace instead of joining a bridge network.
- Arcane uses the `arcane` bridge network at `10.68.10.0/24` and publishes TCP port `3552` only on `NAS_IP`.

Because Plex uses host networking, every listener opened by the Plex container is a listener on the NAS host. The Compose file does not enumerate those ports. Its health check and normal web interface use port `32400`.

The Arcane and Plex services are not automatically routed through the Cloudflare Tunnel. Keep NAS ports restricted to trusted LANs unless you create a separate reviewed access design.

## Published and referenced ports

| Location | Port or mode | How it is exposed |
| --- | --- | --- |
| Unraid web stacks | None | No `ports` mappings; reached through cloudflared and Traefik Docker networks |
| Traefik | `8080`, `8082`, `8084` | Container-only web, health, and metrics entry points |
| cloudflared | `2000` | Container-only readiness/metrics endpoint |
| Authelia | `9091`, `9959` | Container-only web/auth and metrics endpoints |
| Plex | Host network; web on `32400` | Listens directly through the NAS network namespace |
| Arcane | `${NAS_IP}:3552` | Explicit NAS LAN bind |
| `unraid.example.com` backend | `${UNRAID_IP}:3480` | Existing LAN service referenced by Traefik; not created or published by HavenStack Compose |
| `nas.example.com` backend | `${NAS_IP}:5080` | Existing LAN service referenced by Traefik; not created or published by HavenStack Compose |

Internal application ports such as Vaultwarden `8080`, Grafana `3000`, qBittorrent `8090`, and Radarr `7878` are reachable only by containers on their shared Docker networks unless another configuration exposes them.

## Authentication boundaries

Traefik uses hostname rules from `unraid/edge/config/traefik/dynamic/`. A route is protected by Authelia only when it includes the `authelia@file` middleware.

- Traefik, Grafana, qBittorrent, Prowlarr, Radarr, Sonarr, Profilarr, and Vaultwarden `/admin` have specific administrator and two-factor rules.
- Seerr and other protected subdomains without a more specific rule use Authelia's wildcard one-factor rule.
- Homepage has no Authelia middleware.
- The normal Vaultwarden and Nextcloud routes use their native application authentication.

A Tunnel route provides connectivity; it does not automatically add authentication. Review both the Traefik router and Authelia policy before publishing a new hostname.

## Inspect and troubleshoot networks

List the networks:

```bash
docker network ls
```

Inspect membership and addressing without changing anything:

```bash
docker network inspect edge_ingress
docker network inspect apps_backend
```

Common symptoms:

| Symptom | Check first |
| --- | --- |
| External network not found | Start the complete edge stack |
| Address pool overlaps | Compare the fixed subnets with LAN, VPN, and existing Docker networks |
| Cloudflare `502` for every route | cloudflared, `edge_ingress`, and `traefik:8080` |
| Traefik `404` | Hostname and matching dynamic router |
| Traefik `502` for one app | Backend health and shared network membership |
| Authelia redirect or denial | Middleware, cookie domain, user group, factor, and rule order |
| NAS backend unavailable | `NAS_IP`, LAN firewall, and the service listening on the referenced port |

Do not publish a host port simply to bypass a networking error. Fix the intended route or network membership.
