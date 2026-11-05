# Raspberry Pi Setup

Recommended production layout:

```text
/opt/server-manager
/etc/server-manager/services.toml
/var/lib/server-manager/server-manager.db
```

Recommended service model:

- Python virtual environment;
- FastAPI served by uvicorn;
- native systemd unit;
- bind to `127.0.0.1`;
- access through Tailscale;
- Bearer token authentication.

Provided files:

```text
systemd/server-manager.service
systemd/server-manager.env.example
systemd/sudoers.example
scripts/install_rpi.sh
```

Install outline:

```bash
sudo scripts/install_rpi.sh
sudo nano /etc/server-manager/server-manager.env
sudo nano /etc/server-manager/services.toml
sudo systemctl enable --now server-manager.service
```

Server Manager should run as the dedicated `server-manager` Linux user, not as root. The application under `/opt` remains root-owned and read-only to the service. The environment file is `root:server-manager` with mode `0640`; it is readable by the service account's group but not by other local users. Runtime data remains writable under `/var/lib/server-manager`.

For Docker management, add the user to the Docker group only if needed and accept that this is highly privileged. For systemd management, prefer exact sudoers lines for each allowed unit and operation.
