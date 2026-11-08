from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    environment: str
    host: str
    port: int
    api_token: str | None
    config_path: Path
    db_path: Path
    default_actor: str
    log_level: str
    disk_path: str


def _path_from_env(name: str, default: str) -> Path:
    return Path(os.getenv(name, default)).expanduser()


def load_settings() -> Settings:
    return Settings(
        environment=os.getenv("SERVER_MANAGER_ENV", "development").lower(),
        host=os.getenv("SERVER_MANAGER_HOST", "127.0.0.1"),
        port=int(os.getenv("SERVER_MANAGER_PORT", "8080")),
        api_token=os.getenv("SERVER_MANAGER_API_TOKEN"),
        config_path=_path_from_env("SERVER_MANAGER_CONFIG", "config/services.toml"),
        db_path=_path_from_env("SERVER_MANAGER_DB", "data/server-manager.db"),
        default_actor=os.getenv("SERVER_MANAGER_ACTOR", "admin"),
        log_level=os.getenv("SERVER_MANAGER_LOG_LEVEL", "INFO").upper(),
        disk_path=os.getenv("SERVER_MANAGER_DISK_PATH", "/"),
    )
