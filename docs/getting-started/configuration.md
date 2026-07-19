# Configure HavenStack

Complete the [prerequisites](prerequisites.md) before this page. Run commands from the root of the HavenStack repository unless stated otherwise.

The populated environment files, Authelia user database, VPN profiles, certificates, and private keys are intentionally ignored by Git. They remain your responsibility to protect and back up securely.

## 1. Create the local environment files

On Unraid, create the local environment file:

```bash
cp unraid/.env.example unraid/.env
```

On the NAS, create its local environment file:

```bash
cp nas/.env.example nas/.env
```

Edit the files with a plain-text editor. Do not rename variables or add spaces around `=`. Values containing spaces should be quoted. A value containing `$`, such as a password hash, should be enclosed in single quotes so Docker Compose treats it literally.

Review **every** setting, including example values that do not begin with `replace-with-`.

## 2. Configure `unraid/.env`

Use [`unraid/.env.example`](../../unraid/.env.example) as the authoritative list. The sections below explain what must be reviewed.

### Host identity and storage

| Variable | Required value |
| --- | --- |
| `TZ` | An IANA timezone such as `America/Toronto` |
| `NAS_IP` | The stable LAN address of the NAS |
| `UID`, `GID` | Numeric identity that owns local Unraid application data |
| `NAS_UID`, `NAS_GID` | Numeric identity with read/write access to the mounted NAS media data |
| `APPDATA_PATH` | Local persistent application-data root on Unraid |
| `HOMELAB_PATH` | Mounted NAS media/download root exposed to Servarr as `/data` |
| `CLOUD_PATH` | Mounted NAS directory used exclusively for Nextcloud data |

The example paths are illustrative. Confirm that the selected paths exist and that `HOMELAB_PATH` and `CLOUD_PATH` are real mounted shares, not empty local directories.

The following child directories are used below `APPDATA_PATH`: `authelia`, `vaultwarden`, `qbittorrentvpn`, `prowlarr`, `radarr`, `sonarr`, `seerr`, `profilarr`, `prometheus`, and `grafana`. Pre-create them with the ownership and ACL method supported by Unraid, or verify the ownership immediately if Docker creates them.

### Domain and public metadata

| Variable | Required value |
| --- | --- |
| `DOMAIN` | Primary domain only, for example `example.com`; no scheme, path, or trailing slash |
| `DOMAIN_SLD` | Short site name used in metadata and the Authelia session cookie name, for example `example` |
| `SITE_DESCRIPTION` | Homepage description |
| `SITE_KEYWORDS` | Comma-separated Homepage keywords |
| `SITE_LOCALE` | Homepage locale such as `en` |
| `SECURITY_TXT_EXPIRES` | Future RFC 3339 timestamp; update it before it expires |
| `SECURITY_TXT_CONTACT` | A monitored security contact, normally a `mailto:` address |

For the deployment shown in the reference Cloudflare configuration, set `DOMAIN` to the real zone and publish only its apex and wildcard routes to Traefik. Follow the [Cloudflare Tunnel guide](cloudflare-tunnel.md).

### Nextcloud

Replace all three credential placeholders:

- `NEXTCLOUD_ADMIN_PASSWORD`
- `NEXTCLOUD_DATABASE_PASSWORD`
- `NEXTCLOUD_REDIS_PASSWORD`

`NEXTCLOUD_ADMIN_USER` may remain `admin`, but a less predictable name is preferable. The remaining values control logging, upload size, PHP memory, and request duration. The default upload limit is expressed in bytes; change performance limits only when the host has enough resources.

Nextcloud stores its main user data at `CLOUD_PATH` and its application, database, and Redis state in Docker named volumes. Backups must include both types of storage.

### Cloudflare Tunnel

Copy `CLOUDFLARED_TUNNEL_TOKEN` from the remotely managed Cloudflare Tunnel configuration. The token authorizes the connector to run the Tunnel and must remain private.

### Application and authentication credentials

Replace every secret placeholder:

- `AUTH_JWT_SECRET`
- `AUTH_SESSION_SECRET`
- `AUTH_STORAGE_ENCRYPTION_KEY`
- `VAULTWARDEN_ADMIN_TOKEN`
- `GRAFANA_ADMIN_PASSWORD`

Use a password manager to generate the human-entered Nextcloud and Grafana passwords. Generate separate machine secrets with OpenSSL:

```bash
openssl rand -hex 64
```

The command prints a 128-character hexadecimal value. Run it again for every machine secret; never reuse an output. Do not paste generated values into an issue, pull request, chat, screenshot, or shell script committed to the repository.

Vaultwarden accepts a strong random admin token. Its environment-file comment also describes the preferred Argon2 PHC form. If you use a PHC hash containing `$`, store the entire value inside single quotes in `.env` to prevent Compose interpolation.

### qBittorrent VPN

The defaults configure Private Internet Access over OpenVPN:

```dotenv
VPN_ENABLED=yes
VPN_PROV=pia
VPN_CLIENT=openvpn
```

Replace `VPN_USER` and `VPN_PASS` with the provider's VPN credentials. For PIA, these may differ from the credentials used on the provider's website.

Set `LAN_NETWORK` to the trusted LAN subnet plus `servarr_backend`, separated by commas and without spaces. With a `192.168.1.0/24` LAN and the repository's unchanged subnet plan:

```dotenv
LAN_NETWORK=192.168.1.0/24,10.88.40.0/24
```

If you changed `servarr_backend` in [`edge/compose.yml`](../../unraid/edge/compose.yml), use its new subnet here. `NAME_SERVERS` controls DNS inside the VPN container; retain the example Cloudflare resolvers or replace them with resolvers you trust.

## 3. Configure `nas/.env`

Use [`nas/.env.example`](../../nas/.env.example) as the authoritative list.

| Variable | Required value |
| --- | --- |
| `TZ` | Same IANA timezone used on Unraid |
| `UID`, `GID` | Numeric identity that owns Plex and media files on the NAS |
| `DATA_PATH` | Persistent application-data root; the Plex stack uses `plex` below it |
| `MEDIA_PATH` | Root of the Plex media library |

The Plex Compose file maps `/dev/dri`. Confirm the device and its permissions as described in the [prerequisites](prerequisites.md).

## 4. Create the Authelia user database

Create the local file from its example on Unraid:

```bash
cp unraid/edge/config/authelia/users.yml.example \
  unraid/edge/config/authelia/users.yml
```

Generate an Argon2id password hash interactively with the exact Authelia version used by the stack:

```bash
docker run --rm -it authelia/authelia:4.39.20 \
  authelia crypto hash generate argon2
```

Docker downloads the image if necessary and prompts for the password without putting it in shell history. Copy only the complete value shown after `Digest:` into `users.yml`:

```yaml
users:
  admin:
    disabled: false
    displayname: Administrator
    password: '$argon2id$v=19$...'
    email: admin@example.com
    groups:
      - admins
```

Replace the username, display name, email, and the entire example digest. Keep the `admins` group if this account should access services protected by the administrator-only Authelia rules. Do not enter a plain-text password in `users.yml`.

Authelia runs as the `UID:GID` from `unraid/.env`. That identity must be able to read `users.yml` and write to the Authelia configuration directory when password changes or filesystem notifications are used. Apply access through the ownership or ACL tools supported by Unraid.

See the [Authelia password guide](https://www.authelia.com/reference/guides/passwords/) for additional hashing options.

## 5. Install the qBittorrent OpenVPN profile

The host directory mounted at qBittorrent's `/config` is:

```text
APPDATA_PATH/qbittorrentvpn
```

Create an `openvpn` directory below it. Place exactly one provider-supplied `.ovpn` profile there, together with any certificate or key files referenced by the profile:

```text
APPDATA_PATH/qbittorrentvpn/openvpn/provider-profile.ovpn
```

This location is runtime application data, not `unraid/servarr/` in the repository. VPN profiles and keys are ignored by Git and must never be committed.

Verify the profile after replacing the path below with the real `APPDATA_PATH`:

```bash
find /actual/appdata/qbittorrentvpn/openvpn \
  -maxdepth 1 -type f -name '*.ovpn' -print
```

The command should print exactly one `.ovpn` file. Open that file and confirm that every referenced certificate or key also exists in the same directory or at the path expected by the provider.

## 6. Verify paths and permissions

On Unraid, confirm that the configured roots exist:

```bash
test -d /actual/appdata/path && echo 'APPDATA path exists'
test -d /actual/homelab/path && echo 'HOMELAB path exists'
test -d /actual/cloud/path && echo 'CLOUD path exists'
```

Use the actual values from `unraid/.env`. Verify the two NAS-backed paths with `findmnt -T` as described in the [prerequisites](prerequisites.md). A directory merely existing is not proof that the remote share is mounted.

On the NAS, perform the equivalent check for `DATA_PATH` and `MEDIA_PATH`. Confirm ownership with:

```bash
stat -c '%u:%g %A %n' /actual/path
```

The numeric owner and group should match the intended `UID:GID`, or the platform ACL must grant equivalent access. Correct permissions deliberately; do not use world-writable permissions as a shortcut.

## 7. Check that secrets remain outside Git

From the repository root, verify the three local configuration files:

```bash
git check-ignore -v \
  unraid/.env \
  nas/.env \
  unraid/edge/config/authelia/users.yml
```

The expected result lists an applicable `.gitignore` rule for each existing file. If one is not listed, stop before committing anything and investigate.

Check for unfinished placeholders:

```bash
if grep -n 'replace-with-' \
  unraid/.env nas/.env unraid/edge/config/authelia/users.yml; then
  echo 'Replace every value listed above.'
else
  echo 'No replace-with placeholders found.'
fi
```

Also search manually for unchanged examples such as `example.com`, the example IP addresses, `UID=1000`, and sample storage paths. An example value may happen to be correct for your environment, so review it rather than replacing it blindly.

## 8. Validate the Compose models

Run the following commands on Unraid:

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
```

Run these commands on the NAS:

```bash
docker compose --env-file nas/.env \
  -f nas/plex/compose.yml config --quiet
```

No output and exit code `0` means the Compose model passed validation. An error normally identifies a missing variable, invalid interpolation, or YAML/Compose problem.

This validation does not contact applications, test credentials, verify mounts or permissions, detect subnet conflicts, or prove that a container can start. Do not publish the non-quiet output of `docker compose config`, because it can contain expanded secrets.

When every check passes, create the [Cloudflare Tunnel routes](cloudflare-tunnel.md), then continue with the [deployment guide](deployment.md).
