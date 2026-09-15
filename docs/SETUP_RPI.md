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

The final systemd unit and sudoers file should be generated only after the target Raspberry Pi paths and managed units are confirmed.
