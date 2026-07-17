# Quick start

This page is the shortest supported path to a first HavenStack deployment. It assumes the reference design: Unraid runs the web and automation stacks, while a separate NAS provides storage and runs Plex and Arcane.

HavenStack is not a one-click installer. Read the linked detailed guide whenever a step does not match your environment.

## 1. Check the requirements

Before copying any commands, read [Prerequisites](prerequisites.md). You need, at minimum:

- Docker Engine and Docker Compose on each host;
- static LAN addresses for Unraid and the NAS;
- a Cloudflare-managed domain and a remotely managed Tunnel;
- mounted NAS storage for Nextcloud and Servarr;
- numeric user and group IDs that match your storage permissions;
- a VPN account and OpenVPN profile for qBittorrent.

The complete topology is explained in [Architecture overview](../architecture/overview.md). See [Networking](../architecture/networking.md) and [Storage](../architecture/storage.md) before changing paths or subnets.

## 2. Get the repository

Place a copy of the repository on every host that will run a stack:

```bash
git clone https://github.com/shuntps/HavenStack.git
cd HavenStack
```

Run the remaining commands from the repository root. The NAS and Unraid may use separate checkouts.

## 3. Create the environment files

On Unraid:

```bash
cp unraid/.env.example unraid/.env
```

On the NAS:

```bash
cp nas/.env.example nas/.env
```

Follow [Configuration](configuration.md) to replace every placeholder, create the required directories, generate unique secrets, create the Authelia user file, and install the VPN profile.

Do not continue while any required value still begins with `replace-with-`. Never commit populated `.env` files or other secrets.

## 4. Configure Cloudflare

Follow [Configure the Cloudflare Tunnel](cloudflare-tunnel.md). The reference setup requires:

- `example.com` routed to `http://traefik:8080`;
- `*.example.com` routed to `http://traefik:8080`;
- a proxied wildcard `CNAME` DNS record pointing to the tunnel, created manually when Cloudflare does not create it;
- a final `http_status:404` catch-all;
- `ddns.example.com` managed separately by the DDNS updater.

Replace `example.com` with `DOMAIN`. Do not let DDNS manage the Tunnel apex or wildcard records.

## 5. Validate and deploy

For each stack, run these three operations with the environment file and Compose path from the table:

```bash
docker compose --env-file ENVIRONMENT_FILE \
  -f COMPOSE_FILE config --quiet

docker compose --env-file ENVIRONMENT_FILE \
  -f COMPOSE_FILE up -d

docker compose --env-file ENVIRONMENT_FILE \
  -f COMPOSE_FILE ps
```

Replace `ENVIRONMENT_FILE` and `COMPOSE_FILE` with the values from the table.

| Host | Order | Environment file | Compose file |
| --- | ---: | --- | --- |
| NAS | Independent | `nas/.env` | `nas/plex/compose.yml` |
| NAS | Independent | `nas/.env` | `nas/arcane/compose.yml` |
| Unraid | 1 | `unraid/.env` | `unraid/edge/compose.yml` |
| Unraid | 2 | `unraid/.env` | `unraid/apps/compose.yml` |
| Unraid | 3 | `unraid/.env` | `unraid/nextcloud/compose.yml` |
| Unraid | 4 | `unraid/.env` | `unraid/servarr/compose.yml` |
| Unraid | 5 | `unraid/.env` | `unraid/monitoring/compose.yml` |

The NAS stacks do not depend on one another. If the NAS supplies `HOMELAB_PATH` or `CLOUD_PATH`, bring the NAS and those mounts online before starting Servarr or Nextcloud.

On Unraid, always start `edge` first. It creates the external Docker networks required by the other Unraid stacks.

`config --quiet` checks Compose syntax, interpolation, and the resulting model. It does not test paths, permissions, mounts, tokens, application behavior, or health.

For copy-and-paste commands, expected states, logs, and common errors, use [Deployment](deployment.md).

## 6. Verify the installation

Wait for health-checked services to become `healthy`. A temporary `starting` status is normal, especially for Nextcloud. cloudflare-ddns has no Compose health check and normally shows only `Up`.

If a service does not become healthy, inspect its stack logs. For example:

```bash
docker compose --env-file unraid/.env \
  -f unraid/edge/compose.yml logs --tail=100
```

Then complete the [First-run checklist](first-run-checklist.md). It covers Cloudflare routes, Authelia two-factor authentication, Vaultwarden account bootstrap, the qBittorrent VPN kill switch, storage tests, and backups.

Use the [stack guides](../stacks/README.md) for application-specific setup.

## Safety rules

- Review the preconfigured `unraid.example.com` and `nas.example.com` management routes in `unraid/edge/config/traefik/dynamic/external.yml` before starting `edge`; remove them if you do not need them.
- Confirm remote NAS mounts before every stack start that can write to them.
- Keep secrets and authentication files out of Git.
- Do not expose additional host ports as a troubleshooting shortcut.
- Back up configuration and state before updates.
- Never use `docker compose down -v` for routine maintenance; it can delete named volumes.
