from __future__ import annotations

import asyncio
import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.contracts.errors import ErrorResponse, error_response
from app.core.auth import CurrentUser, get_current_user
from app.core.config import settings
from app.modules.proposal.pdf_export import build_proposal_pdf_bytes
from app.integrations.proposal_store import get_proposal_run, list_proposal_runs
from bidforge_schemas import RagConfig, WorkspaceMemory, WorkspaceProposal, WorkspaceSettings, WorkspaceState

from app.pipeline.errors import FailedPipeline
from app.pipeline.orchestrator import execute_proposal_pipeline_async
from app.pipeline.run_envelope import build_insights, minimal_degraded_proposal
from app.pipeline.title_inference import infer_proposal_title
from app.workspace.agents import (
    effective_pipeline_request_mode,
    run_document_normalizer_agent,
    run_settings_injector_agent,
    run_workspace_builder_agent,
    workspace_generation_rfp,
    workspace_rfp_plain,
)

router = APIRouter(tags=["proposal"])


class ProposalWorkspaceInput(BaseModel):
    """Per-run overlays merged into WorkspaceState before SettingsInjector + pipeline."""

    model_config = ConfigDict(populate_by_name=True)

    tone: str = ""
    writing_style: str = ""
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
        description="auto: classify input; enterprise: RFP brain; freelance: Win Engine (hook-first).",
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

    @model_validator(mode="after")
    def _enforce_rfp_size(self) -> ProposalRunRequest:
        if len(self.rfp) > settings.rfp_max_chars:
            raise ValueError(f"RFP exceeds maximum length ({settings.rfp_max_chars} characters)")
        return self


class ProposalRunResponse(BaseModel):
    """Successful pipeline completion (HTTP 200)."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "proposal": {
                        "sections": {
                            "executive_summary": "…",
                            "technical_approach": "…",
                            "delivery_plan": "…",
                            "risk_management": "…",
                        },
                        "format_notes": [],
                        "strategy": {"strategy": "…", "based_on": []},
                        "memory_summary": {
                            "similar_proposals": [],
                            "win_patterns": [],
                            "methodology_blocks": [],
                        },
                        "memory_grounded": True,
                        "grounding_warning": None,
                        "section_attributions": [],
                    },
                    "score": 82,
                    "issues": ["missing_requirement:…"],
                    "trace_id": "550e8400e29b41d4716646655440000",
                    "memory_grounded": True,
                    "grounding_warning": None,
                    "timeline": [{"phase": "Discovery", "duration": "2 weeks"}],
                    "memory_used": {
                        "similar_proposals": [],
                        "win_patterns": [],
                        "methodology_blocks": [],
                    },
                    "status": "success",
                    "pipeline_metadata": {
                        "pipeline_timeout_s": 120.0,
                        "per_agent_timeout_s": 30.0,
                        "rfp_max_chars": 120000,
                    },
                }
            ]
        }
    )

    proposal: dict[str, Any]
    score: int
    issues: list[str]
    suggestions: list[str] = Field(
        default_factory=list,
        description="Verifier-authored remediation hints; not part of the proposal body.",
    )
    trace_id: str
    memory_grounded: bool = Field(
        default=True,
        description="False when no indexed proposal memory was available for this run.",
    )
    grounding_warning: str | None = Field(
        default=None,
        description="Shown when the draft was not historically grounded.",
    )
    status: Literal["success", "degraded"] = Field(
        default="success",
        description="`success` for a full run; `degraded` when the service returned a usable minimal draft.",
    )
    run_id: str = Field(default="", description="Stable id for this proposal run (support).")
    insights: dict[str, Any] = Field(
        default_factory=dict,
        description="Warnings, missing-context flags, and fallback indicators (customer-safe).",
    )
    pipeline_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Non-sensitive echo of server limits (timeouts, max RFP size).",
    )
    timeline: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Deterministic timeline phases extracted from the RFP and requirement matrix.",
    )
    memory_used: dict[str, Any] = Field(
        default_factory=dict,
        description="Echo of retrieval: similar proposals, win patterns, methodology blocks.",
    )
    pipeline_mode: Literal["enterprise", "freelance"] = Field(
        default="enterprise",
        description="Which cognitive path produced this response.",
    )
    input_classification: dict[str, Any] | None = Field(
        default=None,
        description="Classifier output when pipeline_mode was auto or echo of manual override.",
    )
    job_understanding: dict[str, Any] | None = None
    hook: dict[str, Any] | None = Field(default=None, description="Freelance hook agent output when applicable.")
    critique: dict[str, Any] | None = Field(default=None, description="Mode-aware improvement suggestions.")
    verifier_metrics: dict[str, Any] | None = Field(
        default=None,
        description="Sub-scores: enterprise compliance/completeness or freelance reply/hook/trust/conciseness.",
    )
    reply_likelihood_0_100: int | None = Field(
        default=None,
        description="0–100 reply likelihood (freelance); null for enterprise.",
    )
    title: str = Field(
        default="",
        description="Job-specific title derived from RFP / job post / intent (never a product placeholder).",
    )
    cross_proposal_diff: dict[str, Any] | None = Field(
        default=None,
        description="CrossProposalDiffAgent output: hooks, signals, CTA, structure vs last wins.",
    )
    persisted_run_id: str | None = Field(
        default=None,
        description="UUID of the row in `proposal_runs` when persistence succeeded.",
    )
    workspace_state: dict[str, Any] = Field(
        default_factory=dict,
        description="Canonical WorkspaceState echo after run (RFP slice, settings, memory echo, trace).",
    )


class ProposalRunSummaryOut(BaseModel):
    id: str
    title: str
    score: int
    trace_id: str
    pipeline_mode: str
    created_at: str


class ProposalRunDetailOut(BaseModel):
    id: str
    title: str
    score: int
    trace_id: str
    pipeline_mode: str
    created_at: str
    rfp_input: str
    proposal_output: dict[str, Any]
    issues: list[Any]


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
    response_model=ProposalRunResponse,
    summary="Run proposal pipeline",
    description=(
        "Executes the memory-first pipeline (extraction → structuring → RAG → strategy → proposal → timeline → format → verify). "
        "Requires `Authorization: Bearer` with a valid Clerk session JWT unless `SKIP_AUTH` is enabled for local dev. "
        f"Server-side deadline: **{settings.pipeline_timeout_s}s** (504 on timeout). "
        f"Max RFP size: **{settings.rfp_max_chars}** characters."
    ),
    response_description="Structured proposal, verifier score, flattened issues, and trace id.",
    responses={
        422: {"model": ErrorResponse, "description": "Validation or RFP size violation"},
        503: {"model": ErrorResponse, "description": "LLM provider not configured"},
        504: {"model": ErrorResponse, "description": "Pipeline exceeded server timeout"},
        401: {"model": ErrorResponse, "description": "Missing or invalid bearer token"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    },
)
async def run_proposal(
    body: ProposalRunRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> ProposalRunResponse:
    meta = {
        "pipeline_timeout_s": settings.pipeline_timeout_s,
        "per_agent_timeout_s": settings.per_agent_timeout_s,
        "rfp_max_chars": settings.rfp_max_chars,
    }
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
        pm = effective_pipeline_request_mode(ws, body.pipeline_mode)
        result = await execute_proposal_pipeline_async(
            r_core,
            user.user_id,
            rfp_id=body.rfp_id,
            pipeline_mode=pm,
            workspace_snapshot=ws.model_dump(),
            rfp_for_generation=r_gen,
            draft_intensity=body.draft_intensity,
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
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=error_response(
                code="TIMEOUT",
                message="Proposal pipeline timed out.",
            ),
        ) from e
    except FailedPipeline as e:
        rid = str(e.trace_id or uuid.uuid4().hex)
        fail_title = infer_proposal_title(
            body.rfp,
            pipeline_mode="enterprise",
            job_understanding=None,
            input_classification=None,
            requirements=None,
        )
        return ProposalRunResponse(
            proposal=minimal_degraded_proposal(
                headline="We couldn't finish this draft automatically.",
                body="Try again with a shorter brief, or check your connection. Nothing was saved as a final proposal.",
            ),
            score=0,
            issues=[],
            suggestions=[],
            trace_id=rid,
            run_id=rid,
            memory_grounded=False,
            grounding_warning=None,
            status="degraded",
            pipeline_metadata=meta,
            timeline=[],
            memory_used={},
            pipeline_mode="enterprise",
            input_classification=None,
            job_understanding=None,
            hook=None,
            critique=None,
            verifier_metrics=None,
            reply_likelihood_0_100=None,
            title=fail_title,
            cross_proposal_diff=None,
            persisted_run_id=None,
            workspace_state={},
            insights=build_insights(
                warnings=[
                    "We could not complete the full draft. Try again with a shorter brief, "
                    "or contact support if this keeps happening."
                ],
                missing_context=True,
                rag_fallback_mode=True,
                degraded=True,
            ),
        )
    rid = str(result.get("run_id") or result.get("trace_id") or "")
    exec_st = str(result.get("execution_status") or "success")
    api_status: Literal["success", "degraded"] = "degraded" if exec_st == "degraded" else "success"
    return ProposalRunResponse(
        proposal=result["proposal"],
        score=int(result["score"]),
        issues=list(result["issues"]),
        suggestions=list(result.get("suggestions") or []),
        trace_id=rid,
        run_id=rid,
        memory_grounded=bool(result.get("memory_grounded", True)),
        grounding_warning=result.get("grounding_warning"),
        status=api_status,
        pipeline_metadata=meta,
        timeline=list(result.get("timeline") or []),
        memory_used=dict(result.get("memory_used") or {}),
        pipeline_mode="freelance"
        if result.get("pipeline_mode") == "freelance"
        else "enterprise",
        input_classification=dict(result["input_classification"]) if result.get("input_classification") else None,
        job_understanding=dict(result["job_understanding"]) if result.get("job_understanding") else None,
        hook=dict(result["hook"]) if result.get("hook") else None,
        critique=dict(result["critique"]) if result.get("critique") else None,
        verifier_metrics=dict(result["verifier_metrics"]) if result.get("verifier_metrics") else None,
        reply_likelihood_0_100=result.get("reply_likelihood_0_100"),
        insights=dict(result.get("insights") or {}),
        title=str(result.get("title") or ""),
        cross_proposal_diff=dict(result["cross_proposal_diff"]) if result.get("cross_proposal_diff") else None,
        persisted_run_id=str(result["persisted_run_id"]) if result.get("persisted_run_id") else None,
        workspace_state=dict(result.get("workspace_state") or {}),
    )


@router.get(
    "/runs",
    response_model=list[ProposalRunSummaryOut],
    summary="List saved proposal runs",
)
async def list_saved_runs(user: Annotated[CurrentUser, Depends(get_current_user)]) -> list[ProposalRunSummaryOut]:
    rows = list_proposal_runs(user.user_id, limit=50)
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


@router.get(
    "/runs/{run_id}",
    response_model=ProposalRunDetailOut,
    summary="Get one saved proposal run",
    responses={404: {"model": ErrorResponse}},
)
async def get_saved_run(
    run_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> ProposalRunDetailOut:
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
    cid = row.get("created_at")
    return ProposalRunDetailOut(
        id=str(row.get("id") or ""),
        title=str(row.get("title") or ""),
        score=int(row.get("score") or 0),
        trace_id=str(row.get("trace_id") or ""),
        pipeline_mode=str(row.get("pipeline_mode") or "enterprise"),
        created_at=str(cid) if cid is not None else "",
        rfp_input=str(row.get("rfp_input") or ""),
        proposal_output=po,
        issues=issues_list,
    )


@router.post(
    "/export/pdf",
    summary="Export proposal PDF",
    description="Renders proposal sections, timeline, and optional memory appendix as PDF (authenticated).",
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
        memory_appendix=body.memory_appendix,
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="proposal-export.pdf"'},
    )
