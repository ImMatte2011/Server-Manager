# API

The PWA is served at `/` from the same origin. Only the health check is intentionally unauthenticated; every administrative endpoint requires:

```text
Authorization: Bearer <SERVER_MANAGER_API_TOKEN>
```

Operation requests can include:

```text
X-Server-Manager-Source: CLI
```

Valid audit sources are:

- `CLI`
- `Web UI`
- `API`
- `scheduled job`

## Endpoints

```text
GET  /api/health

GET  /api/services
GET  /api/services/{service_id}
GET  /api/services/{service_id}/status
GET  /api/services/{service_id}/resources

POST /api/services/{service_id}/start
POST /api/services/{service_id}/stop
POST /api/services/{service_id}/restart

GET  /api/system/resources
GET  /api/resources/summary

GET    /api/schedules
POST   /api/schedules
DELETE /api/schedules/{schedule_id}

GET  /api/audit
POST /api/registry/reload
```

Administrative responses use `Cache-Control: no-store`. The PWA never caches `/api/` responses and sends the token only in the Authorization header, not in cookies or URLs. Browser CORS is not enabled.

Schedule creation body:

```json
{
  "service_id": "example",
  "operation": "start",
  "kind": "daily",
  "hour": 8,
  "minute": 0
}
```

Weekly schedules use `kind = "weekly"` and `weekdays`, for example `["mon", "fri"]`.

Errors are returned as structured JSON:

```json
{
  "error": {
    "code": "service_unavailable",
    "message": "Service 'example' is unavailable.",
    "details": {
      "reason": "Compose file does not exist: /srv/projects/example/docker-compose.yml"
    }
  }
}
```
