from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from server_manager.models import AuditSource, Operation


@dataclass(frozen=True)
class AuditEvent:
    timestamp: str
    actor: str
    source: AuditSource
    action: str
    service_id: str | None
    success: bool
    message: str | None = None

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "actor": self.actor,
            "source": self.source.value,
            "action": self.action,
            "service_id": self.service_id,
            "success": self.success,
            "message": self.message,
        }


class AuditLog:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def record(
        self,
        *,
        actor: str,
        source: AuditSource,
        action: Operation | str,
        service_id: str | None,
        success: bool,
        message: str | None = None,
    ) -> None:
        action_value = action.value if isinstance(action, Operation) else action
        timestamp = datetime.now(UTC).isoformat()
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO audit_events
                    (timestamp, actor, source, action, service_id, success, message)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (timestamp, actor, source.value, action_value, service_id, int(success), message),
            )

    def list_recent(self, limit: int = 100) -> list[AuditEvent]:
        with sqlite3.connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT timestamp, actor, source, action, service_id, success, message
                FROM audit_events
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [
            AuditEvent(
                timestamp=row[0],
                actor=row[1],
                source=AuditSource(row[2]),
                action=row[3],
                service_id=row[4],
                success=bool(row[5]),
                message=row[6],
            )
            for row in rows
        ]

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    source TEXT NOT NULL,
                    action TEXT NOT NULL,
                    service_id TEXT,
                    success INTEGER NOT NULL,
                    message TEXT
                )
                """
            )
