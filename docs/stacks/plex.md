# Plex stack

The Plex stack runs one Plex Media Server container on the NAS. It reads the NAS media library directly and keeps its database, metadata, and application state under `DATA_PATH`.

## Service and purpose

| Service | Image | Purpose |
| --- | --- | --- |
| `plex` | `linuxserver/plex:1.43.3` | Organizes and streams media from the NAS |

The container has a `1g` memory limit, a restart policy of `unless-stopped`, and a health check against `http://127.0.0.1:32400/identity`.

## Prerequisites and dependencies

Plex is independent of the Unraid Docker networks and can be deployed before or after the Unraid stacks. Prepare:

- Docker Engine and Docker Compose v2 on the NAS;
- a populated `nas/.env`;
- a stable `NAS_IP`;
- `${DATA_PATH}/plex` with enough space for Plex metadata and databases;
- `MEDIA_PATH` containing the media library;
- a `UID:GID` that can read the media and write Plex configuration;
- NAS port `32400` available;
- `/dev/dri` available and accessible if using the Compose file unchanged.

Plex may require outbound internet access for account authentication, metadata, and updates to its online services.

## Network and storage

Plex uses `network_mode: host`. It shares the NAS network namespace instead of joining a Docker bridge, so there is no `ports` section and no Docker hostname for containers on Unraid. Its normal LAN URL is:

```text
http://NAS_IP:32400/web
```

Host networking gives Plex broad access to the NAS network interfaces. Use the NAS firewall and trusted LAN boundaries to control access.

The stack mounts:

| Host path | Container path | Contents |
| --- | --- | --- |
| `${DATA_PATH}/plex` | `/config` | Plex database, metadata, preferences, logs, and state |
| `${MEDIA_PATH}` | `/media` | Media library |
| `/dev/dri` | `/dev/dri` | Linux GPU device for optional hardware acceleration |

The media mount is read/write in the current Compose file. Plex application settings determine whether library files may be deleted. If you want a read-only library, evaluate the required Plex features and make a deliberate Compose change rather than assuming the current mount is read-only.

## Environment variables

The stack reads these values from `nas/.env`:

| Variable | Purpose |
| --- | --- |
| `TZ` | Plex timezone |
| `NAS_IP` | Documented LAN address used to reach the NAS; Plex itself uses host networking |
| `UID`, `GID` | Numeric identity used by the LinuxServer image |
| `DATA_PATH` | Parent of the persistent `/config` directory |
| `MEDIA_PATH` | Host media root mounted at `/media` |

The Compose file also fixes `VERSION=docker` and `UMASK=022`. Files created by Plex are writable by their owner and readable by the owner, group, and others, subject to the NAS filesystem ACLs.

## Hardware acceleration and `/dev/dri`

The current Compose file always maps `/dev/dri`. Check it before deployment:

```bash
ls -l /dev/dri
```

If the directory exists, ensure the container identity is permitted to use the required render device. Hardware support, Plex account requirements, and codec support still determine whether a stream can be hardware-transcoded.

If the NAS has no compatible device and you want software transcoding, deliberately remove or override the `devices` mapping before deployment. The current stack does not provide an automatic fallback for a missing host device. Keep this change under version control if it belongs to your deployment rather than editing an untracked copy that will be forgotten.

## Deploy and verify

Run from the repository root on the NAS:

```bash
docker compose --env-file nas/.env \
  -f nas/plex/compose.yml config --quiet

docker compose --env-file nas/.env \
  -f nas/plex/compose.yml up -d
```

Check the container:

```bash
docker compose --env-file nas/.env \
  -f nas/plex/compose.yml ps
```

It should eventually show `Up` and `healthy`. Verify the same endpoint used by the health check from the NAS:

```bash
curl -fsS http://127.0.0.1:32400/identity
```

A successful request returns a small XML response. It proves that the local Plex process is responding, not that sign-in, media access, transcoding, or remote playback works.

If startup fails, inspect recent logs:

```bash
docker compose --env-file nas/.env \
  -f nas/plex/compose.yml logs --tail=150 plex
```

## First configuration

1. From a trusted device on the LAN, open `http://NAS_IP:32400/web`.
2. Sign in with the Plex account that should own the server and follow Plex's server setup flow.
3. Give the server a recognizable name.
4. Add libraries using paths **inside the container**, below `/media`. For example, if the host directory is `${MEDIA_PATH}/Movies`, select `/media/Movies` in Plex.
5. Start a library scan and confirm that Plex can read representative files.
6. Test direct playback from a LAN client.
7. If hardware acceleration is intended, enable it in Plex according to the current Plex requirements and verify a test transcode in the Plex activity display.

HavenStack does not define a Traefik route for Plex. The wildcard Cloudflare Tunnel route does not automatically create a Plex backend. Remote Plex access, a private VPN, or a separate reverse-proxy design must be configured deliberately outside this stack.

## URL and authentication

The local URL is `http://NAS_IP:32400/web`. Authentication is handled by Plex, not Authelia. Do not publish port `32400` to the internet without understanding Plex's supported remote-access model and the NAS firewall rules.

Seerr runs on Unraid and should connect to Plex using the NAS LAN address and port `32400` when manual details are required. The Docker hostname `plex` is not valid from the Unraid `servarr_backend` network.

## Backups

Back up the complete `${DATA_PATH}/plex` directory. It contains the server identity, database, metadata, posters, preferences, and other state needed to reproduce the installation. Also retain a protected copy of `nas/.env` so the original `UID`, `GID`, and paths are known.

For a consistent filesystem copy, stop Plex first:

```bash
docker compose --env-file nas/.env \
  -f nas/plex/compose.yml stop
```

Restart it after the backup:

```bash
docker compose --env-file nas/.env \
  -f nas/plex/compose.yml start
```

The media library requires its own backup strategy. Plex metadata is not a substitute for the original media. Test a restore to a separate path and preserve the original ownership.

## Security notes

- Restrict NAS port `32400` to intended clients and networks.
- Protect the Plex owner account with the strongest authentication options Plex currently offers.
- The container has `no-new-privileges`, but host networking and `/dev/dri` still grant meaningful host access.
- Ensure `UID:GID` has only the filesystem access Plex requires.
- Review whether the read/write media mount matches your deletion policy.
- Avoid placing Plex configuration or account data in Git or public logs.

## Common problems

### The container fails before becoming healthy

Check whether `/dev/dri` exists. A missing device mapping can prevent container creation. If hardware acceleration is not required, adapt the Compose file deliberately as described above.

### Port `32400` is already in use

Because Plex uses host networking, another Plex process or service on the NAS can conflict directly. Identify the existing listener before stopping or deleting anything.

### Plex opens but shows no media

Confirm that the selected library path starts with `/media`, that the host files exist below `MEDIA_PATH`, and that `UID:GID` or the NAS ACL grants read access through every parent directory.

### Plex cannot write its database or remains in setup

Verify that `${DATA_PATH}/plex` is writable by `UID:GID`, has free space, and is on a healthy filesystem. Inspect the Plex logs before changing permissions.

### Hardware transcoding is not used

Confirm the device exists, its permissions allow access, the hardware and codec are supported, and the Plex setting is enabled. A mounted `/dev/dri` device alone does not guarantee hardware transcoding.

### Seerr cannot connect

Use `http://NAS_IP:32400`, not `localhost` and not `plex:32400`. Confirm the NAS firewall allows traffic from Unraid.

## Official upstream documentation

- [LinuxServer Plex container documentation](https://docs.linuxserver.io/images/docker-plex/)
- [Plex Media Server setup](https://support.plex.tv/articles/200264746-quick-start-step-by-step-guides/)
- [Plex support](https://support.plex.tv/)
