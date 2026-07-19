# Secrets and credentials

HavenStack uses environment-file secrets, application credentials, API keys, password hashes, VPN profiles, and persistent databases. A secret is safe only when its generation, storage, backup, use, and rotation are all controlled.

This page documents the current repository. It does not turn Docker environment variables into a dedicated secret-management system: an administrator with access to Docker or the host can inspect container environments and mounted files.

## What must stay private

The example files are safe to commit because they contain placeholders. Their populated copies are not.

| Location | Sensitive contents |
| --- | --- |
| `unraid/.env` | Cloudflare Tunnel token, Authelia secrets, Nextcloud credentials, Vaultwarden admin token, Grafana password, and VPN credentials |
| `unraid/edge/config/authelia/users.yml` | User identities, groups, and Argon2id password hashes |
| `${APPDATA_PATH}/qbittorrentvpn/openvpn` | VPN profile, certificates, and possibly private keys |
| `${APPDATA_PATH}/qbittorrentvpn/supervisord.log` | The randomly generated initial qBittorrent Web UI password may appear here |
| `${APPDATA_PATH}/authelia` and `notification.txt` | Authelia database, enrolled factors, reset links, and notification data |
| Application-data directories and Docker named volumes | Account databases, sessions, API keys, tokens, integration credentials, and application state |
| Backups and exported diagnostics | Copies of all of the above, and sometimes expanded configuration or logs |

IP addresses, domains, usernames, paths, and UID/GID values are not passwords, but together they form useful infrastructure inventory. Protect the complete configuration even when individual values are not secret.

`SECURITY_TXT_CONTACT` is intentionally published by the Homepage. Do not place a private personal address there unless you intend it to be public.

## Generate secrets safely

Use a password manager to generate and retain unique human-entered passwords. Use a cryptographically secure generator for machine secrets. Never reuse a value across applications or environments.

### General machine secrets

The repository recommends 64 random bytes for Authelia and other long machine secrets:

```bash
openssl rand -hex 64
```

The result contains 128 hexadecimal characters. Run the command separately for every variable. Hexadecimal output is convenient for the Nextcloud database and Redis values because it avoids punctuation that can be misinterpreted in connection strings.

### Authelia user passwords

Do not store an Authelia password in plain text. Generate an Argon2id hash interactively with the image version used by this repository:

```bash
docker run --rm -it authelia/authelia:4.39.20 \
  authelia crypto hash generate argon2
```

Paste the complete `Digest:` value into `users.yml`. Store the original password only in the user's password manager. See the [configuration guide](../getting-started/configuration.md#4-create-the-authelia-user-database) for the complete file format.

### Vaultwarden admin token

Generate the preferred Argon2id PHC value interactively:

```bash
docker run --rm -it vaultwarden/server:1.36.0 /vaultwarden hash
```

Place the generated PHC in `unraid/.env` inside single quotes so Docker Compose does not interpolate its `$` characters:

```dotenv
VAULTWARDEN_ADMIN_TOKEN='$argon2id$...'
```

The admin login uses the original password, not the PHC string. Keep both private.

### Provider-issued credentials

Do not replace provider-issued credentials with OpenSSL output. Obtain these from their authoritative service:

- `CLOUDFLARED_TUNNEL_TOKEN` from the remotely managed Cloudflare Tunnel;
- `VPN_USER`, `VPN_PASS`, the `.ovpn` profile, and certificates from the VPN provider;
- application API keys from the application that generated them.

## Sensitive values by stack

### Edge

| Value | Purpose | Rotation consequence |
| --- | --- | --- |
| `CLOUDFLARED_TUNNEL_TOKEN` | Authorizes `cloudflared` to connect this tunnel | The connector must be recreated with the new token; revoke the old token only after the replacement works |
| `AUTH_JWT_SECRET` | Signs Authelia identity-validation/reset tokens | Outstanding reset or validation tokens become invalid |
| `AUTH_SESSION_SECRET` | Protects Authelia sessions | Existing browser sessions should be expected to end |
| `AUTH_STORAGE_ENCRYPTION_KEY` | Encrypts sensitive Authelia storage values | Changing it without a supported re-encryption procedure can make stored data unreadable |
| `users.yml` password hashes | Authenticates local Authelia users | Replacing a hash changes that user's password; group changes alter authorization |

Treat `AUTH_STORAGE_ENCRYPTION_KEY` as persistent data, not a password to rotate casually. Keep a protected backup of the exact value. This repository does not provide an Authelia storage-key rotation procedure; follow current Authelia documentation and back up the database before attempting one.

The filesystem notifier writes to `unraid/edge/config/authelia/notification.txt`. It may contain password-reset links and must be protected and cleared according to the local operating procedure.

### Apps

`VAULTWARDEN_ADMIN_TOKEN` protects the server administration page. Rotating it requires replacing the PHC in `unraid/.env`, recreating Vaultwarden, and then using the new original password at `/admin`.

Vaultwarden user accounts, vault material, organization data, attachments, and sessions live below `${APPDATA_PATH}/vaultwarden`. They are not recreated from the environment file. Encrypt and access-control every backup of this directory.

The Homepage variables are mostly public metadata. Nevertheless, review `SITE_DESCRIPTION`, `SITE_KEYWORDS`, and `SECURITY_TXT_CONTACT` because the application intentionally renders them publicly.

### Nextcloud

| Value | Important behavior |
| --- | --- |
| `NEXTCLOUD_ADMIN_PASSWORD` | Bootstrap credential for the initial administrator; changing `.env` after initialization is not an account-password reset |
| `NEXTCLOUD_DATABASE_PASSWORD` | Shared by Nextcloud and PostgreSQL; the existing database role also retains its password |
| `NEXTCLOUD_REDIS_PASSWORD` | Shared by Nextcloud and Redis |

Do not rotate the database or Redis value by editing only `.env`. All consumers and the existing backend credential must change together during a planned maintenance window, with a verified backup. Rotate the administrator password through Nextcloud's supported account-management method.

Nextcloud's database volumes and `CLOUD_PATH` contain private user data even though they are not text credentials. Protect them accordingly.

### Servarr and qBittorrent

`VPN_USER` and `VPN_PASS` authenticate the VPN. Replace them in `unraid/.env`, update provider certificates or profiles when required, and recreate qBittorrent with no active transfers. Verify the VPN egress address again after rotation.

qBittorrent's Web UI password and the Prowlarr, Radarr, Sonarr, Seerr, and Profilarr passwords, API keys, and integration tokens are stored in their application-data directories rather than the environment template. When an API key changes, update every application that calls it. Treat support bundles and screenshots of application settings as sensitive.

### Monitoring

`GRAFANA_ADMIN_PASSWORD` is an initialization value persisted in the Grafana database. Editing `.env` later is not a reliable account reset. Change an existing administrator password through Grafana's supported UI or CLI and retain the result in the password manager.

Prometheus data and logs can reveal internal hostnames, URLs, availability patterns, and user-related labels. They are operationally sensitive even when they contain no password.

### Plex

Plex has no credential in `nas/.env`. Its account tokens, server identity, database, and preferences are stored below `${DATA_PATH}/plex`. A copy of that directory can grant meaningful access to the server account and library metadata; protect it like a credential.

## Store local files safely

The repository's [`.gitignore`](../../.gitignore) excludes local environment files, Authelia user data, VPN profiles, common private-key formats, databases, backups, and logs. Verify the exclusions after creating the local files:

```bash
git check-ignore -v \
  unraid/.env \
  nas/.env \
  unraid/edge/config/authelia/users.yml
```

All existing files should be listed with the applicable ignore rule. Before every commit, review the staged file names:

```bash
git diff --cached --name-only
```

An ignore rule is only a safety net. It does not encrypt files, remove a secret already committed, protect a copied file outside the repository, or hide values from a Docker administrator.

Apply restrictive host permissions or platform ACLs while preserving the access needed by the deployment account and container UID/GID. Store a second encrypted copy in a password manager or backup system that is separate from the live hosts. Document which backup contains which secret version.

Do not:

- commit a populated `.env`, even to a private repository;
- paste `docker compose config` output into a public issue, because it expands environment values;
- publish `docker inspect` output without removing container environment values;
- place secrets in Compose comments, screenshots, shell history, PR descriptions, or chat;
- email unencrypted environment files or application-data archives;
- rely on a single copy of an encryption key stored beside the data it decrypts.

Use `docker compose ... config --quiet` when validating a real environment file.

## Rotate a secret deliberately

Use this sequence for a planned rotation:

1. Identify the secret, every producer and consumer, and whether it protects persistent encrypted data.
2. Read the current upstream rotation procedure for that application.
3. Make and verify an encrypted backup of the relevant environment file and application data.
4. Stop dependent writes when consistency requires it.
5. Generate or obtain one new value and update all consumers together.
6. Recreate only the affected containers with the same Compose file and environment file.
7. Test authentication, health, integrations, and recovery before revoking the previous provider token.
8. Update the protected recovery record and destroy obsolete plaintext copies.

Rotate one dependency group at a time. Never rotate an encryption key merely because it is old; first confirm that the application supports re-encrypting existing data.

## If a secret reaches Git or a public log

Assume it has been copied. Removing the current line or deleting the branch is not sufficient because Git history, forks, caches, workflow logs, and local clones may retain it.

1. Revoke or rotate the exposed credential immediately.
2. Update and recreate every affected consumer.
3. Verify that the replacement works and the old value no longer does.
4. Remove the secret from visible logs and Git history using an agreed repository procedure.
5. Review access logs and provider activity for misuse.
6. Record the incident without recording the secret itself.

The [exposure matrix](exposure-matrix.md) explains what an attacker could reach if a credential or application account is compromised.
