# Scheduling

Server Manager supports persistent schedules for:

- `start`
- `stop`
- `restart`

Supported schedule kinds:

- `daily`
- `weekly`

Schedules are stored in SQLite and loaded into APScheduler when the API starts. APScheduler runs in the Server Manager process, so schedules run only while Server Manager is running. Missed-job recovery is intentionally left for a later Android-assisted workflow.

Example:

```json
{
  "service_id": "example",
  "operation": "stop",
  "kind": "weekly",
  "hour": 23,
  "minute": 30,
  "weekdays": ["mon", "fri"]
}
```

Scheduled operations are audited with source `scheduled job`.
