# Storage

HavenStack stores persistent state in three places:

1. bind-mounted directories on Unraid and the NAS;
2. Docker named volumes used by Nextcloud;
3. local configuration and secret files that are intentionally excluded from Git.

Container filesystems and `tmpfs` mounts are disposable. If important data is not stored in a bind mount or named volume, it will not survive container replacement.

## On this page

- [Storage path variables](#storage-path-variables)
- [Unraid bind mounts](#unraid-bind-mounts)
- [Nextcloud named volumes and bind mount](#nextcloud-named-volumes-and-bind-mount)
- [NAS bind mounts](#nas-bind-mounts)
- [Ownership and permissions](#ownership-and-permissions)
- [Verify remote mounts before startup](#verify-remote-mounts-before-startup)
- [What needs backup](#what-needs-backup)
- [Backup consistency and safe stopping](#backup-consistency-and-safe-stopping)
- [Disposable items](#disposable-items)

## Storage path variables

| Host | Variable | Example | Purpose |
| --- | --- | --- | --- |
| Unraid | `APPDATA_PATH` | `/mnt/user/appdata` | Persistent application databases and configuration |
| Unraid | `HOMELAB_PATH` | `/mnt/remotes/nas-homelab` | NAS-backed media/download tree shared by qBittorrent, Radarr, and Sonarr |
| Unraid | `CLOUD_PATH` | `/mnt/remotes/nas_cloud` | NAS-backed Nextcloud user-data directory |
| NAS | `DATA_PATH` | `/volume1/docker` | Persistent Plex and Arcane application data |
| NAS | `MEDIA_PATH` | `/volume1/media` | Media library mounted into Plex |

The example paths are not universal. Set them to real existing locations on your hosts.

`HOMELAB_PATH` and `CLOUD_PATH` use `:rslave` mount propagation. This allows relevant nested host mounts to appear in the container, but it does not verify that the NAS share is mounted. Never start a writer when either path is an empty fallback directory on the Unraid filesystem.

## Unraid bind mounts

### Edge and apps

| Service | Host path | Container path | Data |
| --- | --- | --- | --- |
| Traefik | `unraid/edge/config/traefik` | `/etc/traefik` | Tracked static and dynamic routing configuration, read-only |
| Authelia | `unraid/edge/config/authelia` | `/config` | Tracked configuration plus local `users.yml` and `notification.txt` |
| Authelia | `${APPDATA_PATH}/authelia` | `/data` | SQLite database and authentication state |
| Vaultwarden | `${APPDATA_PATH}/vaultwarden` | `/data` | SQLite database, attachments, Sends, keys, and possible `config.json` |

Homepage, cloudflared, cloudflare-ddns, and Traefik have no persistent runtime-data directory in their Compose services. Homepage cache and temporary directories use `tmpfs`.

### Servarr

| Service | Host path | Container path | Data |
| --- | --- | --- | --- |
| qBittorrent | `${APPDATA_PATH}/qbittorrentvpn` | `/config` | qBittorrent settings and VPN profiles |
| qBittorrent | `${HOMELAB_PATH}` | `/data` | Downloads and shared media tree |
| Prowlarr | `${APPDATA_PATH}/prowlarr` | `/config` | Application database and settings |
| Radarr | `${APPDATA_PATH}/radarr` | `/config` | Application database and settings |
| Radarr | `${HOMELAB_PATH}` | `/data` | Shared downloads and movie library |
| Sonarr | `${APPDATA_PATH}/sonarr` | `/config` | Application database and settings |
| Sonarr | `${HOMELAB_PATH}` | `/data` | Shared downloads and television library |
| Seerr | `${APPDATA_PATH}/seerr` | `/app/config` | Application database and settings |
| Profilarr | `${APPDATA_PATH}/profilarr` | `/config` | Profiles, database, and settings |

qBittorrent, Radarr, and Sonarr deliberately see the same host directory at the same `/data` path. Keep their download and library paths below `/data`; using the same underlying filesystem enables hardlinks or atomic moves when the NAS filesystem supports them.

qBittorrent also mounts `/etc/localtime` read-only. It is host configuration, not application data to back up.

### Monitoring

| Service | Host path | Container path | Data |
| --- | --- | --- | --- |
| Prometheus | `unraid/monitoring/config/prometheus/prometheus.yml` | `/etc/prometheus/prometheus.yml` | Tracked scrape configuration, read-only |
| Prometheus | `${APPDATA_PATH}/prometheus` | `/prometheus` | Time-series database |
| Blackbox Exporter | `unraid/monitoring/config/blackbox/blackbox.yml` | `/etc/blackbox-exporter/blackbox.yml` | Tracked probe configuration, read-only |
| Grafana | `unraid/monitoring/config/grafana/provisioning` | `/etc/grafana/provisioning` | Tracked data source, dashboard, plugin, and alert provisioning, read-only |
| Grafana | `${APPDATA_PATH}/grafana` | `/var/lib/grafana` | Grafana database, users, and UI-created state |

Tracked provisioning can recreate the supplied dashboards, but it cannot recreate UI-created users, settings, or historical Prometheus metrics.

## Nextcloud named volumes and bind mount

The Nextcloud stack uses five explicitly named Docker volumes:

| Named volume | Container location | Purpose |
| --- | --- | --- |
| `nextcloud_aio_apache` | `/mnt/data` in Apache | Apache runtime state |
| `nextcloud_aio_database` | `/var/lib/postgresql/data` | PostgreSQL database |
| `nextcloud_aio_database_dump` | `/mnt/data` in PostgreSQL | Database dump workspace; not an automatic backup |
| `nextcloud_aio_nextcloud` | `/var/www/html` | Nextcloud application configuration and installation state |
| `nextcloud_aio_redis` | `/data` | Redis state |

The Nextcloud application also bind-mounts `${CLOUD_PATH}` at `/mnt/ncdata` for user files. Apache and Notify Push mount `nextcloud_aio_nextcloud` read-only, while the Nextcloud application mounts it read/write.

This is a manual deployment of Nextcloud AIO images without the AIO mastercontainer. There is no built-in AIO management interface or automatic Borg backup workflow. A complete recovery set needs both `${CLOUD_PATH}` and all five named volumes, including a PostgreSQL-consistent database backup.

List the volumes without modifying them:

```bash
docker volume ls --filter name=nextcloud_aio
```

Do not copy a live PostgreSQL volume and assume it is a valid database backup. Follow the [Nextcloud stack guide](../stacks/nextcloud.md) for consistency requirements.

## NAS bind mounts

| Service | Host path | Container path | Data |
| --- | --- | --- | --- |
| Plex | `${DATA_PATH}/plex` | `/config` | Database, metadata, preferences, logs, and server identity |
| Plex | `${MEDIA_PATH}` | `/media` | Media library; read/write in the current Compose file |
| Arcane | `${DATA_PATH}/arcane` | `/app/data` | Arcane database and persistent state |

Plex also receives `/dev/dri` as a device for hardware acceleration. Arcane mounts `/var/run/docker.sock`. Neither is application data, and neither belongs in a backup.

The Docker socket bind uses `:ro`, but that does not make Docker API operations read-only. Treat Arcane and its access credentials as privileged host-management state.

## Ownership and permissions

Use numeric identities that match the owner or ACL of the host storage:

| Identity | Services |
| --- | --- |
| Unraid `UID:GID` | Traefik, Authelia, Vaultwarden, Prometheus, Grafana, Prowlarr environment, Profilarr |
| Unraid `NAS_UID:NAS_GID` | qBittorrent, Radarr, Sonarr and their shared NAS data |
| NAS `UID:GID` | Plex and Arcane configuration |
| Image-selected identity | Seerr and parts of the Nextcloud stack |

Nextcloud explicitly runs Apache as container user `33` and PostgreSQL/Redis as `999`; the Nextcloud application image manages its own runtime identity. The host or NAS ACL must allow the effective application identity to write the intended paths.

Useful read-only checks include:

```bash
id USERNAME
ls -ld /path/to/directory
stat -c '%u:%g %a %n' /path/to/directory
```

Replace `USERNAME` with the account that owns the data. Do not use `chmod 777` as a shortcut. Correct the specific owner, group, ACL, or ID mapping. Preserve the original numeric identities in your recovery documentation.

## Verify remote mounts before startup

Using the example paths:

```bash
findmnt -T /mnt/remotes/nas-homelab
findmnt -T /mnt/remotes/nas_cloud
```

Adjust the commands to your configured paths. `-T` reports the filesystem that contains the path even when the mount point is a parent directory; confirm that the `SOURCE` column shows the NAS export rather than a local Unraid filesystem. Also perform a harmless read/write test using the identity expected by the application.

Docker's short bind-mount syntax may create a missing source directory. A container can then write to local Unraid storage while appearing healthy. Mount verification must happen outside Docker and after every relevant host reboot.

## What needs backup

| Category | Include |
| --- | --- |
| Deployment identity | Git commit or release tag, Compose files, and tracked configuration |
| Secrets and local configuration | `unraid/.env`, `nas/.env`, Authelia `users.yml`, VPN profiles/certificates, and required encryption keys |
| Authentication and vault state | `${APPDATA_PATH}/authelia` and `${APPDATA_PATH}/vaultwarden` |
| Nextcloud | `${CLOUD_PATH}`, all five named volumes, and a database-consistent PostgreSQL backup |
| Servarr | Every relevant `${APPDATA_PATH}` directory; back up `${HOMELAB_PATH}` separately according to the value of downloads and media |
| Monitoring | `${APPDATA_PATH}/grafana`; `${APPDATA_PATH}/prometheus` if historical metrics matter |
| NAS applications | `${DATA_PATH}/plex` and `${DATA_PATH}/arcane` with their required secrets and original ownership |
| Media | `${MEDIA_PATH}` according to its size, replaceability, and recovery requirements |
| External configuration | Cloudflare Tunnel routes, DNS records, token scopes, and other settings that are not stored in Git |

Encrypt backups containing secrets, Vaultwarden, authentication databases, or private keys. Keep at least one copy outside the two HavenStack hosts and test restoration to an isolated location.

## Backup consistency and safe stopping

Application databases may change while a container is running. Use an application-aware database backup or stop the affected stack before copying raw files.

For example, to stop and restart Servarr without deleting volumes:

```bash
docker compose --env-file unraid/.env \
  -f unraid/servarr/compose.yml stop

docker compose --env-file unraid/.env \
  -f unraid/servarr/compose.yml start
```

Vaultwarden has a built-in SQLite backup command, while Nextcloud requires PostgreSQL-aware handling. The individual stack guides describe their known requirements.

Never use `docker compose down -v` during a normal backup or troubleshooting session. The `-v` option can remove the named Nextcloud volumes.

## Disposable items

These normally do not need backup:

- container writable layers and `tmpfs` contents;
- downloaded container images, provided their exact versions remain available;
- `/etc/localtime`;
- `/dev/dri`;
- `/var/run/docker.sock`;
- generated container log files unless they are required for a separate audit policy.

Images using `latest` make exact recreation less deterministic. Record the deployed Git commit and image identifiers before upgrades, and back up state before pulling a newer image.
