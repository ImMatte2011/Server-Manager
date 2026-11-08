from __future__ import annotations

from server_manager.models import Operation, OperationResult, ServiceConfig, ServiceResources, ServiceState, ServiceStatus
from server_manager.providers.base import Provider


class FakeProvider(Provider):
    name = "fake"

    def __init__(self):
        self.states: dict[str, ServiceState] = {}

    def start(self, service: ServiceConfig) -> OperationResult:
        self.states[service.service_id] = ServiceState.RUNNING
        return OperationResult(service.service_id, Operation.START, True, ServiceState.RUNNING)

    def stop(self, service: ServiceConfig) -> OperationResult:
        self.states[service.service_id] = ServiceState.STOPPED
        return OperationResult(service.service_id, Operation.STOP, True, ServiceState.STOPPED)

    def restart(self, service: ServiceConfig) -> OperationResult:
        self.states[service.service_id] = ServiceState.RUNNING
        return OperationResult(service.service_id, Operation.RESTART, True, ServiceState.RUNNING)

    def status(self, service: ServiceConfig) -> ServiceStatus:
        return ServiceStatus(service.service_id, self.states.get(service.service_id, ServiceState.STOPPED), provider=self.name)

    def resources(self, service: ServiceConfig) -> ServiceResources:
        return ServiceResources(service.service_id, cpu_percent=0.0, memory_bytes=0)
