# Servarr stack

The Servarr stack runs the media request, indexing, download, and library automation services on Unraid. Use these tools only with sources and media you are legally allowed to access. This guide explains infrastructure and application integration; it does not provide instructions for finding copyrighted content.

## Services

| Service | Purpose | Docker hostname and port | Public URL |
| --- | --- | --- | --- |
| qBittorrent VPN | Download client routed through an OpenVPN tunnel | `qbittorrent:8090` | `https://qbittorrent.DOMAIN` |
| Prowlarr | Indexer manager for Radarr and Sonarr | `prowlarr:9696` | `https://prowlarr.DOMAIN` |
| Radarr | Movie library automation | `radarr:7878` | `https://radarr.DOMAIN` |
| Sonarr | Series library automation | `sonarr:8989` | `https://sonarr.DOMAIN` |
| Seerr | Media request interface | `seerr:5055` | `https://seerr.DOMAIN` |
| Profilarr | Quality profile management | `profilarr:6868` | `https://profilarr.DOMAIN` |

Replace `DOMAIN` with the value in `unraid/.env`. None of these services publishes a host port. Traefik reaches them by Docker hostname on `servarr_backend`.

## Prerequisites and dependencies

Before deploying this stack, complete the [getting-started installation](../README.md#installation-path) and confirm that:

- `unraid/.env` contains the real paths, IDs, domain, and VPN settings;
- the `edge` stack is running and has created the external `servarr_backend` network;
- `HOMELAB_PATH` is the intended NAS mount and is available on Unraid;
- qBittorrent has exactly one `.ovpn` profile and its referenced certificates under `${APPDATA_PATH}/qbittorrentvpn/openvpn`;
- the VPN credentials are valid and the provider endpoint is reachable;
- the required application-data directories below `APPDATA_PATH` are writable by the correct identities;
- Plex is reachable on the NAS if Seerr will be connected to it.

Do not start the stack when `HOMELAB_PATH` is an unmounted local directory. qBittorrent or a library manager could write to the wrong filesystem.

## Network and storage model

All six services join `servarr_backend`, which is created by [`unraid/edge/compose.yml`](../../unraid/edge/compose.yml). Its repository subnet is `10.88.40.0/24`.

qBittorrent, Radarr, and Sonarr mount the same host path at the same container path:

```text
HOMELAB_PATH -> /data
```

Keep download and library paths below `/data` in all three applications. For example, a deployment may choose `/data/downloads`, `/data/media/movies`, and `/data/media/tv`; the repository does not prescribe these subdirectories. Do not enter the Unraid host path in an application. A single shared mount lets Radarr and Sonarr see qBittorrent's files without remote path mappings and supports hardlinks or atomic moves when the underlying filesystem permits them.

Persistent application data is stored as follows:

| Service | Host path | Container path |
| --- | --- | --- |
| qBittorrent | `${APPDATA_PATH}/qbittorrentvpn` | `/config` |
| Prowlarr | `${APPDATA_PATH}/prowlarr` | `/config` |
| Radarr | `${APPDATA_PATH}/radarr` | `/config` |
| Sonarr | `${APPDATA_PATH}/sonarr` | `/config` |
| Seerr | `${APPDATA_PATH}/seerr` | `/app/config` |
| Profilarr | `${APPDATA_PATH}/profilarr` | `/config` |

The numeric identities intentionally differ:

- Prowlarr uses `UID:GID` because it only stores local configuration.
- Profilarr explicitly runs as `UID:GID`.
- qBittorrent, Radarr, and Sonarr use `NAS_UID:NAS_GID` so they can share `/data`. Their application-data directories must also be writable by that identity.
- Seerr does not receive `PUID` or `PGID` in the current Compose file. Its image-selected runtime identity must be able to write `${APPDATA_PATH}/seerr`.

Avoid solving an ownership error with world-writable permissions. Correct the host owner, group, identity mapping, or ACL for the specific directory.

## Environment variables

The stack reads these values from `unraid/.env`:

| Variable | Used for |
| --- | --- |
| `TZ` | Timezone for every service |
| `DOMAIN` | Profilarr origin and all Traefik public hostnames |
| `APPDATA_PATH` | Persistent local application configuration |
| `HOMELAB_PATH` | Shared NAS-backed `/data` mount |
| `UID`, `GID` | Prowlarr and Profilarr identity |
| `NAS_UID`, `NAS_GID` | qBittorrent, Radarr, and Sonarr identity |
| `VPN_ENABLED` | Enables the qBittorrent VPN and fail-closed firewall; keep `yes` |
| `VPN_USER`, `VPN_PASS` | Provider-supplied VPN credentials |
| `VPN_PROV`, `VPN_CLIENT` | Provider and client; the template uses PIA and OpenVPN |
| `LAN_NETWORK` | LAN and Docker subnets allowed to reach qBittorrent and Privoxy |
| `NAME_SERVERS` | DNS resolvers used inside the VPN container |

With the repository network plan, `LAN_NETWORK` must include `10.88.40.0/24` as well as the trusted LAN. Comma-separate multiple CIDRs without spaces.

The qBittorrent container also has Privoxy enabled on internal port `8118`, strict port forwarding enabled, SOCKS disabled, and `NET_ADMIN` capability. Privoxy is not published on the Unraid host. An application on `servarr_backend` can optionally use `qbittorrent:8118` as an HTTP proxy. Proxying is per application; it does not route the entire Prowlarr, Radarr, or Sonarr container through the VPN.

## Deploy and verify

Run from the repository root on Unraid:

```bash
docker compose --env-file unraid/.env \
  -f unraid/servarr/compose.yml config --quiet

docker compose --env-file unraid/.env \
  -f unraid/servarr/compose.yml up -d
```

No output from `config --quiet` means the Compose model is valid. It does not test the VPN, storage, permissions, or application integrations.

Inspect the services:

```bash
docker compose --env-file unraid/.env \
  -f unraid/servarr/compose.yml ps
```

Every service should eventually be `Up` and `healthy`. The health checks call qBittorrent port `8090`, Prowlarr `/ping`, Radarr `/ping`, Sonarr `/ping`, Seerr `/api/v1/status`, and Profilarr `/api/v1/health` once per minute.

If a service is not healthy, inspect only its recent logs first:

```bash
docker compose --env-file unraid/.env \
  -f unraid/servarr/compose.yml logs --tail=150 qbittorrent
```

Replace `qbittorrent` with another Compose service name when needed.

## First configuration

Configure one service at a time. Use Docker hostnames for communication between containers, never `localhost` and never the public Cloudflare URL.

### 1. Secure and test qBittorrent

Open `https://qbittorrent.DOMAIN`. Authelia requires an `admins` user with two-factor authentication. The qBittorrent image generates an initial Web UI password and records it in `/config/supervisord.log`, which is stored at `${APPDATA_PATH}/qbittorrentvpn/supervisord.log` on Unraid. Retrieve it locally, sign in, and immediately set a unique permanent password.

In qBittorrent, choose download and incomplete-download directories below `/data`. Create categories if desired, but keep every category path below that shared mount.

Verify the VPN before adding any transfer:

1. Confirm `VPN_ENABLED=yes` and review the qBittorrent container logs for a successful OpenVPN connection rather than repeated authentication or endpoint errors.
2. Use a trusted IP-check service from inside the container and compare the result with the normal public address of your LAN. For example:

   ```bash
   docker exec qbittorrentvpn curl -fsS https://api.ipify.org
   ```

   The container address should be the VPN endpoint, not the normal ISP address. This request sends the observed IP address to the selected service; use the VPN provider's own check endpoint instead if preferred.
3. Perform a fail-closed startup test only during maintenance and with no active transfers. The container path `/config/openvpn` corresponds to the host directory `${APPDATA_PATH}/qbittorrentvpn/openvpn`. On the Unraid host:

   ```bash
   docker compose --env-file unraid/.env \
     -f unraid/servarr/compose.yml stop qbittorrent

   mv "${APPDATA_PATH}/qbittorrentvpn/openvpn/PROFILE.ovpn" \
     "${APPDATA_PATH}/qbittorrentvpn/PROFILE.ovpn.disabled"

   docker compose --env-file unraid/.env \
     -f unraid/servarr/compose.yml start qbittorrent
   ```

   Replace `PROFILE.ovpn` with the real profile filename, and expand `${APPDATA_PATH}` manually if it is not set in your shell. Confirm that VPN initialization fails and that qBittorrent does not become healthy or transfer data. Then stop the container again, move the profile back into `openvpn/`, start the service, and repeat the VPN address check.

   This procedure verifies that the container fails closed at startup when no VPN profile is available. It does not simulate a VPN drop during active transfers; use the image provider's documented kill-switch test for runtime behavior.

The image uses internal firewall rules intended to prevent IP leakage when the tunnel is unavailable. A green Web UI health check alone does not prove that the egress address is correct.

### 2. Connect Radarr and Sonarr to qBittorrent

In each application's download-client settings, add qBittorrent with:

| Setting | Value |
| --- | --- |
| Host | `qbittorrent` |
| Port | `8090` |
| Username and password | The qBittorrent Web UI credentials |
| URL base | Empty unless you deliberately changed it |

Use the application's test button before saving. Set the appropriate qBittorrent category and use paths below `/data`. Do not configure a remote path mapping when all three applications use the unchanged shared `/data` mount.

### 3. Connect Prowlarr to Radarr and Sonarr

Obtain the API key from each application's general settings. In Prowlarr's application settings, add:

| Application | Internal URL |
| --- | --- |
| Radarr | `http://radarr:7878` |
| Sonarr | `http://sonarr:8989` |

Paste the matching API key and test the connection. API keys are secrets; do not place them in documentation, Git, screenshots, or public issue logs. Configure only indexers that you are authorized to use.

### 4. Configure library roots

In Radarr and Sonarr, select root folders below `/data` that match the library layout mounted into Plex. Confirm that a test import can be read by the NAS-side Plex identity. If imports copy instead of hardlinking or atomic-moving, verify that downloads and libraries are on the same underlying filesystem and exposed through the single `/data` mount.

### 5. Connect Seerr

Complete Seerr's setup in its Web UI. Plex runs on the NAS with host networking, so use the NAS LAN address and port `32400` when manual server details are required. Connect Radarr with `http://radarr:7878` and Sonarr with `http://sonarr:8989`, using their API keys.

Seerr should request media through Radarr or Sonarr; it does not need direct access to `/data` in this Compose stack.

### 6. Configure Profilarr if used

Profilarr is optional. Follow its setup interface and use the internal Radarr and Sonarr URLs with their API keys when applying profiles. Review proposed profile changes before synchronizing them to an existing library.

## URLs and authentication

The Traefik routes apply rate limiting, security headers, and Authelia forward authentication.

| URL | Current Authelia policy |
| --- | --- |
| `qbittorrent.DOMAIN` | `admins` group plus two-factor authentication |
| `prowlarr.DOMAIN` | `admins` group plus two-factor authentication |
| `radarr.DOMAIN` | `admins` group plus two-factor authentication |
| `sonarr.DOMAIN` | `admins` group plus two-factor authentication |
| `profilarr.DOMAIN` | `admins` group plus two-factor authentication |
| `seerr.DOMAIN` | Falls through to the wildcard one-factor policy |

Authelia protects browser access but does not replace application passwords or API keys. Service-to-service requests use internal URLs and the authentication mechanism required by each application.

## Backups

Back up all six application-data directories, `unraid/.env`, and the qBittorrent OpenVPN files. The application-data directories contain databases, API keys, integration settings, and the qBittorrent state.

Back up the media/download filesystem separately according to its value and size. For a consistent application-data backup, stop the Servarr stack or use an application-aware backup method before copying active databases:

```bash
docker compose --env-file unraid/.env \
  -f unraid/servarr/compose.yml stop
```

Restart it with `start` after the backup. Test restoration to a separate location. A backup is incomplete if it cannot be restored with the original IDs, secrets, and paths.

## Security notes

- Keep VPN credentials, qBittorrent credentials, application passwords, and API keys outside Git.
- Do not expose the internal ports directly on the router. The current stack publishes none of them.
- qBittorrent requires `NET_ADMIN` to manage its tunnel and firewall. The other services do not receive that capability.
- Keep Authelia's administrator-only policies for management applications unless you have a deliberate alternative access model.
- Review the one-factor policy for Seerr against the audience allowed to submit requests.
- Do not use `VPN_ENABLED=no` as a troubleshooting shortcut while transfers exist.
- Ensure the NAS mount is present after every Unraid reboot before starting the stack.

## Common problems

### `servarr_backend` does not exist

Start the `edge` stack first. The Servarr Compose file declares this network as external and cannot create it.

### qBittorrent is unhealthy or keeps restarting

Confirm that exactly one `.ovpn` profile exists, every referenced certificate is present, the VPN credentials are correct, and the provider endpoint is reachable. Review `LAN_NETWORK`; it must include both the trusted client LAN and `10.88.40.0/24` unless the network plan was changed.

### An application cannot connect to another service

Use the Docker hostname and internal port from the service table. `localhost` means the current container, not another service. Test the API key or qBittorrent credentials again.

### Imports fail with `permission denied`

Verify that qBittorrent, Radarr, and Sonarr use the intended `NAS_UID:NAS_GID`, that this identity can write `/data`, and that their individual application-data directories have compatible ownership.

### Files copy instead of hardlinking

Confirm that both download and library paths are below the same `/data` mount and on a filesystem that supports hardlinks. Separate container mounts or separate filesystems force a copy.

### A public URL returns `502` or `504`

Check the target container health, then confirm Traefik and the service both join `servarr_backend`. A successful Cloudflare Tunnel connection does not make an unhealthy backend available.

### Seerr cannot find Plex

Use the NAS LAN address and port `32400`, not `plex` as a Docker hostname. Plex runs on a different host. Confirm the NAS firewall permits access from the Unraid host.

## Official upstream documentation

- [Servarr wiki](https://wiki.servarr.com/)
- [Prowlarr](https://wiki.servarr.com/prowlarr)
- [Radarr](https://wiki.servarr.com/radarr)
- [Sonarr](https://wiki.servarr.com/sonarr)
- [Seerr documentation](https://docs.seerr.dev/)
- [Profilarr documentation](https://dictionarry.dev/profilarr-setup/)
- [binhex qBittorrent VPN image](https://github.com/binhex/arch-qbittorrentvpn)
- [LinuxServer Radarr image and shared-path guidance](https://docs.linuxserver.io/images/docker-radarr/)

