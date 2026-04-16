from __future__ import annotations

import hmac

from fastapi import Header, HTTPException

from app.config import Settings

settings = Settings()


def verify_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if not settings.auth_enabled:
        return

    if not settings.api_key:
        raise HTTPException(status_code=500, detail="API key auth enabled but API_KEY is empty")

    if not x_api_key or not hmac.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(status_code=401, detail="unauthorized")
