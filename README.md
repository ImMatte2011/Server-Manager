# Server Manager

Server Manager is an API-first Raspberry Pi service manager. It controls registered Docker Compose and systemd services from the outside, without requiring managed projects to import Server Manager code or expose custom APIs.

Implemented scope:

- resilient TOML service registry;
- Docker Compose and systemd providers;
- normalized service status and capabilities;
- protected FastAPI API;
- lightweight CLI client;
- system and per-service monitoring where available;
- persistent scheduling with APScheduler + SQLite;
- structured SQLite audit log;
- Raspberry Pi systemd deployment files.

It includes an installable Progressive Web App (PWA) served by the same API origin. On Android and desktop it provides service controls, host/service monitoring, schedules, and recent audit events.

## Local Development

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
cp config/services.example.toml config/services.toml
export SERVER_MANAGER_ENV=development
export SERVER_MANAGER_API_TOKEN="change-me-for-dev"
export SERVER_MANAGER_CONFIG="./config/services.toml"
uvicorn server_manager.api.main:app --host 127.0.0.1 --port 8080
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item config\services.example.toml config\services.toml
$env:SERVER_MANAGER_ENV = "development"
$env:SERVER_MANAGER_API_TOKEN = "change-me-for-dev"
$env:SERVER_MANAGER_CONFIG = ".\config\services.toml"
uvicorn server_manager.api.main:app --host 127.0.0.1 --port 8080
```

In production, `SERVER_MANAGER_API_TOKEN` is required. Missing authentication fails closed.

## PWA

On the Raspberry Pi, keep the API bound to `127.0.0.1` and expose it only through Tailscale Serve over HTTPS. Open the Raspberry Pi's tailnet HTTPS address on the phone or computer, sign in with the configured bearer token, then use the browser's **Install app** / **Add to Home Screen** action.

The PWA uses the API on its own origin. The token is held in memory only; it is not saved in browser storage and is cleared by locking the session, closing/reloading the page, or 15 minutes of inactivity. API responses are never cached by the service worker. Each authorized user still has full administrative API access; protect the token and limit tailnet access with Tailscale ACLs. See [PWA Security](docs/PWA_SECURITY.md).

## CLI

```bash
server-manager status
server-manager status example
server-manager start example
server-manager stop example
server-manager restart example
server-manager resources
server-manager schedules
server-manager schedule-add example start daily 08:00
server-manager schedule-delete <schedule-id>
```

Use:

```bash
export SERVER_MANAGER_URL="http://127.0.0.1:8080"
export SERVER_MANAGER_API_TOKEN="your-token"
```

## Raspberry Pi Layout

Recommended production layout:

```text
/opt/server-manager/        application + virtualenv
/etc/server-manager/        services.toml and environment
/var/lib/server-manager/    SQLite database and runtime data
```

Install files are provided in:

- `systemd/server-manager.service`
- `systemd/server-manager.env.example`
- `systemd/sudoers.example`
- `scripts/install_rpi.sh`

See [Raspberry Pi Setup](docs/SETUP_RPI.md) for the private HTTPS publication steps.

## Safety Model

HTTP input never becomes a system command. A request such as `POST /api/services/example/start` is resolved as:

```text
service_id
  -> registry
  -> validated service config
  -> provider operation
  -> fixed argv command
```

Never:

```text
HTTP input
  -> systemctl <input>
```

systemd units and Docker Compose paths are loaded from the registry. The API only accepts service IDs that pass validation and exist in the registry.

## Tests

```bash
node --check server_manager/web/assets/app.js
node --check server_manager/web/sw.js
python -m compileall server_manager tests
python -m pytest -q
```
