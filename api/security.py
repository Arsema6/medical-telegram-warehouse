"""API key auth and a simple in-process rate limiter."""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader

from src.config import get_settings

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)
PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


def require_api_key(api_key: str | None = Security(API_KEY_HEADER)) -> str:
    expected = get_settings().api_key
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API_KEY is not configured on the server",
        )
    if not api_key or api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key header",
        )
    return api_key


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, request: Request) -> None:
        settings = get_settings()
        limit = settings.api_rate_limit_per_minute
        if request.url.path in PUBLIC_PATHS:
            return
        client = request.client.host if request.client else "anonymous"
        now = time.monotonic()
        window_start = now - 60
        bucket = self._hits[client]
        while bucket and bucket[0] < window_start:
            bucket.popleft()
        if len(bucket) >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded ({limit} requests per minute)",
            )
        bucket.append(now)


rate_limiter = RateLimiter()
