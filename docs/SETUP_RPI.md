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

The API and PWA share one origin. Keep `SERVER_MANAGER_HOST=127.0.0.1`; do not bind the API to `0.0.0.0` or forward port 8080 from the router. After enabling HTTPS certificates for the tailnet and restricting access with Tailscale ACLs, configure Serve as a private HTTPS reverse proxy:

```bash
sudo tailscale serve --bg --https=443 http://127.0.0.1:8080
sudo tailscale serve status
```

Open the displayed `https://<device>.<tailnet>.ts.net` address from an authorized device with Tailscale connected. Tailscale Serve is available only within the tailnet and terminates HTTPS for the local HTTP backend; do not configure Tailscale Funnel, which would make the service publicly reachable. Tailscale Serve access follows the tailnet's access controls. [Tailscale Serve documentation](https://tailscale.com/docs/features/tailscale-serve), [Serve CLI reference](https://tailscale.com/docs/reference/tailscale-cli/serve).

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

Generate a unique high-entropy token on the Pi and place it only in `/etc/server-manager/server-manager.env`:

```bash
openssl rand -hex 32
sudoedit /etc/server-manager/server-manager.env
sudo systemctl restart server-manager.service
```

Do not paste the token into source files, shell history, issue reports, or screenshots. Install the PWA from the HTTPS tailnet address on Android (browser menu, **Install app** / **Add to Home Screen**) or desktop (browser's install control). The PWA asks for the token at each new session and does not persist it.

For Docker management, add the user to the Docker group only if needed and accept that this is highly privileged. For systemd management, prefer exact sudoers lines for each allowed unit and operation.
