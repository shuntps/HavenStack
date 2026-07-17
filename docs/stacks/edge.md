# Edge stack

The edge stack is the entry point for the Unraid services. It connects Cloudflare to Traefik, applies Authelia access rules, updates one separate DDNS record, and creates the shared Docker networks used by the other Unraid stacks.

Run the commands in this guide from the root of the HavenStack repository on Unraid.

## Services

| Service | Image | Purpose |
| --- | --- | --- |
| cloudflared | `cloudflare/cloudflared:2026.7.2` | Opens the outbound Cloudflare Tunnel and forwards tunneled requests to Traefik. |
| cloudflare-ddns | `favonia/cloudflare-ddns:1.16.2` | Updates the dedicated `ddns.example.com` IPv4 DNS record. |
| Traefik | `traefik:v3.7.8` | Matches incoming hostnames and forwards requests to the correct container. |
| Authelia | `authelia/authelia:4.39.20` | Provides file-based user authentication, access policies, TOTP, and WebAuthn. |

## Prerequisites and dependencies

Before deploying the full stack, confirm that:

- `unraid/.env` exists and contains no `replace-with-*` values.
- Your domain is managed in Cloudflare.
- A remotely managed Cloudflare Tunnel exists and you have its connector token.
- The Tunnel has two published application routes for this reference setup:
  - `example.com` to `http://traefik:8080`
  - `*.example.com` to `http://traefik:8080`
- A separate, zone-scoped Cloudflare API token can edit DNS for `ddns.example.com`.
- `CLOUDFLARE_DDNS_DOMAINS` is set to `ddns.example.com`, with your real domain substituted.
- `unraid/edge/config/authelia/users.yml` exists and contains a real user with an Argon2id password hash.
- `${APPDATA_PATH}/authelia` exists and is writable by the configured `UID:GID`.
- The host clock is synchronized. Incorrect time can break TOTP authentication.
- The `10.88.10.0/24` through `10.88.70.0/24` ranges do not overlap existing LAN, VPN, or Docker networks.

### Tunnel DNS and DDNS are separate

Do not put the apex domain or Tunnel wildcard in `CLOUDFLARE_DDNS_DOMAINS`.

- `example.com` and `*.example.com` route through the Cloudflare Tunnel. They do not need your home public IP.
- `ddns.example.com` is a separate DNS record updated with your public IPv4 address by cloudflare-ddns.

The Compose file sets `IP6_PROVIDER=none`, so cloudflare-ddns does not update IPv6. It does not set `PROXIED`; upstream defaults newly created records to DNS-only and preserves the proxy state of existing records. Check the final record in the Cloudflare dashboard. A DNS-only DDNS record exposes your public IP, so use it only for a deliberate purpose and protect any service reached through it.

## Networks and storage

The edge stack creates all shared Unraid networks. Some are marked internal to prevent direct outbound access.

| Network | Subnet | Used by the edge stack | Notes |
| --- | --- | --- | --- |
| `edge_ingress` | `10.88.10.0/24` | cloudflared, Traefik | Carries Tunnel traffic to Traefik. |
| `auth_backend` | `10.88.20.0/24` | Traefik, Authelia | Internal authentication network. |
| `apps_backend` | `10.88.30.0/24` | Traefik | Shared with Vaultwarden and Nextcloud-related routing. |
| `servarr_backend` | `10.88.40.0/24` | Traefik | Shared with the Servarr stack. |
| `homepage_backend` | `10.88.50.0/24` | Traefik | Internal network shared with Homepage. |
| `monitoring_backend` | `10.88.60.0/24` | cloudflared, Traefik, Authelia | Internal network shared with monitoring. |
| `ddns_egress` | `10.88.70.0/24` | cloudflare-ddns | Gives the DDNS updater outbound access. |

The other Unraid Compose files declare these networks as external. Deploy `edge` first and avoid taking it down while dependent stacks are running. For routine maintenance, prefer `docker compose stop` over `docker compose down`.

Persistent and local data:

| Host path | Container path | Contents |
| --- | --- | --- |
| `unraid/edge/config/traefik` | `/etc/traefik` | Version-controlled static and dynamic Traefik configuration, mounted read-only. |
| `unraid/edge/config/authelia` | `/config` | Authelia configuration, local `users.yml`, and filesystem notifications. |
| `${APPDATA_PATH}/authelia` | `/data` | Authelia's SQLite database and persistent state. |

cloudflared, cloudflare-ddns, and Traefik have no persistent runtime volume in this stack. They are recreated from the Compose file, configuration, and secrets.

## Relevant environment variables

| Variable | Used for |
| --- | --- |
| `TZ` | Container time zone. |
| `UID`, `GID` | Runtime identity for Traefik and Authelia. |
| `UNRAID_IP`, `NAS_IP` | Targets used by the external Traefik routes. |
| `DOMAIN` | Base domain, without scheme or trailing slash. |
| `DOMAIN_SLD` | Short name used in the Authelia session cookie name. |
| `APPDATA_PATH` | Root of Authelia's persistent data directory. |
| `CLOUDFLARED_TUNNEL_TOKEN` | Secret connector token for the remotely managed Tunnel. |
| `CLOUDFLARE_DDNS_API_TOKEN` | Zone-scoped token used only to edit the DDNS record. |
| `CLOUDFLARE_DDNS_DOMAINS` | Comma-separated DDNS records; the reference value is `ddns.example.com`. |
| `AUTH_JWT_SECRET` | Secret used for password-reset identity validation. |
| `AUTH_SESSION_SECRET` | Secret used to protect Authelia sessions. |
| `AUTH_STORAGE_ENCRYPTION_KEY` | Key used to encrypt sensitive Authelia storage values. |

Use a different long random value for every authentication secret. Never print a populated `.env` file or rendered Compose configuration in an issue.

## First configuration

### 1. Prepare the Cloudflare Tunnel

In the Cloudflare dashboard, create or select a remotely managed Tunnel and add the apex and wildcard published application routes shown above. Put the connector token in `CLOUDFLARED_TUNNEL_TOKEN`.

The origin name `traefik` works because cloudflared and Traefik share `edge_ingress`. Traefik is not published on a host port.

### 2. Prepare the separate DDNS record

Create a Cloudflare API token limited to DNS editing for the required zone. Put it in `CLOUDFLARE_DDNS_API_TOKEN`, and set:

```dotenv
CLOUDFLARE_DDNS_DOMAINS=ddns.example.com
```

Replace `example.com` with your domain. Do not add the Tunnel apex or wildcard to this value.

### 3. Create Authelia secrets and a user

Generate three different random secrets for the three `AUTH_*` variables. The example file suggests:

```bash
openssl rand -hex 64
```

Run it separately for each secret and store the values securely.

Copy the example user database:

```bash
cp unraid/edge/config/authelia/users.yml.example \
  unraid/edge/config/authelia/users.yml
```

Generate a password hash interactively so the plain-text password is not placed on the command line:

```bash
docker run --rm -it authelia/authelia:4.39.20 \
  authelia crypto hash generate argon2
```

Put only the generated `$argon2id$...` digest in `users.yml`. Update the username, display name, email, and groups. The included policies expect an administrator to belong to the `admins` group.

`users.yml`, `notification.txt`, and the populated `.env` are ignored by Git. Keep encrypted backups of them.

## Deploy and verify

Validate the complete edge configuration without rendering secrets:

```bash
docker compose --env-file unraid/.env \
  -f unraid/edge/compose.yml config --quiet
```

Start the full edge stack:

```bash
docker compose --env-file unraid/.env \
  -f unraid/edge/compose.yml up -d
```

Check status:

```bash
docker compose --env-file unraid/.env \
  -f unraid/edge/compose.yml ps
```

cloudflared, Traefik, and Authelia should eventually report `healthy`. cloudflare-ddns has **no Compose health check**, so `Up` without a health status is expected. Verify it through logs:

```bash
docker compose --env-file unraid/.env \
  -f unraid/edge/compose.yml logs --tail=100 cloudflare-ddns
```

Inspect the other edge logs when needed:

```bash
docker compose --env-file unraid/.env \
  -f unraid/edge/compose.yml logs --tail=100 cloudflared traefik authelia
```

After the Tunnel connects, test `https://auth.example.com`. The Traefik dashboard route can be tested at `https://traefik.example.com` after an administrator has enrolled a second factor.

## Traefik routing and authentication

Traefik reads its static configuration from `unraid/edge/config/traefik/traefik.yml` and watches the YAML files in `config/traefik/dynamic` for routers, services, and middlewares.

The `web` entry point listens on container port `8080`. Separate internal entry points expose health on `8082` and Prometheus metrics on `8084`. The dashboard is enabled but insecure dashboard mode is disabled.

Common middlewares provide:

- Authelia ForwardAuth;
- basic security response headers;
- request rate limiting;
- `www` to apex redirection.

Authelia evaluates access rules in order. The first matching rule wins. The current policies are:

| Route | Current policy |
| --- | --- |
| `auth.example.com` | Bypass, so the authentication portal itself can load. |
| `traefik`, `grafana`, `qbittorrent`, `prowlarr`, `radarr`, `sonarr`, `profilarr` | `admins` group plus two-factor authentication; everyone else is denied. |
| `vault.example.com/admin` | `admins` group plus two-factor authentication; everyone else is denied. |
| Other subdomains using the Authelia middleware | One-factor authentication through the wildcard rule. |
| A request passed to Authelia that matches no rule | Denied. |

Some Traefik routers intentionally do not use Authelia: the Homepage is public, while the normal Vaultwarden and Nextcloud routes use their native application authentication. Authelia rules do not protect a router that does not include the Authelia middleware.

### Environment-specific external routes

`config/traefik/dynamic/external.yml` contains two routes that are specific to the deployment environment:

| Public hostname | Current backend |
| --- | --- |
| `unraid.example.com` | `http://UNRAID_IP:3480` |
| `nas.example.com` | `http://NAS_IP:5080` |

Confirm what is actually listening on both ports before exposing these routes, or remove the routers if they are not needed. These routes use Authelia, but no administrator-specific rule exists for them in the current configuration, so they fall through to the wildcard one-factor policy. Add explicit access rules if they should require the `admins` group and two-factor authentication.

## Backup data

Back up these items together and encrypt the backup:

- `unraid/.env`;
- `unraid/edge/config/authelia/users.yml`;
- `unraid/edge/config/authelia/notification.txt` when it contains information you still need;
- `${APPDATA_PATH}/authelia`, including the SQLite database;
- the Git release or commit containing the Traefik and Authelia configuration;
- an inventory of Tunnel routes, DNS records, and token scopes.

The Authelia database must be restored with the matching storage encryption key. Tunnel and API tokens can be recreated and rotated, but keep a recovery plan that does not depend on the failed server.

## Security notes

- Treat the Tunnel token as a secret: it can connect another cloudflared instance to your Tunnel.
- Use a separate least-privilege API token for DDNS. Do not use a Cloudflare global API key.
- Review every hostname before publishing it. A Tunnel is connectivity, not authentication.
- A DNS-only `ddns.example.com` record reveals the public origin IP.
- Enroll and test TOTP or WebAuthn before relying on administrator-only routes.
- Keep `users.yml`, Authelia storage, and all `AUTH_*` secrets private and backed up.
- Traefik accepts forwarded headers only from `10.88.10.0/24`. If you change `edge_ingress`, update the trusted range deliberately.
- Do not publish Traefik's ports directly unless you also design appropriate firewall and TLS controls.
- Never use `docker compose down -v` as a troubleshooting step.

## Common problems

### cloudflared stays unhealthy

Check the connector token, Tunnel status in Cloudflare, outbound connectivity, and cloudflared logs. A connected Tunnel can still return `502` if its configured origin is wrong or Traefik is unavailable.

### A public hostname returns `404`

Traefik received the request but no router matched it. Check `DOMAIN`, the requested hostname, and the relevant file in `config/traefik/dynamic`.

### A public hostname returns `502` or `504`

Check the target application's health and confirm it shares the expected Docker network with Traefik. If every hostname fails, verify that the Tunnel origin is `http://traefik:8080`.

### Authelia redirects repeatedly

Check `DOMAIN`, `DOMAIN_SLD`, the wildcard Tunnel route, the Traefik router for `auth.example.com`, browser cookies, system time, and Traefik/cloudflared forwarded headers. Test in a private browser window after correcting the configuration.

### An administrator route is denied

Confirm the user is in the `admins` group and has completed a second factor. Authelia rule order matters; inspect the Authelia logs without publishing sensitive session details.

### DDNS shows no health status

This is expected because the service has no health check. Read its logs and verify only `ddns.example.com` in the Cloudflare DNS dashboard. Authentication failures usually mean the API token has the wrong zone or permissions.

### A dependent stack reports a missing external network

Start the complete edge stack and confirm the networks exist:

```bash
docker network ls
docker compose --env-file unraid/.env -f unraid/edge/compose.yml up -d
```

## Official upstream documentation

- [Cloudflare Tunnel overview](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/)
- [Cloudflare published application routes](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/routing-to-tunnel/)
- [cloudflare-ddns repository and settings](https://github.com/favonia/cloudflare-ddns)
- [Traefik file provider](https://doc.traefik.io/traefik/providers/file/)
- [Traefik ForwardAuth middleware](https://doc.traefik.io/traefik/middlewares/http/forwardauth/)
- [Authelia proxy integrations](https://www.authelia.com/integration/proxies/)
- [Authelia access control](https://www.authelia.com/configuration/security/access-control/)
- [Authelia file authentication backend](https://www.authelia.com/configuration/first-factor/file/)
- [Authelia password hashing](https://www.authelia.com/reference/guides/passwords/)
