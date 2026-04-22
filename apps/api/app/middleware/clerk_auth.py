"""Enforce Clerk JWT on every request except explicit public routes."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.contracts.errors import error_response
from app.core.auth import CurrentUser, verify_clerk_bearer_token
from app.core.config import settings

_PUBLIC_PATHS: frozenset[str] = frozenset(
    {
        "/health",
        "/api/version",
        "/docs",
        "/redoc",
        "/openapi.json",
    }
)


def _is_public_path(path: str) -> bool:
    p = path.rstrip("/") or "/"
    if p in _PUBLIC_PATHS:
        return True
    # OpenAPI sub-resources when mounted
    return p.startswith("/openapi")


class ClerkAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path
        if _is_public_path(path):
            return await call_next(request)

        if settings.skip_auth:
            request.state.clerk_user = CurrentUser(user_id="dev_user", email="dev@example.com")
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return JSONResponse(
                status_code=401,
                content=error_response(code="UNAUTHORIZED", message="Missing bearer token"),
            )
        try:
            user = verify_clerk_bearer_token(auth_header)
        except ValueError:
            return JSONResponse(
                status_code=401,
                content=error_response(code="UNAUTHORIZED", message="Invalid token"),
            )

        request.state.clerk_user = user
        return await call_next(request)
