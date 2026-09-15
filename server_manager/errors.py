from __future__ import annotations


class ServerManagerError(Exception):
    code = "server_manager_error"
    status_code = 500

    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ServiceNotFoundError(ServerManagerError):
    code = "service_not_found"
    status_code = 404


class InvalidServiceConfigError(ServerManagerError):
    code = "invalid_service_config"
    status_code = 422


class ServiceUnavailableError(ServerManagerError):
    code = "service_unavailable"
    status_code = 409


class UnsupportedOperationError(ServerManagerError):
    code = "unsupported_operation"
    status_code = 405


class ProviderCommandError(ServerManagerError):
    code = "provider_command_failed"
    status_code = 502


class ProviderUnavailableError(ServerManagerError):
    code = "provider_unavailable"
    status_code = 503
