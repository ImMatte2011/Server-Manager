from __future__ import annotations

import logging
import sqlite3
import uuid
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from server_manager.audit import AuditLog
from server_manager.controller import ServiceController
from server_manager.errors import ScheduleNotFoundError
from server_manager.models import AuditSource, Operation, ScheduleKind, ScheduleRecord, Weekday

logger = logging.getLogger(__name__)


class ScheduleStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def add(self, record: ScheduleRecord) -> ScheduleRecord:
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO schedules
                    (id, service_id, operation, kind, hour, minute, enabled, weekdays)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.schedule_id,
                    record.service_id,
                    record.operation.value,
                    record.kind.value,
                    record.hour,
                    record.minute,
                    int(record.enabled),
                    ",".join(day.value for day in record.weekdays),
                ),
            )
        return record

    def list(self) -> list[ScheduleRecord]:
        with sqlite3.connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT id, service_id, operation, kind, hour, minute, enabled, weekdays
                FROM schedules
                ORDER BY id
                """
            ).fetchall()
        return [_row_to_record(row) for row in rows]

    def delete(self, schedule_id: str) -> None:
        with sqlite3.connect(self.db_path) as connection:
            cursor = connection.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))
            if cursor.rowcount == 0:
                raise ScheduleNotFoundError(f"Schedule '{schedule_id}' was not found.")

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schedules (
                    id TEXT PRIMARY KEY,
                    service_id TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    hour INTEGER NOT NULL,
                    minute INTEGER NOT NULL,
                    enabled INTEGER NOT NULL,
                    weekdays TEXT NOT NULL DEFAULT ''
                )
                """
            )


class ScheduleService:
    def __init__(
        self,
        store: ScheduleStore,
        controller: ServiceController,
        audit_log: AuditLog,
        actor: str,
        scheduler: BackgroundScheduler | None = None,
    ):
        self.store = store
        self.controller = controller
        self.audit_log = audit_log
        self.actor = actor
        self.scheduler = scheduler or BackgroundScheduler()

    def start(self) -> None:
        if not self.scheduler.running:
            self.scheduler.start()
        self.reload_jobs()

    def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    def reload_jobs(self) -> None:
        for job in self.scheduler.get_jobs():
            if job.id.startswith("schedule:"):
                job.remove()
        for record in self.store.list():
            if record.enabled:
                self._add_runtime_job(record)

    def list(self) -> list[ScheduleRecord]:
        return self.store.list()

    def create(
        self,
        *,
        service_id: str,
        operation: Operation,
        kind: ScheduleKind,
        hour: int,
        minute: int,
        weekdays: tuple[Weekday, ...] = (),
        enabled: bool = True,
    ) -> ScheduleRecord:
        # Validate that the service exists and structurally supports the operation.
        record = self.controller.get_service(service_id)
        if not record.capabilities.supports(operation):
            from server_manager.errors import UnsupportedOperationError

            raise UnsupportedOperationError(
                f"Service '{service_id}' does not support '{operation.value}'.",
                details={"capabilities": record.capabilities.to_dict()},
            )

        schedule = ScheduleRecord(
            schedule_id=str(uuid.uuid4()),
            service_id=service_id,
            operation=operation,
            kind=kind,
            hour=hour,
            minute=minute,
            enabled=enabled,
            weekdays=weekdays,
        )
        self.store.add(schedule)
        if enabled and self.scheduler.running:
            self._add_runtime_job(schedule)
        return schedule

    def delete(self, schedule_id: str) -> None:
        self.store.delete(schedule_id)
        if self.scheduler.running:
            job = self.scheduler.get_job(_job_id(schedule_id))
            if job:
                job.remove()

    def _add_runtime_job(self, record: ScheduleRecord) -> None:
        self.scheduler.add_job(
            self._run_schedule,
            trigger=_trigger_for(record),
            id=_job_id(record.schedule_id),
            args=[record],
            replace_existing=True,
            coalesce=True,
            max_instances=1,
            misfire_grace_time=None,
        )

    def _run_schedule(self, record: ScheduleRecord) -> None:
        try:
            result = getattr(self.controller, record.operation.value)(record.service_id)
        except Exception as exc:
            logger.warning("scheduled operation failed", exc_info=True)
            self.audit_log.record(
                actor=self.actor,
                source=AuditSource.SCHEDULED_JOB,
                action=record.operation,
                service_id=record.service_id,
                success=False,
                message=str(exc),
            )
            return
        self.audit_log.record(
            actor=self.actor,
            source=AuditSource.SCHEDULED_JOB,
            action=record.operation,
            service_id=record.service_id,
            success=result.success,
            message=result.message,
        )


def _trigger_for(record: ScheduleRecord) -> CronTrigger:
    if record.kind == ScheduleKind.DAILY:
        return CronTrigger(hour=record.hour, minute=record.minute)
    days = ",".join(day.value for day in record.weekdays)
    return CronTrigger(day_of_week=days, hour=record.hour, minute=record.minute)


def _job_id(schedule_id: str) -> str:
    return f"schedule:{schedule_id}"


def _row_to_record(row: tuple) -> ScheduleRecord:
    weekdays = tuple(Weekday(value) for value in row[7].split(",") if value)
    return ScheduleRecord(
        schedule_id=row[0],
        service_id=row[1],
        operation=Operation(row[2]),
        kind=ScheduleKind(row[3]),
        hour=int(row[4]),
        minute=int(row[5]),
        enabled=bool(row[6]),
        weekdays=weekdays,
    )
