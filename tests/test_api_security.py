from __future__ import annotations

import importlib

from fastapi.testclient import TestClient


def _load_app(monkeypatch, tmp_path):
    config = tmp_path / "services.toml"
    config.write_text(
        """
[services.disabled]
name = "Disabled"
type = "systemd"
enabled = false
unit = "disabled.service"
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("SERVER_MANAGER_API_TOKEN", "test-token")
    monkeypatch.setenv("SERVER_MANAGER_CONFIG", str(config))
    monkeypatch.setenv("SERVER_MANAGER_DB", str(tmp_path / "audit.db"))

    import server_manager.api.main as api_main

    return importlib.reload(api_main)


def test_protected_endpoints_require_valid_token(monkeypatch, tmp_path):
    api_main = _load_app(monkeypatch, tmp_path)
    client = TestClient(api_main.app)

    assert client.get("/api/health").status_code == 200
    assert client.get("/api/services").status_code == 401
    assert client.get("/api/services", headers={"Authorization": "Bearer wrong"}).status_code == 401

    response = client.get("/api/services", headers={"Authorization": "Bearer test-token"})

    assert response.status_code == 200
    assert response.json()["services"][0]["id"] == "disabled"


def test_unknown_and_malicious_service_ids_do_not_dispatch(monkeypatch, tmp_path):
    api_main = _load_app(monkeypatch, tmp_path)
    client = TestClient(api_main.app)
    headers = {"Authorization": "Bearer test-token"}

    class ExplodingProvider:
        def start(self, service_id: str):
            raise AssertionError(f"provider dispatch must not happen for {service_id}")

        stop = restart = status = resources = start

    api_main.controller.providers = {
        key: ExplodingProvider() for key in api_main.controller.providers
    }

    for service_id in ("missing", "..%2F..%2Fsystem", "disabled;reboot", "$(reboot)"):
        response = client.post(f"/api/services/{service_id}/start", headers=headers)
        assert response.status_code in {404, 405}
        body = response.json()
        if response.status_code == 404 and "error" in body:
            assert body["error"]["code"] == "service_not_found"


def test_audit_records_source_without_token(monkeypatch, tmp_path):
    api_main = _load_app(monkeypatch, tmp_path)
    client = TestClient(api_main.app)
    headers = {
        "Authorization": "Bearer test-token",
        "X-Server-Manager-Source": "CLI",
    }

    response = client.post("/api/services/disabled/start", headers=headers)

    assert response.status_code == 409
    audit = client.get("/api/audit", headers={"Authorization": "Bearer test-token"}).json()
    event = audit["events"][0]
    assert event["source"] == "CLI"
    assert event["action"] == "start"
    assert event["service_id"] == "disabled"
    assert "test-token" not in str(event)


def test_provider_errors_are_structured_without_tracebacks(monkeypatch, tmp_path):
    api_main = _load_app(monkeypatch, tmp_path)
    client = TestClient(api_main.app, raise_server_exceptions=False)
    headers = {"Authorization": "Bearer test-token"}

    response = client.get("/api/services/disabled/resources", headers=headers)

    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "service_unavailable"
    assert "Traceback" not in str(body)
    assert "Authorization" not in str(body)


def test_start_stop_restart_success_audit_is_structured(monkeypatch, tmp_path):
    api_main = _load_app(monkeypatch, tmp_path)
    client = TestClient(api_main.app)
    headers = {
        "Authorization": "Bearer test-token",
        "X-Server-Manager-Source": "CLI",
    }

    class SuccessfulController:
        def start(self, service_id: str):
            from server_manager.models import Operation, OperationResult, ServiceState

            return OperationResult(service_id, Operation.START, True, ServiceState.RUNNING, "ok")

        def stop(self, service_id: str):
            from server_manager.models import Operation, OperationResult, ServiceState

            return OperationResult(service_id, Operation.STOP, True, ServiceState.STOPPED, "ok")

        def restart(self, service_id: str):
            from server_manager.models import Operation, OperationResult, ServiceState

            return OperationResult(service_id, Operation.RESTART, True, ServiceState.RUNNING, "ok")

    api_main.controller = SuccessfulController()

    for operation in ("start", "stop", "restart"):
        response = client.post(f"/api/services/safe/{operation}", headers=headers)
        assert response.status_code == 200

    audit = client.get("/api/audit", headers={"Authorization": "Bearer test-token"}).json()
    events = audit["events"][:3]
    assert {event["action"] for event in events} == {"start", "stop", "restart"}
    assert all(event["source"] == "CLI" for event in events)
    assert all(event["success"] is True for event in events)
    assert "test-token" not in str(events)


def test_provider_command_error_is_structured_and_sanitized(monkeypatch, tmp_path):
    api_main = _load_app(monkeypatch, tmp_path)
    client = TestClient(api_main.app)
    headers = {"Authorization": "Bearer test-token"}

    class FailingController:
        def start(self, service_id: str):
            from server_manager.errors import ProviderCommandError

            raise ProviderCommandError(
                "Provider command failed.",
                details={"returncode": 1},
            )

    api_main.controller = FailingController()

    response = client.post("/api/services/safe/start", headers=headers)

    assert response.status_code == 502
    body = response.json()
    assert body["error"]["code"] == "provider_command_failed"
    assert body["error"]["details"] == {"returncode": 1}
    assert "Traceback" not in str(body)
    assert "systemctl" not in str(body)
    assert "docker compose" not in str(body)
    assert "test-token" not in str(body)
