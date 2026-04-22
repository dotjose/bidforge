from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(tags=["meta"])


@router.get(
    "/version",
    summary="API and pipeline contract version",
    response_model_exclude_none=False,
    openapi_extra={"security": []},
)
async def api_version() -> dict[str, str | int | float]:
    """Stable contract metadata for frontends and integrations."""
    return {
        "version": "1.0.0",
        "pipeline": "deterministic-v1",
        "rfp_max_chars": settings.rfp_max_chars,
        "pipeline_timeout_s": settings.pipeline_timeout_s,
        "per_agent_timeout_s": settings.per_agent_timeout_s,
    }
