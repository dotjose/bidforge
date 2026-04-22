from __future__ import annotations

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from app.core.auth import CurrentUser, get_current_user
from app.core.config import settings
from app.integrations.supabase import get_supabase_client
from app.rag.retrieval import _resolve_internal_user_id
from bidforge_shared import LLMTransportError, OpenRouterLLM

router = APIRouter(prefix="/documents", tags=["documents"])
log = logging.getLogger(__name__)


@router.get("/")
async def list_documents(user: Annotated[CurrentUser, Depends(get_current_user)]) -> dict:
    return {"user_id": user.user_id, "items": []}


class MemoryFeedbackBody(BaseModel):
    """Store post-generation feedback for future indexing."""

    content: str = Field(..., min_length=1, max_length=120_000)
    user_feedback: Literal["positive", "negative"]
    memory_type: Literal["proposal_section", "win_pattern", "methodology"] = "proposal_section"


class WinPatternBody(BaseModel):
    """User-captured reusable pattern for proposal memory."""

    content: str = Field(..., min_length=1, max_length=50_000)
    title: str = Field(default="Win pattern", max_length=256)
    tags: list[str] = Field(default_factory=list)
    pattern_kind: Literal["win_pattern", "freelance_win_pattern"] = "win_pattern"

    @field_validator("tags", mode="after")
    @classmethod
    def _cap_tags(cls, v: list[str]) -> list[str]:
        out: list[str] = []
        for t in v[:32]:
            s = (t or "").strip()
            if s and s not in out:
                out.append(s[:128])
        return out


def _require_supabase():
    sb = get_supabase_client()
    if sb is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase is not configured",
        )
    return sb


@router.post("/memory/feedback")
async def save_memory_feedback(
    body: MemoryFeedbackBody,
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict:
    """Persist feedback loop rows (outcome pending until curated)."""
    sb = _require_supabase()
    uid = _resolve_internal_user_id(user.user_id)
    if uid is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not provisioned in BidForge storage yet.",
        )
    meta = {
        "type": body.memory_type,
        "outcome": "pending",
        "user_feedback": body.user_feedback,
        "title": "User feedback capture",
        "feedback": body.user_feedback,
    }
    try:
        sb.table("documents").insert(
            {
                "user_id": str(uid),
                "content": body.content,
                "source": "memory_feedback",
                "metadata": meta,
                "embedding": None,
            }
        ).execute()
    except Exception as e:  # noqa: BLE001
        log.exception("memory feedback insert failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store feedback",
        ) from e
    return {"status": "ok"}


@router.post("/memory/pattern")
async def save_win_pattern(
    body: WinPatternBody,
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict:
    """Save a user-extracted win pattern with embedding for RAG."""
    sb = _require_supabase()
    uid = _resolve_internal_user_id(user.user_id)
    if uid is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not provisioned in BidForge storage yet.",
        )
    if not settings.openrouter_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenRouter is required to embed new patterns",
        )
    client = OpenRouterLLM(
        api_key=settings.openrouter_api_key,
        primary_model=settings.openrouter_model_primary,
        fallback_model=settings.openrouter_model_fallback,
        embedding_model=settings.openrouter_embedding_model,
        timeout_s=min(settings.per_agent_timeout_s, 45.0),
        http_referer=settings.openrouter_http_referer,
    )
    try:
        emb = client.embed_text(body.content)
    except LLMTransportError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Embedding failed: {e!s}",
        ) from e
    meta = {
        "type": body.pattern_kind,
        "outcome": "pending",
        "title": body.title,
        "tags": body.tags,
        "job_type": "upwork",
        "metrics": {},
    }
    try:
        sb.table("documents").insert(
            {
                "user_id": str(uid),
                "content": body.content,
                "source": "user_pattern",
                "metadata": meta,
                "embedding": emb,
            }
        ).execute()
    except Exception as e:  # noqa: BLE001
        log.exception("win pattern insert failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store pattern",
        ) from e
    return {"status": "ok"}
