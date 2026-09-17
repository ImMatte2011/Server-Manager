from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Path, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from server_manager.audit import AuditLog
from server_manager.config import load_settings
from server_manager.controller import ServiceController
from server_manager.errors import ServerManagerError
from server_manager.logging_config import configure_logging
from server_manager.models import AuditSource, Operation
from server_manager.monitoring.system import resource_summary, system_resources
from server_manager.registry import ServiceRegistry
from server_manager.scheduling import ScheduleService, ScheduleStore
from server_manager.security import require_auth
from server_manager.api.schemas import ScheduleCreateRequest
from server_manager.registry import SERVICE_ID_RE

settings = load_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)
registry = ServiceRegistry(settings.config_path)
controller = ServiceController(registry)
audit_log = AuditLog(settings.db_path)
schedule_service = ScheduleService(
    ScheduleStore(settings.db_path),
    controller,
    audit_log,
    settings.default_actor,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    schedule_service.start()
    try:
        yield
    finally:
        schedule_service.shutdown()


app = FastAPI(title="Server Manager", version="0.1.0", lifespan=lifespan)
ServiceIdPath = Annotated[str, Path(pattern=SERVICE_ID_RE.pattern, min_length=1, max_length=64)]


@app.exception_handler(ServerManagerError)
async def server_manager_error_handler(_: Request, exc: ServerManagerError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
    )


@app.exception_handler(HTTPException)
async def http_error_handler(_: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, dict) else None
    code = detail.get("code", "http_error") if detail else "http_error"
    message = detail.get("message", str(exc.detail)) if detail else str(exc.detail)
    details = detail.get("details", {}) if detail else {}
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": code, "message": message, "details": details}},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "invalid_request",
                "message": "Request validation failed.",
                "details": {"errors": _sanitize_validation_errors(exc.errors())},
            }
        },
    )


@app.exception_handler(Exception)
async def generic_error_handler(_: Request, exc: Exception):
    logger.exception("Unhandled API error")
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
def get_service(service_id: ServiceIdPath):
    return {"service": controller.get_service(service_id).to_dict()}


@app.get("/api/services/{service_id}/status", dependencies=[Depends(require_auth)])
def service_status(service_id: ServiceIdPath):
    return {"status": controller.status(service_id).to_dict()}


@app.get("/api/services/{service_id}/resources", dependencies=[Depends(require_auth)])
def service_resources(service_id: ServiceIdPath):
    return {"resources": controller.resources(service_id).to_dict()}


@app.post("/api/services/{service_id}/start", dependencies=[Depends(require_auth)])
def start_service(service_id: ServiceIdPath, x_server_manager_source: str | None = Header(default=None)):
    return _operation(service_id, Operation.START, x_server_manager_source)


@app.post("/api/services/{service_id}/stop", dependencies=[Depends(require_auth)])
def stop_service(service_id: ServiceIdPath, x_server_manager_source: str | None = Header(default=None)):
    return _operation(service_id, Operation.STOP, x_server_manager_source)


@app.post("/api/services/{service_id}/restart", dependencies=[Depends(require_auth)])
def restart_service(service_id: ServiceIdPath, x_server_manager_source: str | None = Header(default=None)):
    return _operation(service_id, Operation.RESTART, x_server_manager_source)


@app.get("/api/system/resources", dependencies=[Depends(require_auth)])
def get_system_resources():
    return {"resources": system_resources(settings.disk_path)}


@app.get("/api/resources/summary", dependencies=[Depends(require_auth)])
def get_resource_summary():
    service_items = []
    for record in controller.list_services():
        if record.capabilities.resources:
            item = {"service_id": record.service_id}
            try:
                item["status"] = controller.status(record.service_id).to_dict()
            except ServerManagerError as exc:
                item["status_error"] = exc.code
            try:
                item.update(controller.resources(record.service_id).to_dict())
            except ServerManagerError as exc:
                item["error"] = exc.code
            service_items.append(item)
    return resource_summary(service_items, settings.disk_path)


@app.get("/api/audit", dependencies=[Depends(require_auth)])
def get_audit(limit: int = 100):
    bounded_limit = max(1, min(limit, 500))
    return {"events": [event.to_dict() for event in audit_log.list_recent(bounded_limit)]}


@app.get("/api/schedules", dependencies=[Depends(require_auth)])
def list_schedules():
    return {"schedules": [record.to_dict() for record in schedule_service.list()]}


@app.post("/api/schedules", dependencies=[Depends(require_auth)])
def create_schedule(
    request: ScheduleCreateRequest,
    x_server_manager_source: str | None = Header(default=None),
):
    source = _source_from_header(x_server_manager_source)
    record = schedule_service.create(
        service_id=request.service_id,
        operation=request.operation,
        kind=request.kind,
        hour=request.hour,
        minute=request.minute,
        enabled=request.enabled,
        weekdays=tuple(request.weekdays),
    )
    audit_log.record(
        actor=settings.default_actor,
        source=source,
        action="schedule.create",
        service_id=record.service_id,
        success=True,
        message=record.schedule_id,
    )
    return {"schedule": record.to_dict()}


@app.delete("/api/schedules/{schedule_id}", dependencies=[Depends(require_auth)])
def delete_schedule(schedule_id: str, x_server_manager_source: str | None = Header(default=None)):
    source = _source_from_header(x_server_manager_source)
    schedule_service.delete(schedule_id)
    audit_log.record(
        actor=settings.default_actor,
        source=source,
        action="schedule.delete",
        service_id=None,
        success=True,
        message=schedule_id,
    )
    return {"success": True}


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


def _sanitize_validation_errors(errors: list[dict]) -> list[dict]:
    sanitized = []
    for error in errors:
        item = {}
        for key, value in error.items():
            if key == "ctx" and isinstance(value, dict):
                item[key] = {ctx_key: str(ctx_value) for ctx_key, ctx_value in value.items()}
            else:
                item[key] = value
        sanitized.append(item)
    return sanitized
