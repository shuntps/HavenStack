# Apps stack

The apps stack runs HavenStack's public Homepage and its Vaultwarden password manager. Neither service publishes a host port; Traefik reaches them over Docker networks created by the edge stack.

Run the commands in this guide from the root of the HavenStack repository on Unraid.

## Services

| Service | Image | Purpose |
| --- | --- | --- |
| Homepage | `shuntps/homepage:1.1.0` | Displays the HavenStack landing page and generated site/security metadata. |
| Vaultwarden | `vaultwarden/server:1.36.0` | Provides a self-hosted, Bitwarden-compatible password vault and administration panel. |

The Homepage image is a custom image published by the repository owner. It is not the `gethomepage/homepage` project, so do not apply that project's configuration instructions to this container.

## Prerequisites and dependencies

Before deploying the apps stack, confirm that:

- The full `edge` stack is running.
- Docker networks named `apps_backend` and `homepage_backend` exist.
- `unraid/.env` exists and contains no placeholder values.
- `${APPDATA_PATH}/vaultwarden` exists and is writable by `UID:GID`.
- The Cloudflare Tunnel apex and wildcard routes reach `http://traefik:8080`.
- Authelia has a working administrator with two-factor authentication for the Vaultwarden admin route.
- `VAULTWARDEN_ADMIN_TOKEN` is a strong secret, preferably an Argon2 PHC value.

## Networks and storage

| Service | Network | Persistent storage |
| --- | --- | --- |
| Homepage | `homepage_backend` | None. Temporary files use `/tmp` and `/app/.next/cache` in memory-backed filesystems. |
| Vaultwarden | `apps_backend` | `${APPDATA_PATH}/vaultwarden` is mounted at `/data`. |

Both networks are external to this Compose project and are created by `unraid/edge/compose.yml`. `homepage_backend` is internal. Neither application has a `ports` section, so direct access through an Unraid host port is not expected.

## Relevant environment variables

| Variable | Used for |
| --- | --- |
| `TZ` | Time zone for both containers. |
| `UID`, `GID` | User and group used to run Vaultwarden and own its data. |
| `DOMAIN` | Homepage domain and Vaultwarden public URL at `https://vault.DOMAIN`. |
| `DOMAIN_SLD` | Homepage author/site label. |
| `APPDATA_PATH` | Root of the persistent Vaultwarden data directory. |
| `SITE_DESCRIPTION` | Homepage description metadata. |
| `SITE_KEYWORDS` | Homepage keyword metadata. |
| `SITE_LOCALE` | Homepage locale. |
| `SECURITY_TXT_EXPIRES` | Future RFC 3339 expiration timestamp for generated security contact metadata. |
| `SECURITY_TXT_CONTACT` | Security contact URI, such as `mailto:security@example.com`. |
| `VAULTWARDEN_ADMIN_TOKEN` | Secret or Argon2 PHC used to authenticate to Vaultwarden's `/admin` panel. |

The Homepage listens on container port `3000`. Vaultwarden listens on container port `8080`; its public `DOMAIN` is set by Compose to `https://vault.${DOMAIN}`.

## Deploy and verify

Validate without rendering secrets:

```bash
docker compose --env-file unraid/.env \
  -f unraid/apps/compose.yml config --quiet
```

Start both services:

```bash
docker compose --env-file unraid/.env \
  -f unraid/apps/compose.yml up -d
```

Check health:

```bash
docker compose --env-file unraid/.env \
  -f unraid/apps/compose.yml ps
```

Both services should eventually report `healthy`. If they do not, inspect the last log messages:

```bash
docker compose --env-file unraid/.env \
  -f unraid/apps/compose.yml logs --tail=100
```

The health checks call Homepage's `/api/health` endpoint and Vaultwarden's `/alive` endpoint from inside their respective containers. A healthy result does not prove that Cloudflare, Traefik, authentication, or persistent storage works correctly.

## Homepage first configuration

Homepage has no persistent configuration volume or interactive setup in this stack. Its site metadata comes from `unraid/.env`.

1. Set `DOMAIN`, `DOMAIN_SLD`, `SITE_DESCRIPTION`, `SITE_KEYWORDS`, and `SITE_LOCALE`.
2. Set `SECURITY_TXT_CONTACT` to a contact you actually monitor.
3. Set `SECURITY_TXT_EXPIRES` to a future RFC 3339 timestamp and plan to update it before it expires.
4. Validate and run `up -d` again after changing these values.
5. Test `https://example.com`, `https://www.example.com`, `/api/health`, and the generated security contact metadata.

Replace `example.com` with your domain. The `www` route redirects to the apex domain.

The current Traefik router does not apply Authelia to the Homepage. Treat everything displayed there as public information. Do not add private hostnames, internal addresses, tokens, or personal details to its metadata.

## Vaultwarden first configuration

### Prepare the admin token

Vaultwarden's official documentation recommends hashing the admin token with Argon2id. Generate it interactively with the deployed image version:

```bash
docker run --rm -it vaultwarden/server:1.36.0 /vaultwarden hash
```

Put the generated PHC value in `unraid/.env` using single quotes so the `$` characters remain literal:

```dotenv
VAULTWARDEN_ADMIN_TOKEN='$argon2id$...'
```

When signing in to `/admin`, enter the original password used to generate the hash, not the PHC string. Keep both the password and populated `.env` private.

### Understand the first-user limitation

The current Compose file deliberately sets:

```yaml
SIGNUPS_ALLOWED: "false"
INVITATIONS_ALLOWED: "false"
```

This means:

- open user registration is disabled;
- organization administrators cannot invite users;
- according to Vaultwarden's current primary documentation and source, the Vaultwarden **server administrator** can still invite a user from the `/admin` panel while registration is disabled.

This repository does not configure SMTP, automate the invitation, or test the complete first-user invitation flow. Its CI validates only the Compose model. Therefore:

1. Open `https://vault.example.com/admin` only after Authelia two-factor authentication works.
2. Sign in with the Vaultwarden admin-token password.
3. Follow Vaultwarden's official admin-panel documentation to invite the intended first user.
4. Test the complete invitation and account-registration flow in your environment before storing credentials.

Do not temporarily enable public registration based solely on this guide. If the invitation cannot be completed, stop and consult the linked Vaultwarden documentation for your exact mail and client setup.

Vaultwarden's admin panel can write `/data/config.json`. Once created, values saved there can take precedence over corresponding environment variables. Avoid casually saving unrelated admin settings, and include `config.json` in backups if it exists.

### Finish the application setup

- Sign in to `https://vault.example.com` with the intended user account.
- Enroll a supported second factor in Vaultwarden itself.
- Create, retrieve, edit, and delete a harmless test item.
- Test the web vault over HTTPS; the upstream web vault requires a secure context.
- Confirm a private browser cannot create an uninvited account.

## URLs and authentication

| URL | Authentication in this repository |
| --- | --- |
| `https://example.com` | Public Homepage; no Authelia middleware. |
| `https://www.example.com` | Permanent redirect to the apex Homepage. |
| `https://vault.example.com` | Vaultwarden's native login; no Authelia middleware on the normal vault route. |
| `https://vault.example.com/admin` | Authelia `admins` group with two-factor authentication, followed by the Vaultwarden admin token. |

The normal Vaultwarden route intentionally avoids Authelia so Bitwarden-compatible clients can communicate with the server. Protect user accounts with strong master passwords and Vaultwarden-supported two-factor authentication.

## Backup data

### Homepage

Homepage has no persistent application volume in this stack. Back up:

- the Git release or commit containing the Compose file;
- the non-secret site metadata in your configuration inventory;
- the encrypted `unraid/.env` backup used to recreate the deployment.

### Vaultwarden

All Vaultwarden state is under `${APPDATA_PATH}/vaultwarden`, including the SQLite database, attachments, Sends, RSA keys, and a possible `config.json`.

Vaultwarden includes a SQLite backup command:

```bash
docker exec -it vaultwarden /vaultwarden backup
```

That database backup does not replace a backup of attachments and the rest of `/data`. Follow the upstream backup guide, copy all required persistent files to encrypted backup storage, and test a restore. Protect backups as strongly as the live password vault.

## Security notes

- Vaultwarden stores highly sensitive data. Keep it behind HTTPS and maintain tested encrypted backups.
- Keep `SIGNUPS_ALLOWED` and `INVITATIONS_ALLOWED` at `false` unless you have reviewed and deliberately changed the account policy.
- Use an Argon2 PHC for `VAULTWARDEN_ADMIN_TOKEN` and keep the original password secret.
- The `/admin` route has two independent checks: Authelia administrator 2FA and the Vaultwarden admin token.
- The normal vault uses Vaultwarden authentication, not Authelia. Test Vaultwarden's own two-factor authentication.
- The Homepage is public and may reveal whatever metadata it renders.
- Both containers use read-only root filesystems, drop Linux capabilities, and enable `no-new-privileges`. Vaultwarden can write only to its mounted data and temporary directories.
- Do not expose container ports directly as a shortcut around Traefik.
- Never use `docker compose down -v` for routine maintenance.

## Common problems

### `network ... declared as external, but could not be found`

Deploy the complete edge stack first:

```bash
docker compose --env-file unraid/.env -f unraid/edge/compose.yml up -d
```

### Homepage is healthy but the domain returns `404` or `502`

Check the Tunnel apex route, `DOMAIN`, Traefik logs, and `homepage_backend`. A `404` usually means no Traefik router matched; a `502` usually means Traefik could not reach the Homepage service.

### Homepage metadata is outdated

Update `unraid/.env`, run `config --quiet`, and apply the change with `up -d`. A plain container `restart` does not reliably apply changed environment values.

### Vaultwarden reports `permission denied`

Check `${APPDATA_PATH}/vaultwarden` ownership and the configured `UID:GID`. Do not solve the issue by making the password-vault directory world-writable.

### New users cannot register

That is expected: `SIGNUPS_ALLOWED=false`. Use the server-admin invitation capability documented upstream. The complete no-SMTP first-user flow is not tested by this repository.

### Organization administrators cannot invite users

That is expected: `INVITATIONS_ALLOWED=false` disables organization-admin invitations. It does not disable the separate server-admin invitation capability described by Vaultwarden.

### The admin token is rejected

If it is an Argon2 PHC, confirm it is single-quoted in `unraid/.env` and sign in with the original password, not the hash. Also check whether `/data/config.json` contains an admin setting that overrides the environment variable.

### Vaultwarden is healthy but clients fail

Confirm `https://vault.example.com` works with a valid certificate and that `DOMAIN` matches it exactly. Review Vaultwarden and Traefik logs. Do not publish logs containing account identifiers or tokens.

## Official upstream documentation

- [Vaultwarden repository](https://github.com/dani-garcia/vaultwarden)
- [Vaultwarden admin panel and secure admin token](https://github.com/dani-garcia/vaultwarden/wiki/Enabling-admin-page)
- [Vaultwarden backup guide](https://github.com/dani-garcia/vaultwarden/wiki/Backing-up-your-vault)
- [Vaultwarden current configuration source](https://github.com/dani-garcia/vaultwarden/blob/main/src/config.rs)
- [Vaultwarden hardening guide](https://github.com/dani-garcia/vaultwarden/wiki/Hardening-Guide)
- [Published Homepage image](https://hub.docker.com/r/shuntps/homepage)
- [RFC 9116 security.txt](https://www.rfc-editor.org/rfc/rfc9116.html)

No separate upstream setup manual for the custom `shuntps/homepage` image is linked by this repository. The Homepage details above are intentionally limited to behavior visible in `unraid/apps/compose.yml` and `unraid/.env.example`.
