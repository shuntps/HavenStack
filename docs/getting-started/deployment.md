# Deploy HavenStack

This guide takes you from prepared configuration files to running containers. Run every command from the root of the HavenStack repository unless a step says otherwise.

HavenStack is split between two machines:

- The **NAS stack** runs Plex.
- The **Unraid stacks** run the edge, application, Nextcloud, Servarr, and monitoring services. On Unraid, deploy `edge` first because it creates the shared Docker networks used by the other stacks.

If the NAS provides the storage mounted by Unraid, make sure the NAS and those mounts are available before starting Nextcloud or Servarr.

## Before you begin

You should already have:

- Docker Engine and the Docker Compose plugin installed on each target machine.
- A copy of this repository on each machine that will run a stack.
- `unraid/.env` created from `unraid/.env.example` on Unraid.
- `nas/.env` created from `nas/.env.example` on the NAS.
- Every `replace-with-*` value replaced with a real value.
- The directories referenced by `APPDATA_PATH`, `HOMELAB_PATH`, `CLOUD_PATH`, `DATA_PATH`, and `MEDIA_PATH` created and writable by the configured user IDs.
- The NAS shares used by `HOMELAB_PATH` and `CLOUD_PATH` mounted on Unraid. Do not continue if these paths are supposed to be remote mounts but are currently empty local directories.
- `unraid/edge/config/authelia/users.yml` created from `users.yml.example`, with a real Argon2id password hash.
- A provider-supplied OpenVPN profile and its required certificates in the host directory mounted as qBittorrent's `/config/openvpn` directory. With the default layout, this is `${APPDATA_PATH}/qbittorrentvpn/openvpn`.

Keep populated `.env` files, Authelia users, VPN profiles, certificates, and private keys out of Git. If a secret contains `$`, use Docker Compose's env-file quoting rules so it is not accidentally interpolated. In particular, a single-quoted value is treated literally.

## 1. Validate the Compose configuration

Validate only the stacks you intend to deploy. These commands use the real local `.env` files, so Compose can report unresolved variables and interpolation errors. A placeholder such as `replace-with-a-secret` is still syntactically valid, which is why you must check placeholders separately.

### NAS

Run these commands on the NAS:

```bash
docker compose --env-file nas/.env \
  -f nas/plex/compose.yml config --quiet
```

### Unraid

Run these commands on Unraid:

```bash
docker compose --env-file unraid/.env \
  -f unraid/edge/compose.yml config --quiet

docker compose --env-file unraid/.env \
  -f unraid/apps/compose.yml config --quiet

docker compose --env-file unraid/.env \
  -f unraid/nextcloud/compose.yml config --quiet

docker compose --env-file unraid/.env \
  -f unraid/servarr/compose.yml config --quiet

docker compose --env-file unraid/.env \
  -f unraid/monitoring/compose.yml config --quiet
```

No output and an exit code of `0` means the validation passed.

`config --quiet` validates the Compose syntax, variable interpolation, and resulting Compose model. It does **not** prove that:

- host directories exist or have the correct permissions;
- remote NAS shares are mounted;
- credentials and tokens are valid;
- an image is compatible with the host;
- Docker network ranges do not conflict with the rest of your environment;
- a container can start or pass its health check;
- an application works correctly.

Do not publish the output of `docker compose config` without `--quiet`: the rendered configuration can contain secrets from your `.env` file.

## 2. Optionally pull images first

`docker compose up -d` downloads missing images automatically. Pulling them first is optional, but it separates download failures from startup failures.

For a new NAS installation:

```bash
docker compose --env-file nas/.env -f nas/plex/compose.yml pull
```

For a new Unraid installation:

```bash
docker compose --env-file unraid/.env -f unraid/edge/compose.yml pull
docker compose --env-file unraid/.env -f unraid/apps/compose.yml pull
docker compose --env-file unraid/.env -f unraid/nextcloud/compose.yml pull
docker compose --env-file unraid/.env -f unraid/servarr/compose.yml pull
docker compose --env-file unraid/.env -f unraid/monitoring/compose.yml pull
```

For an existing installation, do not treat `pull` as a complete update procedure. Back up stateful services and review the image changes first, especially for images using the `latest` tag.

## 3. Deploy the NAS stack

Start Plex on the NAS:

```bash
docker compose --env-file nas/.env \
  -f nas/plex/compose.yml up -d
```

Check the deployed stack:

```bash
docker compose --env-file nas/.env -f nas/plex/compose.yml ps
```

Plex uses host networking and normally listens on port `32400`. Confirm that this port is reachable only from networks you trust.

## 4. Deploy the Unraid stacks

### Start the edge stack first

The edge stack creates `edge_ingress`, `auth_backend`, `apps_backend`, `servarr_backend`, `homepage_backend`, and `monitoring_backend`. Other Unraid stacks refer to several of these as external networks. Start the complete edge stack:

```bash
docker compose --env-file unraid/.env \
  -f unraid/edge/compose.yml up -d
```

Check it before continuing:

```bash
docker compose --env-file unraid/.env -f unraid/edge/compose.yml ps
```

It is normal for health status to show `starting` briefly. Wait for Traefik, Authelia, and cloudflared to become healthy.

If the edge services remain unhealthy, inspect their logs before starting more stacks:

```bash
docker compose --env-file unraid/.env \
  -f unraid/edge/compose.yml logs --tail=100
```

### Start the remaining stacks

Once `edge` is running, start the stacks you want in this order:

```bash
docker compose --env-file unraid/.env \
  -f unraid/apps/compose.yml up -d

docker compose --env-file unraid/.env \
  -f unraid/nextcloud/compose.yml up -d

docker compose --env-file unraid/.env \
  -f unraid/servarr/compose.yml up -d

docker compose --env-file unraid/.env \
  -f unraid/monitoring/compose.yml up -d
```

Nextcloud can take several minutes during its first initialization. Its internal services use health-based dependencies, so do not interrupt it merely because some containers initially show `starting`.

## 5. Verify the deployment

Check every Unraid stack you deployed:

```bash
docker compose --env-file unraid/.env -f unraid/edge/compose.yml ps
docker compose --env-file unraid/.env -f unraid/apps/compose.yml ps
docker compose --env-file unraid/.env -f unraid/nextcloud/compose.yml ps
docker compose --env-file unraid/.env -f unraid/servarr/compose.yml ps
docker compose --env-file unraid/.env -f unraid/monitoring/compose.yml ps
```

The expected result is:

- each requested service is `Up`;
- services with a health check eventually report `healthy`;
- no service repeatedly restarts;
- logs do not show recurring authentication, permission, mount, database, or network errors.

To inspect one stack:

```bash
docker compose --env-file unraid/.env \
  -f unraid/nextcloud/compose.yml logs --tail=100
```

To inspect one service, add its Compose service name:

```bash
docker compose --env-file unraid/.env \
  -f unraid/nextcloud/compose.yml logs --tail=100 nextcloud-aio-nextcloud
```

Add `--follow` to watch new log messages. Press `Ctrl+C` to stop watching; this does not stop the containers.

Container health is necessary but not sufficient. Complete the [first-run checklist](first-run-checklist.md) before relying on the installation or storing important data.

## Safe stop and restart commands

For routine maintenance, prefer `stop` and `start`. This preserves containers, networks, and volumes:

```bash
docker compose --env-file unraid/.env \
  -f unraid/servarr/compose.yml stop

docker compose --env-file unraid/.env \
  -f unraid/servarr/compose.yml start
```

After changing a Compose file or `.env` value, run validation again and apply the change with `up -d`:

```bash
docker compose --env-file unraid/.env \
  -f unraid/servarr/compose.yml config --quiet

docker compose --env-file unraid/.env \
  -f unraid/servarr/compose.yml up -d
```

`restart` only restarts existing containers; it does not reliably apply changed Compose configuration.

Avoid taking the edge stack down while other Unraid stacks use its networks. If full shutdown is required, stop the dependent stacks first and stop `edge` last.

> **Never add `-v` to `docker compose down` unless you intentionally want to delete named volumes and have verified backups.** For routine maintenance, `docker compose stop` is safer.

## Common deployment errors

### `env file ... not found`

- Run the command from the repository root.
- Confirm that the correct machine has `unraid/.env` or `nas/.env`.
- Copy the corresponding `.env.example` if the file has not been created yet, then replace every placeholder.

### A variable is missing or empty

- Compare the local `.env` with the matching `.env.example`.
- Check spelling and quoting.
- Run `config --quiet` again.
- Do not paste the populated `.env` or rendered Compose configuration into a public issue.

### `network ... declared as external, but could not be found`

The Unraid `edge` stack has not created the shared networks, or it was removed.

```bash
docker network ls
docker compose --env-file unraid/.env -f unraid/edge/compose.yml up -d
```

Then retry the dependent stack.

### Docker reports an overlapping network range

The configured `10.88.x.0/24` or `10.68.10.0/24` range conflicts with another Docker, LAN, or VPN network. Resolve the subnet plan before starting the stacks. If you change `servarr_backend`, also review `LAN_NETWORK` because qBittorrent must permit that backend network.

### `permission denied` or a container cannot write data

- Confirm that the host path exists.
- Confirm that the NAS share is actually mounted.
- Verify `UID`, `GID`, `NAS_UID`, and `NAS_GID` against the owner of the target directories.
- Check that Docker is allowed to access the path.
- Correct ownership or permissions deliberately; do not make sensitive directories world-writable as a shortcut.

### A service stays `unhealthy` or restarts

Use `ps` and `logs --tail=100` for that stack. Common causes include invalid credentials, unavailable databases, wrong permissions, missing VPN files, unavailable mounts, or conflicting ports. Fix the first recurring error rather than repeatedly restarting the container.

### A public URL returns `502` or `504`

- Confirm the target application is healthy.
- Confirm Traefik and cloudflared are healthy.
- Confirm the application and Traefik share the expected Docker network.
- Confirm the Cloudflare Tunnel public hostname points to the Traefik origin used by this topology.

### A container name or port is already in use

Inspect the existing container or process before changing or deleting anything. It may belong to an earlier installation or another application. Do not remove an unknown container just to make the command succeed.
