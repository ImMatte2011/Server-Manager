from __future__ import annotations

from pathlib import Path

from server_manager.audit import AuditLog
from server_manager.controller import ServiceController
from server_manager.models import Operation, ScheduleKind, ServiceState, ServiceType, Weekday
from server_manager.providers.fake import FakeProvider
from server_manager.registry import ServiceRegistry
from server_manager.scheduling import ScheduleService, ScheduleStore


def _registry(tmp_path: Path) -> ServiceRegistry:
    config = tmp_path / "services.toml"
    config.write_text(
        """
[services.safe]
name = "Safe"
type = "systemd"
unit = "safe.service"
""",
        encoding="utf-8",
    )
    return ServiceRegistry(config)


def test_schedule_persists_to_sqlite(tmp_path: Path):
    store = ScheduleStore(tmp_path / "server-manager.db")
    controller = ServiceController(
        _registry(tmp_path),
        providers={ServiceType.SYSTEMD: FakeProvider()},
    )
    service = ScheduleService(store, controller, AuditLog(tmp_path / "server-manager.db"), "tester")

    record = service.create(
        service_id="safe",
        operation=Operation.START,
        kind=ScheduleKind.DAILY,
        hour=8,
        minute=30,
    )

    reloaded = ScheduleStore(tmp_path / "server-manager.db").list()
    assert len(reloaded) == 1
    assert reloaded[0].schedule_id == record.schedule_id
    assert reloaded[0].service_id == "safe"
    assert reloaded[0].operation == Operation.START


def test_weekly_schedule_keeps_weekdays(tmp_path: Path):
    store = ScheduleStore(tmp_path / "server-manager.db")
    controller = ServiceController(
        _registry(tmp_path),
        providers={ServiceType.SYSTEMD: FakeProvider()},
    )
    service = ScheduleService(store, controller, AuditLog(tmp_path / "server-manager.db"), "tester")

    service.create(
        service_id="safe",
        operation=Operation.STOP,
        kind=ScheduleKind.WEEKLY,
        hour=23,
        minute=15,
        weekdays=(Weekday.MON, Weekday.FRI),
    )

    record = store.list()[0]
    assert record.weekdays == (Weekday.MON, Weekday.FRI)


def test_schedule_run_records_audit(tmp_path: Path):
    store = ScheduleStore(tmp_path / "server-manager.db")
    audit = AuditLog(tmp_path / "server-manager.db")
    provider = FakeProvider()
    controller = ServiceController(
        _registry(tmp_path),
        providers={ServiceType.SYSTEMD: provider},
    )
    service = ScheduleService(store, controller, audit, "tester")
    record = service.create(
        service_id="safe",
        operation=Operation.START,
        kind=ScheduleKind.DAILY,
        hour=8,
        minute=0,
    )

    service._run_schedule(record)

    assert provider.states["safe"] == ServiceState.RUNNING
    event = audit.list_recent(1)[0]
    assert event.source.value == "scheduled job"
    assert event.action == "start"
    assert event.success is True
