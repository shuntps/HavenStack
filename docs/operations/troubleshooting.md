# Troubleshooting

Troubleshoot HavenStack from the lowest failing layer upward. Collect evidence before restarting or changing anything; the first error is usually more useful than the errors caused by repeated retries.

## Safety rules

- Never use `docker compose down -v` as a troubleshooting command.
- Do not delete application directories, databases, or Docker volumes to make a service start.
- Do not disable the qBittorrent VPN or kill switch while transfers exist.
- Do not expose internal ports on the router as a shortcut around Cloudflare or Traefik.
- Do not paste `.env`, rendered secrets, Tunnel tokens, VPN credentials, private keys, or full authentication logs into a public issue.
- Confirm NAS mounts before starting containers that write to `${HOMELAB_PATH}` or `${CLOUD_PATH}`.

Commands using a repository Compose file were syntax-checked with the example environments. Runtime results remain **environment-dependent** because they require the deployed hosts, real secrets, mounts, networks, and containers.

## 1. Determine the scope

Ask these questions before changing state:

- Is one service failing, one stack failing, or every public hostname failing?
- Did it begin after a Git change, image pull, host reboot, NAS outage, token rotation, or VPN profile change?
- Does the application fail only through its public URL, or also on its internal health endpoint?
- Is the container stopped, restarting, `unhealthy`, or healthy with a functional problem?
- Are Unraid and NAS clocks, storage, DNS, and network connectivity normal?

Record the current Git commit and maintenance timeline.

## 2. Validate the Compose model

Run `config --quiet` before starting a changed stack. Example for Servarr:

```bash
docker compose --env-file unraid/.env \
  -f unraid/servarr/compose.yml config --quiet
```

This **repository-validated** command catches YAML, interpolation, and model errors. No output means the model rendered; it does not test credentials, mounts, image availability, or runtime connectivity.

All seven validation commands are in the [deployment guide](../getting-started/deployment.md#1-validate-the-compose-configuration).

If validation reports a missing variable, compare the local file with `.env.example` without replacing real secrets. If a value contains `$`, review Compose env-file quoting rules.

## 3. Inspect state and health

Show running and stopped containers for the affected stack:

```bash
docker compose --env-file unraid/.env \
  -f unraid/servarr/compose.yml ps --all
```

Interpret the result:

- `starting` can be normal during the configured grace period;
- `unhealthy` means the repeated health command failed, not necessarily that the process exited;
- `restarting` means the main process keeps exiting;
- `exited` requires the exit code and logs;
- a blank health column can be expected: `cloudflare-ddns` has no Compose health check.

A healthy container proves only its local health command. It does not prove public routing, authentication, storage integrity, service integrations, or VPN protection.

Docker-standard runtime inspection commands include:

```bash
docker inspect --format '{{json .State.Health}}' CONTAINER_NAME
docker inspect --format '{{.RestartCount}}' CONTAINER_NAME
```

These commands are **environment-dependent** because the named container must exist. Health output can contain command results but should not normally contain secrets; still review it before sharing.

## 4. Read focused logs

Read recent logs with timestamps:

```bash
docker compose --env-file unraid/.env \
  -f unraid/servarr/compose.yml logs \
  --since=15m --tail=200 --timestamps SERVICE_NAME
```

Add `--follow` only when actively reproducing the error; `Ctrl+C` stops following logs, not the container.

Look for the first recurring error involving:

- authentication or an expired token;
- permission denied or read-only filesystem;
- database migration or schema version;
- missing file, certificate, or mount;
- name resolution or connection refused;
- address or subnet conflict;
- out-of-memory termination;
- registry image not found.

Redact tokens, email addresses, client IPs, cookies, and VPN details before sharing logs.

## 5. Check the host and storage

The following are **environment-dependent host diagnostics** and may differ on a NAS appliance:

```bash
docker info
docker system df
df -h
date
findmnt -T /mnt/remotes/nas-homelab
findmnt -T /mnt/remotes/nas_cloud
```

Confirm:

- Docker is running and the expected Docker context is active;
- the host has free disk space and inodes;
- system time and timezone are correct;
- NAS paths resolve to the intended remote filesystem;
- directories exist with the configured `UID:GID` or `NAS_UID:NAS_GID` ownership;
- `/dev/dri` exists on the Plex host if hardware acceleration is configured;
- the NAS IP still matches both environment files.

If a remote mount disappeared, stop affected containers before remounting it. Docker can otherwise create or use a local directory at the same path, making data appear missing and consuming the Unraid disk.

## 6. Inspect Docker networks and name resolution

The edge stack creates the external Unraid networks. If another stack says a network does not exist, start edge first after checking its configuration.

List and inspect networks:

```bash
docker network ls
docker network inspect edge_ingress
docker network inspect apps_backend
docker network inspect servarr_backend
docker network inspect monitoring_backend
```

Expected relationships include:

- `cloudflared` and `traefik` on `edge_ingress`;
- Traefik and Authelia on `auth_backend`;
- Traefik and Vaultwarden/Nextcloud Apache on `apps_backend`;
- Traefik and all Servarr containers on `servarr_backend`;
- edge metrics services and monitoring on `monitoring_backend`.

Docker service names resolve only on a shared network. `localhost` inside a container refers to that same container. The Tunnel origin must therefore be `http://traefik:8080`, not `localhost:8080`.

Minimal images may not contain `ping`, `curl`, a shell, or DNS tools. Do not assume a missing diagnostic utility means DNS is broken. A temporary diagnostic container changes runtime state and may pull an image; use one only when intentionally approved and attach it to the exact network under test.

## 7. Trace a public request layer by layer

The request path is:

```text
public DNS -> Cloudflare edge -> Tunnel -> cloudflared
  -> traefik:8080 -> optional Authelia -> application
```

### Public DNS

From a client, check the apex and one application hostname:

```bash
nslookup example.com
nslookup auth.example.com
```

The apex and wildcard application names belong to the Tunnel and should not reveal the home public IP. `ddns.example.com` is the separate DDNS record and must not also be a Tunnel route.

If only the apex fails, confirm the explicit apex Tunnel route; `*.example.com` does not match `example.com`. If only subdomains fail, check the wildcard route and DNS record.

### Cloudflare Tunnel and cloudflared

Check that the connector is healthy in the Cloudflare dashboard, then inspect:

```bash
docker logs --since=15m --tail=200 --timestamps cloudflared
```

Verify:

- `CLOUDFLARED_TUNNEL_TOKEN` belongs to this Tunnel;
- both published routes target `http://traefik:8080`;
- the catch-all `http_status:404` rule is last;
- outbound DNS, HTTPS, and Cloudflare Tunnel connectivity are allowed;
- restrictive firewalls allow outbound port `7844` over TCP and UDP.

Do not open inbound router ports `80` or `443` to repair a Tunnel connection.

### Traefik

If the Tunnel connects but a hostname fails, inspect Traefik:

```bash
docker logs --since=15m --tail=200 --timestamps traefik
```

Check `DOMAIN`, the requested `Host` rule, the target service name and port, and the shared backend network. Dynamic routes are under `unraid/edge/config/traefik/dynamic/`.

### Authelia

For redirect loops or access denial, check:

- `DOMAIN` and `DOMAIN_SLD`;
- client, Unraid, and NAS time synchronization;
- browser cookies in a private window;
- the user's groups and second-factor enrollment;
- Authelia rule order;
- Traefik forwarded headers and the trusted `edge_ingress` subnet.

Use Authelia logs locally and redact user and session information before sharing.

## Public error guide

| Symptom | Likely layer | First check |
| --- | --- | --- |
| DNS name does not resolve | Public DNS | Apex/wildcard records and Cloudflare nameservers |
| Cloudflare says no Tunnel connection | Tunnel connector | cloudflared state, token, outbound connectivity |
| Cloudflare `502` | Tunnel origin | Traefik health, `traefik:8080`, and `edge_ingress` |
| `404` page | Traefik routing | Exact hostname and matching dynamic router |
| `502` or `504` for one app | Backend | App health, service port, and shared network |
| Authentication redirect loop | Authelia/headers | Domain, clock, cookies, forwarded headers |
| Login succeeds but app data is absent | Application/storage | Correct volume, mount, ownership, and database |
| Every app fails after edge stops | Dependency order | Restore edge and its external networks first |

HTTP error pages can be customized, so confirm the responding layer in logs rather than relying only on the status code.

## 8. Troubleshoot qBittorrent VPN safely

The qBittorrent health check calls only its local web interface. It does not verify the VPN tunnel, provider-assigned public IP, port forwarding, DNS privacy, or kill switch.

If qBittorrent is unhealthy or restarting, review its logs and confirm:

- `VPN_ENABLED=yes`;
- `VPN_PROV=pia` and `VPN_CLIENT=openvpn` still match the installed profile;
- the VPN-specific username and password are valid;
- exactly one intended `.ovpn` profile and every referenced certificate/key are under `${APPDATA_PATH}/qbittorrentvpn/openvpn`;
- `LAN_NETWORK` includes the trusted LAN and `10.88.40.0/24`, unless the subnet plan changed;
- the configured DNS resolvers are reachable;
- the container retains `NET_ADMIN` and the host permits tunnel creation;
- provider endpoints and requested port forwarding are available.

After fixing configuration, perform the VPN provider's recommended public-IP and kill-switch tests from the deployed environment. These checks are **environment-dependent** and cannot be validated by this repository. Keep transfers stopped until the observed public IP belongs to the VPN and the kill switch has been proven.

See [Servarr troubleshooting](../stacks/servarr.md#common-problems) for paths, hardlinks, API connections, and Seerr/Plex integration.

## 9. Application-specific diagnosis

Use the relevant guide instead of applying a generic database fix:

- [Edge](../stacks/edge.md#common-problems)
- [Apps and Vaultwarden](../stacks/apps.md#common-problems)
- [Nextcloud](../stacks/nextcloud.md#common-problems)
- [Servarr and qBittorrent](../stacks/servarr.md#common-problems)
- [Monitoring](../stacks/monitoring.md#common-problems)
- [Plex](../stacks/plex.md#common-problems)
- [Arcane](../stacks/arcane.md#common-problems)

Do not run a database repair, migration, permissions rewrite, or file rescan copied from an unrelated installation without checking the installed version and official upstream instructions.

## 10. Prepare a useful support report

Include:

- the affected stack and service;
- Git commit or release tag;
- image name and actual image ID;
- Docker and Compose versions;
- exact time and timezone of the failure;
- `docker compose ps --all` output;
- a short, sanitized log excerpt beginning before the first error;
- whether mounts, free space, and system time were checked;
- whether the problem occurs internally, publicly, or both;
- the last known change and steps to reproduce.

Do not attach populated environment files. Always remove passwords, tokens, cookies, session identifiers, API keys, and private keys — without exception. Domains, IP addresses, usernames, and paths may instead be replaced with consistent placeholders, such as `example.com`, so the report keeps the structure needed to diagnose the problem.

## Official references

- [Docker Compose command reference](https://docs.docker.com/reference/cli/docker/compose/)
- [Docker Compose `ps`](https://docs.docker.com/reference/cli/docker/compose/ps/)
- [Docker container logs](https://docs.docker.com/reference/cli/docker/container/logs/)
- [Docker inspect](https://docs.docker.com/reference/cli/docker/inspect/)
- [Docker networking overview](https://docs.docker.com/engine/network/)
- [Cloudflare Tunnel troubleshooting](https://developers.cloudflare.com/tunnel/troubleshooting/)
