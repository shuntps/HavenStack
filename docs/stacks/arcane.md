# Arcane stack

Arcane provides a browser-based management interface for the Docker Engine running on the NAS. The current stack manages the local NAS Docker daemon through `/var/run/docker.sock`; it is not configured as a remote manager for Unraid.

## Service and purpose

| Service | Repository image | Purpose |
| --- | --- | --- |
| `arcane` | `ghcr.io/getarcaneapp/arcane:latest` | Inspect and manage local Docker resources |

The container has a `512m` memory limit, restarts unless stopped, and uses Arcane's built-in `/app/arcane health` command.

The repository currently uses the `arcane:latest` image name, while current upstream installation examples use `ghcr.io/getarcaneapp/manager:latest`. This guide does not silently change the Compose file. Verify the repository image before a new installation and review an image-name migration as a separate tested change.

## Prerequisites and dependencies

Arcane is independent of the Unraid stacks. The NAS needs:

- Docker Engine with a local `/var/run/docker.sock` Unix socket;
- Docker Compose v2;
- a populated `nas/.env`;
- a stable `NAS_IP` assigned to a NAS interface;
- `${DATA_PATH}/arcane` writable by `UID:GID`;
- two unique 32-byte secrets;
- unused NAS TCP port `3552`;
- no existing Docker network that overlaps `10.68.10.0/24`.

Only trusted administrators should be able to reach Arcane. Access to a Docker management API can lead to full control of the NAS.

## Network and storage

Arcane joins a dedicated bridge named `arcane` with subnet `10.68.10.0/24`. Its Web UI is published only on the configured NAS address:

```text
NAS_IP:3552 -> container port 3552
```

The stack mounts:

| Host path | Container path | Purpose |
| --- | --- | --- |
| `${DATA_PATH}/arcane` | `/app/data` | Arcane database and persistent state |
| `/var/run/docker.sock` | `/var/run/docker.sock` | Local Docker API |

The socket bind includes `:ro`, but this only makes the mounted socket filesystem entry read-only. It does **not** turn Docker API operations into read-only operations. Arcane can still send requests that start, stop, create, update, or delete Docker resources. Treat this container as highly privileged even though it also has `no-new-privileges` enabled.

## Environment variables and secrets

The stack reads:

| Variable | Purpose |
| --- | --- |
| `TZ` | Arcane timezone |
| `NAS_IP` | Host address on which port `3552` is published |
| `UID`, `GID` | Numeric identity used for Arcane data |
| `DATA_PATH` | Parent of the persistent Arcane directory |
| `ENCRYPTION_KEY` | Encryption key for protected Arcane data |
| `JWT_SECRET` | Secret used to sign authentication tokens |

Current Arcane documentation requires `ENCRYPTION_KEY` to be 32 bytes and recommends 32 bytes for both generated secrets. Generate each separately:

```bash
openssl rand -hex 32
```

Each command prints 64 hexadecimal characters, representing 32 random bytes. Never reuse a value. Store the results in `nas/.env`, keep a secure backup, and do not commit the file.

Generate these values once for an installation. Changing `ENCRYPTION_KEY` later can make encrypted stored data unreadable; changing `JWT_SECRET` invalidates existing sessions.

## Deploy and verify

Run from the repository root on the NAS:

```bash
docker compose --env-file nas/.env \
  -f nas/arcane/compose.yml config --quiet

docker compose --env-file nas/.env \
  -f nas/arcane/compose.yml pull

docker compose --env-file nas/.env \
  -f nas/arcane/compose.yml up -d
```

The separate `pull` makes an unavailable or renamed image visible before container creation. Because the repository uses `latest`, review the image change and back up Arcane before repeating this command during an update.

Check the service:

```bash
docker compose --env-file nas/.env \
  -f nas/arcane/compose.yml ps
```

It should eventually report `Up` and `healthy`. Inspect logs if it does not:

```bash
docker compose --env-file nas/.env \
  -f nas/arcane/compose.yml logs --tail=150 arcane
```

Confirm the NAS is listening on the configured address:

```bash
curl -fsS http://NAS_IP:3552/api/health
```

Replace `NAS_IP` first. A successful response proves the Arcane process is responding, not that login or every Docker action works.

## First configuration

1. From a trusted LAN device, open `http://NAS_IP:3552`.
2. Follow the first-run flow presented by the installed Arcane version.
3. Change any initial administrator password immediately if prompted, and store the new credential in a password manager.
4. Confirm that Arcane lists the NAS containers, images, networks, and volumes expected from the local Docker Engine.
5. Test with a non-critical container before relying on Arcane for management actions.

Do not copy default credentials from an old guide: first-run behavior can change with the unpinned `latest` image. Follow the installed UI and current upstream documentation.

## URL and authentication

The configured URL is:

```text
http://NAS_IP:3552
```

Authentication is handled by Arcane. HavenStack does not define a Traefik or Authelia route for Arcane; `nas.DOMAIN` points to the NAS management endpoint configured in Traefik, not Arcane.

Keep Arcane on a trusted management LAN or behind a deliberately configured private access layer. Do not publish port `3552` directly to the internet. If a reverse proxy is added later, follow Arcane's WebSocket and proxy guidance and retain Arcane authentication.

## Backups

Back up these items together:

- `${DATA_PATH}/arcane`;
- `nas/.env`, especially the original `ENCRYPTION_KEY` and `JWT_SECRET`;
- the Compose file version used by the installation.

For a consistent filesystem backup, stop Arcane first:

```bash
docker compose --env-file nas/.env \
  -f nas/arcane/compose.yml stop
```

Restart it afterward:

```bash
docker compose --env-file nas/.env \
  -f nas/arcane/compose.yml start
```

The Docker socket is not data and should not be backed up. Arcane data also does not replace backups of the containers, Compose files, volumes, and bind-mounted data that it manages. Test restoration with the same secrets and ownership.

## Security notes

- Treat Arcane access as equivalent to Docker administrator access.
- Restrict `NAS_IP:3552` with the NAS firewall or management network.
- Use a unique administrator password and the strongest authentication options supported by the installed Arcane version.
- Keep `ENCRYPTION_KEY`, `JWT_SECRET`, and `nas/.env` outside Git and public logs.
- Do not assume the `:ro` Docker socket bind prevents destructive API calls.
- Consider Arcane's documented socket-proxy option if its reduced-access model fits your requirements.
- Review every update because the Compose file currently uses the mutable `latest` tag.
- Do not use Arcane to delete an unfamiliar container, volume, image, or network merely to clear an error.

## Common problems

### The image cannot be pulled

The repository image name may no longer match current upstream packaging. Compare the pinned repository configuration with the current Arcane installation and migration documentation before changing it. Do not switch image names without backing up `${DATA_PATH}/arcane` and reviewing migration notes.

### `bind: cannot assign requested address`

`NAS_IP` is not assigned to a NAS network interface, or it contains an old address. Correct `nas/.env` and validate the Compose model again.

### Port `3552` is already in use

Identify the current listener before changing the port or stopping anything. If the Arcane port is changed, update the URL and firewall rules consistently.

### Docker network overlap

The `arcane` network uses `10.68.10.0/24`. Select a non-conflicting subnet in the Compose file if that range is already used by the LAN, VPN, or another Docker network.

### Arcane cannot list or manage containers

Confirm `/var/run/docker.sock` exists and that the Arcane process can open it. Inspect container logs for permission or API-version errors. Do not make the socket world-writable.

### Arcane cannot write its data

Confirm `${DATA_PATH}/arcane` exists, has free space, and is writable by `UID:GID`. Correct the specific ownership or ACL instead of granting broad write permissions.

### Login fails after changing a secret

Restore the original `ENCRYPTION_KEY` and `JWT_SECRET` from the protected backup. Secrets are persistent installation state, not disposable passwords.

## Official upstream documentation

- [Arcane documentation](https://getarcane.app/docs)
- [Arcane installation guide](https://getarcane.app/docs/setup/installation)
- [Arcane container management](https://getarcane.app/docs/features/containers)
- [Arcane source repository](https://github.com/getarcaneapp/arcane)

