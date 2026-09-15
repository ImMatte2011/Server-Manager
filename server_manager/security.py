from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, status

from server_manager.config import load_settings


def require_auth(authorization: str | None = Header(default=None)) -> None:
    token = load_settings().api_token
    if not token:
        return
    expected = f"Bearer {token}"
    if authorization is None or not secrets.compare_digest(authorization, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "Missing or invalid API token."},
        )
