# Rollback

A rollback is safe only when the previous code, images, secrets, and persistent data are compatible with one another. Replacing a container image does not undo a database migration.

Use this guide after an update fails or produces unacceptable behavior. For diagnosis before changing state, start with [Troubleshooting](troubleshooting.md).

## Three different rollbacks

| Type | What changes | Main risk |
| --- | --- | --- |
| Configuration rollback | Compose, environment, or mounted configuration returns to a known revision | Old configuration may not understand current data or secrets |
| Image rollback | A service returns to a known previous image tag or digest | The older application may not read a migrated database |
| Full-state restore | Code, images, databases, files, and secrets return to one recovery point | Data created after that point is lost |

Decide which type is required before running commands. If the application wrote to its database after the update, assume an image-only downgrade may be unsafe until upstream documentation proves otherwise.

## Rollback prerequisites

A prepared rollback needs:

- a Git commit or release tag from before the change;
- the exact previous images, preferably recorded by repository digest;
- a recovery manifest from before the update;
- verified application and database backups from the same recovery point;
- the matching `.env`, encryption keys, user database, VPN material, and storage paths;
- enough maintenance time to validate the restored system.

GitHub release tags record repository content, not the bytes behind mutable container tags. Nextcloud currently uses `latest`, so a Git tag alone cannot recreate its former images. Do not prune old images until the rollback window has closed.

## Stop and preserve evidence

If an update fails:

1. stop updating other stacks;
2. save sanitized logs and `docker compose ps --all` output;
3. record the new and old image IDs that still exist locally;
4. identify whether persistent data was opened or migrated by the new version;
5. prevent new user activity and automation;
6. choose a roll-forward fix, image rollback, or full-state restore.

Do not repeatedly recreate containers while investigating. Each start may run another migration or change data.

## Prefer a corrective Git change

For repository history, create a corrective branch and use a normal pull request. If one merged commit must be undone, `git revert` creates a new commit that reverses it without rewriting shared history:

```bash
git switch main
git pull --ff-only
git switch -c fix/rollback-failed-update
git revert COMMIT_HASH
```

Replace `COMMIT_HASH` with the ordinary, non-merge commit to reverse. Review the generated diff, validate all Compose files, and open a pull request. A GitHub pull request may have produced a merge commit; reverting a merge requires choosing its mainline parent. Use GitHub's **Revert** action when it is available, or inspect the merge parents and follow the official `git revert` documentation instead of guessing a `-m` value. Do not use `git reset --hard` on shared work as a rollback workflow.

If a grouped Dependabot commit changed several images, reverting the whole commit also reverts all of them. A targeted corrective commit may be safer when only one service failed, but review compatibility among components first.

## Configuration-only rollback

Use this path only when the images and data remain compatible with the previous configuration.

1. Restore the known configuration through a reviewed corrective commit.
2. Restore matching secret values from encrypted storage if they changed.
3. Validate the affected Compose model.
4. Apply the restored configuration with `up -d`.
5. Verify health, data, authentication, routing, and integrations.

Example **repository-validated** commands for the Apps stack:

```bash
docker compose --env-file unraid/.env \
  -f unraid/apps/compose.yml config --quiet

docker compose --env-file unraid/.env \
  -f unraid/apps/compose.yml up -d
```

`restart` does not apply changed environment or Compose settings.

## Image rollback without restoring data

Attempt this only when upstream documentation confirms that the previous image can use the current persistent data.

1. Change the Compose image reference to the exact known previous tag or digest on a branch.
2. Review and validate the change.
3. Stop the affected service or stack gracefully.
4. Pull the exact previous image if it is not available locally.
5. Apply it with `up -d`.
6. Watch logs from the first start and stop if the application rejects the database version.
7. Complete the stack's functional checks.

Never guess an older tag. Never assume a local image named `latest` still represents the previous version. Do not roll back only one Nextcloud AIO component; its images operate as a coordinated set.

## Full-state restore

Use a matched restore when the update migrated or corrupted persistent state, when upstream does not support downgrading, or when the previous image cannot use the current data.

1. Select one complete pre-update recovery point.
2. Stop the affected stack and any service that can write to its storage.
3. Restore the matching Git revision, image set, `.env`, and secrets.
4. Restore bind-mounted files and named volumes while containers are stopped.
5. Restore the database with the tested application- or database-aware process.
6. Restore related files from the same recovery point; do not mix timestamps casually.
7. Validate Compose.
8. Start dependencies in order and observe the first application start.
9. Run the restore acceptance checks in [Backup and restore](backup-and-restore.md#restore-acceptance-checklist).

The storage and database restore steps are **environment-dependent**. This repository cannot know the snapshot technology, PostgreSQL backup format, NAS filesystem, or off-site backup product in use.

## Stack-specific cautions

### Edge

An edge failure can remove browser access to every Unraid application. Work from the local Unraid console, not only through a hostname routed by the failed stack. Restore Traefik, Authelia, `users.yml`, the Authelia database, and matching `AUTH_*` secrets together. Tunnel tokens can be rotated if needed.

Start edge before dependent stacks after a full outage because it creates their external Docker networks.

### Vaultwarden and Authelia

Both contain sensitive databases and cryptographic state. Restoring a database without its matching keys or secrets can make data unusable. Vaultwarden's database backup alone does not include every file under `/data`.

### Nextcloud

The stack is a manual assembly of five AIO component images, all currently tagged `latest`. It has no AIO rollback button or built-in AIO backup interface. A safe rollback generally requires the recorded component image set and a database-consistent recovery point that matches `${CLOUD_PATH}` and the named volumes. Follow the [Nextcloud guide](../stacks/nextcloud.md#updates-and-rollback) and upstream manual-install instructions.

### Servarr and qBittorrent

Restore all application configuration that must agree on paths, credentials, and API keys. Keep `${HOMELAB_PATH}` mounted at the same `/data` layout. After rollback, reverify the qBittorrent VPN and kill switch before resuming transfers.

### Monitoring

Historical Prometheus data is independent of application data. A monitoring rollback can discard history if that is acceptable, but Grafana users and UI-created state require `${APPDATA_PATH}/grafana`. Provisioned dashboards can be recreated from Git.

### Plex

Plex database compatibility must follow Plex's supported downgrade or restore guidance.

## Safe start order after rollback

For a full environment restore:

1. start the NAS and verify storage exports;
2. start or verify Plex on the NAS as required by the maintenance plan;
3. verify `${HOMELAB_PATH}` and `${CLOUD_PATH}` on Unraid;
4. start edge;
5. start apps;
6. start Nextcloud and wait for all health dependencies;
7. start Servarr;
8. start monitoring.

Use `start` only when restored containers already exist unchanged. After restoring Compose, environment values, or images, use validated `up -d` commands.

## Abort conditions

Stop the rollback and reassess if:

- the old image is unavailable or its digest is unknown;
- logs say that the database schema is newer than the application;
- only part of a coordinated component set is available;
- the database and file backup timestamps do not form a known recovery point;
- required encryption keys or secrets are missing;
- NAS mounts resolve to an unexpected local filesystem;
- the restore test would contact or overwrite the production environment.

A controlled outage is safer than guessing with irreplaceable data.

## After recovery

Record the cause, recovery point, exact images, data loss, and commands used. Keep the failed logs, rotate exposed credentials, open a corrective issue, and improve the pre-update checklist before trying again.

## Official references

- [Git `revert`](https://git-scm.com/docs/git-revert)
- [Docker Compose `up`](https://docs.docker.com/reference/cli/docker/compose/up/)
- [Docker Compose `pull`](https://docs.docker.com/reference/cli/docker/compose/pull/)
- [Nextcloud AIO manual update procedure](https://github.com/nextcloud/all-in-one/blob/main/manual-install/readme.md#how-to-update)
