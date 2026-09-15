from __future__ import annotations

import json

from server_manager.errors import ProviderCommandError
from server_manager.models import Operation, OperationResult, ServiceConfig, ServiceResources, ServiceState, ServiceStatus
from server_manager.providers.base import Provider
from server_manager.providers.commands import run_checked


class DockerComposeProvider(Provider):
    name = "docker_compose"

    def start(self, service: ServiceConfig) -> OperationResult:
        self._compose(service, ["up", "-d"])
        return OperationResult(service.service_id, Operation.START, True, ServiceState.RUNNING, "Started.")

    def stop(self, service: ServiceConfig) -> OperationResult:
        self._compose(service, ["down"])
        return OperationResult(service.service_id, Operation.STOP, True, ServiceState.STOPPED, "Stopped.")

    def restart(self, service: ServiceConfig) -> OperationResult:
        self._compose(service, ["restart"])
        return OperationResult(service.service_id, Operation.RESTART, True, ServiceState.RUNNING, "Restarted.")

    def status(self, service: ServiceConfig) -> ServiceStatus:
        try:
            output = self._compose(service, ["ps", "--format", "json"])
        except ProviderCommandError as exc:
            return ServiceStatus(
                service.service_id,
                ServiceState.UNKNOWN,
                detail="Docker Compose status could not be read.",
                provider=self.name,
                raw={"error": exc.code},
            )

        containers = _parse_compose_ps(output.stdout)
        if not containers:
            return ServiceStatus(service.service_id, ServiceState.STOPPED, "No containers.", self.name)

        states = [str(container.get("State", "")).lower() for container in containers]
        exit_codes = [container.get("ExitCode") for container in containers]
        if all(state == "running" for state in states):
            state = ServiceState.RUNNING
        elif any(state == "running" for state in states):
            state = ServiceState.UNKNOWN
        elif any(code not in (None, 0, "0") for code in exit_codes):
            state = ServiceState.FAILED
        else:
            state = ServiceState.STOPPED

        return ServiceStatus(
            service.service_id,
            state,
            detail=f"{len(containers)} compose container(s).",
            provider=self.name,
            raw={"containers": containers},
        )

    def resources(self, service: ServiceConfig) -> ServiceResources:
        try:
            import docker
        except ImportError as exc:
            raise ProviderCommandError("Docker SDK is not installed.") from exc

        client = docker.from_env()
        project_dir = str(service.project_dir) if service.project_dir else None
        compose_file = str(service.compose_file) if service.compose_file else None
        containers = client.containers.list(all=True)
        matched = []
        memory_total = 0
        cpu_total = 0.0
        for container in containers:
            labels = container.labels or {}
            if not _matches_compose_container(labels, project_dir, compose_file):
                continue
            stats = container.stats(stream=False)
            memory = int(stats.get("memory_stats", {}).get("usage") or 0)
            cpu = _docker_cpu_percent(stats)
            memory_total += memory
            cpu_total += cpu
            matched.append({"id": container.short_id, "name": container.name, "memory_bytes": memory, "cpu_percent": cpu})

        return ServiceResources(
            service.service_id,
            cpu_percent=round(cpu_total, 2),
            memory_bytes=memory_total,
            memory_note="Docker memory is container-attributed and may include shared/cache effects.",
            raw={"containers": matched},
        )

    def _compose(self, service: ServiceConfig, args: list[str]):
        if service.compose_file is None:
            raise ProviderCommandError("Missing compose file in service config.")
        argv = ["docker", "compose", "-f", str(service.compose_file), *args]
        cwd = str(service.project_dir) if service.project_dir else None
        return run_checked(argv, cwd=cwd)


def _parse_compose_ps(stdout: str) -> list[dict]:
    if not stdout:
        return []
    lines = [line for line in stdout.splitlines() if line.strip()]
    containers: list[dict] = []
    for line in lines:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, list):
            containers.extend(item for item in value if isinstance(item, dict))
        elif isinstance(value, dict):
            containers.append(value)
    return containers


def _matches_compose_container(labels: dict[str, str], project_dir: str | None, compose_file: str | None) -> bool:
    working_dir = labels.get("com.docker.compose.project.working_dir")
    config_files = labels.get("com.docker.compose.project.config_files", "")
    if project_dir and working_dir == project_dir:
        return True
    if compose_file and compose_file in config_files.split(","):
        return True
    return False


def _docker_cpu_percent(stats: dict) -> float:
    cpu_stats = stats.get("cpu_stats", {})
    precpu_stats = stats.get("precpu_stats", {})
    cpu_delta = (
        cpu_stats.get("cpu_usage", {}).get("total_usage", 0)
        - precpu_stats.get("cpu_usage", {}).get("total_usage", 0)
    )
    system_delta = cpu_stats.get("system_cpu_usage", 0) - precpu_stats.get("system_cpu_usage", 0)
    online_cpus = cpu_stats.get("online_cpus") or len(cpu_stats.get("cpu_usage", {}).get("percpu_usage", [])) or 1
    if system_delta <= 0 or cpu_delta <= 0:
        return 0.0
    return (cpu_delta / system_delta) * online_cpus * 100.0
