"""Proposal memory ingestion (RAG index)."""

from __future__ import annotations

import logging
import re
from typing import Annotated, Any, Literal
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from app.core.auth import CurrentUser, get_current_user
from app.core.config import settings
from app.integrations.supabase import get_supabase_client
from app.rag.retrieval import _resolve_internal_user_id
from bidforge_shared import LLMTransportError, OpenRouterLLM

router = APIRouter(prefix="/memory", tags=["memory"])
log = logging.getLogger(__name__)

_CHUNK = 1800


def _chunk_text(text: str) -> list[str]:
    raw = (text or "").strip()
    if not raw:
        return []
    parts = re.split(r"\n{2,}", raw)
    chunks: list[str] = []
    buf = ""
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if len(buf) + len(p) + 2 <= _CHUNK:
            buf = f"{buf}\n\n{p}" if buf else p
        else:
            if buf:
                chunks.append(buf)
            buf = p[:_CHUNK] if len(p) > _CHUNK else p
    if buf:
        chunks.append(buf)
    out: list[str] = []
    for c in chunks:
        if len(c) <= _CHUNK:
            out.append(c)
        else:
            for i in range(0, len(c), _CHUNK):
                out.append(c[i : i + _CHUNK])
    return out[:80]


class MemoryIngestBody(BaseModel):
    """Ingest past proposal text into vector memory (chunked + embedded)."""

    text: str = Field(..., min_length=1, max_length=500_000)
    title: str = Field(default="Imported proposal", max_length=256)
    outcome: Literal["won", "lost", "pending"] = "pending"
    memory_type: Literal["proposal_section", "win_pattern", "methodology", "freelance_win_pattern"] = (
        "proposal_section"
    )
    tags: list[str] = Field(default_factory=list)

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


@router.post("/ingest")
async def ingest_memory(
    body: MemoryIngestBody,
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, Any]:
    """Chunk, embed, and store proposal memory for the authenticated tenant."""
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
            detail="OpenRouter is required to embed memory",
        )

    chunks = _chunk_text(body.text)
    if not chunks:
        raise HTTPException(status_code=422, detail="No ingestable text after normalization")

    client = OpenRouterLLM(
        api_key=settings.openrouter_api_key,
        primary_model=settings.openrouter_model_primary,
        fallback_model=settings.openrouter_model_fallback,
        embedding_model=settings.openrouter_embedding_model,
        timeout_s=min(settings.per_agent_timeout_s, 45.0),
        http_referer=settings.openrouter_http_referer,
    )

    company_id = str(uid)
    inserted = 0
    for i, chunk in enumerate(chunks):
        meta: dict[str, Any] = {
            "type": body.memory_type,
            "outcome": body.outcome,
            "title": f"{body.title} (part {i + 1}/{len(chunks)})" if len(chunks) > 1 else body.title,
            "tags": body.tags,
            "company_id": company_id,
            "chunk_index": i,
            "chunk_total": len(chunks),
        }
        try:
            emb = client.embed_text(chunk)
        except LLMTransportError as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Embedding failed: {e!s}",
            ) from e
        try:
            sb.table("documents").insert(
                {
                    "user_id": str(uid),
                    "content": chunk,
                    "source": "memory_ingest",
                    "metadata": meta,
                    "embedding": emb,
                }
            ).execute()
        except Exception as e:  # noqa: BLE001
            log.exception("memory ingest insert failed")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to store memory chunk",
            ) from e
        inserted += 1

    return {"status": "ok", "chunks_indexed": inserted}
