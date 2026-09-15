from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class ServiceType(StrEnum):
    DOCKER_COMPOSE = "docker_compose"
    SYSTEMD = "systemd"


class ServiceState(StrEnum):
    RUNNING = "running"
    STOPPED = "stopped"
    STARTING = "starting"
    STOPPING = "stopping"
    RESTARTING = "restarting"
    FAILED = "failed"
    UNKNOWN = "unknown"
    UNAVAILABLE = "unavailable"
    DISABLED = "disabled"
    INVALID = "invalid"


class ConfigStatus(StrEnum):
    VALID = "valid"
    INVALID = "invalid"


class Availability(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    DISABLED = "disabled"
    UNKNOWN = "unknown"


class Operation(StrEnum):
    START = "start"
    STOP = "stop"
    RESTART = "restart"
    STATUS = "status"
    RESOURCES = "resources"


class AuditSource(StrEnum):
    CLI = "CLI"
    WEB_UI = "Web UI"
    API = "API"
    SCHEDULED_JOB = "scheduled job"


@dataclass(frozen=True)
class Capabilities:
    start: bool = False
    stop: bool = False
    restart: bool = False
    status: bool = True
    resources: bool = False

    def supports(self, operation: Operation) -> bool:
        return bool(getattr(self, operation.value))

    def to_dict(self) -> dict[str, bool]:
        return asdict(self)


@dataclass(frozen=True)
class ServiceConfig:
    service_id: str
    name: str
    type: ServiceType
    enabled: bool = True
    project_dir: Path | None = None
    compose_file: Path | None = None
    unit: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ServiceRecord:
    service_id: str
    name: str
    type: ServiceType | None
    enabled: bool
    config_status: ConfigStatus
    availability: Availability
    capabilities: Capabilities
    config: ServiceConfig | None = None
    errors: tuple[str, ...] = ()
    unavailable_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.service_id,
            "name": self.name,
            "type": self.type.value if self.type else None,
            "enabled": self.enabled,
            "config_status": self.config_status.value,
            "availability": self.availability.value,
            "capabilities": self.capabilities.to_dict(),
            "errors": list(self.errors),
            "unavailable_reason": self.unavailable_reason,
        }


@dataclass(frozen=True)
class ServiceStatus:
    service_id: str
    state: ServiceState
    detail: str | None = None
    provider: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.service_id,
            "state": self.state.value,
            "detail": self.detail,
            "provider": self.provider,
            "raw": self.raw,
        }


@dataclass(frozen=True)
class ServiceResources:
    service_id: str
    cpu_percent: float | None = None
    memory_bytes: int | None = None
    memory_note: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OperationResult:
    service_id: str
    operation: Operation
    success: bool
    state: ServiceState | None = None
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.service_id,
            "operation": self.operation.value,
            "success": self.success,
            "state": self.state.value if self.state else None,
            "message": self.message,
        }
