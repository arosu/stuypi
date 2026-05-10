# Samba

Dockerized Samba using `ghcr.io/servercontainers/samba:latest`.

The container uses `network_mode: host` and binds native SMB on port `445`.
Avahi, WSDD2, and NetBIOS are disabled here because the native setup only used
direct SMB over port `445`.

Shares:

- `//stuypi/arosu` -> `/mnt/ssd/files/arosu`
- `//stuypi/iclotea` -> `/mnt/ssd/files/iclotea`

Credentials are stored as Samba NT hashes in ignored `samba/.env`, migrated from
the old native Samba password database.

Useful commands:

```sh
sudo docker compose up -d
sudo docker logs --tail=100 samba
sudo docker exec samba testparm -s
```
