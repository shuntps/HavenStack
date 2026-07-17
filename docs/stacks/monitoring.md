# Monitoring stack

This stack collects metrics, probes service health, and displays dashboards. It provides visibility, but it does not currently send alerts.

## Services

| Service | Purpose | Memory limit |
| --- | --- | --- |
| Prometheus | Scrapes metrics and stores time series | 512 MiB |
| Blackbox Exporter | Performs HTTP health probes | 64 MiB |
| Grafana | Queries Prometheus and displays dashboards | 768 MiB |

Prometheus scrapes every 15 seconds with a 10-second timeout. Rule evaluation also runs every 15 seconds. Local metrics are retained for **30 days or 10 GB, whichever limit is reached first**.

## Prerequisites

Before deploying:

- deploy `unraid/edge` so the shared Docker networks exist;
- preferably start the apps, Nextcloud, and Servarr stacks so their probes can succeed;
- set `DOMAIN`, `TZ`, `NAS_IP`, `APPDATA_PATH`, `UID`, and `GID` in `unraid/.env`;
- set strong `GRAFANA_ADMIN_USER` and `GRAFANA_ADMIN_PASSWORD` values;
- create `${APPDATA_PATH}/prometheus` and `${APPDATA_PATH}/grafana` with ownership that matches `UID:GID`.

Prometheus and Grafana run as `${UID}:${GID}`. Incorrect ownership of either data directory causes startup failures. Do not solve this with `chmod 777`.

## Networks and storage

| Resource | Used by | Purpose |
| --- | --- | --- |
| `monitoring_backend` | All monitoring services plus edge metrics endpoints | Prometheus, Grafana, and edge monitoring traffic |
| `apps_backend` | Blackbox Exporter | Probes Vaultwarden and Nextcloud |
| `servarr_backend` | Blackbox Exporter | Probes media automation services |
| `homepage_backend` | Blackbox Exporter | Probes Homepage |
| `${APPDATA_PATH}/prometheus` | Prometheus `/prometheus` | Time-series database |
| `${APPDATA_PATH}/grafana` | Grafana `/var/lib/grafana` | Grafana database and state |

The provisioning and Prometheus configuration directories are mounted read-only from the repository. Prometheus and Blackbox Exporter have no public Traefik route. Grafana is routed at `https://grafana.example.com` and protected by Authelia.

## Environment variables

| Variable | Purpose |
| --- | --- |
| `DOMAIN` | Builds Grafana's public root URL |
| `TZ` | Container timezone |
| `NAS_IP` | Maps the internal name `nas-host` for the Plex probe |
| `APPDATA_PATH` | Persistent Prometheus and Grafana directories |
| `UID`, `GID` | Filesystem identity for Prometheus and Grafana |
| `GRAFANA_ADMIN_USER` | Initial Grafana administrator |
| `GRAFANA_ADMIN_PASSWORD` | Initial Grafana administrator password |

Grafana uses the admin values when it initializes its persistent database. Changing `.env` later is not a reliable password-reset method. Never commit the populated `.env` file.

## Collected targets

Prometheus directly scrapes metrics from:

- Prometheus at `127.0.0.1:9090`;
- Traefik at `traefik:8084`;
- Authelia at `authelia:9959`;
- cloudflared at `cloudflared:2000`;
- Blackbox Exporter at `blackbox-exporter:9115`.

Blackbox Exporter performs 15 HTTP probes:

| Service | Target |
| --- | --- |
| Prometheus | `http://prometheus:9090/-/ready` |
| Traefik | `http://traefik:8082/ping` |
| cloudflared | `http://cloudflared:2000/ready` |
| Authelia | `http://authelia:9091/api/health` |
| Vaultwarden | `http://vaultwarden:8080/alive` |
| Homepage | `http://homepage:3000/api/health` |
| Grafana | `http://grafana:3000/api/health` |
| Nextcloud | `http://nextcloud-aio-apache:11000/status.php` |
| qBittorrent | `http://qbittorrent:8090` |
| Prowlarr | `http://prowlarr:9696/ping` |
| Radarr | `http://radarr:7878/ping` |
| Seerr | `http://seerr:5055/api/v1/status` |
| Sonarr | `http://sonarr:8989/ping` |
| Profilarr | `http://profilarr:6868` |
| Plex | `http://nas-host:32400/identity` |

The `http_2xx` probe follows redirects, prefers IPv4, accepts HTTP/1.1 and HTTP/2, and times out after five seconds. `nas-host` resolves to `NAS_IP` through the Compose `extra_hosts` entry.

## Provisioned Grafana content

Grafana automatically provisions:

- an uneditable default Prometheus data source at `http://prometheus:9090`;
- Authelia, Blackbox Exporter, cloudflared, and Traefik dashboards;
- dashboard definitions from the repository every 30 seconds.

The dashboard provider sets `allowUiUpdates: false`. Treat these dashboards as code: edit their JSON files in Git rather than trying to save changes in Grafana. Provisioned source changes can overwrite UI copies.

`alerting.yml` currently contains only `apiVersion: 1`, so there are **no alert rules, contact points, or notification policies**. `plugins.yml` contains no apps, and automatic plugin preinstallation is disabled. The current stack is metrics and dashboards only until alert resources are added.

## Deploy and verify

Validate Compose:

```bash
docker compose --env-file unraid/.env \
  -f unraid/monitoring/compose.yml config --quiet
```

Start the stack:

```bash
docker compose --env-file unraid/.env \
  -f unraid/monitoring/compose.yml up -d
```

Check health:

```bash
docker compose --env-file unraid/.env \
  -f unraid/monitoring/compose.yml ps
```

Validate Prometheus after it starts:

```bash
docker exec prometheus \
  promtool check config /etc/prometheus/prometheus.yml

docker exec prometheus \
  promtool check ready --url=http://127.0.0.1:9090
```

Open `https://grafana.example.com`, pass the Authelia check, and sign in to Grafana with the initial admin credentials. In **Explore**, query:

```promql
up
```

Direct metric targets should return `1`. Then query:

```promql
probe_success
```

Healthy HTTP probes should return `1`. A `0` is useful information and does not mean that the monitoring stack itself is broken.

## First configuration

1. Confirm the Prometheus data source is present and marked as default.
2. Open all four provisioned dashboards and confirm that they load data.
3. Review `up` and `probe_success` for missing services.
4. Confirm Plex is reachable from Unraid at `${NAS_IP}:32400`.
5. Decide whether 30 days and 10 GB fit the available local disk.
6. Add alert rules and contact points before relying on the stack for notifications.

Authelia protects the Grafana route, but Grafana still has its own login. This configuration is not Grafana single sign-on.

## Backups

Back up:

- `${APPDATA_PATH}/grafana`, which contains Grafana's local database and state;
- `${APPDATA_PATH}/prometheus` if historical metrics must be recoverable;
- `unraid/monitoring/config`, which is also versioned in Git;
- an encrypted copy of the relevant `.env` values.

For a simple filesystem backup, stop Grafana before copying its data directory. Stop Prometheus cleanly before copying its time-series directory; copying a live write-ahead log is not a reliable backup method. The Prometheus admin snapshot API is not enabled in this Compose file.

The repository can recreate provisioned dashboards and the data source, but it cannot recreate UI-created Grafana users or historical Prometheus metrics. Test restoration and restore the original `UID:GID` ownership.

## Security notes

- Grafana sign-up is disabled.
- Grafana analytics, update checks, and plugin preinstallation are disabled.
- All three containers use read-only root filesystems, dropped capabilities, and `no-new-privileges`.
- Prometheus and Blackbox Exporter remain on Docker networks and have no public route.
- Keep Grafana credentials secret and restrict access to both persistent data directories.
- Do not add Internet-facing routes for raw metrics endpoints without authentication.

## Common problems

| Symptom | Check |
| --- | --- |
| External network not found | Deploy the edge stack first |
| Prometheus or Grafana reports permission denied | Ownership of its `${APPDATA_PATH}` directory and `UID:GID` |
| Grafana waits for Prometheus | Prometheus must pass its health check first |
| A target has `up = 0` | Container health, target port, and shared Docker network |
| A probe has `probe_success = 0` | Target service, path, expected 2xx response, and five-second timeout |
| Only Plex is down | `NAS_IP`, NAS firewall, Plex state, and port `32400` |
| Dashboard has no data | Prometheus data source, metric target, and metric names used by the dashboard |
| Dashboard edits cannot be saved | Provisioned dashboards intentionally set `allowUiUpdates: false` |
| No notifications arrive | No alert rules or contact points are currently provisioned |
| Metrics disappear before 30 days | The 10 GB retention limit was reached first |

## Official references

- [Prometheus configuration](https://prometheus.io/docs/prometheus/latest/configuration/configuration/)
- [Prometheus local storage and retention](https://prometheus.io/docs/prometheus/latest/storage/)
- [Prometheus multi-target exporter pattern](https://prometheus.io/docs/guides/multi-target-exporter/)
- [Blackbox Exporter](https://github.com/prometheus/blackbox_exporter)
- [Grafana provisioning](https://grafana.com/docs/grafana/latest/administration/provisioning/)
- [Grafana alerting file provisioning](https://grafana.com/docs/grafana/latest/alerting/set-up/provision-alerting-resources/file-provisioning/)
- [Back up Grafana](https://grafana.com/docs/grafana/latest/administration/back-up-grafana/)
