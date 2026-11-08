from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field, field_validator

from server_manager.models import Operation, ScheduleKind, Weekday
from server_manager.registry import SERVICE_ID_RE

ServiceId = Annotated[str, Field(pattern=SERVICE_ID_RE.pattern, min_length=1, max_length=64)]


class ScheduleCreateRequest(BaseModel):
    service_id: ServiceId
    operation: Operation
    kind: ScheduleKind
    hour: int = Field(ge=0, le=23)
    minute: int = Field(ge=0, le=59)
    enabled: bool = True
    weekdays: list[Weekday] = Field(default_factory=list)

    @field_validator("operation")
    @classmethod
    def operation_must_be_mutating(cls, value: Operation) -> Operation:
        if value not in {Operation.START, Operation.STOP, Operation.RESTART}:
            raise ValueError("Schedules can only run start, stop or restart.")
        return value

    @field_validator("weekdays")
    @classmethod
    def weekly_schedules_need_days(cls, value: list[Weekday], info):
        kind = info.data.get("kind")
        if kind == ScheduleKind.WEEKLY and not value:
            raise ValueError("Weekly schedules require at least one weekday.")
        if kind == ScheduleKind.DAILY and value:
            raise ValueError("Daily schedules must not include weekdays.")
        return value
