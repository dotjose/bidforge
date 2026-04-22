"""OpenAPI customization — security schemes, tags, and global metadata."""

from __future__ import annotations

from typing import Any

from fastapi.openapi.utils import get_openapi

from app.core.config import settings


def build_openapi_schema(*, app: Any, title: str, version: str, description: str) -> dict[str, Any]:
    openapi_schema = get_openapi(
        title=title,
        version=version,
        openapi_version="3.1.0",
        description=description,
        routes=app.routes,
    )
    schemes = openapi_schema.setdefault("components", {}).setdefault("securitySchemes", {})
    http_bearer = schemes.get("HTTPBearer")
    clerk_desc = (
        "Clerk-issued session JWT (`Authorization: Bearer <token>`). "
        "The authenticated subject is always taken from this token — never from JSON bodies."
    )
    if isinstance(http_bearer, dict):
        http_bearer["bearerFormat"] = "JWT"
        http_bearer["description"] = clerk_desc
    else:
        schemes["HTTPBearer"] = {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": clerk_desc,
        }
    openapi_schema.setdefault("tags", [])
    tag_names = {t["name"] for t in openapi_schema["tags"] if isinstance(t, dict) and "name" in t}
    extra_tags = [
        {
            "name": "proposal",
            "description": (
                "Proposal generation. Pipeline runs synchronously with a server-side timeout "
                f"of **{settings.pipeline_timeout_s}s** (HTTP 504 on overrun). "
                f"RFP body is capped at **{settings.rfp_max_chars}** characters. "
                "Rate limits: see `X-RateLimit-*` response headers when enabled."
            ),
        },
        {
            "name": "meta",
            "description": "Version and capability metadata for clients.",
        },
        {
            "name": "health",
            "description": "Liveness and dependency flags.",
        },
    ]
    for t in extra_tags:
        if t["name"] not in tag_names:
            openapi_schema["tags"].append(t)

    openapi_schema["info"].setdefault("x-timeout-seconds", settings.pipeline_timeout_s)
    openapi_schema["info"].setdefault("x-rfp-max-chars", settings.rfp_max_chars)
    return openapi_schema


def attach_custom_openapi(app: Any) -> None:
    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema
        app.openapi_schema = build_openapi_schema(
            app=app,
            title=app.title,
            version=app.version,
            description=str(app.description or ""),
        )
        return app.openapi_schema

    app.openapi = custom_openapi  # type: ignore[method-assign]
