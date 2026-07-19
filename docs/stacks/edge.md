# Edge stack

The edge stack is the entry point for the Unraid services. It connects Cloudflare to Traefik, applies Authelia access rules, and creates the shared Docker networks used by the other Unraid stacks.

Run the commands in this guide from the root of the HavenStack repository on Unraid.

## Services

| Service | Image | Purpose |
| --- | --- | --- |
| cloudflared | `cloudflare/cloudflared:2026.7.2` | Opens the outbound Cloudflare Tunnel and forwards tunneled requests to Traefik. |
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
- `unraid/edge/config/authelia/users.yml` exists and contains a real user with an Argon2id password hash.
- `${APPDATA_PATH}/authelia` exists and is writable by the configured `UID:GID`.
- The host clock is synchronized. Incorrect time can break TOTP authentication.
- The `10.88.10.0/24` through `10.88.60.0/24` ranges do not overlap existing LAN, VPN, or Docker networks.

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

The other Unraid Compose files declare these networks as external. Deploy `edge` first and avoid taking it down while dependent stacks are running. For routine maintenance, prefer `docker compose stop` over `docker compose down`.

Persistent and local data:

| Host path | Container path | Contents |
| --- | --- | --- |
| `unraid/edge/config/traefik` | `/etc/traefik` | Version-controlled static and dynamic Traefik configuration, mounted read-only. |
| `unraid/edge/config/authelia` | `/config` | Authelia configuration, local `users.yml`, and filesystem notifications. |
| `${APPDATA_PATH}/authelia` | `/data` | Authelia's SQLite database and persistent state. |

cloudflared and Traefik have no persistent runtime volume in this stack. They are recreated from the Compose file, configuration, and secrets.

## Relevant environment variables

| Variable | Used for |
| --- | --- |
| `TZ` | Container time zone. |
| `UID`, `GID` | Runtime identity for Traefik and Authelia. |
| `DOMAIN` | Base domain, without scheme or trailing slash. |
| `DOMAIN_SLD` | Short name used in the Authelia session cookie name. |
| `APPDATA_PATH` | Root of Authelia's persistent data directory. |
| `CLOUDFLARED_TUNNEL_TOKEN` | Secret connector token for the remotely managed Tunnel. |
| `AUTH_JWT_SECRET` | Secret used for password-reset identity validation. |
| `AUTH_SESSION_SECRET` | Secret used to protect Authelia sessions. |
| `AUTH_STORAGE_ENCRYPTION_KEY` | Key used to encrypt sensitive Authelia storage values. |

Use a different long random value for every authentication secret. Never print a populated `.env` file or rendered Compose configuration in an issue.

## First configuration

### 1. Prepare the Cloudflare Tunnel

In the Cloudflare dashboard, create or select a remotely managed Tunnel and add the apex and wildcard published application routes shown above. Put the connector token in `CLOUDFLARED_TUNNEL_TOKEN`.

The origin name `traefik` works because cloudflared and Traefik share `edge_ingress`. Traefik is not published on a host port.

### 2. Create Authelia secrets and a user

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

cloudflared, Traefik, and Authelia should eventually report `healthy`. Inspect the edge logs when needed:

```bash
docker compose --env-file unraid/.env \
  -f unraid/edge/compose.yml logs --tail=100 cloudflared traefik authelia
```

After the Tunnel connects, test `https://auth.example.com`. The Traefik dashboard route can be tested at `https://traefik.example.com` after an administrator has enrolled a second factor.

## Traefik routing and authentication

Traefik reads its static configuration from `unraid/edge/config/traefik/traefik.yml` and watches the YAML files in `config/traefik/dynamic` for routers, services, and middlewares.

The `web` entry point listens on container port `8080`. Separate internal entry points expose health on `8082` and Prometheus metrics on `8084`. The dashboard is enabled but insecure dashboard mode is disabled.

The `web` entry point rejects encoded reserved characters in request paths. This prevents Traefik and an application from decoding a path differently and bypassing a path-specific rule such as the protected Vaultwarden `/admin` router. Do not relax these settings without reviewing every public backend against Traefik's [encoded-character security guidance](https://doc.traefik.io/traefik/reference/install-configuration/entrypoints/#encoded-characters).

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

## Backup data

Back up these items together and encrypt the backup:

- `unraid/.env`;
- `unraid/edge/config/authelia/users.yml`;
- `unraid/edge/config/authelia/notification.txt` when it contains information you still need;
- `${APPDATA_PATH}/authelia`, including the SQLite database;
- the Git release or commit containing the Traefik and Authelia configuration;
- an inventory of Tunnel routes and DNS records.

The Authelia database must be restored with the matching storage encryption key. Tunnel tokens can be recreated and rotated, but keep a recovery plan that does not depend on the failed server.

## Security notes

- Treat the Tunnel token as a secret: it can connect another cloudflared instance to your Tunnel.
- Review every hostname before publishing it. A Tunnel is connectivity, not authentication.
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

### A dependent stack reports a missing external network

Start the complete edge stack and confirm the networks exist:

```bash
docker network ls
docker compose --env-file unraid/.env -f unraid/edge/compose.yml up -d
```

## Official upstream documentation

- [Cloudflare Tunnel overview](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/)
- [Cloudflare published application routes](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/routing-to-tunnel/)
- [Traefik file provider](https://doc.traefik.io/traefik/providers/file/)
- [Traefik ForwardAuth middleware](https://doc.traefik.io/traefik/middlewares/http/forwardauth/)
- [Authelia proxy integrations](https://www.authelia.com/integration/proxies/)
- [Authelia access control](https://www.authelia.com/configuration/security/access-control/)
- [Authelia file authentication backend](https://www.authelia.com/configuration/first-factor/file/)
- [Authelia password hashing](https://www.authelia.com/reference/guides/passwords/)
