# Backup and restore

A HavenStack backup is more than a copy of the repository. The repository contains the deployment model, while passwords, application databases, user files, VPN material, and runtime configuration live outside Git.

This guide defines what must be protected and a safe order of work. It does not prescribe one backup product because the correct snapshot, database, and NAS commands depend on the filesystems and tools in your environment.

## Command scope

Commands marked **repository-validated** below were checked against all seven Compose files with the example environment files. They validate or control the Compose projects, but they do not prove that an application backup is consistent.

Steps marked **environment-dependent** require a storage- or application-aware procedure selected and tested by the operator. In particular, this guide does not invent PostgreSQL dump or restore commands.

## Define the recovery objective first

Decide before scheduling backups:

- how much data loss is acceptable;
- how long the system may be unavailable;
- which media can be recreated and which data is irreplaceable;
- where encryption keys and backup credentials are stored;
- which machine will be used for a restore if Unraid or the NAS fails.

Keep at least one backup separate from both production hosts. A backup stored only beside the live data does not protect against host loss, ransomware, or operator error.

## Persistent-data inventory

### Deployment identity and secrets

Back up these items in encrypted storage:

- the Git commit or release tag used for deployment;
- `unraid/.env` and `nas/.env`;
- `unraid/edge/config/authelia/users.yml`;
- `${APPDATA_PATH}/authelia`, including its database;
- the Authelia `AUTH_*` secrets that match that database;
- the qBittorrent OpenVPN profile, certificates, and keys under `${APPDATA_PATH}/qbittorrentvpn/openvpn`;
- an inventory of Cloudflare Tunnel routes, DNS records, token scopes, and Authelia policies;
- the actual container image IDs or repository digests used at the recovery point.

Cloudflare and VPN tokens can be reissued, but the recovery plan must explain how to do that when the original host is unavailable. Do not place populated secret files in Git.

### Unraid application data

| Stack | Persistent data |
| --- | --- |
| Edge | `${APPDATA_PATH}/authelia` and the untracked Authelia files above |
| Apps | `${APPDATA_PATH}/vaultwarden`; Homepage has no persistent volume |
| Servarr | `${APPDATA_PATH}/qbittorrentvpn`, `prowlarr`, `radarr`, `sonarr`, `seerr`, and `profilarr` |
| Monitoring | `${APPDATA_PATH}/grafana` and, if history matters, `${APPDATA_PATH}/prometheus` |
| Nextcloud | `${CLOUD_PATH}` plus all five `nextcloud_aio_*` named volumes |

`${HOMELAB_PATH}` contains the media and download filesystem used by qBittorrent, Radarr, and Sonarr. Back it up separately according to its size and replaceability.

Nextcloud requires special care. This repository manually assembles AIO component images and has no AIO mastercontainer backup interface. A useful recovery point must keep the PostgreSQL state, `${CLOUD_PATH}`, configuration, named volumes, secrets, and image set consistent. Follow the [Nextcloud stack backup section](../stacks/nextcloud.md#backups).

### NAS data

| Stack | Persistent data |
| --- | --- |
| Plex | `${DATA_PATH}/plex` plus `${MEDIA_PATH}` if the media itself must be protected |
| Arcane | `${DATA_PATH}/arcane` and the original `ENCRYPTION_KEY` and `JWT_SECRET` |

The Docker socket mounted into Arcane is not backup data. Arcane also does not replace backups of the workloads it manages.

See the individual [stack guides](../stacks/README.md) for application-specific boundaries.

## Record a recovery manifest

Create a small manifest beside each backup containing:

- backup time and timezone;
- Git commit or tag;
- host names and operating-system versions;
- Docker and Compose versions;
- values of `UID`, `GID`, `NAS_UID`, and `NAS_GID` without including passwords;
- storage paths and mount sources;
- image names, tags, image IDs, and available repository digests;
- the backup tool and whether each application was stopped or quiesced;
- checksums produced by the chosen backup system.

The following **repository-validated** command records images for one stack without exposing `.env` values:

```bash
docker compose --env-file unraid/.env \
  -f unraid/nextcloud/compose.yml images
```

Repeat it for every deployed Compose file on the correct host. A tag such as `latest` is not enough to identify an immutable image.

## Safe full-environment backup sequence

The following sequence intentionally includes downtime. A no-downtime database backup requires application- and database-specific tooling that is outside this repository.

1. Announce the maintenance window and prevent new user activity where the application supports maintenance mode.
2. Confirm that `${HOMELAB_PATH}`, `${CLOUD_PATH}`, `${APPDATA_PATH}`, `${DATA_PATH}`, and `${MEDIA_PATH}` resolve to the expected mounted storage. Do not continue if a NAS mount is missing.
3. Record the recovery manifest and current health state.
4. Run any verified application-aware export or database procedure before copying files. Vaultwarden and Nextcloud have additional requirements in their stack guides.
5. Stop Unraid stacks in reverse dependency order: monitoring, Servarr, Nextcloud, apps, then edge.
6. On the NAS, stop Plex before making its application-data copy. Stop Arcane before copying Arcane data.
7. Use the chosen **environment-dependent** backup tool to copy bind-mounted data, named volumes, secrets, and database recovery artifacts.
8. Verify the backup tool's result and checksums before restarting services.
9. Start the NAS, restore its storage services, and start or verify Plex and Arcane as required.
10. Confirm the NAS shares are mounted on Unraid.
11. Start Unraid stacks in dependency order: edge, apps, Nextcloud, Servarr, then monitoring.
12. Complete functional checks, not only container health checks.

For example, this **repository-validated** command safely stops one stack without deleting its volumes:

```bash
docker compose --env-file unraid/.env \
  -f unraid/servarr/compose.yml stop
```

Use `start` only when the existing containers and configuration are unchanged:

```bash
docker compose --env-file unraid/.env \
  -f unraid/servarr/compose.yml start
```

If files, environment values, or restored containers changed, validate and use `up -d` instead.

Nextcloud defines long stop grace periods: up to 10 minutes for the application and 30 minutes for PostgreSQL. Do not replace a graceful stop with `kill` merely because shutdown takes time. Prometheus has a two-minute stop grace period.

> Never use `docker compose down -v` for maintenance or backup. The `-v` option can remove the named Nextcloud volumes.

## Consistency requirements

Stopping a stack makes simple file-based databases and configuration directories safer to copy, but it does not turn every filesystem copy into a verified application backup.

- **Nextcloud:** use a PostgreSQL-aware recovery method and keep it synchronized with `${CLOUD_PATH}` and the matching configuration. A live copy of the PostgreSQL volume alone is not sufficient.
- **Vaultwarden:** its built-in SQLite backup covers the database, not attachments, Sends, keys, or the rest of `/data`. Follow [the Apps guide](../stacks/apps.md#vaultwarden).
- **Servarr, Plex, Authelia, Arcane, and Grafana:** stop the writing application or use an upstream-supported application-aware method before copying active databases.
- **Prometheus:** its admin snapshot API is not enabled by this Compose file. Stop Prometheus cleanly before a filesystem backup, or deploy and test a supported snapshot procedure first.
- **Media:** application configuration and media files are separate recovery decisions.

Do not combine a database from one time with files from another unless the application explicitly supports that recovery method.

## Restore procedure

Perform the first restore test in an isolated environment whenever possible. Prevent restored services from sending notifications, starting downloads, modifying production DNS, or competing with the live Cloudflare Tunnel.

1. Select one complete recovery point and its manifest.
2. Check out the matching Git commit or release. Do not assume the current `main` branch matches an old database.
3. Restore the same image set. If an old tag has moved or a `latest` image was not recorded, stop and assess compatibility rather than guessing.
4. Recreate the original storage mounts, directories, network prerequisites, and numeric ownership.
5. Restore `unraid/.env`, `nas/.env`, Authelia users, VPN material, and required secrets from encrypted storage.
6. With all affected containers stopped, restore bind-mounted directories and named-volume contents using the tested **environment-dependent** storage procedure.
7. Restore databases using the matching application- or database-aware method. Do not start the application against a half-restored database.
8. Validate all Compose models.
9. Start the NAS and verify mounts from Unraid.
10. Start edge first, then apps, Nextcloud, Servarr, and monitoring.
11. Verify authentication, files, integrations, VPN routing, public URLs, and monitoring.
12. Rotate credentials if the recovery event may have exposed secrets.

All seven **repository-validated** configuration checks are listed in the [deployment guide](../getting-started/deployment.md#1-validate-the-compose-configuration).

## Restore acceptance checklist

A restore is not complete until you have confirmed:

- all expected containers are running and health checks stabilize;
- Cloudflare reaches Traefik without exposing the origin ports;
- Authelia users can authenticate and protected routes enforce the expected policy;
- Vaultwarden records and attachments are present;
- a Nextcloud test file can be downloaded and uploaded;
- qBittorrent uses the VPN and its kill switch passes the provider-approved test;
- Radarr and Sonarr can see the same `/data` layout as before;
- Plex sees its libraries and application history;
- Grafana has its expected state and Prometheus is collecting fresh samples;
- no service is writing to an accidental local directory because a remote mount is missing.

Document the test date and any manual steps discovered. Update the runbook while the details are fresh.

## Official references

- [Docker volume backup, restore, and migration](https://docs.docker.com/engine/storage/volumes/#back-up-restore-or-migrate-data-volumes)
- [Docker Compose `stop`](https://docs.docker.com/reference/cli/docker/compose/stop/)
- [Nextcloud backup requirements](https://docs.nextcloud.com/server/latest/admin_manual/maintenance/backup.html)
- [Prometheus storage backup considerations](https://prometheus.io/docs/prometheus/latest/storage/)
- [Grafana backup guidance](https://grafana.com/docs/grafana/latest/administration/back-up-grafana/)
