"""Proposal memory: embed → Supabase vector match → structured context (mandatory when configured)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID

from bidforge_schemas import RagContext
from bidforge_shared import OpenRouterLLM

from app.core.config import settings
from app.integrations.supabase import get_supabase_client

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)


def _resolve_internal_user_id(clerk_user_id: str) -> UUID | None:
    """Map Clerk id → tenant uuid using only `public.users.id` (vector RPC expects uuid `filter_user_id`)."""
    sb = get_supabase_client()
    if sb is None or not clerk_user_id:
        return None
    try:
        r = sb.table("users").select("id").eq("clerk_user_id", clerk_user_id).limit(1).execute()
    except Exception as e:  # noqa: BLE001
        log.warning("users lookup failed: %s", e)
        return None
    rows = getattr(r, "data", None) or []
    if not rows or not isinstance(rows[0], dict):
        return None
    row = rows[0]
    raw = row.get("id")
    if raw is None:
        log.warning("users row missing id for clerk_user_id=%r", clerk_user_id[:32])
        return None
    try:
        return UUID(str(raw))
    except (ValueError, TypeError):
        log.warning("users.id is not a valid uuid: %r", raw)
        return None


def _meta(row: dict[str, Any]) -> dict[str, Any]:
    m = row.get("metadata") or {}
    if isinstance(m, str):
        return {}
    return m if isinstance(m, dict) else {}


def _rows_to_context(rows: list[dict[str, Any]], *, memory_scope: str = "enterprise") -> RagContext:
    similar: list[dict[str, Any]] = []
    win_patterns: list[dict[str, Any]] = []
    methodology: list[dict[str, Any]] = []
    flat_templates: list[str] = []
    freelance_wins: list[dict[str, Any]] = []

    for row in rows:
        meta = _meta(row)
        mem_type = str(meta.get("type") or "proposal_section").lower()
        excerpt = (row.get("content") or "")[:2000]
        rid = str(row.get("id", ""))
        outcome = str(meta.get("outcome") or "unknown")
        title = str(meta.get("title") or meta.get("source") or "Proposal memory")
        section_type = str(meta.get("section_type") or "")
        tags = meta.get("tags") if isinstance(meta.get("tags"), list) else []
        score = meta.get("score")

        base = {
            "id": rid,
            "title": title,
            "excerpt": excerpt,
            "outcome": outcome,
            "section_type": section_type,
            "similarity": row.get("similarity"),
            "tags": tags,
            "score": score,
        }

        if mem_type == "freelance_win_pattern":
            if memory_scope != "freelance":
                continue
            metrics = meta.get("metrics") if isinstance(meta.get("metrics"), dict) else {}
            job_type = str(meta.get("job_type") or meta.get("platform") or "upwork")
            freelance_wins.append(
                {
                    "id": rid,
                    "label": title,
                    "excerpt": excerpt,
                    "outcome": outcome,
                    "tags": tags,
                    "job_type": job_type,
                    "metrics": metrics,
                    "similarity": row.get("similarity"),
                }
            )
            continue

        if memory_scope == "freelance":
            continue

        if mem_type == "win_pattern":
            win_patterns.append(
                {
                    "id": rid,
                    "label": title,
                    "excerpt": excerpt,
                    "outcome": outcome,
                    "tags": tags,
                }
            )
        elif mem_type == "methodology":
            methodology.append(
                {
                    "id": rid,
                    "title": title,
                    "content": excerpt,
                    "tags": tags,
                }
            )
            if excerpt:
                flat_templates.append(excerpt[:400])
        else:
            similar.append(base)
            tpl = meta.get("company_templates") or meta.get("templates")
            if isinstance(tpl, list):
                flat_templates.extend(str(t) for t in tpl if t)
            elif isinstance(tpl, str) and tpl:
                flat_templates.append(tpl)

    return RagContext(
        similar_proposals=similar[:16],
        win_patterns=win_patterns[:20],
        methodology_blocks=methodology[:20],
        company_templates=list(dict.fromkeys(flat_templates))[:20],
        freelance_win_patterns=freelance_wins[:24],
    )


def _rpc_match(
    sb: Any,
    emb: list[float],
    match_count: int,
    uid: UUID,
    rpc_name: str,
) -> list[dict[str, Any]]:
    res = sb.rpc(
        rpc_name,
        {
            "query_embedding": emb,
            "match_count": match_count,
            "filter_user_id": str(uid),
        },
    ).execute()
    rows = getattr(res, "data", None) or []
    return rows if isinstance(rows, list) else []


def retrieve_rag_context(
    rfp_text: str,
    clerk_user_id: str,
    *,
    llm: OpenRouterLLM | None = None,
    match_count: int = 12,
    requirement_context: str | None = None,
    memory_scope: str = "enterprise",
) -> RagContext:
    """Embedding + vector search. Tenant isolation via internal user id (maps to company memory rows)."""
    sb = get_supabase_client()
    if sb is None or not settings.openrouter_api_key:
        return RagContext()
    uid = _resolve_internal_user_id(clerk_user_id)
    if uid is None:
        return RagContext()

    client = llm
    if client is None:
        client = OpenRouterLLM(
            api_key=settings.openrouter_api_key,
            primary_model=settings.openrouter_model_primary,
            fallback_model=settings.openrouter_model_fallback,
            embedding_model=settings.openrouter_embedding_model,
            timeout_s=min(settings.per_agent_timeout_s, 45.0),
            http_referer=settings.openrouter_http_referer,
        )
    scope = (memory_scope or "enterprise").lower()
    effective_match = 24 if scope == "freelance" else match_count

    q = (requirement_context or "").strip()
    if q:
        embed_input = f"{q[:4000]}\n\n---\n\n{(rfp_text or '')[:6000]}"
    else:
        embed_input = rfp_text or ""
    try:
        emb = client.embed_text(embed_input)
    except Exception as e:  # noqa: BLE001
        log.warning("embedding failed (RAG empty): %s", e)
        return RagContext()

    rows: list[dict[str, Any]] = []
    for rpc in ("match_proposal_memory", "match_documents"):
        try:
            rows = _rpc_match(sb, emb, effective_match, uid, rpc)
            if rows:
                break
        except Exception as e:  # noqa: BLE001
            log.debug("rpc %s failed: %s", rpc, e)
            continue

    return _rows_to_context(rows, memory_scope=scope)
