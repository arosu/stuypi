# Pi-hole

Dockerized Pi-hole using the official `pihole/pihole:latest` image.

The container runs with `network_mode: host` so it can replace the previous
native install without changing LAN or WireGuard DNS behavior:

- DNS: `:53/tcp` and `:53/udp`
- Web UI: `:8083`
- NTP, if enabled in Pi-hole: `:123/udp`

Persisted state lives in ignored local directories:

- `etc-pihole/`
- `etc-dnsmasq.d/`
- `etc-pivpn/`

`etc-pivpn/hosts.wireguard` is mounted for the migrated PiVPN dnsmasq snippet:

```conf
addn-hosts=/etc/pivpn/hosts.wireguard
```

Useful commands:

```sh
sudo docker compose up -d
sudo docker exec pihole pihole status
sudo docker logs --tail=100 pihole
```
