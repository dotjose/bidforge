"""Per-IP sliding-window rate limiting (in-process; swap for Redis at scale)."""

from __future__ import annotations

import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.contracts.errors import error_response
from app.core.config import settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: object) -> None:
        super().__init__(app)
        self._window_s = 60.0
        self._hits: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        limit = settings.rate_limit_per_minute
        if limit <= 0:
            return await call_next(request)
        client = request.client
        ip = client.host if client else "unknown"
        now = time.monotonic()
        cutoff = now - self._window_s
        arr = [t for t in self._hits[ip] if t > cutoff]
        reset_epoch = int(time.time() + self._window_s)

        if len(arr) >= limit:
            body = error_response(
                code="RATE_LIMITED",
                message="Too many requests — try again shortly.",
            )
            resp = JSONResponse(status_code=429, content=body)
            resp.headers["X-RateLimit-Limit"] = str(limit)
            resp.headers["X-RateLimit-Remaining"] = "0"
            resp.headers["X-RateLimit-Reset"] = str(reset_epoch)
            return resp

        arr.append(now)
        self._hits[ip] = arr
        remaining_after = max(0, limit - len(arr))
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining_after)
        response.headers["X-RateLimit-Reset"] = str(reset_epoch)
        return response
