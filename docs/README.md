# HavenStack documentation

This documentation explains how to reproduce the HavenStack reference deployment on an Unraid server and a separate NAS.

HavenStack is a collection of Docker Compose stacks rather than a one-click installer. Follow the pages below in order for a first installation. Each step explains what to configure, how to start it, and how to verify it before continuing.

## Installation path

Start with the [quick-start guide](getting-started/quick-start.md) for the shortest safe path through a first installation. Use the detailed pages when you need the reasoning, complete checks, or troubleshooting context:

1. [Review the prerequisites](getting-started/prerequisites.md).
2. [Understand the architecture](architecture/overview.md).
3. [Configure the environment and local files](getting-started/configuration.md).
4. [Create the Cloudflare Tunnel routes](getting-started/cloudflare-tunnel.md).
5. [Deploy the stacks](getting-started/deployment.md).
6. [Complete the first-run checks](getting-started/first-run-checklist.md).

## Architecture

- [System overview](architecture/overview.md)
- [Networking and request flow](architecture/networking.md)
- [Storage layout and ownership](architecture/storage.md)

## Stack guides

After the base deployment, use the [stack guide index](stacks/README.md) for detailed configuration and verification:

- [Edge](stacks/edge.md)
- [Apps](stacks/apps.md)
- [Nextcloud](stacks/nextcloud.md)
- [Servarr](stacks/servarr.md)
- [Monitoring](stacks/monitoring.md)
- [Plex](stacks/plex.md)
- [Arcane](stacks/arcane.md)

## Operations

- [Backup and restore](operations/backup-and-restore.md)
- [Updating](operations/updating.md)
- [Rollback](operations/rollback.md)
- [Troubleshooting](operations/troubleshooting.md)
- [Frequently asked questions](operations/faq.md)

## Security

- [Secrets](security/secrets.md)
- [Exposure matrix](security/exposure-matrix.md)

## Reference deployment

The complete deployment uses:

- an Unraid host for ingress, authentication, private applications, Nextcloud, media automation, and monitoring;
- a NAS for persistent storage, Plex, and Arcane;
- a domain managed by Cloudflare;
- a remotely managed Cloudflare Tunnel for inbound web traffic;
- a dedicated DDNS hostname, separate from the Tunnel hostnames;
- a VPN subscription and OpenVPN profile for qBittorrent.

The stacks are modular, but their dependencies still matter. In particular, the Unraid `edge` stack creates the shared Docker networks required by the other Unraid stacks.

## Safety notes

- Never commit populated `.env` files, passwords, tunnel tokens, VPN profiles, private keys, or `users.yml`.
- Use a dedicated DDNS name only for services that need the home public IP; never reuse the Tunnel apex or wildcard names.
- Confirm that remote NAS shares are mounted before starting containers that write to them.
- Back up configuration, secrets, databases, and application data before an update.
- Do not run `docker compose down -v` during normal maintenance. The `-v` option removes named volumes and can destroy persistent data.

## Documentation scope

These guides document the current repository configuration, initial deployment, routine operations, recovery planning, and security boundaries. They cannot verify environment-specific details such as your Cloudflare dashboard, firewall rules, NAS mount configuration, credentials, or backup destination. Validate those items on the real hosts before relying on the deployment.
