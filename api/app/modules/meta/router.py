from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings
from app.integrations.supabase import get_supabase_proposals_readable, supabase_project_ref_from_url

router = APIRouter(tags=["meta"])


@router.get(
    "/version",
    summary="API and pipeline contract version",
    response_model_exclude_none=False,
    openapi_extra={"security": []},
)
async def api_version() -> dict[str, str | int | float | bool | None]:
    """Stable contract metadata for frontends and integrations."""
    return {
        "version": "1.0.0",
        "pipeline": "5-node-dag-v1",
        "rfp_max_chars": settings.rfp_max_chars,
        "pipeline_timeout_s": settings.pipeline_timeout_s,
        "per_agent_timeout_s": settings.per_agent_timeout_s,
        # True when the API process loaded non-empty SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY
        # (from api/.env or environment). Does not guarantee inserts succeed (schema/RLS/network).
        "supabase_env_loaded": bool(settings.supabase_url.strip() and settings.supabase_service_role_key.strip()),
        # Parsed from SUPABASE_URL — compare with Supabase Dashboard → Settings → General (Project ID).
        "supabase_project_ref": supabase_project_ref_from_url(),
        # True after startup if public.proposals responded to PostgREST; False if missing (wrong project / no migration).
        "supabase_proposals_readable": get_supabase_proposals_readable(),
        "langfuse_credentials_loaded": bool(
            settings.langfuse_public_key.strip() and settings.langfuse_secret_key.strip()
        ),
        "langfuse_tracing_enabled": settings.is_langfuse_tracing_enabled(),
    }
