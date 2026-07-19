# First-run checklist

Use this checklist after the containers are running and before storing important data or considering the installation complete. A green Docker health check confirms that a process responds; it does not confirm that authentication, routing, backups, permissions, or application integrations are correct.

Use the [stack guides](../stacks/README.md) alongside this checklist for service-specific configuration. Before storing important data, also review [Backup and restore](../operations/backup-and-restore.md), [Secrets and credentials](../security/secrets.md), and the [Exposure matrix](../security/exposure-matrix.md).

Complete only the sections for stacks you deployed.

## Record the deployed state

- [ ] Record the Git commit and, when available, the release tag you deployed.

  ```bash
  git rev-parse HEAD
  git describe --tags --always --dirty
  ```

- [ ] Keep a protected copy of the final configuration inventory: host IPs, selected stacks, paths, user IDs, Docker subnets, and public hostnames.
- [ ] Store `.env` files, Authelia users, VPN material, and other secrets in an encrypted backup or password manager. Do not commit them.
- [ ] Confirm that no value still begins with `replace-with-`.
- [ ] Confirm that the working tree does not show populated `.env`, `users.yml`, certificate, key, or VPN files as files ready to commit.

## Containers and storage

- [ ] Run `docker compose ... ps` for every deployed stack and wait for health-checked services to become `healthy`.
- [ ] Review the last 100 log lines for each stack and resolve recurring errors.
- [ ] Confirm `APPDATA_PATH`, `DATA_PATH`, and `MEDIA_PATH` point to the intended storage.
- [ ] Confirm the NAS shares behind `HOMELAB_PATH` and `CLOUD_PATH` are mounted, not empty fallback directories created on the Unraid boot drive.
- [ ] Create and delete a harmless test file using the same UID/GID as the relevant application where practical. This verifies real write access without changing production data.
- [ ] Confirm the Docker network ranges do not overlap the LAN, VPN, or other Docker networks.

## Cloudflare and application URLs

The repository configures the following routes. Replace `example.com` with your `DOMAIN`, and test only the services you deployed or intentionally exposed.

| URL | Expected destination |
| --- | --- |
| `https://example.com` | Homepage |
| `https://www.example.com` | Redirect to the main domain |
| `https://auth.example.com` | Authelia |
| `https://vault.example.com` | Vaultwarden |
| `https://cloud.example.com` | Nextcloud |
| `https://traefik.example.com` | Traefik dashboard |
| `https://grafana.example.com` | Grafana |
| `https://qbittorrent.example.com` | qBittorrent |
| `https://prowlarr.example.com` | Prowlarr |
| `https://radarr.example.com` | Radarr |
| `https://sonarr.example.com` | Sonarr |
| `https://seerr.example.com` | Seerr |
| `https://profilarr.example.com` | Profilarr |

- [ ] Confirm the Cloudflare Tunnel reports a healthy connector.
- [ ] Confirm every intended public hostname is configured in Cloudflare. In this topology, tunneled web traffic must reach Traefik on `http://traefik:8080` through the shared `edge_ingress` network.
- [ ] Remove Cloudflare hostnames that you do not intend to expose.
- [ ] Confirm each HTTPS URL has a valid certificate and does not produce a redirect loop.
- [ ] Test protected URLs in a private browser window so an existing session does not hide authentication problems.
- [ ] Confirm direct host ports are not unexpectedly reachable from untrusted networks. Most Unraid applications are intentionally reachable through Traefik rather than published host ports.

The current routing policy intentionally differs by application:

- The homepage has no Authelia middleware.
- Vaultwarden and Nextcloud use their own application login for normal use.
- Vaultwarden's `/admin` route is additionally protected by Authelia and requires an administrator with two-factor authentication.
- Traefik, Grafana, qBittorrent, Prowlarr, Radarr, Sonarr, and Profilarr require an Authelia administrator with two-factor authentication.
- Other routed subdomains using the Authelia middleware fall back to the wildcard one-factor policy unless a more specific rule exists.

Verify that this matches your intended exposure before inviting users.

## Authelia

- [ ] Confirm `unraid/edge/config/authelia/users.yml` contains a real Argon2id password hash and no example account details.
- [ ] Sign in through `https://auth.example.com` with the intended administrator account.
- [ ] Enroll and test TOTP or WebAuthn before relying on a two-factor-protected route.
- [ ] Confirm an administrator can reach `https://traefik.example.com` only after completing two-factor authentication.
- [ ] If you create a non-administrator test user, confirm that user is denied access to administrator-only routes.
- [ ] Review `unraid/edge/config/authelia/notification.txt` during enrollment or password-reset testing. The current configuration uses a filesystem notifier rather than email; protect and remove sensitive notification contents when they are no longer needed.
- [ ] Back up `users.yml`, the Authelia database under `${APPDATA_PATH}/authelia`, and the matching authentication secrets together. Losing the storage encryption key can make restored data unusable.

## Vaultwarden

The Compose configuration sets both `SIGNUPS_ALLOWED` and `INVITATIONS_ALLOWED` to `false`. This is a secure steady-state setting, but a completely new installation still needs a deliberate first-account bootstrap.

- [ ] Confirm an intended Vaultwarden account can sign in before storing credentials.
- [ ] If no account exists, bootstrap the first account with a server-administrator invitation from `/admin`, as described in [the Apps guide](../stacks/apps.md#understand-the-first-user-limitation). Do not enable public registration: the route is published through the Tunnel, so a temporary registration window is never private. Afterward, verify in a private browser window that registration remains closed.
- [ ] Do not expose open registration to the public Internet just to simplify initial setup.
- [ ] Confirm the Vaultwarden admin token is strong; an Argon2 PHC value is preferable to a plain-text password.
- [ ] Confirm `https://vault.example.com/admin` requires Authelia two-factor authentication in addition to the Vaultwarden admin token.
- [ ] Test creation and retrieval of a non-critical sample item.
- [ ] Back up `${APPDATA_PATH}/vaultwarden` and test the documented export or restore process before treating it as your only password store.

## qBittorrent VPN and kill switch

- [ ] Confirm `VPN_ENABLED=yes` and all VPN placeholder credentials have been replaced.
- [ ] Confirm the provider's OpenVPN profile and required certificates are present in the host directory mounted at `/config/openvpn`.
- [ ] Review qBittorrent container logs for a successful tunnel connection and the absence of repeated authentication or routing errors.
- [ ] Verify the public IP observed from inside the qBittorrent container belongs to the VPN provider and is different from your normal public IP. Use a trusted IP-check service or your VPN provider's recommended test.
- [ ] Perform the VPN image provider's documented kill-switch test before adding real downloads. qBittorrent must lose Internet access when the tunnel is unavailable.
- [ ] Confirm `LAN_NETWORK` includes the trusted LAN and the `servarr_backend` subnet. The repository default for that Docker network is `10.88.40.0/24`.
- [ ] Confirm the qBittorrent web interface is accessible through its protected URL but is not unexpectedly exposed through a public host port.

Do not assume the HTTP container health check proves the VPN tunnel or kill switch works; it verifies only that the local qBittorrent web service responds.

## Nextcloud

- [ ] Confirm `${CLOUD_PATH}` is the intended mounted storage and is writable before uploading data.
- [ ] Allow the first initialization to finish, then confirm all Nextcloud Compose services are healthy.
- [ ] Sign in at `https://cloud.example.com` with the intended administrator account.
- [ ] Replace any temporary bootstrap password and store the final credentials securely.
- [ ] Upload, download, rename, and delete a harmless test file.
- [ ] Confirm the test operation writes to the intended NAS storage rather than the Unraid boot drive.
- [ ] Confirm `https://cloud.example.com/status.php` responds through Traefik without exposing sensitive debugging information.
- [ ] Establish a database-consistent backup of the Nextcloud PostgreSQL data, named volumes, configuration, and `${CLOUD_PATH}` before adding important files. Copying a live database volume alone is not a complete backup procedure.

## Servarr applications

Detailed field-by-field configuration belongs in the individual stack guides. For the first run, verify the integration boundaries before importing a library or starting downloads.

- [ ] Sign in to each deployed Servarr application through its expected URL.
- [ ] Configure Prowlarr indexers and connect Prowlarr to Radarr and Sonarr.
- [ ] Add qBittorrent as the download client and use the container-visible `/data` paths consistently.
- [ ] Confirm Radarr, Sonarr, and qBittorrent see the same files under `/data`; avoid unnecessary remote path mappings when the paths already match.
- [ ] Test permissions with a harmless file before importing or moving a media library.
- [ ] Connect Seerr to Plex, Radarr, and Sonarr if Seerr is deployed.
- [ ] Review Profilarr profiles before allowing it to change production application settings.
- [ ] Run one controlled end-to-end test only after the VPN and kill switch have passed their checks.

## Monitoring

- [ ] Sign in to Grafana and confirm the configured administrator password is not a placeholder.
- [ ] Open the provisioned dashboards and confirm Prometheus data appears.
- [ ] Check Prometheus targets and resolve targets that remain down.
- [ ] Confirm Blackbox Exporter can reach the intended internal and NAS endpoints.
- [ ] Decide whether alerts are required. The repository currently provisions no alert rules or notification destinations, so add and test both before relying on monitoring for incident notification.
- [ ] Remember that monitoring data under `${APPDATA_PATH}/prometheus` has finite retention and is not a backup of application data.

## NAS service

### Plex

- [ ] Open `http://NAS_IP:32400/web`, claim or sign in to the intended Plex server, and confirm the server is not associated with an unexpected account.
- [ ] Add a small test library and confirm `${MEDIA_PATH}` maps to `/media` as expected.
- [ ] If hardware transcoding is required, confirm `/dev/dri` exists and perform a controlled transcode test.
- [ ] Protect Plex's host-networked ports with NAS and network firewall rules.
- [ ] Back up `${DATA_PATH}/plex`; media files require a separate backup decision based on their size and replaceability.

## Backups and recovery readiness

- [ ] Back up the Git release or commit identifier, configuration, encrypted secrets, application data, databases, and required external configuration such as Cloudflare Tunnel hostnames.
- [ ] Keep at least one encrypted copy outside the two HavenStack hosts.
- [ ] Define how much data loss is acceptable and schedule backups accordingly.
- [ ] Test a restore to a temporary location or isolated environment. A backup is not proven until it can be restored.
- [ ] Document the order required to restore storage, databases, applications, edge routing, and monitoring.
- [ ] Never use `docker compose down -v` as a troubleshooting step; it can delete named volumes.

## Installation completion criteria

The installation is ready for normal use only when:

- [ ] every deployed service is stable and expected health checks pass;
- [ ] intended URLs work and unintended exposure has been removed;
- [ ] Authelia two-factor authentication, application logins, and authorization rules have been tested;
- [ ] the qBittorrent VPN path and kill switch have been verified;
- [ ] storage mounts and permissions have passed real read/write tests;
- [ ] backups exist and at least one restore path has been tested.
