# Configuration

Infrastructure settings come from environment variables.

```text
SERVER_MANAGER_HOST
SERVER_MANAGER_PORT
SERVER_MANAGER_API_TOKEN
SERVER_MANAGER_CONFIG
SERVER_MANAGER_DB
SERVER_MANAGER_ACTOR
SERVER_MANAGER_ENV
SERVER_MANAGER_LOG_LEVEL
SERVER_MANAGER_DISK_PATH
SERVER_MANAGER_SYSTEMCTL_SUDO
```

Services are declared in TOML:

```toml
schema_version = 1

[services.photos]
name = "Photos"
type = "docker_compose"
enabled = true
project_dir = "/srv/projects/photos"
compose_file = "/srv/projects/photos/docker-compose.yml"
compose_project_name = "photos"

[services.backup]
name = "Backup"
type = "systemd"
enabled = true
unit = "backup.service"
```

Missing files do not invalidate the full registry. They make only that service unavailable.

`compose_project_name` is optional but recommended when deterministic Docker container matching matters.

In production, `SERVER_MANAGER_API_TOKEN` must be configured. In development or test environments, the API can run without a token for local work.
