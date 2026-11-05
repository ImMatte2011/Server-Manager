from __future__ import annotations

from pathlib import Path

import pytest

from server_manager.errors import ProviderCommandError
from server_manager.models import Operation, ServiceConfig, ServiceState, ServiceType
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
        compose_project_name="safe",
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

    result = DockerComposeProvider().start(service)

    assert len(calls) == 2
    assert result.state == ServiceState.STOPPED
    argv, cwd, _ = calls[0]
    assert argv == [
        "docker",
        "compose",
        "-f",
        str(compose_file),
        "-p",
        "safe",
        "up",
        "-d",
    ]
    assert cwd == str(tmp_path)
    assert all(";" not in part for part in argv)
    assert calls[1][0] == [
        "docker",
        "compose",
        "-f",
        str(compose_file),
        "-p",
        "safe",
        "ps",
        "--format",
        "json",
    ]


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


def test_systemd_start_reports_state_read_after_operation(monkeypatch):
    service = ServiceConfig(
        service_id="safe",
        name="Safe",
        type=ServiceType.SYSTEMD,
        unit="safe.service",
    )
    calls = []

    class Output:
        stdout = "active\n"

    def fake_run_checked(argv, *, cwd=None, timeout=60):
        calls.append(("operation", argv))
        return Output()

    def fake_run_command(argv, *, cwd=None, timeout=60):
        calls.append(("status", argv))
        return Output()

    monkeypatch.setattr("server_manager.providers.systemd.run_checked", fake_run_checked)
    monkeypatch.setattr("server_manager.providers.systemd.run_command", fake_run_command)

    result = SystemdProvider().start(service)

    assert result.operation == Operation.START
    assert result.state == ServiceState.RUNNING
    assert calls == [
        ("operation", ["systemctl", "start", "safe.service"]),
        ("status", ["systemctl", "is-active", "safe.service"]),
    ]


def test_command_os_errors_are_sanitized(monkeypatch):
    def permission_denied(*args, **kwargs):
        raise PermissionError("sensitive path or command details")

    monkeypatch.setattr("server_manager.providers.commands.subprocess.run", permission_denied)

    with pytest.raises(ProviderCommandError, match="could not be executed") as exc_info:
        from server_manager.providers.commands import run_command

        run_command(["systemctl", "start", "safe.service"])

    assert "sensitive path" not in exc_info.value.message
    assert exc_info.value.details == {}


def test_docker_container_matching_requires_project_and_path():
    labels = {
        "com.docker.compose.project": "safe",
        "com.docker.compose.project.working_dir": "/srv/safe",
        "com.docker.compose.project.config_files": "/srv/safe/docker-compose.yml",
    }

    assert _matches_compose_container(labels, "safe", "/srv/safe", "/srv/safe/docker-compose.yml")
    assert not _matches_compose_container(labels, "other", "/srv/safe", "/srv/safe/docker-compose.yml")
    assert not _matches_compose_container(labels, "safe", "/srv/other", "/srv/other/docker-compose.yml")
    assert not _matches_compose_container(labels, "safe", "/srv/safe", "/srv/safe/other.yml")
