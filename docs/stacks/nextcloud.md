# Nextcloud stack

This stack provides Nextcloud at `https://cloud.example.com`. Replace `example.com` with `DOMAIN` from `unraid/.env`.

## Important: this is a manual AIO component installation

HavenStack directly assembles five images from Nextcloud All-in-One (AIO). It does **not** run the AIO mastercontainer.

As a result, there is no AIO management web interface, automatic AIO update workflow, or built-in AIO Borg backup and restore. Manage this stack with Docker Compose and maintain your own tested backups. The upstream [manual installation guide](https://github.com/nextcloud/all-in-one/blob/main/manual-install/readme.md) lists these differences and must be reviewed before upgrades.

## Services and startup order

| Service | Purpose | Memory limit |
| --- | --- | --- |
| `nextcloud-aio-database` | PostgreSQL database | 1 GiB |
| `nextcloud-aio-redis` | Redis cache and locking | 256 MiB |
| `nextcloud-aio-nextcloud` | Nextcloud PHP application | 2 GiB |
| `nextcloud-aio-notify-push` | Push notifications | 128 MiB |
| `nextcloud-aio-apache` | Web server reached by Traefik | 512 MiB |

Compose health dependencies enforce this sequence:

```text
database + Redis healthy
  -> Nextcloud healthy
  -> notify-push healthy
  -> Apache healthy
```

Apache also waits directly for Nextcloud. During the first installation, later services may remain unstarted while the database and application initialize.

Optional AIO components such as ClamAV, Collabora, full-text search, Imaginary, OnlyOffice, Talk, Talk recording, and Whiteboard are disabled in this repository. The `notify_push` app is enabled at startup.

## Prerequisites

Before deploying:

- deploy `unraid/edge` so that the external `apps_backend` network exists;
- configure the Cloudflare apex and wildcard Tunnel routes;
- set the `cloud.example.com` Traefik route, which is already present in this repository;
- create and verify the storage mounted at `CLOUD_PATH`;
- complete every Nextcloud variable in `unraid/.env`;
- make a recovery plan before storing important files.

`CLOUD_PATH` must be a dedicated, persistent location. If it is a NAS mount, confirm that the NAS is mounted before every start. Otherwise Docker may write to an unintended local directory.

For the example path, this command shows the filesystem that contains it:

```bash
findmnt -T /mnt/remotes/nas_cloud
```

Do not use world-writable permissions as a shortcut. The directory must be writable by the Nextcloud process inside the container and compatible with the NAS permission model.

## Environment variables

| Variable | Purpose |
| --- | --- |
| `DOMAIN` | Builds `cloud.${DOMAIN}` for Nextcloud and Traefik |
| `TZ` | Container and PostgreSQL timezone |
| `CLOUD_PATH` | Host or NAS path mounted as `/mnt/ncdata` |
| `NEXTCLOUD_ADMIN_USER` | Initial Nextcloud administrator name |
| `NEXTCLOUD_ADMIN_PASSWORD` | Initial administrator password |
| `NEXTCLOUD_DATABASE_PASSWORD` | PostgreSQL password used by Nextcloud |
| `NEXTCLOUD_REDIS_PASSWORD` | Redis password used by Nextcloud |
| `NEXTCLOUD_LOG_LEVEL` | AIO component log level |
| `NEXTCLOUD_UPLOAD_LIMIT` | Apache and PHP upload size limit; the example is 16 GiB |
| `NEXTCLOUD_MEMORY_LIMIT` | PHP memory limit; the example is `2048M` |
| `NEXTCLOUD_MAX_TIME` | Apache and PHP request time limit; the example is 3600 seconds |

Choose final database and Redis secrets before the first start. Changing only `.env` after PostgreSQL has initialized can prevent the application from reconnecting. The upstream manual installation guide warns against using `@` or `:` in manual-install passwords because they can break generated connection strings.

Never commit `unraid/.env`.

## Networks and persistent data

| Resource | Mount or members | Purpose |
| --- | --- | --- |
| `apps_backend` | Apache and Traefik | HTTP proxy path from Traefik to Apache |
| `nextcloud_backend` | All five Nextcloud services | Internal database, cache, application, web, and push traffic |
| `nextcloud_egress` | Nextcloud application | Outbound access for Nextcloud and its apps |
| `CLOUD_PATH` | `/mnt/ncdata` | User files |
| `nextcloud_aio_nextcloud` | `/var/www/html` | Application, configuration, and installed apps |
| `nextcloud_aio_database` | `/var/lib/postgresql/data` | PostgreSQL data |
| `nextcloud_aio_database_dump` | `/mnt/data` in PostgreSQL | Database dump workspace; it is not an automatic backup |
| `nextcloud_aio_redis` | `/data` | Redis state |
| `nextcloud_aio_apache` | `/mnt/data` in Apache | Apache component data |

No service publishes a host port. Traefik reaches Apache at `http://nextcloud-aio-apache:11000` on `apps_backend`.

## Deploy and verify

Validate the configuration:

```bash
docker compose --env-file unraid/.env \
  -f unraid/nextcloud/compose.yml config --quiet
```

Start the stack:

```bash
docker compose --env-file unraid/.env \
  -f unraid/nextcloud/compose.yml up -d
```

Watch the health states:

```bash
docker compose --env-file unraid/.env \
  -f unraid/nextcloud/compose.yml ps
```

If initialization stalls, inspect the service that is not healthy and then its dependency:

```bash
docker compose --env-file unraid/.env \
  -f unraid/nextcloud/compose.yml logs --tail 100
```

Do not repeatedly remove and recreate volumes to troubleshoot. Those volumes contain the installation.

## First configuration

1. Wait until all five containers are healthy.
2. Open `https://cloud.example.com`.
3. Sign in with `NEXTCLOUD_ADMIN_USER` and `NEXTCLOUD_ADMIN_PASSWORD`.
4. Open **Administration settings > Overview** and review any warnings.
5. Configure email delivery and create normal user accounts as needed.
6. Upload a small test file, download it again, and confirm it appears under `CLOUD_PATH` before importing important data.

This Traefik route does not use the Authelia middleware. Nextcloud performs its own authentication. Cloudflare still terminates public TLS, and Nextcloud is configured with `OVERWRITEPROTOCOL=https` and `OVERWRITEHOST=cloud.${DOMAIN}`.

## Updates and rollback

All five image references use the mutable `latest` tag. A later `docker compose pull` can replace several components even though `compose.yml` did not change. This also means the repository alone cannot reproduce the previous image versions for a rollback.

Before updating:

1. create and verify a database-consistent backup;
2. record the current images and image IDs with `docker compose ... images`;
3. compare this Compose file with the current upstream manual-install files and release notes;
4. update all related components as one tested set, not one image at a time.

Do not downgrade Nextcloud or PostgreSQL by guessing an older tag. Restore the matching application, database, files, configuration, and image set from a known recovery point.

## Backups

The AIO backup buttons and Borg workflow are unavailable because there is no mastercontainer. A useful backup must include:

- a consistent PostgreSQL logical dump or an application-consistent PostgreSQL snapshot;
- `CLOUD_PATH`;
- all five named volumes listed above;
- `unraid/nextcloud/compose.yml` and the matching repository revision;
- an encrypted copy of the required `.env` values.

For a simple downtime backup:

1. enable Nextcloud maintenance mode;
2. stop web and application activity;
3. create and verify a PostgreSQL-consistent backup using your chosen PostgreSQL-aware tool;
4. stop the remaining stack before copying raw volume and file data;
5. back up `CLOUD_PATH`, the named volumes, configuration, and secrets;
6. restart the stack, disable maintenance mode, and test access.

The standard maintenance commands are:

```bash
docker exec --user www-data nextcloud-aio-nextcloud \
  php occ maintenance:mode --on

docker exec --user www-data nextcloud-aio-nextcloud \
  php occ maintenance:mode --off
```

Do not treat a live copy of the PostgreSQL data directory as a verified database backup. Test the complete restore procedure on an isolated system. Never use `docker compose down -v` during routine maintenance because `-v` removes named volumes.

See the official [Nextcloud backup documentation](https://docs.nextcloud.com/server/latest/admin_manual/maintenance/backup.html) for the consistency requirements.

## Security notes

- The database and Redis are reachable only on the internal `nextcloud_backend` network.
- Apache and the other supporting containers use read-only root filesystems where configured, reduced capabilities, and `no-new-privileges`.
- Keep the database, Redis, and admin secrets out of Git and backups encrypted.
- Restrict direct access to `CLOUD_PATH`; changes outside Nextcloud can desynchronize its file cache.
- Keep public access through Cloudflare and Traefik. Do not expose PostgreSQL, Redis, or Apache directly.

## Common problems

| Symptom | Check |
| --- | --- |
| `apps_backend` does not exist | Deploy the edge stack first |
| Database or Redis stays unhealthy | Secrets, volume permissions, free space, and service logs |
| Nextcloud stays unhealthy | Database and Redis health, then Nextcloud logs |
| Apache does not start | Nextcloud and notify-push must both be healthy |
| `502 Bad Gateway` | Apache health and membership in `apps_backend` |
| Permission denied under `/mnt/ncdata` | NAS mount state and `CLOUD_PATH` permissions |
| Files were written to the Unraid disk | The NAS was not mounted at `CLOUD_PATH` before startup |
| Admin secret changed but login did not | Initial credentials are persisted; changing `.env` is not an account reset |

## Official references

- [Nextcloud AIO manual installation](https://github.com/nextcloud/all-in-one/blob/main/manual-install/readme.md)
- [Nextcloud AIO project](https://github.com/nextcloud/all-in-one)
- [Nextcloud reverse proxy guidance](https://github.com/nextcloud/all-in-one/blob/main/reverse-proxy.md)
- [Nextcloud backup requirements](https://docs.nextcloud.com/server/latest/admin_manual/maintenance/backup.html)
- [Nextcloud `occ` command](https://docs.nextcloud.com/server/latest/admin_manual/occ_command.html)
