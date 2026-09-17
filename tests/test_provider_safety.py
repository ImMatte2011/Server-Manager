from __future__ import annotations

from pathlib import Path

from server_manager.models import ServiceConfig, ServiceType
from server_manager.providers.docker_compose import DockerComposeProvider, _matches_compose_container
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

    assert len(calls) == 2
    argv, cwd, _ = calls[0]
    assert argv == ["docker", "compose", "-f", str(compose_file), "up", "-d"]
    assert cwd == str(tmp_path)
    assert all(";" not in part for part in argv)
    assert calls[1][0] == ["docker", "compose", "-f", str(compose_file), "ps", "--format", "json"]


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


def test_docker_container_matching_requires_project_and_path():
    labels = {
        "com.docker.compose.project": "safe",
        "com.docker.compose.project.working_dir": "/srv/safe",
        "com.docker.compose.project.config_files": "/srv/safe/docker-compose.yml",
    }

    assert _matches_compose_container(labels, "safe", "/srv/safe", "/srv/safe/docker-compose.yml")
    assert not _matches_compose_container(labels, "other", "/srv/safe", "/srv/safe/docker-compose.yml")
    assert not _matches_compose_container(labels, "safe", "/srv/other", "/srv/other/docker-compose.yml")
