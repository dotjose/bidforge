from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.contracts.errors import ErrorResponse, error_response
from app.core.auth import CurrentUser, get_current_user
from app.core.config import settings
from app.modules.proposal.pdf_export import build_proposal_pdf_bytes
from app.integrations.proposal_store import (
    fetch_freelance_win_memory_rows,
    get_proposal_run,
    list_proposal_runs,
    merge_proposal_run_output_metadata,
    update_proposal_run_pattern,
)
from app.contracts.proposal_public import (
    ProposalPublicRunResponse,
    ProposalSavedRunPublic,
    build_public_from_stored_proposal_output,
    build_public_run_response,
)
from app.integrations.workspace_settings_store import upsert_workspace_settings_full
from bidforge_schemas import RagConfig, WorkspaceMemory, WorkspaceProposal, WorkspaceSettings, WorkspaceState

from app.integrations.supabase import probe_supabase_proposal_persistence_bundle
from app.pipeline.errors import FailedPipeline
from app.pipeline.orchestrator import execute_proposal_pipeline_async
from app.pipeline.title_inference import infer_proposal_title
from app.workspace.agents import (
    effective_pipeline_request_mode,
    run_document_normalizer_agent,
    run_settings_injector_agent,
    run_workspace_builder_agent,
    workspace_generation_rfp,
    workspace_rfp_plain,
)

log = logging.getLogger(__name__)


def _pipeline_failed_user_hint(failed_step: str | None, message: str) -> str:
    """Short actionable suffix for 502 PIPELINE_FAILED (full detail remains in server logs)."""
    fs = (failed_step or "").lower()
    msg = (message or "").lower()
    if "openrouter" in msg or "404" in msg or "llmtransport" in msg or "connection" in msg:
        return " Hint: check OPENROUTER_API_KEY and OPENROUTER_MODEL_PRIMARY on openrouter.ai/models."
    if "proposal_events" in fs or "proposal_node_cache" in fs:
        return " Hint: run Supabase migrations for DAG tables, or set STRICT_PROPOSAL_PERSISTENCE=0 in development."
    if "supabase_persist" in fs or "proposal_not_saved" in msg:
        return " Hint: verify SUPABASE_URL / key and public.proposals visibility."
    if fs:
        return f" Hint: failed_step={failed_step!s} — see API logs for this trace_id."
    return ""


router = APIRouter(tags=["proposal"])


class ProposalWorkspaceInput(BaseModel):
    """Per-run overlays merged into WorkspaceState before SettingsInjector + pipeline."""

    model_config = ConfigDict(populate_by_name=True)

    tone: str = ""
    writing_style: str = ""
    openrouter_model_primary: str = Field(
        default="",
        alias="openrouterModelPrimary",
        max_length=200,
        description="Optional OpenRouter model id for this run (overrides saved workspace default).",
    )
    proposal_mode: Literal["auto", "enterprise", "freelance"] = Field(
        default="auto",
        alias="proposalMode",
        description="Overrides workspace default for this run only when not auto.",
    )
    rag: dict[str, Any] | None = None
    company_profile: dict[str, Any] | None = Field(default=None, alias="companyProfile")


def _merge_workspace_overlay(ws: WorkspaceState, overlay: ProposalWorkspaceInput | None) -> WorkspaceState:
    if overlay is None:
        return ws
    s = ws.settings.model_dump()
    if overlay.tone.strip():
        s["tone"] = overlay.tone.strip()[:4000]
    if overlay.writing_style.strip():
        s["writing_style"] = overlay.writing_style.strip()[:8000]
    if overlay.openrouter_model_primary.strip():
        s["openrouter_model_primary"] = overlay.openrouter_model_primary.strip()[:200]
    if overlay.proposal_mode != "auto":
        s["proposal_mode"] = overlay.proposal_mode
    if overlay.company_profile:
        s["company_profile"] = {**(s.get("company_profile") or {}), **overlay.company_profile}
    if overlay.rag:
        rg = {**(s.get("rag") or {}), **overlay.rag}
        s["rag"] = RagConfig.model_validate(
            {
                "enabled": bool(rg.get("enabled", True)),
                "enterprise_case_studies": bool(rg.get("enterprise_case_studies", True)),
                "freelance_win_memory": bool(rg.get("freelance_win_memory", True)),
            }
        )
    return ws.model_copy(update={"settings": WorkspaceSettings.model_validate(s)})


class ProposalRunRequest(BaseModel):
    """Run the deterministic proposal pipeline on RFP text."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "examples": [
                {
                    "rfp": "Section 1: scope…\nSection 2: compliance (SOC 2)…",
                    "job_description": "Optional alias of `rfp` for legacy clients.",
                    "rfp_id": "opportunity-2026-0421",
                }
            ]
        },
    )

    rfp_id: str | None = Field(default=None, max_length=128, description="Optional stable id for tracing.")
    pipeline_mode: Literal["auto", "enterprise", "freelance"] = Field(
        default="auto",
        alias="pipelineMode",
        description="auto: classify input; enterprise: RFP brain; freelance: job-post proposal path.",
    )
    rfp: str = Field(
        ...,
        min_length=1,
        max_length=120_000,
        alias="job_description",
        description="Primary RFP or job description body.",
    )
    workspace: ProposalWorkspaceInput | None = Field(
        default=None,
        description="Optional per-run settings overlay (tone, RAG toggles) merged before pipeline.",
    )
    draft_intensity: Literal["balanced", "strong", "weak"] = Field(
        default="balanced",
        alias="draftIntensity",
        description="Shapes tone and assertiveness for this run (threaded into workspace prefs / brief).",
    )
    continuation_run_id: str | None = Field(
        default=None,
        alias="continuationRunId",
        max_length=120,
        description="Optional prior saved run id — chains pipeline_state.previous_run_ids for incremental drafts.",
    )
    learning_snippet: str | None = Field(
        default=None,
        alias="learningSnippet",
        max_length=4000,
        description="User-saved pattern or operator cues appended to the generation brief (UTF-8).",
    )
    proposal_depth: Literal["short", "full"] = Field(
        default="full",
        alias="proposalDepth",
        description="Job-post path: concise vs full depth (same structure).",
    )

    @model_validator(mode="after")
    def _enforce_rfp_size(self) -> ProposalRunRequest:
        if len(self.rfp) > settings.rfp_max_chars:
            raise ValueError(f"RFP exceeds maximum length ({settings.rfp_max_chars} characters)")
        return self


class MemoryPatternItemOut(BaseModel):
    label: str
    outcome: str


class ProposalRunSummaryOut(BaseModel):
    id: str
    title: str
    score: int
    trace_id: str
    pipeline_mode: str
    created_at: str


def build_proposal_run_summaries(clerk_user_id: str, *, limit: int = 50) -> list[ProposalRunSummaryOut]:
    rows = list_proposal_runs(clerk_user_id, limit=limit)
    out: list[ProposalRunSummaryOut] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        cid = r.get("created_at")
        out.append(
            ProposalRunSummaryOut(
                id=str(r.get("id") or ""),
                title=str(r.get("title") or ""),
                score=int(r.get("score") or 0),
                trace_id=str(r.get("trace_id") or ""),
                pipeline_mode=str(r.get("pipeline_mode") or "enterprise"),
                created_at=str(cid) if cid is not None else "",
            )
        )
    return out


def _persist_after_successful_proposal_run(
    clerk_user_id: str,
    ws: WorkspaceState,
    rfp_id: str | None,
    result: dict[str, Any],
) -> None:
    """Upsert workspace settings used for this run; attach settings snapshot + rfp_id to saved proposal row."""
    rag_c = {**ws.settings.rag.model_dump(), "proposal_mode": ws.settings.proposal_mode}
    upsert_workspace_settings_full(
        clerk_user_id,
        {
            "company_profile": ws.settings.company_profile,
            "tone": ws.settings.tone,
            "writing_style": ws.settings.writing_style,
            "openrouter_model_primary": ws.settings.openrouter_model_primary,
            "rag_config": rag_c,
        },
    )
    snap = {
        "user_id": clerk_user_id,
        "tone": ws.settings.tone,
        "writing_style": ws.settings.writing_style,
        "mode": str(ws.settings.proposal_mode),
        "rag_enabled": bool(ws.settings.rag.enabled),
        "rag_config": ws.settings.rag.model_dump(),
        "company_profile": ws.settings.company_profile,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    pid = result.get("persisted_run_id")
    if pid and str(pid).strip():
        merge_proposal_run_output_metadata(
            clerk_user_id,
            str(pid).strip(),
            settings_snapshot=snap,
            rfp_id=rfp_id,
        )


class ProposalPatternRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    proposal_id: str = Field(..., max_length=120, alias="proposalId")
    pattern: Literal["strong", "weak", "saved"]


class ProposalPdfExportRequest(BaseModel):
    """Build a PDF from structured proposal fields (client supplies last run payload)."""

    title: str = Field(default="Proposal", max_length=256)
    sections: dict[str, str] = Field(
        default_factory=dict,
        description="Keys: executive_summary, technical_approach, delivery_plan, risk_management.",
    )
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    memory_appendix: str | None = Field(
        default=None,
        max_length=50_000,
        description="Deprecated — ignored. Use memory_insight_bullets for short pattern labels.",
    )
    score: int | None = Field(default=None, ge=0, le=100)
    issues: list[str] | None = Field(default=None, max_length=24)
    memory_insight_bullets: list[str] | None = Field(
        default=None,
        max_length=12,
        description="Short win-pattern labels only (no raw RFP or full documents).",
    )
    pipeline_mode: Literal["enterprise", "freelance"] = Field(
        default="enterprise",
        description="Freelance uses conversion-style section headings in the PDF.",
    )


@router.post(
    "/run",
    response_model=ProposalPublicRunResponse,
    summary="Run proposal pipeline",
    description=(
        "Executes the 5-node DAG (router → job_intel → solution → proposal → verifier; then persist). "
        "Requires `Authorization: Bearer` with a valid Clerk session JWT unless `SKIP_AUTH` is enabled for local dev. "
        f"Server-side deadline: **{settings.pipeline_timeout_s}s** (504 on timeout). "
        f"Max RFP size: **{settings.rfp_max_chars}** characters."
    ),
    response_description="Sanitized client contract: title, sections, score, issues, memory_used flag, diff summary.",
    responses={
        422: {"model": ErrorResponse, "description": "Validation or RFP size violation"},
        503: {"model": ErrorResponse, "description": "LLM provider not configured"},
        504: {"model": ErrorResponse, "description": "Pipeline exceeded server timeout"},
        401: {"model": ErrorResponse, "description": "Missing or invalid bearer token"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        502: {"model": ErrorResponse, "description": "Pipeline agent failed (strict orchestrator)"},
        503: {
            "model": ErrorResponse,
            "description": "Supabase not configured, schema missing, or proposal row not persisted",
        },
    },
)
async def run_proposal(
    body: ProposalRunRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> ProposalPublicRunResponse:
    if settings.persistence_strict_enforced():
        gate = probe_supabase_proposal_persistence_bundle()
        if gate == "no_env":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=error_response(
                    code="ENV_NOT_LOADED",
                    message="Supabase credentials are not configured; proposal runs cannot be persisted.",
                ),
            )
        if gate == "missing_table":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=error_response(
                    code="SUPABASE_SCHEMA_MISSING",
                    message=(
                        "public.proposals and public.proposal_events must both be visible to the API. "
                        "Apply infra/supabase migrations (including proposal DAG tables) and reload the PostgREST schema."
                    ),
                ),
            )
        if gate == "error":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=error_response(
                    code="SUPABASE_UNAVAILABLE",
                    message="Could not reach Supabase to verify persistence. Retry shortly.",
                ),
            )
    try:
        norm = run_document_normalizer_agent(
            raw_bytes=None,
            raw_text=body.rfp.strip(),
            source="text",
        )
        ws = run_workspace_builder_agent(norm, user.user_id, source="text")
        ws = _merge_workspace_overlay(ws, body.workspace)
        ws = run_settings_injector_agent(ws, user.user_id)
        r_core = workspace_rfp_plain(ws)
        r_gen = workspace_generation_rfp(ws)
        learn = (body.learning_snippet or "").strip()
        if learn:
            r_gen = (
                f"{r_gen}\n[USER_PATTERN — honor voice and structure; never copy verbatim; "
                "never invent credentials]\n"
                f"{learn[:4000]}\n"
            )
        cont = (body.continuation_run_id or "").strip()
        prior_ids: list[str] = []
        if cont:
            prior_ids = [cont]
            prev_row = get_proposal_run(user.user_id, cont)
            po = prev_row.get("proposal_output") if isinstance(prev_row, dict) else None
            if isinstance(po, dict):
                ps = po.get("pipeline_state")
                if isinstance(ps, dict):
                    ch = ps.get("previous_run_ids")
                    if isinstance(ch, list):
                        tail = [str(x) for x in ch if str(x).strip()][-7:]
                        prior_ids = [*tail, cont] if cont not in tail else tail
        pm = effective_pipeline_request_mode(ws, body.pipeline_mode)
        result = await execute_proposal_pipeline_async(
            r_core,
            user.user_id,
            rfp_id=body.rfp_id,
            pipeline_mode=pm,
            workspace_snapshot=ws.model_dump(),
            rfp_for_generation=r_gen,
            draft_intensity=body.draft_intensity,
            prior_run_ids=prior_ids or None,
            learning_snippet_applied=bool(learn),
            proposal_depth=body.proposal_depth,
        )
        rid = str(result.get("run_id") or result.get("trace_id") or "")
        ws_out = ws.model_copy(
            update={
                "trace_id": rid,
                "memory": WorkspaceMemory(
                    rag_context_summary=dict(result.get("memory_used") or {}),
                    last_retrieval_mode=str(result.get("pipeline_mode") or ""),
                ),
                "proposal": WorkspaceProposal(status="complete", score=int(result.get("score") or 0)),
            }
        )
        result = {**result, "workspace_state": ws_out.model_dump()}
        try:
            _persist_after_successful_proposal_run(
                user.user_id,
                ws,
                body.rfp_id,
                result,
            )
        except Exception as e:  # noqa: BLE001
            log.warning("post-run persistence hook failed: %s", e)
    except RuntimeError as e:
        msg = str(e)
        if "OPENROUTER" in msg.upper():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=error_response(code="SERVICE_UNAVAILABLE", message=msg),
            ) from e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response(code="INTERNAL_ERROR", message=msg),
        ) from e
    except asyncio.TimeoutError as e:
        budget_s = float(settings.pipeline_timeout_s)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=error_response(
                code="TIMEOUT",
                message=(
                    f"The proposal run exceeded the server time limit ({budget_s:g}s; raise PIPELINE_TIMEOUT_S). "
                    "Common causes: OpenRouter slow or unreachable (check OPENROUTER_API_KEY and network), or many "
                    "LLM retries. For Langfuse noise in local logs, clear LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY."
                ),
            ),
        ) from e
    except FailedPipeline as e:
        log.warning("pipeline failed trace_id=%s step=%s", str(e.trace_id)[:32], e.failed_step)
        hint = _pipeline_failed_user_hint(e.failed_step, str(e))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=error_response(
                code="PIPELINE_FAILED",
                message=str(e) + hint,
                failed_step=e.failed_step,
                trace_id=str(e.trace_id) if e.trace_id else None,
            ),
        ) from e
    rid = str(result.get("run_id") or result.get("trace_id") or "")
    if settings.persistence_strict_enforced() and not result.get("persisted_run_id"):
        log.error("persisted_run_id missing after pipeline trace_id=%s", rid[:32])
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_response(
                code="PROPOSAL_NOT_SAVED",
                message="Pipeline completed but the proposal row was not persisted.",
                trace_id=rid or None,
            ),
        )
    if not result.get("persisted_run_id"):
        log.warning(
            "persisted_run_id missing after pipeline trace_id=%s",
            rid[:32],
        )
    cross_delta = int(result.get("cross_diff_delta_score") or 0)
    pm = "freelance" if result.get("pipeline_mode") == "freelance" else "enterprise"
    prop = result.get("proposal") if isinstance(result.get("proposal"), dict) else None
    diff_raw = result.get("cross_proposal_diff") if isinstance(result.get("cross_proposal_diff"), dict) else None
    return build_public_run_response(
        proposal=prop,
        score=int(result.get("score") or 0),
        issues=list(result.get("issues") or []),
        title=str(result.get("title") or ""),
        pipeline_mode=pm,
        memory_grounded=bool(result.get("memory_grounded", True)),
        memory_status=str(result.get("memory_status") or ""),
        memory_used=dict(result.get("memory_used") or {}) if isinstance(result.get("memory_used"), dict) else None,
        cross_proposal_diff=diff_raw,
        persisted_run_id=str(result["persisted_run_id"]) if result.get("persisted_run_id") else None,
        run_id=rid,
        cross_diff_delta_score=cross_delta,
    )


@router.get(
    "/runs",
    response_model=list[ProposalRunSummaryOut],
    summary="List saved proposal runs",
)
async def list_saved_runs(user: Annotated[CurrentUser, Depends(get_current_user)]) -> list[ProposalRunSummaryOut]:
    return build_proposal_run_summaries(user.user_id, limit=50)


@router.post(
    "/pattern",
    summary="Persist operator pattern on a saved proposal run",
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def persist_proposal_pattern(
    body: ProposalPatternRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, str]:
    rid = body.proposal_id.strip()
    if not rid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=error_response(code="VALIDATION_ERROR", message="proposal_id is required."),
        )
    ok = update_proposal_run_pattern(user.user_id, rid, pattern=body.pattern)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_response(code="NOT_FOUND", message="Proposal run not found."),
        )
    return {"status": "ok", "proposal_id": rid, "pattern": body.pattern}


@router.get(
    "/runs/{run_id}",
    response_model=ProposalSavedRunPublic,
    summary="Get one saved proposal run (sanitized)",
    responses={404: {"model": ErrorResponse}},
)
async def get_saved_run(
    run_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> ProposalSavedRunPublic:
    row = get_proposal_run(user.user_id, run_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_response(code="NOT_FOUND", message="Proposal run not found."),
        )
    po = row.get("proposal_output")
    if not isinstance(po, dict):
        po = {}
    issues_raw = row.get("issues")
    issues_list: list[Any]
    if isinstance(issues_raw, list):
        issues_list = issues_raw
    else:
        issues_list = []
    return build_public_from_stored_proposal_output(
        po,
        row_title=str(row.get("title") or ""),
        row_score=int(row.get("score") or 0),
        row_issues=issues_list,
        row_id=str(row.get("id") or ""),
        rfp_input=str(row.get("rfp_input") or ""),
        row_pipeline_mode=str(row.get("pipeline_mode") or ""),
    )


@router.get(
    "/memory/patterns",
    response_model=list[MemoryPatternItemOut],
    summary="Human-readable win hooks for Memory tab (no embeddings)",
)
async def list_memory_patterns(
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> list[MemoryPatternItemOut]:
    rows = fetch_freelance_win_memory_rows(user.user_id, limit=16)
    out: list[MemoryPatternItemOut] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        hook = str(r.get("opening_hook") or "").strip()
        if not hook:
            continue
        jt = str(r.get("job_type") or "pattern")
        out.append(MemoryPatternItemOut(label=hook[:200] + ("…" if len(hook) > 200 else ""), outcome=jt))
    return out


@router.post(
    "/export/pdf",
    summary="Export proposal PDF",
    description="Renders title, executive summary, technical approach, timeline, and risks only (authenticated).",
    responses={401: {"model": ErrorResponse}},
)
async def export_proposal_pdf(
    body: ProposalPdfExportRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> Response:
    _ = user
    pdf_bytes = build_proposal_pdf_bytes(
        title=body.title,
        sections=body.sections,
        timeline=body.timeline,
        pipeline_mode=body.pipeline_mode,
        score=body.score,
        issues=body.issues,
        memory_insight_bullets=body.memory_insight_bullets,
        memory_appendix=None,
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="proposal-export.pdf"'},
    )
