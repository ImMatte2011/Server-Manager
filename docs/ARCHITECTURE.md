# Architecture

Server Manager is an external orchestrator for services already present on a Raspberry Pi. Managed services do not import Server Manager libraries, do not share its database, and do not expose special APIs for it.

The implementation is API-first. CLI and the same-origin PWA call the same protected API:

```text
CLI / same-origin PWA / scheduled job
  -> FastAPI
  -> ServiceController
  -> ServiceRegistry
  -> Provider
  -> Docker Compose or systemd
```

## Registry

The registry is a TOML file. It is the only place where Docker Compose files and systemd units are declared.

The registry loader separates:

- syntactic validity;
- operational availability.

A service with a missing Compose file can still be loaded as valid but unavailable. This prevents one bad path from breaking the entire registry.

The registry supports `schema_version = 1`. Unknown schema versions invalidate the registry instead of guessing.

## Provider Model

Providers implement:

```text
start()
stop()
restart()
status()
resources()
```

Each service also exposes capabilities:

```text
start
stop
restart
status
resources
```

The API checks capabilities before dispatching an operation.

After start, stop and restart, providers read the real service status where possible and return that state in the operation result.

## Monitoring

System monitoring uses `psutil` for CPU, RAM, swap, disk, boot time and uptime. Docker Compose resources are matched through Compose labels using the configured or derived project name plus registry paths. systemd resources are estimated from MainPID and children.

The memory summary distinguishes monitored service memory from unattributed used memory. Unattributed memory is not described as free memory.

## Scheduling

Scheduling uses APScheduler in-process and SQLite persistence through Server Manager's database. Schedules currently support daily and weekly start, stop and restart operations. Missed-job recovery is intentionally not implemented yet.

## systemd Safety Rule

The systemd flow is:

```text
service_id
  -> registry
  -> unit already validated
  -> operation allowed by capabilities
  -> fixed systemctl argv
```

The forbidden flow is:

```text
HTTP input
  -> systemctl <input>
```

The API never accepts unit names or shell commands for start, stop or restart.

## PWA

FastAPI serves the installable PWA and `/api` from the same origin. Browser requests use the relative API paths, same-origin fetch mode, and a bearer token held only in page memory. A restrictive CSP and a service worker that caches only static shell files reduce exposure; administrative API responses are `no-store`. In deployment, Tailscale Serve provides HTTPS to authorized tailnet devices while FastAPI remains bound to loopback. See [PWA Security](PWA_SECURITY.md).
