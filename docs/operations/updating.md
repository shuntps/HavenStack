# Updating HavenStack

HavenStack updates are reviewed changes to Compose image references and repository configuration. Dependabot proposes changes, but nothing in this repository automatically deploys them to Unraid or the NAS.

## What is automated

`.github/dependabot.yml` checks:

- GitHub Actions every Monday at 08:00 America/Toronto;
- Docker Compose images in all six stack directories every Monday at 08:30;
- minor and patch image updates as grouped version-update pull requests;
- other eligible updates, such as major versions, outside that minor/patch group.

Each pull request targeting `main` runs the Compose validation workflow with the example environment files. This confirms that all six YAML models render successfully. It does **not** start containers, test a database migration, verify a VPN, mount a NAS share, or prove application compatibility.

Each pull request targeting `main` also runs the documentation validation workflow. It checks that internal Markdown links and anchors resolve and that image versions pinned in the documentation match the Compose files. When a Dependabot pull request changes an image tag, this check fails until the documentation pages that mention the old version are updated in the same pull request. A separate scheduled workflow checks the external documentation links weekly.

Merging a pull request only changes `main`. Pushing a `v*` tag creates a GitHub Release after the same Compose and documentation validations; it still does not deploy the hosts.

## Image version policy in this repository

Most services use explicit version tags. All five Nextcloud component images use `latest` and need additional care.

A version tag is easier to read than a digest but may still be moved by a registry. `latest` does not identify a version at all. This repository currently does not pin image digests, so record the actual image IDs and repository digests before every deployment change.

Dependabot may not be able to propose a meaningful version change for an image already written as `latest`. Review [Nextcloud](../stacks/nextcloud.md#updates-and-rollback) separately rather than treating `pull` as a safe update plan.

## Before accepting an update

1. Work on a branch or review the Dependabot branch; do not edit production directly on `main`.
2. Read the upstream release notes for every changed image.
3. Identify configuration changes, removed options, data migrations, new permissions, and supported upgrade paths.
4. Create and verify a recovery point using [Backup and restore](backup-and-restore.md).
5. Record the current Git commit and the images used by each affected stack.
6. Confirm free disk space on the Docker host and persistent storage.
7. Plan a maintenance window for stateful or ingress services.
8. Run the pull-request validation and review the rendered diff.

Do not merge merely because the Compose check is green. A grouped Dependabot PR can change more than one service and therefore increases the amount that must be reviewed and tested.

## Record the current images

The following is a **repository-validated** command for one stack:

```bash
docker compose --env-file unraid/.env \
  -f unraid/servarr/compose.yml images
```

Run the matching command for every affected stack on its host. Keep the output with the backup manifest. If rollback matters, confirm that the old image is still available by its repository digest; a local image may later be removed by cleanup.

For an image that is already present, this Docker-standard, **environment-dependent** command shows any recorded repository digests:

```bash
docker image inspect \
  --format '{{json .RepoDigests}}' IMAGE_NAME
```

Replace `IMAGE_NAME` with the exact image reference shown by Compose. An empty digest list is not a usable immutable rollback reference.

## Validate before pulling

The validation commands below are **repository-validated** and match the GitHub Actions workflow:

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

docker compose --env-file nas/.env \
  -f nas/plex/compose.yml config --quiet

```

No output means that Compose accepted the model. It says nothing about runtime health or data compatibility.

## Pull without deploying

`pull` downloads images but does not replace running containers. This separation gives you a chance to detect registry or image-name problems before the maintenance window.

```bash
docker compose --env-file unraid/.env \
  -f unraid/apps/compose.yml pull
```

For a NAS stack, run the command on the NAS with `nas/.env` and the matching Compose path.

Treat a `latest` pull as an actual version change even when Git shows no diff. Do not pull Nextcloud component images independently; they are intended to operate as a compatible set.

## Apply one stack at a time

After the recovery point, review, validation, and pull succeed, apply the affected stack:

```bash
docker compose --env-file unraid/.env \
  -f unraid/apps/compose.yml up -d
```

Compose recreates a service when its image or configuration changed and preserves mounted volumes. `restart` is not a deployment command: it restarts existing containers without applying changed Compose or environment values.

Update and verify one stack before moving to another. Suggested risk order for a multi-stack maintenance window:

1. a low-impact stateless service or test environment;
2. NAS applications, one at a time;
3. Unraid application stacks, one at a time;
4. Nextcloud using its upstream manual-install upgrade requirements;
5. edge during an announced ingress interruption;
6. monitoring after the services it observes are stable.

This is an operational recommendation, not a dependency requirement. On a cold start, always use the documented deployment order with edge first.

## Verify after each stack

Check all containers, including stopped ones:

```bash
docker compose --env-file unraid/.env \
  -f unraid/apps/compose.yml ps --all
```

Read new logs with timestamps:

```bash
docker compose --env-file unraid/.env \
  -f unraid/apps/compose.yml logs \
  --since=10m --tail=200 --timestamps
```

Then complete the affected stack guide's functional checks. At minimum, confirm:

- containers remain stable rather than repeatedly restarting;
- health checks become healthy where defined;
- public routing and authentication still work;
- application data is present;
- service-to-service integrations still work;
- storage paths still point to mounted storage;
- qBittorrent still uses the VPN and kill switch;
- monitoring shows fresh samples.

A healthy qBittorrent web interface does not prove that the VPN is connected.

## Updating configuration without changing an image

After changing `.env`, Compose, or a mounted configuration file:

1. validate the model;
2. review `docker compose config` output carefully without publishing secrets;
3. use `up -d` to recreate services whose container configuration changed;
4. restart only services that read a bind-mounted configuration at startup and were not recreated;
5. repeat the functional checks.

Never paste a fully rendered production Compose model into a public issue because it can contain secrets.

## Failed update

Stop applying changes to additional stacks. Preserve logs, current containers, old images, and the recovery point. Determine whether the failure is:

- a configuration error that can be corrected forward;
- a transient registry or network problem;
- an application incompatibility requiring the previous image;
- a data migration requiring a matched data restore.

Follow [Rollback](rollback.md). Do not downgrade an application blindly after it has modified its database.

## Cleanup

Keep previous images until the rollback window closes and the recovery test succeeds. Do not run broad image, volume, or system pruning as part of the update itself. In particular, never delete volumes to make a failed update start.

## Official references

- [Docker Compose `pull`](https://docs.docker.com/reference/cli/docker/compose/pull/)
- [Docker Compose `up`](https://docs.docker.com/reference/cli/docker/compose/up/)
- [Docker Compose `restart` limitations](https://docs.docker.com/reference/cli/docker/compose/restart/)
- [Dependabot version updates](https://docs.github.com/en/code-security/concepts/supply-chain-security/dependabot-version-updates)
- [Dependabot grouped updates](https://docs.github.com/en/code-security/tutorials/secure-your-dependencies/optimizing-pr-creation-version-updates)
