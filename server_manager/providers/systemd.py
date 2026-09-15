from __future__ import annotations

import os

from server_manager.models import Operation, OperationResult, ServiceConfig, ServiceResources, ServiceState, ServiceStatus
from server_manager.providers.base import Provider
from server_manager.providers.commands import run_checked, run_command


class SystemdProvider(Provider):
    name = "systemd"

    def start(self, service: ServiceConfig) -> OperationResult:
        run_checked(self._systemctl(service, "start"))
        return OperationResult(service.service_id, Operation.START, True, ServiceState.RUNNING, "Started.")

    def stop(self, service: ServiceConfig) -> OperationResult:
        run_checked(self._systemctl(service, "stop"))
        return OperationResult(service.service_id, Operation.STOP, True, ServiceState.STOPPED, "Stopped.")

    def restart(self, service: ServiceConfig) -> OperationResult:
        run_checked(self._systemctl(service, "restart"))
        return OperationResult(service.service_id, Operation.RESTART, True, ServiceState.RUNNING, "Restarted.")

    def status(self, service: ServiceConfig) -> ServiceStatus:
        output = run_command(self._systemctl(service, "is-active"), timeout=15)
        value = output.stdout.strip().lower()
        state = {
            "active": ServiceState.RUNNING,
            "inactive": ServiceState.STOPPED,
            "failed": ServiceState.FAILED,
            "activating": ServiceState.STARTING,
            "deactivating": ServiceState.STOPPING,
        }.get(value, ServiceState.UNKNOWN)
        return ServiceStatus(service.service_id, state, detail=value, provider=self.name)

    def resources(self, service: ServiceConfig) -> ServiceResources:
        try:
            import psutil
        except ImportError:
            return ServiceResources(
                service.service_id,
                cpu_percent=None,
                memory_bytes=None,
                memory_note="psutil is not installed.",
            )

        pid_output = run_checked(
            self._systemctl(service, "show", "--property=MainPID", "--value"),
            timeout=15,
        )
        try:
            main_pid = int(pid_output.stdout.strip() or "0")
        except ValueError:
            main_pid = 0

        if main_pid <= 0:
            return ServiceResources(
                service.service_id,
                cpu_percent=None,
                memory_bytes=None,
                memory_note="systemd unit has no active MainPID.",
            )

        try:
            root = psutil.Process(main_pid)
            processes = [root, *root.children(recursive=True)]
            memory = sum(process.memory_info().rss for process in processes if process.is_running())
            cpu = sum(process.cpu_percent(interval=0.0) for process in processes if process.is_running())
        except psutil.Error:
            return ServiceResources(
                service.service_id,
                cpu_percent=None,
                memory_bytes=None,
                memory_note="MainPID disappeared while reading process metrics.",
            )

        return ServiceResources(
            service.service_id,
            cpu_percent=round(cpu, 2),
            memory_bytes=memory,
            memory_note="systemd memory is estimated from MainPID and child processes.",
            raw={"main_pid": main_pid},
        )

    def _systemctl(self, service: ServiceConfig, operation: str, *extra_args: str) -> list[str]:
        if service.unit is None:
            raise ValueError("Missing systemd unit in service config.")
        argv = ["systemctl", operation, service.unit, *extra_args]
        if os.getenv("SERVER_MANAGER_SYSTEMCTL_SUDO", "0") == "1":
            return ["sudo", "--non-interactive", *argv]
        return argv
