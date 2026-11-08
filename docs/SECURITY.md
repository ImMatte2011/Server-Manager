# Security

Server Manager is an administrative API. It must not be exposed directly to the public Internet.

Recommended access model:

- bind the API to `127.0.0.1`;
- expose it through Tailscale Serve or another controlled Tailscale-only route;
- keep application-level Bearer token authentication enabled;
- run Server Manager as a dedicated Linux user;
- grant only the minimum required Docker/systemd permissions.

The PWA is served from the API's own origin. Keep it behind HTTPS Tailscale Serve and tailnet ACLs; do not use Tailscale Funnel or expose port 8080 to the Internet. The UI keeps the bearer token in memory only, while the API remains the authorization boundary. Read [PWA Security](PWA_SECURITY.md) for session and browser details.

## Command Execution

Server Manager does not expose arbitrary command execution.

Allowed operations are constrained to registered services:

- start;
- stop;
- restart;
- status;
- resources.

Docker Compose commands are built from the registered `compose_file`. systemd commands are built from the registered `unit`.

In production, authentication fails closed when `SERVER_MANAGER_API_TOKEN` is missing or too short. Development/test environments may run without a token to simplify local work.

Generate a unique high-entropy production token (for example, 32 random bytes encoded as hex), keep it in `/etc/server-manager/server-manager.env`, and rotate it if a device is lost or suspected compromised. Every bearer token currently has the same full administrative permissions.

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

## Logs

Application logs use Python logging and are suitable for journald when running under systemd. Audit events are stored separately in SQLite and should not contain tokens or environment secrets.
