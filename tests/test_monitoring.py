from __future__ import annotations

import psutil

from server_manager.monitoring.system import resource_summary, system_resources


def test_system_resources_shape():
    payload = system_resources()

    assert "cpu_percent" in payload
    assert payload["memory"]["total_bytes"] >= payload["memory"]["available_bytes"]
    assert "disk" in payload
    assert "swap" in payload
    assert payload["uptime_seconds"] >= 0


def test_resource_summary_accounts_monitored_memory():
    payload = resource_summary(
        [
            {"service_id": "a", "memory_bytes": 100},
            {"service_id": "b", "memory_bytes": None},
            {"service_id": "c", "memory_bytes": 50},
        ]
    )

    assert payload["memory_accounting"]["monitored_services_bytes"] == 150
    assert payload["memory_accounting"]["unattributed_used_bytes"] >= 0


def test_system_resources_degrades_when_swap_metrics_are_unavailable(monkeypatch):
    monkeypatch.setattr(psutil, "swap_memory", lambda: (_ for _ in ()).throw(RuntimeError("unavailable")))

    payload = system_resources()

    assert payload["memory"]["total_bytes"] > 0
    assert payload["swap"] == {
        "total_bytes": None,
        "used_bytes": None,
        "free_bytes": None,
        "percent": None,
        "note": "Swap metrics are unavailable on this system.",
    }
