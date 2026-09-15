# Architecture

Server Manager is an external orchestrator for services already present on a Raspberry Pi. Managed services do not import Server Manager libraries, do not share its database, and do not expose special APIs for it.

The first implementation is API-first:

```text
CLI / future Web UI / scheduled job
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
