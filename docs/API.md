# API

All administrative endpoints require:

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

GET  /api/audit
POST /api/registry/reload
```

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
