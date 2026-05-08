# stuypi-services

Self-hosted services running on a Raspberry Pi (host: `16.242.6.136`, hostname: `stuypi`). The Pi boots from an SD card, with persistent data on an external SSD mounted at `/mnt/ssd` (ext4).

```
/home/arosu/stuypi-services/   ← this repo (docker-compose.yaml + minimal configs)
/mnt/ssd/                      ← all bulk + runtime data
  ├── files/                       (user file shares; backed up to Backblaze)
  ├── photo-library/               (Immich photo blobs; backed up to Backblaze)
  ├── immich-database/             (Immich Postgres data dir)
  ├── media-library/{movies,tv-shows}  (Plex content; rebuildable from arr-stack)
  ├── kitchenowl/                  (KitchenOwl SQLite DB; `backups/` and `upload/` subfolders synced to Backblaze under `rosu-recipes-backup/{dumps,uploads}/`)
  └── usenet/{incomplete,complete}     (SABnzbd workspace; ephemeral)
```

Secrets are kept in `~/stuypi-services/.env` (gitignored). Service-specific runtime state lives in each app's `config/` dir (also gitignored).

---

## Services overview

| Service | Port | Purpose | State location |
|---|---|---|---|
| **homepage** | `:3000` | Dashboard / landing page | `homepage/config/` (mostly committable) |
| **plex** | `:32400` | Media server | `plex/config/` (gitignored) |
| **immich** | `:2283` | Photo backup + albums | `/mnt/ssd/photo-library/`, `/mnt/ssd/immich-database/` |
| **arr-stack** | various (see below) | Automated movie/TV/subtitle pipeline | `arr-stack/config/` (gitignored) |
| **beszel** | `:8090` | Host metrics + alerting | `beszel/beszel_*_data/` (gitignored) |
| **uptime-kuma** | `:3001` | Service uptime monitor + status page | `uptime-kuma/data/kuma.db` (gitignored) |
| **speedtest-tracker** | `:8080` | Periodic ISP speed checks | `speedtest-tracker/config/` (gitignored) |
| **pi-hole** | `:53` (DNS), `:8083` (`/admin`) | Network-wide DNS adblocker + LAN-only DNS overrides | native install on host (systemd `pihole-FTL.service`); config at `/etc/pihole/` |
| **caddy** | `:80` (HTTP), Phase 2: `:443` (HTTPS) | Reverse proxy — clean subdomain URLs over LAN/WireGuard | `caddy/Caddyfile` (committable), `caddy/data/` (certs, gitignored once Phase 2 is on) |
| **kitchenowl** | `:9926` (web), `:9927` (stats sidecar) | Shared shopping list + recipe planning | `/mnt/ssd/kitchenowl/` (live SQLite DB at root; weekly gzipped JSON dumps in `backups/` and recipe images in `upload/` both synced to B2 bucket `rosu-recipes-backup`) |

### arr-stack components

| Container | Port (host:container) | Role |
|---|---|---|
| sabnzbd | 8181:8080 | Usenet download client (Frugal Usenet servers configured) |
| prowlarr | 9696 | Indexer aggregator (NZBgeek configured) |
| radarr | 7878 | Movie automation; Plex Watchlist import list; HD-1080p quality profile |
| sonarr | 8989 | TV automation; same import list + profile |
| bazarr | 6767 | Subtitle automation (OpenSubtitles.com + Podnapisi providers, English profile) |

All five auth via Forms login. All five send Discord webhook notifications (configured via API).

### Networking + paths

- The arr-stack apps share the `arr-stack_default` Docker network and resolve each other by container name (`http://radarr:7878` etc.).
- Inter-stack communication uses the host LAN IP `http://16.242.6.136:PORT`.
- Plex's libraries point at `/mnt/ssd/media-library/movies` and `/mnt/ssd/media-library/tv-shows`. Radarr/Sonarr write into those exact paths. **Don't rename them** — Plex will lose its library if you do.
- SABnzbd downloads to `/mnt/ssd/usenet/{incomplete,complete}/`; Radarr/Sonarr **hardlink** files from there into the media library (verified — same ext4 mount, `copyUsingHardlinks: true`).

### Reverse proxy + clean URLs

Caddy reverse-proxies a curated set of services onto subdomains under `*.alexandrurosu.com`. Resolution is LAN-only (Pi-hole serves DNS overrides; nothing is exposed publicly).

| URL | Backend |
|---|---|
| `stuypi.alexandrurosu.com` | homepage `:3000` |
| `watch.alexandrurosu.com` | plex `:32400` |
| `photos.alexandrurosu.com` | immich `:2283` |
| `status.alexandrurosu.com` | uptime-kuma `:3001/status/stuypi` (auto-redirects from `/`) |
| `metrics.alexandrurosu.com` | beszel `:8090` |
| `speedtest.alexandrurosu.com` | speedtest-tracker `:8080` |
| `pihole.alexandrurosu.com` | pi-hole `:8083/admin` (auto-redirects from `/`) |
| `home.alexandrurosu.com` | home-assistant `:8123` |
| `kitchen.alexandrurosu.com` | kitchenowl `:9926` |

The arr-stack apps (sonarr/radarr/prowlarr/sabnzbd/bazarr) are intentionally **not** behind Caddy — kept on direct ports as a privacy/attack-surface decision.

**Required for client devices to reach these URLs:** they must use the Pi (`16.242.6.136`) as their DNS server. Configured via:
- LAN: router DHCP advertises Pi as primary DNS (already done for Pi-hole ad-blocking).
- WireGuard: `[Interface]` block in client config has `DNS = 16.242.6.136`.

Without that, `*.alexandrurosu.com` won't resolve on that device.

**Pi-hole port note.** Pi-hole's web admin used to live on `:80/:443` but was moved to `:8083` so Caddy could take over `:80`. DNS (port 53) is unchanged. The change is in `/etc/pihole/pihole.toml` under `[webserver].port` (also requires `pihole-FTL.service` restart).

#### Phase 2 — HTTPS via Cloudflare DNS-01 (done)

Every URL is now `https://...` with valid Let's Encrypt certs. Caddy auto-redirects HTTP → HTTPS. Renewal is automatic — Caddy reissues at ~60 days for each per-subdomain cert (90-day Let's Encrypt expiry).

Reference for re-doing this from scratch (e.g. after Scenario A recovery):

**Prerequisites:**

1. **Domain transfer to Cloudflare must be complete** (`alexandrurosu.com` showing in your Cloudflare dashboard with NS records pointing at Cloudflare's nameservers).
2. **Cloudflare API token** with the minimum scope to manage DNS records on this zone:
   - Cloudflare dashboard → My Profile → API Tokens → Create Token → "Edit zone DNS" template.
   - Permissions: `Zone:DNS:Edit`. Zone resources: `Include → Specific zone → alexandrurosu.com`.
   - Copy the token (Cloudflare only shows it once).

**Steps when ready:**

1. **Add the token to `.env`** (gitignored):
   ```sh
   export CLOUDFLARE_API_TOKEN="<token>"
   ```
   Also add the same line (with empty value) to `.env.example`.

2. **Rebuild Caddy with the Cloudflare DNS plugin** (the stock `caddy:2-alpine` image doesn't include it). Replace `caddy/docker-compose.yaml`'s `image:` with a `build:` block, and add a `caddy/Dockerfile`:
   ```dockerfile
   FROM caddy:2-builder AS builder
   RUN xcaddy build --with github.com/caddy-dns/cloudflare
   FROM caddy:2-alpine
   COPY --from=builder /usr/bin/caddy /usr/bin/caddy
   ```
   And in `caddy/docker-compose.yaml`:
   ```yaml
   services:
     caddy:
       build: .
       environment:
         CF_API_TOKEN: ${CLOUDFLARE_API_TOKEN}
       # rest unchanged
   ```

3. **Update `caddy/Caddyfile`** — drop the `auto_https off`, drop the `:80` from each site block, add a global `tls` block that uses Cloudflare DNS:
   ```caddy
   {
       email <your-email-for-letsencrypt>
   }

   (cf_tls) {
       tls {
           dns cloudflare {env.CF_API_TOKEN}
       }
   }

   stuypi.alexandrurosu.com {
       import cf_tls
       reverse_proxy localhost:3000
   }
   # …same pattern for the other 6 subdomains
   ```

4. **Bring up the rebuilt Caddy:**
   ```sh
   cd ~/stuypi-services/caddy
   source ~/stuypi-services/.env
   docker compose up -d --build
   ```
   Caddy will request a wildcard cert (`*.alexandrurosu.com`) — Let's Encrypt fires off a DNS challenge → Caddy uses the API token to write/delete a TXT record under `alexandrurosu.com` → cert issued in ~30 seconds.

5. **Update `caddy/.gitignore` (or root `.gitignore`)** to skip `caddy/data/` and `caddy/config/` since they'll now contain certificates and account keys.

6. **Update homepage `services.yaml`** — change all `http://*.alexandrurosu.com` hrefs to `https://`. Update `widget.url` for Pi-hole too if needed.

7. **Update Beszel `APP_URL`** → `https://metrics.alexandrurosu.com`.

8. **Plex specifically** — once HTTPS is live, add `https://watch.alexandrurosu.com` to Plex → Settings → Network → "Custom server access URLs" so the Plex apps treat it as canonical.

**Renewal is automatic.** Caddy stores the cert in `caddy/data/`; Let's Encrypt certs expire every 90 days, Caddy re-issues at ~60 days with no intervention.

### Secrets in `.env`

`~/stuypi-services/.env` (gitignored, sourced by Docker before each `docker compose up`) holds:

| Variable | Used by | Origin |
|---|---|---|
| `IMMICH_API_KEY` | homepage widget | Immich → Account Settings → API Keys |
| `BESZEL_PASSWORD` | homepage widget | Beszel admin login password |
| `PIHOLE_PASSWORD` | homepage widget | Pi-hole admin password |
| `PLEX_TOKEN` | homepage widget + Radarr/Sonarr Plex Watchlist + Plex notifier | Plex → Settings → Account → "X-Plex-Token" |
| `SPEEDTEST_TRACKER_*` | homepage widget | Speedtest Tracker → Settings → API |
| `SONARR_API_KEY`, `RADARR_API_KEY`, `PROWLARR_API_KEY`, `SABNZBD_API_KEY`, `BAZARR_API_KEY` | homepage widgets | each app → Settings → General/Auth |
| `BESZEL_AGENT_TOKEN` | beszel agent auth to hub | Beszel UI → Systems → Add System (or rotate via the existing system's settings) |
| `KITCHENOWL_JWT_SECRET` | kitchenowl backend — signs JWTs | random 64-hex (`openssl rand -hex 32`); rotating logs everyone out |
| `KITCHENOWL_TOKEN` | `kitchenowl-stats` sidecar / homepage widget | KitchenOwl → Settings → Long-Lived Tokens (or `POST /api/auth` with username/password) |
| `RCLONE_DISCORD_WEBHOOK_URL` | `bin/rclone_discord.py` (Backblaze sync notifier) | Discord channel → Edit → Integrations → Webhooks |
| `KUMA_PUSH_URL_BACKBLAZE` | same script, for the "Backblaze Sync" push monitor | Uptime Kuma → edit "Backblaze Sync" monitor → copy push URL |
| `CLOUDFLARE_API_TOKEN` | Caddy (Phase 2 only) — DNS-01 cert issuance | Cloudflare dashboard → My Profile → API Tokens → "Edit zone DNS" |

Plus secrets that live **only** inside each app's gitignored config dir (not in `.env`):

| Secret | Lives in |
|---|---|
| Frugal Usenet username/password (3 servers) | `arr-stack/config/sabnzbd/sabnzbd.ini` |
| OpenSubtitles.com username/password | `arr-stack/config/bazarr/config/config.yaml` |
| NZBgeek API key | `arr-stack/config/prowlarr/prowlarr.db` |
| Discord webhook URL (used by all 5 arr-stack apps + Uptime Kuma) | each app's DB/INI |
| Forms-login passwords for each *arr/SAB/Bazarr | each app's DB |

If you lose a config dir, you lose all of these. Either keep the original creds in a password manager or accept regenerating them from each provider's portal.

---

## Recovery scenarios

### Scenario A: SD card dies (boot disk gone, SSD survives)

This is the most common Pi failure mode. SSD data including all media, photos, and Immich DB is intact. You only need to rebuild the OS + reattach the SSD + re-run `docker compose up` for each service. State for **homepage, plex, immich, beszel, uptime-kuma, speedtest-tracker, arr-stack apps** is gone (it was on the SD), but `/mnt/ssd/...` is fine.

**Steps:**

1. **Flash a fresh SD card** with Raspberry Pi OS (Lite or Desktop, 64-bit). Match the previous version if possible.
2. **Boot, set hostname** to `stuypi`, set static IP / DHCP reservation to `16.242.6.136` (your router probably already does this).
3. **Install Docker + compose:**
   ```sh
   curl -sSL https://get.docker.com | sh
   sudo usermod -aG docker arosu
   ```
4. **Mount the SSD.** `lsblk` to find the device (probably `/dev/sda1`). Add to `/etc/fstab`:
   ```
   /dev/sda1  /mnt/ssd  ext4  defaults,noatime  0  2
   ```
   Then `sudo mkdir -p /mnt/ssd && sudo mount -a`.
5. **Clone this repo:**
   ```sh
   cd ~ && git clone <your-git-remote>/stuypi-services.git
   ```
6. **Restore `.env`** from your password manager / off-site backup. This file is the single biggest blocker — without it, every homepage widget breaks and Radarr/Sonarr lose their Plex Watchlist link.
7. **Bring up infrastructure first:**
   ```sh
   source ~/stuypi-services/.env
   cd ~/stuypi-services/uptime-kuma && docker compose up -d
   cd ~/stuypi-services/beszel && docker compose up -d
   cd ~/stuypi-services/speedtest-tracker && docker compose up -d
   cd ~/stuypi-services/homepage && docker compose up -d
   ```
8. **Bring up Immich:** `cd ~/stuypi-services/immich && docker compose up -d`. Postgres data at `/mnt/ssd/immich-database/` is intact, so albums and metadata return as-is. Photos at `/mnt/ssd/photo-library/` likewise.
9. **Bring up Plex:** `cd ~/stuypi-services/plex && docker compose up -d`. Plex will need to re-scan and re-claim. Sign in with your Plex account; libraries pointing at `/mnt/ssd/media-library/{movies,tv-shows}` will repopulate from the on-disk files. Watch progress and metadata is preserved if your Plex account had server sync enabled (default).
10. **Bring up arr-stack:** `cd ~/stuypi-services/arr-stack && docker compose up -d`. **All five apps will start fresh with no config.** See [Reconfiguring arr-stack from scratch](#reconfiguring-arr-stack-from-scratch) below — this is the longest part of the recovery (15–30 minutes).
10b. **Bring up KitchenOwl:** `cd ~/stuypi-services/kitchenowl && docker compose up -d`. Data dir at `/mnt/ssd/kitchenowl/` is intact, so accounts, recipes, and shopping lists return as-is. Both the main app and the `kitchenowl-stats` sidecar require `KITCHENOWL_JWT_SECRET` and `KITCHENOWL_TOKEN` in `.env` — if those values changed, all sessions invalidate and the homepage widget breaks until refreshed.
11. **Reconfigure Uptime Kuma:** create user, re-add the 13 monitors and 1 status page (5 min via UI; faster via DB SQL if you keep a snapshot).
12. **Reconfigure Beszel:** add the `stuypi` host as a system, install agent. Copy the new `BESZEL_AGENT_TOKEN` into `.env`.
13. **Install Pi-hole.** Run the standard installer (`curl -sSL https://install.pi-hole.net | bash`). Once installed, **move the web admin off `:80`** so Caddy can take it: edit `/etc/pihole/pihole.toml`, find `[webserver].port`, change to `port = "8083o,[::]:8083o"`, then `sudo systemctl restart pihole-FTL`. Set Pi-hole admin password (push to `PIHOLE_PASSWORD` in `.env`).
14. **Add Pi-hole local DNS overrides** for the 9 reverse-proxied subdomains. In `/etc/pihole/pihole.toml` find `[dns].hosts = []` and replace with:
    ```toml
    hosts = ["16.242.6.136 stuypi.alexandrurosu.com", "16.242.6.136 watch.alexandrurosu.com", "16.242.6.136 photos.alexandrurosu.com", "16.242.6.136 status.alexandrurosu.com", "16.242.6.136 metrics.alexandrurosu.com", "16.242.6.136 speedtest.alexandrurosu.com", "16.242.6.136 pihole.alexandrurosu.com", "16.242.6.136 home.alexandrurosu.com", "16.242.6.136 kitchen.alexandrurosu.com"]
    ```
    Then `sudo systemctl restart pihole-FTL`.
15. **Bring up Caddy:** `cd ~/stuypi-services/caddy && docker compose up -d`. Caddyfile is committed so this Just Works (Phase 1 / HTTP-only). For Phase 2 / HTTPS, also restore `CLOUDFLARE_API_TOKEN` to `.env`, re-do the Phase 2 build steps from the section above.
16. **Verify:** `curl -sI -H "Host: stuypi.alexandrurosu.com" http://localhost/` should return 200. From a client on LAN/WG, `http://stuypi.alexandrurosu.com` should load homepage.

**Total recovery time:** ~1–2 hours, mostly wall-clock time waiting for image pulls and Plex's library scan.

### Scenario B: SSD dies (boot disk survives, data gone)

Worst case — Plex content, photos, Immich database, and all service `config/` dirs are gone. The Pi still boots; Docker still has cached images.

**Photos and files are safe** if Backblaze sync was running (`bin/backblaze-rclone-sync.sh`):
- `alex-photo-backups`, `ioana-photo-backups` → restore to `/mnt/ssd/photo-library/library/{admin,iclotea}/`
- `alex-file-backups`, `ioana-file-backups` → restore to `/mnt/ssd/files/{arosu,iclotea}/`

**Steps:**

1. **Replace the SSD.** Format ext4, mount at `/mnt/ssd`.
2. **Recreate top-level dirs:** `mkdir -p /mnt/ssd/{files,photo-library,immich-database,media-library/{movies,tv-shows},kitchenowl,usenet/{incomplete,complete}}`. Match ownership (`arosu:arosu`).
3. **Restore from Backblaze** for files, photos, and recipe backups:
   ```sh
   rclone copy backblaze:alex-photo-backups   /mnt/ssd/photo-library/library/admin
   rclone copy backblaze:ioana-photo-backups  /mnt/ssd/photo-library/library/iclotea
   rclone copy backblaze:alex-file-backups    /mnt/ssd/files/arosu
   rclone copy backblaze:ioana-file-backups          /mnt/ssd/files/iclotea
   rclone copy backblaze:rosu-recipes-backup/dumps   /mnt/ssd/kitchenowl/backups
   rclone copy backblaze:rosu-recipes-backup/uploads /mnt/ssd/kitchenowl/upload
   ```
4. **Immich database is NOT in Backblaze.** Albums, metadata, and machine-learning indexes are gone. Photos are intact, but Immich will treat them as fresh imports. After Immich is up, point it at `/mnt/ssd/photo-library/` as an external library and let it re-index — slow on a Pi (could take 8–24h) but everything comes back, just unsorted.
5. **Plex media library is NOT in Backblaze.** Movies/shows must be re-downloaded via Radarr/Sonarr. Both apps remember everything they've ever grabbed (in the gitignored DB which is *also* gone) — so you're starting over.
6. **KitchenOwl SQLite DB is NOT in Backblaze** — only the gzipped recipe-export dumps and `upload/` images are. Shopping lists, accounts, expense splits, and household settings are gone. After bringing KitchenOwl up against an empty data dir, sign up again (first user becomes admin), generate a new `KITCHENOWL_TOKEN` for the homepage widget, then re-import recipes by POSTing the latest dump to `/api/household/1/import` (the dump matches `ImportSchema` shape directly). Recipe images come back automatically once `/mnt/ssd/kitchenowl/upload/` is restored. See `bin/kitchenowl-export-recipes.py` for token + endpoint reference.
7. **Bring services up** in the same order as Scenario A. Reconfigure arr-stack as below. Re-add everything to Plex Watchlist that you want back; Radarr/Sonarr will re-grab.

**Total recovery time:** Backblaze restore + days of Plex media re-downloading.

### Scenario C: Total Pi loss (theft, fire, both disks gone)

Same as Scenario B + Scenario A combined. Recovery procedure is the SD-card-replacement steps from Scenario A, then the SSD-restore steps from Scenario B. You need three things off-site or in a password manager to recover at all:

- **The git remote URL** (so you can clone this repo)
- **The `.env` file contents** (passwords, API keys — none of it is in git)
- **Backblaze B2 account credentials** (for photos and user files)

Without those three, recovery isn't possible — content can be re-downloaded, but personal photos can't.

---

## Reconfiguring arr-stack from scratch

After a fresh `docker compose up`, all five apps boot with empty config. Recovery checklist (you'll do most of this once via the UI, much like the original setup):

1. **Set Forms auth + admin password** in each of Sonarr/Radarr/Prowlarr/SABnzbd/Bazarr (Settings → General/Auth or first-run wizard).
2. **SABnzbd:** add 3 Frugal servers (`news.frugalusenet.com`, `eunews.frugalusenet.com`, `bonus.frugalusenet.com`, port 563 SSL, username `redolphin`, password from manager). Set `complete_dir = /data/usenet/complete`, `download_dir = /data/usenet/incomplete`. Add `movies` and `tv` categories pointing at `movies`/`tv`. Set `host_whitelist = sabnzbd, radarr, sonarr, prowlarr, localhost` and `local_ranges = 16.242.6.0/24, 127.0.0.0/8, 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16`.
3. **Prowlarr:** add NZBgeek (Newznab type, URL `https://api.nzbgeek.info`, API key from NZBgeek profile). Add Radarr (`http://radarr:7878`) and Sonarr (`http://sonarr:8989`) under Settings → Apps with their respective API keys.
4. **Radarr + Sonarr:**
   - Add SABnzbd as download client (`host: sabnzbd`, `port: 8080`, SAB API key, category `movies`/`tv`).
   - Set root folder: `/data/media/movies` (Radarr) / `/data/media/tv-shows` (Sonarr).
   - Quality profile: `HD-1080p` only (disable Remux + BR-DISK; set `min size: 5 MB/min` for WEBDL/WEBRip/HDTV-1080p, `10 MB/min` for Bluray-1080p).
   - Add Plex Watchlist import list (`PlexImport`, accessToken = `PLEX_TOKEN` from `.env`, `qualityProfileId: 4`, `searchOnAdd: true`).
   - Add Plex notifier (host `16.242.6.136`, port `32400`, authToken = `PLEX_TOKEN`, `updateLibrary: true`).
   - Add Discord notifier (`webHookUrl` = your Discord webhook).
5. **Bazarr:**
   - Edit `config/bazarr/config/config.yaml`: set `general.use_radarr=true`, `general.use_sonarr=true`, `radarr.{ip,port,apikey} = (radarr, 7878, ...)`, same for sonarr. Set `general.movie_default_enabled=true`, `general.movie_default_profile=1`, same for series. Add to `general.enabled_providers: [opensubtitlescom, podnapisi]`. Set `opensubtitlescom.{username,password}`.
   - Insert language profile into `config/bazarr/db/bazarr.db` (English, code `en`). Or use the UI: Languages → enable English → create "English" profile.
   - Apply profile to existing movies/series via API or UI.
6. **Wire Discord** into all five apps (same webhook URL).
7. **Re-add Uptime Kuma monitors** for each: `:8989/ping`, `:7878/ping`, `:9696/ping`, `:8181/`, `:6767/`.

The Plex Watchlist import list will then start re-grabbing whatever's still on your watchlist.

### Things you'll lose that aren't recoverable

- **Blocklist** in Radarr/Sonarr — every "junk release" you ever marked failed is gone. Radarr/Sonarr might re-grab the same fake release that fooled you before. Mitigation: aggressive min-size floors (already configured) prevent most junk.
- **Plex watch history** — unless your Plex account had cloud sync enabled (default), play state and "continue watching" is gone.
- **Bazarr download history** — purely cosmetic.

---

## Day-to-day operations

### Updating images

All compose files use `:latest`. To upgrade a stack:
```sh
cd ~/stuypi-services/arr-stack
docker compose pull
docker compose up -d
```

### Restarting after edits

```sh
cd ~/stuypi-services/<service>
source ~/stuypi-services/.env   # only needed for stacks that interpolate env vars (homepage)
docker compose up -d
```

### Tail logs

```sh
docker logs -f sabnzbd      # or any container_name
```

### Check disk space

```sh
df -h /mnt/ssd
```
SSD is currently the only meaningful storage; if it goes above ~85% full, downloads start failing imports.
