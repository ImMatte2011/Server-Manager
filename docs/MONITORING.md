# Monitoring

System resources are read through `psutil`.

Service resources are provider-specific:

- Docker Compose: Docker SDK container stats, matched through Compose labels.
- systemd: estimated from MainPID and child processes.

Memory accounting intentionally avoids false precision.

```text
total memory
used memory
available memory
monitored services memory
unattributed used memory
```

Unattributed memory includes the operating system, Docker daemon, unmanaged processes, shared memory and Linux cache effects.
