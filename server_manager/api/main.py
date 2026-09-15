from __future__ import annotations

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from server_manager.audit import AuditLog
from server_manager.config import load_settings
from server_manager.controller import ServiceController
from server_manager.errors import ServerManagerError
from server_manager.models import AuditSource, Operation
from server_manager.monitoring.system import resource_summary, system_resources
from server_manager.registry import ServiceRegistry
from server_manager.security import require_auth

settings = load_settings()
registry = ServiceRegistry(settings.config_path)
controller = ServiceController(registry)
audit_log = AuditLog(settings.db_path)

app = FastAPI(title="Server Manager", version="0.1.0")


@app.exception_handler(ServerManagerError)
async def server_manager_error_handler(_: Request, exc: ServerManagerError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
    )


@app.exception_handler(Exception)
async def generic_error_handler(_: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "internal_error", "message": "Unexpected server error."}},
    )


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/registry/reload", dependencies=[Depends(require_auth)])
def reload_registry():
    registry.reload()
    return {"success": True, "services": len(registry.list())}


@app.get("/api/services", dependencies=[Depends(require_auth)])
def list_services():
    return {"services": [record.to_dict() for record in controller.list_services()]}


@app.get("/api/services/{service_id}", dependencies=[Depends(require_auth)])
def get_service(service_id: str):
    return {"service": controller.get_service(service_id).to_dict()}


@app.get("/api/services/{service_id}/status", dependencies=[Depends(require_auth)])
def service_status(service_id: str):
    return {"status": controller.status(service_id).to_dict()}


@app.get("/api/services/{service_id}/resources", dependencies=[Depends(require_auth)])
def service_resources(service_id: str):
    return {"resources": controller.resources(service_id).to_dict()}


@app.post("/api/services/{service_id}/start", dependencies=[Depends(require_auth)])
def start_service(service_id: str, x_server_manager_source: str | None = Header(default=None)):
    return _operation(service_id, Operation.START, x_server_manager_source)


@app.post("/api/services/{service_id}/stop", dependencies=[Depends(require_auth)])
def stop_service(service_id: str, x_server_manager_source: str | None = Header(default=None)):
    return _operation(service_id, Operation.STOP, x_server_manager_source)


@app.post("/api/services/{service_id}/restart", dependencies=[Depends(require_auth)])
def restart_service(service_id: str, x_server_manager_source: str | None = Header(default=None)):
    return _operation(service_id, Operation.RESTART, x_server_manager_source)


@app.get("/api/system/resources", dependencies=[Depends(require_auth)])
def get_system_resources():
    return {"resources": system_resources()}


@app.get("/api/resources/summary", dependencies=[Depends(require_auth)])
def get_resource_summary():
    service_items = []
    for record in controller.list_services():
        if record.capabilities.resources:
            try:
                service_items.append(controller.resources(record.service_id).to_dict())
            except ServerManagerError as exc:
                service_items.append({"service_id": record.service_id, "error": exc.code})
    return resource_summary(service_items)


@app.get("/api/audit", dependencies=[Depends(require_auth)])
def get_audit(limit: int = 100):
    bounded_limit = max(1, min(limit, 500))
    return {"events": [event.to_dict() for event in audit_log.list_recent(bounded_limit)]}


def _operation(service_id: str, operation: Operation, source_header: str | None):
    source = _source_from_header(source_header)
    try:
        result = getattr(controller, operation.value)(service_id)
    except ServerManagerError as exc:
        audit_log.record(
            actor=settings.default_actor,
            source=source,
            action=operation,
            service_id=service_id,
            success=False,
            message=exc.message,
        )
        raise

    audit_log.record(
        actor=settings.default_actor,
        source=source,
        action=operation,
        service_id=service_id,
        success=True,
        message=result.message,
    )
    return {"result": result.to_dict()}


def _source_from_header(value: str | None) -> AuditSource:
    if value is None:
        return AuditSource.API
    normalized = value.strip().lower().replace("_", " ")
    for source in AuditSource:
        if source.value.lower() == normalized:
            return source
    raise HTTPException(
        status_code=422,
        detail={"code": "invalid_source", "message": "Invalid audit source."},
    )
