# Server Manager

Server Manager is an API-first Raspberry Pi service manager. It controls registered services from the outside, without requiring managed projects to import Server Manager code or expose custom APIs.

This first implementation covers the foundation through Phase 8:

- resilient service registry;
- Docker Compose and systemd provider architecture;
- normalized service status;
- capabilities per service;
- protected FastAPI endpoints;
- lightweight CLI client;
- system resource monitoring;
- SQLite audit log.

It intentionally does not include a frontend yet.

## Run Locally

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
cp config/services.example.toml config/services.toml
export SERVER_MANAGER_API_TOKEN="change-me"
export SERVER_MANAGER_CONFIG="./config/services.toml"
uvicorn server_manager.api.main:app --host 127.0.0.1 --port 8080
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item config\services.example.toml config\services.toml
$env:SERVER_MANAGER_API_TOKEN = "change-me"
$env:SERVER_MANAGER_CONFIG = ".\config\services.toml"
uvicorn server_manager.api.main:app --host 127.0.0.1 --port 8080
```

## CLI

```bash
server-manager status
server-manager status example
server-manager start example
server-manager stop example
server-manager restart example
server-manager resources
```

Use:

```bash
export SERVER_MANAGER_URL="http://127.0.0.1:8080"
export SERVER_MANAGER_API_TOKEN="change-me"
```

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

systemd units and Docker Compose paths are loaded from the registry. The API only accepts service IDs.
