# wg-easy

Dockerized WireGuard Easy using `ghcr.io/wg-easy/wg-easy:15`.

Current settings:

- Endpoint: `stuypi.duckdns.org:51820`
- VPN CIDR: `10.138.60.0/24`
- Server VPN IP: `10.138.60.1`
- Web UI: `http://16.242.6.136:51821`

The container runs with `network_mode: host` so existing clients that use
`DNS = 10.138.60.1` continue to reach the Dockerized Pi-hole on the host.

Persisted state lives in ignored local directories:

- `data/`

Useful commands:

```sh
sudo docker compose up -d
sudo docker exec wg-easy wg show
sudo docker logs --tail=100 wg-easy
```
