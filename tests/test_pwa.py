from __future__ import annotations

import importlib
import json

from fastapi.testclient import TestClient


def test_pwa_shell_security_and_nonpersistent_token(monkeypatch, tmp_path):
    config = tmp_path / "services.toml"
    config.write_text("schema_version = 1\n", encoding="utf-8")
    monkeypatch.setenv("SERVER_MANAGER_ENV", "test")
    monkeypatch.setenv("SERVER_MANAGER_API_TOKEN", "test-bearer-token")
    monkeypatch.setenv("SERVER_MANAGER_CONFIG", str(config))
    monkeypatch.setenv("SERVER_MANAGER_DB", str(tmp_path / "audit.db"))

    import server_manager.api.main as api_main

    api_main = importlib.reload(api_main)
    client = TestClient(api_main.app)

    page = client.get("/")
    assert page.status_code == 200
    assert "Content-Security-Policy" in page.headers
    assert "default-src 'self'" in page.headers["Content-Security-Policy"]
    assert page.headers["X-Content-Type-Options"] == "nosniff"
    assert page.headers["X-Frame-Options"] == "DENY"
    assert "/assets/app.js" in page.text

    manifest = client.get("/manifest.webmanifest")
    assert manifest.status_code == 200
    manifest_data = json.loads(manifest.text)
    assert manifest_data["display"] == "standalone"
    assert {"192x192", "512x512"} <= {icon["sizes"] for icon in manifest_data["icons"]}

    worker = client.get("/sw.js")
    assert worker.status_code == 200
    assert "Service-Worker-Allowed" in worker.headers
    assert 'url.pathname.startsWith("/api/")' in worker.text

    app_asset = client.get("/assets/app.js")
    assert app_asset.status_code == 200
    app_script = app_asset.text
    assert "localStorage" not in app_script
    assert "sessionStorage" not in app_script
    assert "credentials: \"omit\"" in app_script
    assert "mode: \"same-origin\"" in app_script
    assert "innerHTML" not in app_script
    assert client.get("/assets/icon.svg").status_code == 200
    for icon in ("icon-180.png", "icon-192.png", "icon-512.png"):
        response = client.get(f"/assets/{icon}")
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"

    protected = client.get("/api/services")
    assert protected.status_code == 401
    assert protected.headers["Cache-Control"] == "no-store"
