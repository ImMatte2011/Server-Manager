from __future__ import annotations

from pathlib import Path

from server_manager.models import ServiceConfig, ServiceType
from server_manager.providers.docker_compose import DockerComposeProvider
from server_manager.providers.systemd import SystemdProvider
from server_manager.registry import load_registry


def test_docker_compose_provider_uses_registry_paths(monkeypatch, tmp_path: Path):
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text("services: {}\n", encoding="utf-8")
    service = ServiceConfig(
        service_id="safe",
        name="Safe",
        type=ServiceType.DOCKER_COMPOSE,
        project_dir=tmp_path,
        compose_file=compose_file,
    )
    calls = []

    def fake_run_checked(argv, *, cwd=None, timeout=60):
        calls.append((argv, cwd, timeout))

        class Output:
            stdout = ""
            stderr = ""
            returncode = 0

        return Output()

    monkeypatch.setattr("server_manager.providers.docker_compose.run_checked", fake_run_checked)

    DockerComposeProvider().start(service)

    argv, cwd, _ = calls[0]
    assert argv == ["docker", "compose", "-f", str(compose_file), "up", "-d"]
    assert cwd == str(tmp_path)
    assert all(";" not in part for part in argv)


def test_systemd_registry_rejects_command_like_units(tmp_path: Path):
    config = tmp_path / "services.toml"
    config.write_text(
        """
[services.bad]
name = "Bad"
type = "systemd"
unit = "safe.service;reboot"
""",
        encoding="utf-8",
    )

    records = load_registry(config)

    assert records["bad"].config_status.value == "invalid"


def test_systemd_provider_builds_fixed_argv_from_validated_unit():
    service = ServiceConfig(
        service_id="safe",
        name="Safe",
        type=ServiceType.SYSTEMD,
        unit="safe.service",
    )

    argv = SystemdProvider()._systemctl(service, "start")

    assert argv == ["systemctl", "start", "safe.service"]
