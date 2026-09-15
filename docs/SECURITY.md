# Security

Server Manager is an administrative API. It must not be exposed directly to the public Internet.

Recommended access model:

- bind the API to `127.0.0.1`;
- expose it through Tailscale Serve or another controlled Tailscale-only route;
- keep application-level Bearer token authentication enabled;
- run Server Manager as a dedicated Linux user;
- grant only the minimum required Docker/systemd permissions.

## Command Execution

Server Manager does not expose arbitrary command execution.

Allowed operations are constrained to registered services:

- start;
- stop;
- restart;
- status;
- resources.

Docker Compose commands are built from the registered `compose_file`. systemd commands are built from the registered `unit`.

## sudoers

If systemd operations need sudo, use a narrow sudoers rule. The exact production rule depends on the final install path and unit list, but it should never allow arbitrary shell execution.

Example shape:

```text
server-manager ALL=(root) NOPASSWD: /usr/bin/systemctl start example.service
server-manager ALL=(root) NOPASSWD: /usr/bin/systemctl stop example.service
server-manager ALL=(root) NOPASSWD: /usr/bin/systemctl restart example.service
server-manager ALL=(root) NOPASSWD: /usr/bin/systemctl is-active example.service
server-manager ALL=(root) NOPASSWD: /usr/bin/systemctl show example.service --property=MainPID --value
```

This is intentionally repetitive. It is safer than allowing broad patterns.

## Docker Permission Warning

Membership in the `docker` group is effectively root-equivalent on Linux. If Server Manager needs Docker control, treat the Server Manager user as highly privileged.
