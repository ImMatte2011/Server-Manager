from __future__ import annotations

import threading
from collections import defaultdict

from server_manager.errors import (
    InvalidServiceConfigError,
    ServiceNotFoundError,
    ServiceUnavailableError,
    UnsupportedOperationError,
)
from server_manager.models import (
    Availability,
    ConfigStatus,
    Operation,
    OperationResult,
    ServiceRecord,
    ServiceResources,
    ServiceStatus,
    ServiceType,
)
from server_manager.providers.base import Provider
from server_manager.providers.docker_compose import DockerComposeProvider
from server_manager.providers.systemd import SystemdProvider
from server_manager.registry import ServiceRegistry


class ServiceController:
    def __init__(self, registry: ServiceRegistry, providers: dict[ServiceType, Provider] | None = None):
        self.registry = registry
        self.providers = providers or {
            ServiceType.DOCKER_COMPOSE: DockerComposeProvider(),
            ServiceType.SYSTEMD: SystemdProvider(),
        }
        self._locks: defaultdict[str, threading.Lock] = defaultdict(threading.Lock)

    def list_services(self) -> list[ServiceRecord]:
        return self.registry.list()

    def get_service(self, service_id: str) -> ServiceRecord:
        record = self.registry.get(service_id)
        if record is None:
            raise ServiceNotFoundError(f"Service '{service_id}' was not found.")
        return record

    def status(self, service_id: str) -> ServiceStatus:
        record = self._require_usable(service_id, Operation.STATUS, allow_unavailable=True)
        if record.config is None:
            return ServiceStatus(service_id, _state_for_unusable(record), detail="Service cannot be queried.")
        if record.availability in {Availability.DISABLED, Availability.UNAVAILABLE}:
            return ServiceStatus(
                service_id,
                _state_for_unusable(record),
                detail=record.unavailable_reason,
                provider=record.type.value if record.type else None,
            )
        return self._provider(record).status(record.config)

    def resources(self, service_id: str) -> ServiceResources:
        record = self._require_usable(service_id, Operation.RESOURCES)
        return self._provider(record).resources(record.config)  # type: ignore[arg-type]

    def start(self, service_id: str) -> OperationResult:
        return self._operate(service_id, Operation.START)

    def stop(self, service_id: str) -> OperationResult:
        return self._operate(service_id, Operation.STOP)

    def restart(self, service_id: str) -> OperationResult:
        return self._operate(service_id, Operation.RESTART)

    def _operate(self, service_id: str, operation: Operation) -> OperationResult:
        record = self._require_usable(service_id, operation)
        with self._locks[service_id]:
            provider = self._provider(record)
            method = getattr(provider, operation.value)
            return method(record.config)

    def _require_usable(
        self,
        service_id: str,
        operation: Operation,
        *,
        allow_unavailable: bool = False,
    ) -> ServiceRecord:
        record = self.get_service(service_id)
        if record.config_status != ConfigStatus.VALID:
            raise InvalidServiceConfigError(
                f"Service '{service_id}' has invalid configuration.",
                details={"errors": list(record.errors)},
            )
        if not record.capabilities.supports(operation):
            raise UnsupportedOperationError(
                f"Service '{service_id}' does not support '{operation.value}'.",
                details={"capabilities": record.capabilities.to_dict()},
            )
        if not allow_unavailable and record.availability in {Availability.DISABLED, Availability.UNAVAILABLE}:
            raise ServiceUnavailableError(
                f"Service '{service_id}' is {record.availability.value}.",
                details={"reason": record.unavailable_reason},
            )
        return record

    def _provider(self, record: ServiceRecord) -> Provider:
        if record.type is None:
            raise InvalidServiceConfigError("Service has no provider type.")
        return self.providers[record.type]


def _state_for_unusable(record: ServiceRecord):
    from server_manager.models import ServiceState

    if record.config_status == ConfigStatus.INVALID:
        return ServiceState.INVALID
    if record.availability == Availability.DISABLED:
        return ServiceState.DISABLED
    if record.availability == Availability.UNAVAILABLE:
        return ServiceState.UNAVAILABLE
    return ServiceState.UNKNOWN
