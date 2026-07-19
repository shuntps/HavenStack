# Prerequisites

HavenStack is a collection of Docker Compose stacks for two machines. It is not a one-click installer. Prepare the hosts, storage, network, domain, and external accounts on this page before editing the configuration.

The commands below assume a POSIX-compatible shell on the target host, such as the Unraid terminal or an SSH session on the NAS. Settings such as static addresses, share mounts, ACLs, and hardware access are platform-specific; use the administration method supported by your host.

## Deployment topology

The reference deployment expects these two Docker hosts:

| Host | Responsibilities | Repository directory |
| --- | --- | --- |
| Unraid | Cloudflare Tunnel, Traefik, Authelia, Homepage, Vaultwarden, Nextcloud, Servarr, qBittorrent, Prometheus, and Grafana | `unraid/` |
| NAS | Plex, persistent media, and the storage mounted by Unraid | `nas/` |

Both hosts must be able to reach each other over the LAN. Unraid must also be able to read and write the NAS shares used for media and Nextcloud data.

You need a copy of the repository on each host that will run a stack. A shared checkout is also possible, but each host still needs its own local environment file and access to the paths referenced by that file.

## Hardware and capacity

There is no universal hardware minimum because media size, Nextcloud usage, and Plex transcoding determine the real load. The Compose files do set these memory ceilings:

| Host | Sum of configured container memory limits | Notes |
| --- | ---: | --- |
| Unraid | 11,072 MiB (10.8125 GiB) | Includes every Unraid stack |
| NAS | 1,024 MiB (1 GiB) | Plex |

These values are upper limits, not reserved memory and not a guarantee that the applications will perform well with less. Leave additional memory for the host operating system, Docker, filesystem cache, and workload spikes. The repository does not define CPU limits.

The NAS Plex service maps `/dev/dri` into the container. The current Compose file therefore expects a Linux Direct Rendering Infrastructure device on the NAS, normally provided by a compatible integrated or discrete GPU:

```bash
ls -l /dev/dri
```

The expected result is a directory containing one or more device nodes, commonly `card0` and `renderD128`. If `/dev/dri` does not exist, decide whether to configure a supported GPU on the NAS or deliberately adapt the Plex Compose file before deployment.

Storage capacity is workload-dependent. Plan room for:

- container application data and databases;
- the complete Plex media library;
- qBittorrent downloads and Servarr imports;
- Nextcloud user data, file versions, and trash;
- backups separate from the live data.

Do not count the live NAS share itself as a backup.

## Docker and command-line access

Install Docker Engine and the current Docker Compose plugin on both hosts. HavenStack uses the `docker compose` command with a space, not the retired `docker-compose` v1 command.

Verify each host:

```bash
docker version
docker compose version
```

Both commands must succeed. Docker Compose may report a newer major version than the original v2 plugin; newer releases are expected to work but are not verified automatically at runtime. The account used for deployment must be allowed to talk to the Docker daemon. Avoid making the Docker socket broadly writable to solve a permission problem.

You also need:

- a terminal or SSH access on each host;
- Git, or another safe way to copy the repository to each host;
- `openssl` for random secret generation;
- accurate date and time synchronization, which is important for Authelia sessions and two-factor authentication.

## LAN addresses and connectivity

Assign stable LAN addresses to Unraid and the NAS, using either DHCP reservations or the network configuration supported by each platform. The example addresses in the repository are not defaults that must be retained:

- `NAS_IP=192.168.1.10`

Record the real addresses. From Unraid, verify that the NAS is reachable; from the NAS, verify the Unraid address in the same way:

```bash
ping -c 3 192.168.1.10
```

Replace the address before running the command. A successful test receives replies without packet loss. Some hosts block ICMP; in that case, verify reachability using the host's management page or an existing TCP service.

Plex uses host networking and normally listens on NAS port `32400`. Restrict this LAN service to trusted networks with the controls available on the NAS and firewall.

## Docker subnet plan

HavenStack assigns fixed subnets to the shared Unraid networks:

| Network | Subnet |
| --- | --- |
| `edge_ingress` | `10.88.10.0/24` |
| `auth_backend` | `10.88.20.0/24` |
| `apps_backend` | `10.88.30.0/24` |
| `servarr_backend` | `10.88.40.0/24` |
| `homepage_backend` | `10.88.50.0/24` |
| `monitoring_backend` | `10.88.60.0/24` |

None of these ranges may overlap your LAN, another Docker network, a site-to-site network, or a VPN route. Inspect the existing Docker networks on each host:

```bash
docker network inspect $(docker network ls -q) \
  --format '{{.Name}}: {{range .IPAM.Config}}{{.Subnet}} {{end}}'
```

Compare the output with the table and with the networks used by your router and VPN. Resolve every overlap before starting the stacks.

If you change the subnet plan, update every reference to the affected subnet. In particular:

- Traefik trusts `10.88.10.0/24` in [`traefik.yml`](../../unraid/edge/config/traefik/traefik.yml);
- qBittorrent's `LAN_NETWORK` must include `servarr_backend`, currently `10.88.40.0/24`.

## Domain and Cloudflare

You need:

- a registered domain whose DNS zone is managed by Cloudflare;
- permission to create a remotely managed Cloudflare Tunnel;
- the token generated for that tunnel;
- two published application routes: the apex domain and its wildcard, both targeting `http://traefik:8080`;
- a final catch-all rule returning HTTP `404`.

For a domain named `example.com`, the required routes are `example.com` and `*.example.com`. The detailed procedure is in the [Cloudflare Tunnel guide](cloudflare-tunnel.md).

The tunnel makes outbound connections to Cloudflare, so normal inbound router port forwarding is not required for HavenStack web applications. Both hosts and the containers that need internet access must still be allowed outbound DNS and HTTPS traffic.

## VPN account and profile

qBittorrent is configured to run through `binhex/arch-qbittorrentvpn` with its VPN enabled and kill switch active. Before deploying the Servarr stack, obtain:

- an active VPN account;
- VPN-specific credentials from the provider;
- one provider-supplied OpenVPN profile and every certificate or key referenced by that profile.

The environment template is configured for Private Internet Access (`VPN_PROV=pia`) over OpenVPN (`VPN_CLIENT=openvpn`). Using another provider or client requires reviewing the qBittorrent image's supported settings rather than merely changing the provider name.

Do not start qBittorrent without a valid profile. Do not disable the VPN just to make initial deployment easier unless you intentionally accept direct torrent traffic from your normal internet connection.

## Storage paths and mounts

Prepare these host paths before deployment:

| Variable | Host | Purpose |
| --- | --- | --- |
| `APPDATA_PATH` | Unraid | Persistent application configuration, databases, and monitoring data |
| `HOMELAB_PATH` | Unraid | NAS-backed media and download data shared by qBittorrent, Radarr, and Sonarr |
| `CLOUD_PATH` | Unraid | NAS-backed Nextcloud data |
| `DATA_PATH` | NAS | Persistent Plex application data |
| `MEDIA_PATH` | NAS | Plex media library |

Mount the NAS shares at the exact Unraid paths selected for `HOMELAB_PATH` and `CLOUD_PATH`, and configure those mounts to return after a reboot. This step is platform-specific: use the supported Unraid and NAS share/mount tools.

On Unraid, verify each remote path after mounting it:

```bash
findmnt -T /actual/path/to/homelab
findmnt -T /actual/path/to/cloud
```

Each command should identify the intended remote filesystem. If it instead resolves to the local root filesystem, stop: starting the containers could write data into an empty local directory while the NAS is unavailable.

## Users, groups, and permissions

The numeric identities in the environment files must match the owners of the files on each host:

- Unraid `UID` and `GID` own local application data.
- Unraid `NAS_UID` and `NAS_GID` must be able to read and write the mounted media share.
- NAS `UID` and `GID` own the NAS application and media files used by Plex.

Find the numeric values on each host:

```bash
id ACCOUNT_NAME
```

Replace `ACCOUNT_NAME` with the account that owns the relevant data. Example output includes `uid=1000(...) gid=1000(...)`. Use the numeric values, not the account names.

Permissions across NFS or SMB mounts may be affected by server-side ACLs and identity mapping. Verify access from Unraid using the same numeric identity configured for the containers. Do not make application data, cloud data, or the media library world-writable as a shortcut, and do not recursively change ownership of an existing library without understanding the impact on other clients.

The detailed paths, secrets, and local files are prepared in the [configuration guide](configuration.md).
