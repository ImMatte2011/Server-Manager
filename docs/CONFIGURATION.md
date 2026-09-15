# Configuration

Infrastructure settings come from environment variables.

```text
SERVER_MANAGER_HOST
SERVER_MANAGER_PORT
SERVER_MANAGER_API_TOKEN
SERVER_MANAGER_CONFIG
SERVER_MANAGER_DB
SERVER_MANAGER_ACTOR
SERVER_MANAGER_SYSTEMCTL_SUDO
```

Services are declared in TOML:

```toml
[services.photos]
name = "Photos"
type = "docker_compose"
enabled = true
project_dir = "/srv/projects/photos"
compose_file = "/srv/projects/photos/docker-compose.yml"

[services.backup]
name = "Backup"
type = "systemd"
enabled = true
unit = "backup.service"
```

Missing files do not invalidate the full registry. They make only that service unavailable.
