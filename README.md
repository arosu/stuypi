# stuypi-services

Self-hosted services running on Raspberry Pi `stuypi`
(`16.242.6.136`). The Pi boots from SD card; bulk and durable app data lives on
the external SSD mounted at `/mnt/ssd`.

```
/home/arosu/stuypi-services/   repo, compose files, small service scripts
/mnt/ssd/
  files/                       SMB shares, backed up to Backblaze
  photo-library/               Immich photo blobs, backed up to Backblaze
  immich-database/             Immich Postgres data
  media-library/{movies,tv-shows}
  kitchenowl/                  KitchenOwl SQLite DB, backups, uploads
  usenet/{incomplete,complete} SABnzbd workspace
```

Secrets live in `~/stuypi-services/.env` and are gitignored. Runtime state lives
in gitignored service directories such as `plex/config/`, `uptime-kuma/data/`,
`pihole/etc-pihole/`, `wg-easy/data/`, and `samba/.env`.

## Services

| Service | Port | Purpose | State |
|---|---:|---|---|
| Plex | `32400` | Media server | `plex/config/`, `/mnt/ssd/media-library/` |
| Immich | `2283` | Photo backup and albums | `/mnt/ssd/photo-library/`, `/mnt/ssd/immich-database/` |
| arr-stack | various | Sonarr/Radarr/Prowlarr/SABnzbd/Bazarr | `arr-stack/config/`, `/mnt/ssd/usenet/` |
| Home Assistant | `8123` | Home automation and dashboards | `home-assistant/config/` |
| Caddy | `80`, `443` | LAN/WireGuard HTTPS reverse proxy | `caddy/Caddyfile`, `caddy/data/` |
| Uptime Kuma | `3001` | Service monitoring and status page | `uptime-kuma/data/` |
| Beszel | `8090` | Host/container metrics | `beszel/beszel_*`, `beszel/stats.py` |
| Pi-hole | `53`, `8083` | DNS adblocker and LAN DNS overrides | `pihole/etc-pihole/` |
| wg-easy | `51820/udp`, `51821/tcp` | WireGuard VPN and admin UI | `wg-easy/data/` |
| Samba | `445` | Private SMB shares | `/mnt/ssd/files/{arosu,iclotea}`, `samba/.env` |
| KitchenOwl | `9926` | Shopping list and recipes | `/mnt/ssd/kitchenowl/` |
| Watchtower | internal | Scheduled image updates | Docker socket |

Deleted services: `homepage` and `speedtest-tracker`.

### arr-stack

| Container | Port | Role |
|---|---:|---|
| sabnzbd | `8181 -> 8080` | Usenet downloader |
| prowlarr | `9696` | Indexer manager |
| radarr | `7878` | Movie automation |
| sonarr | `8989` | TV automation |
| bazarr | `6767` | Subtitle automation |

The arr-stack apps share Docker DNS by container name (`http://radarr:7878`,
`http://sabnzbd:8080`, etc.). Inter-stack access generally uses
`http://16.242.6.136:PORT`.

Plex libraries point at:

```
/mnt/ssd/media-library/movies
/mnt/ssd/media-library/tv-shows
```

Radarr/Sonarr write to those exact paths and hardlink completed downloads from
`/mnt/ssd/usenet/complete`.

## Networking

Caddy reverse-proxies selected services under `*.alexandrurosu.com`.
Resolution is LAN/VPN-only through Pi-hole DNS overrides.

| URL | Backend |
|---|---|
| `https://watch.alexandrurosu.com` | Plex `localhost:32400` |
| `https://photos.alexandrurosu.com` | Immich `localhost:2283` |
| `https://status.alexandrurosu.com` | Uptime Kuma `localhost:3001` |
| `https://metrics.alexandrurosu.com` | Beszel `localhost:8090` |
| `https://pihole.alexandrurosu.com` | Pi-hole `localhost:8083/admin` |
| `https://home.alexandrurosu.com` | Home Assistant `localhost:8123` |
| `https://kitchen.alexandrurosu.com` | KitchenOwl `localhost:9926` |

Clients must use the Pi as DNS:

- LAN: router DHCP advertises `16.242.6.136`
- WireGuard: clients use `DNS = 10.138.60.1`

Pi-hole, wg-easy, Samba, Caddy, Plex, and Home Assistant run with host
networking where needed. Pi-hole is Dockerized, not native systemd. wg-easy owns
host `wg0` and preserves the old PiVPN server key/network:

```
VPN CIDR: 10.138.60.0/24
Server VPN IP: 10.138.60.1
Endpoint: stuypi.duckdns.org:51820
```

The public router should only forward WireGuard UDP `51820`. Do not expose
wg-easy's admin UI (`51821/tcp`) directly to the public internet.

## Monitoring

Uptime Kuma currently monitors:

- Immich
- Beszel
- Pi-hole web UI
- Backblaze Sync push monitor
- Plex
- Sonarr
- Radarr
- Prowlarr
- SABnzbd
- Bazarr
- KitchenOwl
- Home Assistant
- wg-easy
- Pi-hole DNS
- Samba

Home Assistant uses the Uptime Kuma integration for service status sensors and
has REST sensors for Immich and Beszel metrics. Backblaze Sync remains in Uptime
Kuma as a push monitor, but it is intentionally not part of the Home Assistant
service-status popup because push monitors can show as unavailable after HA
restarts until the next push.

Beszel metrics are exposed to Home Assistant by `beszel-stats` on `:9928`.
It authenticates to Beszel with:

```
BESZEL_USER
BESZEL_PASSWORD
BESZEL_SYSTEM
BESZEL_SYSTEM_ID
```

## Secrets

`~/stuypi-services/.env` should include at least:

| Variable | Used by | Recovery/source |
|---|---|---|
| `BESZEL_USER` | `beszel-stats` | Beszel account email |
| `BESZEL_PASSWORD` | `beszel-stats` | Beszel account password |
| `BESZEL_SYSTEM` | `beszel-stats` | Usually `stuypi` |
| `BESZEL_SYSTEM_ID` | `beszel-stats` | Beszel system record ID |
| `BESZEL_AGENT_TOKEN` | `beszel-agent` | Beszel UI -> Systems -> Add/refresh system |
| `KITCHENOWL_JWT_SECRET` | KitchenOwl app | Existing value keeps sessions valid; rotating logs everyone out |
| `KITCHENOWL_TOKEN` | `bin/kitchenowl-export-recipes.py` | KitchenOwl long-lived token; refresh in KitchenOwl if lost |
| `PLEX_TOKEN` | Radarr/Sonarr Plex Watchlist + Plex notifier | Plex `Preferences.xml` value `PlexOnlineToken="..."` |
| `RCLONE_DISCORD_WEBHOOK_URL` | Backblaze sync notifier | Discord webhook |
| `KUMA_PUSH_URL_BACKBLAZE` | Backblaze Sync push monitor | Uptime Kuma push monitor URL |
| `WATCHTOWER_NOTIFICATION_URL` | Watchtower update reports | Shoutrrr notification URL |
| `CLOUDFLARE_API_TOKEN` | Caddy DNS-01 cert renewal | Cloudflare token with `Zone:DNS:Edit` |

The Plex token can be recovered from:

```
plex/config/Library/Application Support/Plex Media Server/Preferences.xml
```

Look for `PlexOnlineToken="..."`.

Other secrets live inside gitignored app config/state:

| Secret | Location |
|---|---|
| Pi-hole admin password/hash and DB | `pihole/etc-pihole/` |
| wg-easy admin/user config and WireGuard keys | `wg-easy/data/` |
| Samba NT password hashes | `samba/.env` |
| Arr-stack app auth/API keys | `arr-stack/config/` |
| Caddy certificates/account keys | `caddy/data/`, `caddy/config/` |
| Uptime Kuma monitors/webhooks | `uptime-kuma/data/` |

## Routine Operations

Bring up a stack:

```sh
cd ~/stuypi-services/<service>
source ~/stuypi-services/.env
docker compose up -d
```

Update images manually:

```sh
cd ~/stuypi-services/<service>
docker compose pull
docker compose up -d
```

Watchtower also runs and updates images on its configured schedule.

Useful checks:

```sh
docker ps
docker logs --tail=100 <container>
docker exec wg-easy wg show
docker exec pihole pihole status
df -h /mnt/ssd
```

## Recovery

### SD Card Dies, SSD Survives

1. Flash Raspberry Pi OS 64-bit and restore hostname/networking for `stuypi`.
2. Install Docker and Compose.
3. Mount the SSD at `/mnt/ssd`.
4. Clone this repo to `/home/arosu/stuypi-services`.
5. Restore `.env`.
6. Start core services:

   ```sh
   source ~/stuypi-services/.env
   cd ~/stuypi-services/pihole && docker compose up -d
   cd ~/stuypi-services/wg-easy && docker compose up -d
   cd ~/stuypi-services/caddy && docker compose up -d --build
   cd ~/stuypi-services/uptime-kuma && docker compose up -d
   cd ~/stuypi-services/beszel && docker compose up -d
   ```

7. Start app/data services:

   ```sh
   cd ~/stuypi-services/immich && docker compose up -d
   cd ~/stuypi-services/plex && docker compose up -d
   cd ~/stuypi-services/kitchenowl && docker compose up -d
   cd ~/stuypi-services/samba && docker compose up -d
   cd ~/stuypi-services/home-assistant && docker compose up -d
   cd ~/stuypi-services/arr-stack && docker compose up -d
   cd ~/stuypi-services/watchtower && docker compose up -d
   ```

Most app state on the SD card is gitignored, so restore from backups or
reconfigure if those directories are gone. SSD-backed data survives.

### SSD Dies

1. Replace and mount the SSD at `/mnt/ssd`.
2. Recreate:

   ```sh
   mkdir -p /mnt/ssd/{files,photo-library,immich-database,media-library/{movies,tv-shows},kitchenowl,usenet/{incomplete,complete}}
   ```

3. Restore Backblaze-backed data:

   ```sh
   rclone copy backblaze:alex-photo-backups          /mnt/ssd/photo-library/library/admin
   rclone copy backblaze:ioana-photo-backups         /mnt/ssd/photo-library/library/iclotea
   rclone copy backblaze:alex-file-backups           /mnt/ssd/files/arosu
   rclone copy backblaze:ioana-file-backups          /mnt/ssd/files/iclotea
   rclone copy backblaze:rosu-recipes-backup/dumps   /mnt/ssd/kitchenowl/backups
   rclone copy backblaze:rosu-recipes-backup/uploads /mnt/ssd/kitchenowl/upload
   ```

Immich database, Plex media library, and most app config databases are not fully
recoverable from Backblaze unless separately backed up.

### Reconfiguring Arr-Stack

If `arr-stack/config/` is lost:

1. Set Forms auth/admin password in Sonarr, Radarr, Prowlarr, SABnzbd, Bazarr.
2. Configure SABnzbd Frugal servers and paths:
   - incomplete: `/data/usenet/incomplete`
   - complete: `/data/usenet/complete`
   - categories: `movies`, `tv`
3. Configure Prowlarr indexers and connect Radarr/Sonarr.
4. Configure Radarr/Sonarr:
   - SABnzbd download client at `sabnzbd:8080`
   - root folders `/data/media/movies`, `/data/media/tv-shows`
   - Plex Watchlist import using `PLEX_TOKEN`
   - Plex notifier using `PLEX_TOKEN`
5. Configure Bazarr providers and Sonarr/Radarr API keys.
6. Re-add Discord notifications.
7. Re-add or restore Uptime Kuma monitors if `uptime-kuma/data/` was lost.

## Current Verification Notes

As of this cleanup:

- `homepage` and `speedtest-tracker` are removed.
- Pi-hole, wg-easy, and Samba are Dockerized.
- Native Pi-hole, PiVPN, and Samba system packages/config were removed.
- `PLEX_TOKEN` in `.env` was verified against Plex `Preferences.xml`.
- Radarr/Sonarr Plex Watchlist import lists and Plex notifiers use the current
  `PLEX_TOKEN`.
- `KITCHENOWL_TOKEN` in `.env` was regenerated from the `stuypi` long-lived
  token row and verified against the recipe export endpoint.
- `beszel-stats` returns system/container data for Home Assistant.
- All active Uptime Kuma monitors report up.
- Compose files validate with the current `.env`.
- Docker containers for Pi-hole, wg-easy, Samba, KitchenOwl, Beszel, Plex, and
  the rest of the stack are running.
