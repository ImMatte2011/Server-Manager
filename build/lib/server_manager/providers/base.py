from __future__ import annotations

from abc import ABC, abstractmethod

from server_manager.models import OperationResult, ServiceConfig, ServiceResources, ServiceStatus


class Provider(ABC):
    name: str

    @abstractmethod
    def start(self, service: ServiceConfig) -> OperationResult:
        raise NotImplementedError

    @abstractmethod
    def stop(self, service: ServiceConfig) -> OperationResult:
        raise NotImplementedError

    @abstractmethod
    def restart(self, service: ServiceConfig) -> OperationResult:
        raise NotImplementedError

    @abstractmethod
    def status(self, service: ServiceConfig) -> ServiceStatus:
        raise NotImplementedError

    @abstractmethod
    def resources(self, service: ServiceConfig) -> ServiceResources:
        raise NotImplementedError
