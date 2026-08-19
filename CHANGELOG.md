# Changelog

Every entry is a deployable state of the fleet. Releases are cut automatically
when something under `unraid/` or `nas/` changes; documentation and CI changes
do not produce a version because they change nothing you could deploy.

The tag for a version points at the commit the CI suite validated. This file is
written immediately afterwards, so on `main` it always runs one commit ahead of
the release it describes.

## v1.1.0 — 2026-08-19

### Images

No image changed in this release.

### Redeploy

```bash
docker compose --env-file nas/.env -f nas/arcane/compose.yml up -d
```

### Changes

#### New capabilities

- **ci**: cut releases automatically when the deployment changes (03435ca)

#### Refactoring

- **arcane**: declare the compose project name explicitly (e73d60a)

#### CI

- run every workflow on main pushes and v* tags (a0fde5d)
- **release**: push the changelog with RELEASE_TOKEN (d555b4e)

**Full diff**: https://github.com/shuntps/HavenStack/compare/v1.0.0...v1.1.0

## v1.0.0 — 2026-08-19

First tagged state of HavenStack. Everything up to here was tracked in git but
never named, so "roll back to before it broke" meant reading `git log`. From
this tag on, there is a point to return to.

**This release is different from the ones that follow.** There is no previous
tag to diff against, so it describes the *state* of the deployment rather than
what changed. Later releases will be deltas: what changed, and which stacks
need redeploying.

### Fleet

| Host | Stack | Services |
| --- | --- | --- |
| Unraid | `edge` | cloudflared, cloudflare-ddns, traefik, authelia |
| Unraid | `apps` | homepage, vaultwarden |
| Unraid | `servarr` | qbittorrent, prowlarr, radarr, sonarr, seerr, profilarr |
| NAS | `plex` | plex |
| NAS | `arcane` | arcane |

14 services, 8 pinned networks under `10.88.0.0/16`, two hosts.

### Image inventory

The reason this tag is a rollback point. Restoring `v1.0.0` restores exactly
these versions.

| Stack | Service | Image |
| --- | --- | --- |
| `unraid/edge` | cloudflared | `cloudflare/cloudflared:2026.8.2` |
| `unraid/edge` | cloudflare-ddns | `favonia/cloudflare-ddns:1.17.0` |
| `unraid/edge` | traefik | `traefik:v3.7.10` |
| `unraid/edge` | authelia | `authelia/authelia:4.39.20` |
| `unraid/apps` | homepage | `shuntps/homepage:1.1.0` |
| `unraid/apps` | vaultwarden | `vaultwarden/server:1.37.1` |
| `unraid/servarr` | qbittorrent | `binhex/arch-qbittorrentvpn:5.2.3-3-01` |
| `unraid/servarr` | prowlarr | `linuxserver/prowlarr:2.5.2` |
| `unraid/servarr` | radarr | `linuxserver/radarr:6.3.0` |
| `unraid/servarr` | sonarr | `linuxserver/sonarr:4.0.19` |
| `unraid/servarr` | seerr | `ghcr.io/seerr-team/seerr:v3.4.1` |
| `unraid/servarr` | profilarr | `ghcr.io/dictionarry-hub/profilarr:2.2.0` |
| `nas/plex` | plex | `linuxserver/plex:1.43.3` |
| `nas/arcane` | arcane | `ghcr.io/getarcaneapp/arcane:latest` |

Caveat: these are tags, not digests. Tags are mutable, so pulling this release
in six months may not give byte-identical images. Digest pinning would close
that gap.

### What CI guarantees about this state

Seven required checks pass on this commit:

- every stack renders against its `.env.example`
- no variable a compose file interpolates is missing or empty in that template
- every Traefik router resolves to a service and middleware that exists
- Traefik and Authelia agree on what is protected: no broken `two_factor`/`deny`
  pair, no policy that is never consulted, no route silently downgraded to one
  factor
- every service meets the hardening baseline or carries a justified waiver
- Authelia's configuration loads in the real Authelia binary
- workflows lint clean

### Deploying this release from scratch

`edge` first — it is the only stack that defines the shared networks.

```bash
git checkout v1.0.0
docker compose --env-file unraid/.env -f unraid/edge/compose.yml up -d
docker compose --env-file unraid/.env -f unraid/apps/compose.yml up -d
docker compose --env-file unraid/.env -f unraid/servarr/compose.yml up -d
docker compose --env-file nas/.env -f nas/plex/compose.yml up -d
docker compose --env-file nas/.env -f nas/arcane/compose.yml up -d
```

### Required on the hosts, not in this tag

- `unraid/.env` and `nas/.env`, from the `.env.example` templates
- `unraid/edge/config/authelia/users.yml`, argon2id-hashed
- one OpenVPN profile in the qBittorrent `/config/openvpn` directory

### Accepted waivers

Deliberate, documented in `.github/ci/invariant-exceptions.yml`, enforced by CI:

- `cloudflare-ddns` runs without a healthcheck — its `FROM scratch` image has no
  shell and no HTTP endpoint to probe
- `prowlarr`, `radarr`, `sonarr`, `plex`, `qbittorrent`, `arcane` run without
  `read_only`/`cap_drop`
- `arcane` tracks `latest` and holds the Docker socket
