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

Server Manager should run as the dedicated `server-manager` Linux user, not as root.

For Docker management, add the user to the Docker group only if needed and accept that this is highly privileged. For systemd management, prefer exact sudoers lines for each allowed unit and operation.
