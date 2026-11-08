from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, status

from server_manager.config import load_settings
from server_manager.errors import AuthenticationNotConfiguredError


def require_auth(authorization: str | None = Header(default=None)) -> None:
    settings = load_settings()
    token = settings.api_token
    if not token:
        if settings.environment in {"dev", "development", "test", "local"}:
            return
        raise AuthenticationNotConfiguredError(
            "API authentication is not configured. Set SERVER_MANAGER_API_TOKEN."
        )
    if len(token) < 16 and settings.environment not in {"dev", "development", "test", "local"}:
        raise AuthenticationNotConfiguredError(
            "API token is too short for production. Use at least 16 characters."
        )
    if authorization is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "Missing or invalid API token."},
        )
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0] != "Bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "Missing or invalid API token."},
        )
    candidate = parts[1]
    if not secrets.compare_digest(candidate, token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "Missing or invalid API token."},
        )
