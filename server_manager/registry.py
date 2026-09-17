from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any

from server_manager.models import (
    Availability,
    Capabilities,
    ConfigStatus,
    ServiceConfig,
    ServiceRecord,
    ServiceType,
)

SERVICE_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}$")
SYSTEMD_UNIT_RE = re.compile(r"^[a-zA-Z0-9:_.@-]+\.(service|timer|socket|target)$")
COMPOSE_PROJECT_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,62}$")
SUPPORTED_SCHEMA_VERSION = 1


class ServiceRegistry:
    def __init__(self, config_path: Path):
        self.config_path = config_path
        self._records: dict[str, ServiceRecord] = {}
        self.reload()

    def reload(self) -> None:
        self._records = load_registry(self.config_path)

    def list(self) -> list[ServiceRecord]:
        return list(self._records.values())

    def get(self, service_id: str) -> ServiceRecord | None:
        return self._records.get(service_id)


def load_registry(config_path: Path) -> dict[str, ServiceRecord]:
    if not config_path.exists():
        return {}

    with config_path.open("rb") as handle:
        data = tomllib.load(handle)

    schema_version = data.get("schema_version", SUPPORTED_SCHEMA_VERSION)
    if schema_version != SUPPORTED_SCHEMA_VERSION:
        return {
            "__registry__": ServiceRecord(
                service_id="__registry__",
                name="Registry",
                type=None,
                enabled=False,
                config_status=ConfigStatus.INVALID,
                availability=Availability.UNAVAILABLE,
                capabilities=Capabilities(),
                errors=(f"Unsupported schema_version '{schema_version}'.",),
            )
        }

    services = data.get("services", {})
    if not isinstance(services, dict):
        return {
            "__registry__": ServiceRecord(
                service_id="__registry__",
                name="Registry",
                type=None,
                enabled=False,
                config_status=ConfigStatus.INVALID,
                availability=Availability.UNAVAILABLE,
                capabilities=Capabilities(),
                errors=("Top-level 'services' must be a table.",),
            )
        }

    records: dict[str, ServiceRecord] = {}
    for service_id, raw in services.items():
        records[service_id] = _parse_service(service_id, raw)
    return records


def _parse_service(service_id: str, raw: Any) -> ServiceRecord:
    errors: list[str] = []

    if not SERVICE_ID_RE.match(service_id):
        errors.append(
            "Service id must start with an alphanumeric character and contain only "
            "letters, numbers, dot, underscore or dash."
        )

    if not isinstance(raw, dict):
        return _invalid_record(service_id, "Unnamed service", True, errors + ["Service must be a table."])

    name = _read_str(raw, "name") or service_id
    enabled_value = raw.get("enabled", True)
    if not isinstance(enabled_value, bool):
        errors.append("'enabled' must be a boolean.")
        enabled = True
    else:
        enabled = enabled_value
    type_value = _read_str(raw, "type")
    if not type_value:
        return _invalid_record(service_id, name, enabled, errors + ["Missing required field 'type'."])

    try:
        service_type = ServiceType(type_value)
    except ValueError:
        return _invalid_record(service_id, name, enabled, errors + [f"Unsupported type '{type_value}'."])

    config = _build_config(service_id, name, service_type, enabled, raw, errors)
    if errors or config is None:
        return _invalid_record(service_id, name, enabled, errors, service_type)

    availability, reason = _assess_availability(config)
    return ServiceRecord(
        service_id=service_id,
        name=name,
        type=service_type,
        enabled=enabled,
        config_status=ConfigStatus.VALID,
        availability=availability,
        capabilities=_capabilities_for(config, availability),
        config=config,
        unavailable_reason=reason,
    )


def _build_config(
    service_id: str,
    name: str,
    service_type: ServiceType,
    enabled: bool,
    raw: dict[str, Any],
    errors: list[str],
) -> ServiceConfig | None:
    if service_type == ServiceType.DOCKER_COMPOSE:
        compose_file = _read_path(raw, "compose_file")
        if compose_file is None:
            errors.append("Docker Compose services require 'compose_file'.")
        project_dir = _read_path(raw, "project_dir")
        if project_dir is not None and not project_dir.is_absolute():
            errors.append("'project_dir' must be an absolute path when provided.")
        if compose_file is not None and not compose_file.is_absolute():
            errors.append("'compose_file' must be an absolute path.")
        compose_project_name = _read_str(raw, "compose_project_name")
        if compose_project_name and not COMPOSE_PROJECT_RE.match(compose_project_name):
            errors.append(
                "'compose_project_name' must contain lowercase letters, numbers, underscores or dashes."
            )
        if errors:
            return None
        return ServiceConfig(
            service_id=service_id,
            name=name,
            type=service_type,
            enabled=enabled,
            project_dir=project_dir or compose_file.parent,
            compose_file=compose_file,
            compose_project_name=compose_project_name,
            raw=raw,
        )

    if service_type == ServiceType.SYSTEMD:
        unit = _read_str(raw, "unit")
        if unit is None:
            errors.append("systemd services require 'unit'.")
        elif not SYSTEMD_UNIT_RE.match(unit):
            errors.append("'unit' must be a plain systemd unit name, not a path or command.")
        if errors:
            return None
        return ServiceConfig(
            service_id=service_id,
            name=name,
            type=service_type,
            enabled=enabled,
            unit=unit,
            raw=raw,
        )

    errors.append(f"Unsupported service type '{service_type}'.")
    return None


def _assess_availability(config: ServiceConfig) -> tuple[Availability, str | None]:
    if not config.enabled:
        return Availability.DISABLED, "Service is disabled in the registry."

    if config.type == ServiceType.DOCKER_COMPOSE:
        if config.compose_file and not config.compose_file.exists():
            return Availability.UNAVAILABLE, f"Compose file does not exist: {config.compose_file}"
        if config.project_dir and not config.project_dir.exists():
            return Availability.UNAVAILABLE, f"Project directory does not exist: {config.project_dir}"
        return Availability.AVAILABLE, None

    if config.type == ServiceType.SYSTEMD:
        return Availability.UNKNOWN, "systemd unit existence is checked by the provider at runtime."

    return Availability.UNKNOWN, None


def _capabilities_for(config: ServiceConfig, availability: Availability) -> Capabilities:
    if config.type == ServiceType.DOCKER_COMPOSE:
        return Capabilities(start=True, stop=True, restart=True, status=True, resources=True)

    if config.type == ServiceType.SYSTEMD:
        return Capabilities(start=True, stop=True, restart=True, status=True, resources=True)

    return Capabilities(status=True)


def _invalid_record(
    service_id: str,
    name: str,
    enabled: bool,
    errors: list[str],
    service_type: ServiceType | None = None,
) -> ServiceRecord:
    return ServiceRecord(
        service_id=service_id,
        name=name,
        type=service_type,
        enabled=enabled,
        config_status=ConfigStatus.INVALID,
        availability=Availability.UNAVAILABLE,
        capabilities=Capabilities(status=True),
        errors=tuple(errors),
    )


def _read_str(raw: dict[str, Any], key: str) -> str | None:
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _read_path(raw: dict[str, Any], key: str) -> Path | None:
    value = _read_str(raw, key)
    return Path(value).expanduser() if value else None
