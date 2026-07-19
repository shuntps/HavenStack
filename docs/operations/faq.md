# Frequently asked questions

Short answers to the questions that come up most often, with links to the
pages that explain each topic in full. This page adds no new rules; the
linked pages remain authoritative.

## Why does HavenStack expose no ports on my router?

Inbound traffic enters through a Cloudflare Tunnel: the `cloudflared`
container opens an outbound connection to Cloudflare, so ports `80` and
`443` never need to be forwarded, and the web stacks publish no host ports
at all. See [Networking](../architecture/networking.md#public-web-request-flow)
and the [exposure matrix](../security/exposure-matrix.md).

## The hop from cloudflared to Traefik uses HTTP. Is that insecure?

Visitors always use HTTPS to Cloudflare, and the Cloudflare-to-`cloudflared`
tunnel is encrypted. Only the short hop inside the `edge_ingress` Docker
network uses HTTP, which keeps certificate management out of Traefik. See
[How an HTTPS request is handled](../architecture/overview.md#how-an-https-request-is-handled).

## Why do I have to create the wildcard DNS record myself?

Cloudflare creates DNS records automatically for exact hostname routes but
**not** for wildcard routes; without the manual proxied `CNAME`, the apex
works while every subdomain fails. See
[Create the wildcard DNS record](../getting-started/cloudflare-tunnel.md#create-the-wildcard-dns-record).

## Why are both the apex and wildcard Tunnel routes required?

`*.example.com` does not match `example.com`, and HavenStack serves the
Homepage at the apex. See
[Why both hostname routes are required](../getting-started/cloudflare-tunnel.md#why-both-hostname-routes-are-required).

## Why is `docker compose down -v` dangerous?

The `-v` option deletes named volumes, which for Nextcloud includes the
PostgreSQL database. Use `stop`/`start` for routine maintenance. See
[Storage](../architecture/storage.md#backup-consistency-and-safe-stopping).

## Why does Authelia not protect every route?

Authelia is a Traefik middleware, not a global gate: it applies only to
routers that include the `authelia@file` middleware. Homepage, the normal
Vaultwarden route, and Nextcloud intentionally use their own authentication.
See [Authentication boundaries](../security/exposure-matrix.md#authentication-boundaries-to-remember).

## Why must the edge stack start first?

It creates the shared Docker networks that the other Unraid stacks declare
as external; they fail to deploy if the networks do not exist. See
[Why the edge stack starts first](../architecture/overview.md#why-the-edge-stack-starts-first).

## Why do qBittorrent, Radarr, and Sonarr share one `/data` mount?

Seeing the same filesystem at the same path enables hardlinks and atomic
moves instead of slow copies between downloads and the library. See
[Storage](../architecture/storage.md#servarr).

## Why does Plex use host networking?

Plex relies on discovery and streaming listeners that are simplest to run in
the NAS network namespace; the trade-off is that every Plex listener becomes
a NAS host listener. See [NAS networking](../architecture/networking.md#nas-networking).

## Why do the Nextcloud images use the `latest` tag?

The five AIO component images are designed to operate as a compatible set,
so this repository does not pin them individually. Record image digests
before every update and treat a `pull` as a real version change. See
[Image version policy](../operations/updating.md#image-version-policy-in-this-repository).

## A container is healthy. Does that mean everything works?

No. A health check proves the process answers its own probe, not that
authentication, storage, VPN egress, or integrations work. Complete the
functional checks in each guide. See
[Reading a stack guide](../stacks/README.md#reading-a-stack-guide) and the
[first-run checklist](../getting-started/first-run-checklist.md).
