from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASE_URL = "http://127.0.0.1:8080"
TOKEN = "smoke-token"


def request(method: str, path: str, token: str | None = TOKEN, source: str | None = None):
    headers = {"Accept": "application/json"}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    if source:
        headers["X-Server-Manager-Source"] = source
    req = urllib.request.Request(BASE_URL + path, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            payload = json.loads(body) if body else None
        except json.JSONDecodeError:
            payload = body
        return exc.code, payload


def expect(name: str, condition: bool, details):
    print(f"{name}: {'OK' if condition else 'FAIL'}")
    if not condition:
        print(json.dumps(details, indent=2, sort_keys=True), file=sys.stderr)
        raise SystemExit(1)


def main() -> int:
    status, payload = request("GET", "/api/health", token=None)
    expect("health", status == 200 and payload["status"] == "ok", payload)

    status, payload = request("GET", "/api/services", token=None)
    expect("missing auth rejected", status == 401, payload)

    status, payload = request("GET", "/api/services", token="wrong")
    expect("wrong token rejected", status == 401, payload)

    status, payload = request("GET", "/api/services?authorization=Bearer%20smoke-token", token=None)
    expect("query token bypass rejected", status == 401, payload)

    status, payload = request("GET", "/api/services")
    expect("correct token accepted", status == 200 and "services" in payload, payload)

    status, payload = request("POST", "/api/services/missing/start", source="CLI")
    expect("unknown service rejected", status == 404 and payload["error"]["code"] == "service_not_found", payload)

    status, payload = request("POST", "/api/services/..%2F..%2Fsystem/start", source="CLI")
    expect("path traversal rejected", status in {404, 405}, payload)

    status, payload = request("POST", "/api/services/smoke_systemd_disabled/start", source="CLI")
    expect("disabled systemd not started", status == 409 and payload["error"]["code"] == "service_unavailable", payload)

    status, payload = request("GET", "/api/services/smoke_compose/status")
    expect("compose status structured", status in {200, 502}, payload)
    expect("compose status no traceback", "Traceback" not in str(payload), payload)
    expect("compose status hides local docker details", "docker_engine" not in str(payload), payload)

    status, payload = request("POST", "/api/services/smoke_compose/start", source="CLI")
    expect("compose provider error structured", status == 502, payload)
    expect("compose provider error sanitized", "docker_engine" not in str(payload), payload)
    expect("compose provider error no traceback", "Traceback" not in str(payload), payload)

    status, payload = request("GET", "/api/services/smoke_systemd_disabled/resources")
    expect("disabled systemd resources rejected", status == 409, payload)

    status, payload = request("GET", "/api/audit")
    expect("audit readable", status == 200 and "events" in payload, payload)
    expect("audit excludes token", TOKEN not in str(payload), payload)

    print("smoke api: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
