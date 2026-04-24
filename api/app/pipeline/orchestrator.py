"""Stateless orchestration: Langfuse trace + sequential agent stages."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import time
import uuid
from typing import Any, Callable

from bidforge_agents.job_intel_agent import (
    run_job_intel_extract,
    run_job_intel_matrix,
    run_job_intel_signals,
)
from bidforge_agents.router_agent import run_router
from bidforge_agents.proposal_dag import (
    PipelineStages,
    enterprise_solution_builder_stage,
    enterprise_strategy_stage,
    enterprise_verifier_stage,
    enterprise_writer_stage,
    freelance_solution_builder_stage,
    freelance_strategy_stage,
    freelance_verifier_stage,
    freelance_writer_stage,
)
from bidforge_schemas import (
    WorkspaceState,
    CrossProposalDiffOutput,
    InputClassifierOutput,
    JobUnderstandingOutput,
    ProposalWriterOutput,
    RagContext,
    RequirementAgentOutput,
    RequirementStructuringOutput,
    SolutionBlueprintOutput,
    StrategyAgentOutput,
    StructuredRequirementItem,
    VerifierAgentOutput,
)
from bidforge_shared import LLMClient, LLMTransportError, OpenRouterLLM, PipelineStepError, StubLLM

from app.core.config import settings
from app.integrations.langfuse import get_langfuse_client
from app.integrations.llm_factory import build_llm_from_settings
from app.integrations.proposal_store import (
    build_extracted_patterns,
    build_winning_sections_payload,
    fetch_freelance_win_memory_rows,
    get_proposal_run,
    insert_canonical_proposal_row,
    insert_freelance_win_memory,
    insert_proposal_memory_entries,
    insert_proposal_run,
    insert_memory_usage_log_row,
    insert_proposal_draft_row,
    merge_freelance_win_rows_into_rag_patterns,
)
from app.pipeline.dag_run import (
    PIPELINE_VERSION,
    DagRun,
    composite_job_intel_version_enterprise,
    composite_job_intel_version_freelance,
    composite_solution_version_enterprise,
    composite_solution_version_freelance,
    composite_verifier_version_enterprise,
    composite_verifier_version_freelance,
)
from app.pipeline.errors import FailedPipeline
from app.pipeline.run_envelope import attach_run_envelope, build_insights
from app.pipeline.title_inference import infer_proposal_title
from app.rag.retrieval import retrieve_rag_context
from app.workspace.agents import workspace_preferences_block

log = logging.getLogger(__name__)


def _dag_out(
    dag: DagRun | None,
    node_id: str,
    prompt_version: str,
    input_obj: dict[str, Any],
    producer: Callable[[], Any],
    model_cls: type[Any],
) -> Any:
    """Run `producer` with optional per-node DAG event + cache (see ``DagRun.record``)."""
    if dag is None:
        return producer()
    raw = dag.record(node_id, prompt_version, input_obj, lambda: producer().model_dump())
    return model_cls.model_validate(raw)


def _dag_bundle(
    dag: DagRun | None,
    node_id: str,
    prompt_version: str,
    input_obj: dict[str, Any],
    work: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    if dag is None:
        return work()
    return dag.record(node_id, prompt_version, input_obj, work)


def _proposal_plaintext_for_persistence(payload: dict[str, Any], *, pipeline_mode: str) -> str:
    prop = payload.get("proposal")
    if not isinstance(prop, dict):
        return ""
    secs = prop.get("sections")
    if isinstance(secs, list):
        parts: list[str] = []
        title = str(prop.get("title") or "").strip()
        if title:
            parts.append(title)
        for item in secs:
            if not isinstance(item, dict):
                continue
            t = str(item.get("title") or "").strip()
            c = str(item.get("content") or "").strip()
            if c:
                parts.append(f"{t}\n{c}" if t else c)
        return "\n\n".join(p for p in parts if p)
    if isinstance(secs, dict):
        keys2 = (
            "opening",
            "understanding",
            "solution",
            "execution_plan",
            "timeline",
            "deliverables",
            "experience",
            "risks",
            "next_step",
        )
        parts2 = [str(secs.get(k) or "").strip() for k in keys2]
        return "\n\n".join(p for p in parts2 if p)
    return ""


def _timeline_phases_from_blueprint(bp: SolutionBlueprintOutput) -> list[dict[str, str]]:
    return [{"phase": str(line).strip(), "duration": ""} for line in bp.timeline if str(line).strip()]


def _rag_requirement_context(req: RequirementAgentOutput) -> str:
    lines: list[str] = []
    for row in req.requirement_matrix:
        lines.append(f"{row.id} ({row.type}): {row.description}")
    if not lines:
        for s in req.structured_requirements:
            lines.append(f"{s.ref}: {s.text}")
    return "\n".join(lines)[:6000]


def _rag_job_context(ju: JobUnderstandingOutput) -> str:
    parts: list[str] = []
    if ju.explicit_requirements:
        parts.append("Explicit:\n" + "\n".join(f"- {x}" for x in ju.explicit_requirements[:24]))
    if ju.implicit_requirements:
        parts.append("Implicit:\n" + "\n".join(f"- {x}" for x in ju.implicit_requirements[:16]))
    if ju.buyer_intent.strip():
        parts.append(f"Buyer intent: {ju.buyer_intent}")
    if ju.urgency.strip():
        parts.append(f"Urgency: {ju.urgency}")
    if ju.buyer_sophistication.strip():
        parts.append(f"Buyer sophistication: {ju.buyer_sophistication}")
    if ju.budget_sensitivity.strip():
        parts.append(f"Budget sensitivity: {ju.budget_sensitivity}")
    if ju.decision_triggers:
        parts.append("Triggers:\n" + "\n".join(f"- {x}" for x in ju.decision_triggers[:12]))
    if ju.conversion_triggers:
        parts.append("Conversion triggers:\n" + "\n".join(f"- {x}" for x in ju.conversion_triggers[:12]))
    if ju.risk_concerns:
        parts.append("Risk concerns:\n" + "\n".join(f"- {x}" for x in ju.risk_concerns[:12]))
    if ju.recommended_tone.strip():
        parts.append(f"Tone: {ju.recommended_tone}")
    return "\n\n".join(parts)[:5000]


def _merge_structuring(
    req: RequirementAgentOutput,
    struct_out: RequirementStructuringOutput,
) -> RequirementAgentOutput:
    matrix = list(struct_out.requirements)
    structured = [StructuredRequirementItem(ref=r.id, text=r.description) for r in matrix]
    return req.model_copy(update={"requirement_matrix": matrix, "structured_requirements": structured})


def _build_llm(workspace_snapshot: dict[str, Any] | None = None) -> LLMClient:
    return build_llm_from_settings(workspace_snapshot)


def _effective_rfp_id(rfp_text: str, rfp_id: str | None) -> str:
    if rfp_id and str(rfp_id).strip():
        return str(rfp_id).strip()
    return hashlib.sha256(rfp_text.encode("utf-8", errors="ignore")).hexdigest()[:16]


def _flatten_issues(ver: VerifierAgentOutput) -> list[str]:
    out = list(ver.issues)
    out.extend(f"missing_requirement:{m}" for m in ver.missing_requirements)
    out.extend(f"compliance_risk:{c}" for c in ver.compliance_risks)
    out.extend(f"weak_claim:{w}" for w in ver.weak_claims)
    for f in ver.freelance_fail_flags:
        out.append(f"freelance_fail:{f}")
    return out


def _workspace_rag_flags(
    workspace_snapshot: dict[str, Any] | None,
) -> tuple[bool, bool, bool]:
    """Returns (rag_enabled, enterprise_case_studies, freelance_win_memory)."""
    if not workspace_snapshot:
        return True, True, True
    s = workspace_snapshot.get("settings") or {}
    r = s.get("rag") or {}
    return (
        bool(r.get("enabled", True)),
        bool(r.get("enterprise_case_studies", True)),
        bool(r.get("freelance_win_memory", True)),
    )


def _draft_intensity_block(mode: str) -> str:
    m = (mode or "balanced").strip().lower()
    if m == "strong":
        return (
            "\n[DRAFT_INTENSITY — STRONG]\n"
            "Prefer confident, specific language and compelling hooks; still never invent credentials.\n"
        )
    if m == "weak":
        return (
            "\n[DRAFT_INTENSITY — CAUTIOUS]\n"
            "Emphasize risks, compliance, and mitigations; hedge claims; reduce marketing hyperbole.\n"
        )
    return ""


def _freelance_rag_with_table_merge(
    rfp_text: str,
    user_id: str,
    ju: JobUnderstandingOutput,
    client_llm: LLMClient,
    *,
    rag_enabled: bool = True,
    use_freelance_memory_table: bool = True,
) -> RagContext:
    if not rag_enabled:
        return RagContext()
    try:
        rag_core = retrieve_rag_context(
            rfp_text,
            user_id,
            llm=_rag_embedding_llm(client_llm),
            requirement_context=_rag_job_context(ju),
            memory_scope="freelance",
        )
    except Exception as e:  # noqa: BLE001
        log.warning("freelance RAG retrieval failed (continuing empty): %s", e)
        rag_core = RagContext()
    if not use_freelance_memory_table:
        return rag_core
    try:
        extra = fetch_freelance_win_memory_rows(user_id, limit=3)
        merged = merge_freelance_win_rows_into_rag_patterns(rag_core.freelance_win_patterns, extra)
        return rag_core.model_copy(update={"freelance_win_patterns": merged})
    except Exception as e:  # noqa: BLE001
        log.debug("freelance_win_memory table merge skipped: %s", e)
        return rag_core


def _safe_enterprise_rag(
    rfp_text: str,
    user_id: str,
    req: RequirementAgentOutput,
    client_llm: LLMClient,
    *,
    rag_enabled: bool = True,
    enterprise_case_studies: bool = True,
) -> RagContext:
    if not rag_enabled or not enterprise_case_studies:
        return RagContext()
    try:
        return retrieve_rag_context(
            rfp_text,
            user_id,
            llm=_rag_embedding_llm(client_llm),
            requirement_context=_rag_requirement_context(req),
            memory_scope="enterprise",
        )
    except Exception as e:  # noqa: BLE001
        log.warning("enterprise RAG retrieval failed (continuing empty): %s", e)
        return RagContext()


def _freelance_job_type(ic: InputClassifierOutput) -> str:
    it = ic.input_type
    if it == "freelancer":
        return "freelancer"
    if it in ("upwork", "job_post"):
        return "upwork"
    return "enterprise" if it == "rfp" else "upwork"


def _maybe_autosave_high_score_win(
    user_id: str,
    pw: ProposalWriterOutput,
    ver: VerifierAgentOutput,
    ic: InputClassifierOutput,
    llm: LLMClient,
) -> None:
    if ver.score <= 75:
        return
    overview = next(
        (s.content for s in pw.sections if (s.title or "").strip().lower() == "overview"),
        "",
    )
    open_text = (overview or "").strip()
    if not open_text:
        return
    hook_line = open_text.split("\n")[0][:2000]
    opening_lines = [x.strip() for x in open_text.split("\n")[:3] if x.strip()]
    emb = None
    if isinstance(llm, OpenRouterLLM):
        try:
            emb = llm.embed_text(hook_line[:1500])
        except Exception as e:  # noqa: BLE001
            log.debug("embed for win memory skipped: %s", e)
    insert_freelance_win_memory(
        user_id,
        job_type=_freelance_job_type(ic),
        opening_hook=hook_line,
        winning_sections=build_winning_sections_payload(pw.model_dump()),
        score=int(ver.score),
        extracted_patterns=build_extracted_patterns(
            structure_pattern="Overview → Solution → Execution Plan → Timeline → Deliverables → Risk → Next Steps",
            opening_lines=opening_lines,
            score=int(ver.score),
        ),
        embedding=emb,
    )


def _rfp_title_from_workspace_snapshot(ws: dict[str, Any] | None) -> str | None:
    if not ws or not isinstance(ws, dict):
        return None
    rfp = ws.get("rfp")
    if not isinstance(rfp, dict):
        return None
    t = str(rfp.get("title") or "").strip()
    return t or None


def _enrich_run_payload_and_persist(
    payload: dict[str, Any],
    *,
    rfp_text: str,
    user_id: str,
    llm: LLMClient,
    pipeline_mode: str,
    ic: InputClassifierOutput | None,
    ju: JobUnderstandingOutput | None,
    req: RequirementAgentOutput | None,
    proposal_document: ProposalWriterOutput | None,
    ver: VerifierAgentOutput,
    draft_intensity: str = "balanced",
    prior_run_ids: list[str] | None = None,
    learning_snippet_applied: bool = False,
    workspace_snapshot: dict[str, Any] | None = None,
    dag: DagRun | None = None,
) -> None:
    """Adds title, cross_proposal_diff, persisted_run_id; autosaves freelance wins. Mutates payload."""
    icx = ic or InputClassifierOutput(
        input_type="job_post",
        recommended_pipeline="freelance" if pipeline_mode == "freelance" else "enterprise",
        rationale="",
    )
    prop_for_title = payload.get("proposal") if isinstance(payload.get("proposal"), dict) else None
    title = infer_proposal_title(
        rfp_text,
        pipeline_mode=pipeline_mode,
        job_understanding=ju,
        input_classification=icx,
        requirements=req,
        source_document_title=_rfp_title_from_workspace_snapshot(workspace_snapshot),
        proposal_payload=prop_for_title,
    )
    payload["title"] = title
    prop_inner = payload.get("proposal")
    if isinstance(prop_inner, dict):
        prop_inner["title"] = title
    if proposal_document is not None:
        current: dict[str, Any] = proposal_document.model_dump()
    else:
        current = {}
    cross = CrossProposalDiffOutput()
    payload["cross_proposal_diff"] = cross.model_dump()

    prev_score: int | None = None
    if prior_run_ids:
        tail_id = str(prior_run_ids[-1]).strip()
        if tail_id:
            prow = get_proposal_run(user_id, tail_id)
            if isinstance(prow, dict):
                prev_score = int(prow.get("score") or 0)
    cross_delta = int(payload.get("score") or 0) - prev_score if prev_score is not None else 0
    payload["cross_diff_delta_score"] = cross_delta

    trace = str(payload.get("trace_id") or "")
    di = (draft_intensity or "balanced").strip().lower()
    if di not in ("balanced", "strong", "weak"):
        di = "balanced"
    # Product contract: strong | weak | saved (saved = balanced / default voice path).
    pat = "strong" if di == "strong" else ("weak" if di == "weak" else "saved")
    prev = [str(x) for x in (prior_run_ids or []) if str(x).strip()][-8:]
    draft_version = len(prev) + 1
    mem_influenced = bool(payload.get("memory_grounded"))
    ps0: dict[str, Any] = {
        "draft_version": draft_version,
        "draft_intensity": di,
        "selected_pattern": pat,
        "previous_run_ids": prev,
        "previous_drafts": list(prev),
        "learning_snippet_applied": bool(learning_snippet_applied),
        "memory_used": mem_influenced,
        "cross_diff_delta_score": cross_delta,
    }
    if dag is not None:
        ps0 = {
            **ps0,
            "dag_meta": {
                "pipeline_version": PIPELINE_VERSION,
                "node_versions": dict(dag.node_versions),
                "replayable": True,
                "events_emitted_ok": dag.events_emitted_ok,
            },
        }
    prop_out: dict[str, Any] = {
        "proposal": payload.get("proposal"),
        "timeline": payload.get("timeline"),
        "memory_used": payload.get("memory_used"),
        "memory_grounded": payload.get("memory_grounded"),
        "score": payload.get("score"),
        "issues": payload.get("issues"),
        "suggestions": payload.get("suggestions"),
        "pipeline_mode": pipeline_mode,
        "cross_proposal_diff": payload.get("cross_proposal_diff"),
        "pipeline_state": ps0,
    }
    pid = insert_proposal_run(
        user_id,
        rfp_input=rfp_text,
        proposal_output=prop_out,
        score=int(payload.get("score") or 0),
        issues=list(payload.get("issues") or []),
        title=title,
        trace_id=trace,
        pipeline_mode=pipeline_mode,
        input_type=str(icx.input_type or "")[:128],
    )
    if not pid and (
        settings.persistence_strict_enforced()
        or (settings.env != "test" and settings.supabase_configured())
    ):
        raise FailedPipeline(
            trace_id=trace or str(uuid.uuid4().hex),
            failed_step="supabase_persist",
            message=(
                "PROPOSAL_NOT_SAVED: insert into public.proposals did not return an id. "
                "Verify SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY, migrations, and PostgREST schema reload."
            ),
            partial={"title": title, "pipeline_mode": pipeline_mode},
        )
    if pid:
        payload["persisted_run_id"] = pid
        if dag is not None:
            dag.attach_proposal_id(str(pid))
            dag.emit_run_summary(proposal_id=str(pid), pipeline_mode=pipeline_mode)
        try:
            from app.contracts.proposal_public import build_public_run_response

            pub = build_public_run_response(
                proposal=payload.get("proposal") if isinstance(payload.get("proposal"), dict) else None,
                score=int(payload.get("score") or 0),
                issues=list(payload.get("issues") or []),
                title=title,
                pipeline_mode=pipeline_mode,
                memory_grounded=bool(payload.get("memory_grounded")),
                memory_status=str(payload.get("memory_status") or ""),
                memory_used=dict(payload.get("memory_used") or {})
                if isinstance(payload.get("memory_used"), dict)
                else None,
                cross_proposal_diff=dict(payload.get("cross_proposal_diff") or {})
                if isinstance(payload.get("cross_proposal_diff"), dict)
                else None,
                persisted_run_id=pid,
                run_id=trace,
                cross_diff_delta_score=cross_delta,
            )
            insert_proposal_draft_row(str(pid), draft_version, pub.model_dump())
            insert_memory_usage_log_row(str(pid), bool(payload.get("memory_grounded")))
        except Exception as e:  # noqa: BLE001
            log.warning("proposal_draft / memory_usage_log insert skipped: %s", e)

    plain = _proposal_plaintext_for_persistence(payload, pipeline_mode=pipeline_mode)
    if plain.strip():
        canon_id = insert_canonical_proposal_row(
            user_id,
            title=title,
            body=plain,
            score=int(payload.get("score") or 0),
            issues=list(payload.get("issues") or []),
            job_description=rfp_text[:12_000],
        )
        if canon_id:
            payload["persisted_proposal_id"] = canon_id

    mem_snips: list[tuple[str, str]] = []
    if proposal_document is not None:
        overview = next(
            (s.content for s in proposal_document.sections if (s.title or "").strip().lower() == "overview"),
            "",
        )
        open_line = (overview or "").strip().split("\n")[0][:2000]
        if open_line:
            mem_snips.append(("strong_line", open_line))
        exec_body = next(
            (s.content for s in proposal_document.sections if (s.title or "").strip() == "Execution Plan"),
            "",
        )
        tech0 = (exec_body or "").strip()[:2000]
        if tech0:
            mem_snips.append(("win_pattern", tech0))
    if mem_snips:
        insert_proposal_memory_entries(user_id, mem_snips, llm)

    if pipeline_mode == "freelance" and proposal_document is not None and ic is not None and ver.score > 75:
        try:
            _maybe_autosave_high_score_win(user_id, proposal_document, ver, ic, llm)
        except Exception as e:  # noqa: BLE001
            log.warning("freelance win memory autosave failed: %s", e)

    if dag is not None and settings.persistence_strict_enforced() and not dag.events_emitted_ok:
        raise FailedPipeline(
            trace_id=trace or uuid.uuid4().hex,
            failed_step="proposal_events",
            message="DAG event append failed while strict persistence is enabled.",
            partial={"title": title, "pipeline_mode": pipeline_mode},
        )


def _apply_freelance_cold_start_if_needed(rag: RagContext) -> tuple[RagContext, bool]:
    """Returns (rag_for_agents, had_real_indexed_freelance_memory). Empty memory does not mutate RAG."""
    had_real = rag.has_usable_freelance_memory()
    if had_real:
        return rag, True
    log.debug(
        "No indexed freelance win memory for this account — pipeline continues (memory_status=empty)",
    )
    return rag, False


def _resolve_brain(
    pipeline_mode: str,
    rfp_text: str,
    llm: LLMClient,
    *,
    dag: DagRun | None = None,
) -> tuple[InputClassifierOutput, str]:
    pm = (pipeline_mode or "auto").strip().lower()
    if pm == "freelance":
        ic = InputClassifierOutput(
            input_type="manual",
            recommended_pipeline="freelance",
            rationale="User selected Freelance Win Engine.",
        )
        if dag is not None:
            pv = dag.node_prompt_versions["router"]
            dag.record(
                "router",
                pv,
                {"rfp_excerpt": (rfp_text or "")[:4000], "pipeline_mode_arg": pm},
                lambda: ic.model_dump(),
            )
        return ic, "freelance"
    if pm == "enterprise":
        ic = InputClassifierOutput(
            input_type="manual",
            recommended_pipeline="enterprise",
            rationale="User selected Enterprise mode.",
        )
        if dag is not None:
            pv = dag.node_prompt_versions["router"]
            dag.record(
                "router",
                pv,
                {"rfp_excerpt": (rfp_text or "")[:4000], "pipeline_mode_arg": pm},
                lambda: ic.model_dump(),
            )
        return ic, "enterprise"

    def _classifier_body() -> dict[str, Any]:
        ic0 = run_router(rfp_text, llm)
        mode = ic0.recommended_pipeline
        if mode not in ("enterprise", "freelance"):
            mode = "freelance" if ic0.input_type in ("job_post", "upwork", "freelancer") else "enterprise"
        if ic0.recommended_pipeline != mode:
            ic0 = ic0.model_copy(update={"recommended_pipeline": mode})  # type: ignore[arg-type]
        return ic0.model_dump()

    if dag is not None:
        pv = dag.node_prompt_versions["router"]
        raw = dag.record(
            "router",
            pv,
            {"rfp_excerpt": (rfp_text or "")[:8000], "pipeline_mode_arg": pm},
            _classifier_body,
        )
        ic = InputClassifierOutput.model_validate(raw)
        return ic, ic.recommended_pipeline
    ic = run_router(rfp_text, llm)
    mode = ic.recommended_pipeline
    if mode not in ("enterprise", "freelance"):
        mode = "freelance" if ic.input_type in ("job_post", "upwork", "freelancer") else "enterprise"
    if ic.recommended_pipeline != mode:
        ic = ic.model_copy(update={"recommended_pipeline": mode})  # type: ignore[arg-type]
    return ic, mode


def _memory_summary_for_ui(rag: RagContext, *, pipeline_mode: str = "enterprise") -> dict[str, Any]:
    """UI-facing retrieval summary — real rows only; explicit `memory` / `source` when RAG is empty vs grounded."""
    fwp = [
        {"id": w.get("id"), "label": w.get("label"), "outcome": w.get("outcome")}
        for w in rag.freelance_win_patterns[:12]
        if str(w.get("outcome") or "").lower() != "synthetic_seed"
    ]
    wps = [
        {"id": w.get("id"), "label": w.get("label"), "outcome": w.get("outcome")}
        for w in rag.win_patterns[:12]
    ]
    if (pipeline_mode or "").lower() == "freelance":
        grounded = rag.has_usable_freelance_memory()
        src_ids = [str(w.get("id") or "").strip() for w in fwp if str(w.get("id") or "").strip()]
    else:
        grounded = rag.has_usable_memory()
        src_ids = []
        for w in wps:
            sid = str(w.get("id") or "").strip()
            if sid:
                src_ids.append(sid)
        for w in rag.similar_proposals[:12]:
            if not isinstance(w, dict):
                continue
            sid = str(w.get("id") or "").strip()
            if sid:
                src_ids.append(sid)
        for w in rag.methodology_blocks[:12]:
            if not isinstance(w, dict):
                continue
            sid = str(w.get("id") or "").strip()
            if sid:
                src_ids.append(sid)
    return {
        "similar_proposals": [],
        "methodology_blocks": [],
        "win_patterns": wps,
        "freelance_win_patterns": fwp,
        "pipeline_mode": pipeline_mode,
        "memory": "grounded" if grounded else "general",
        "source": src_ids[:32],
    }


def _proposal_document_payload(
    *,
    pw: ProposalWriterOutput,
    strat: StrategyAgentOutput,
    blueprint: SolutionBlueprintOutput,
    memory_grounded: bool,
    grounding_warning: str | None,
    pipeline_mode: str,
) -> dict[str, Any]:
    return {
        "title": pw.title,
        "sections": [s.model_dump() for s in pw.sections],
        "strategy": {
            "strategy": strat.strategy,
            "based_on": strat.based_on,
            "positioning": strat.positioning,
            "win_themes": strat.win_themes,
            "differentiators": strat.differentiators,
            "response_tone": strat.response_tone,
            "freelance_hook_strategy": strat.freelance_hook_strategy or "",
        },
        "solution_blueprint": blueprint.model_dump(),
        "memory_grounded": memory_grounded,
        "grounding_warning": grounding_warning,
        "section_attributions": [],
        "pipeline_mode": pipeline_mode,
    }


def _verifier_metrics(ver: VerifierAgentOutput, brain: str) -> dict[str, Any]:
    base: dict[str, Any] = {"brain": brain}
    if brain == "freelance":
        base.update(
            {
                "reply_probability_score": ver.reply_probability_score,
                "hook_strength": ver.hook_strength,
                "trust_signals_score": ver.trust_signals_score,
                "conciseness_score": ver.conciseness_score,
                "freelance_fail_flags": list(ver.freelance_fail_flags),
            }
        )
    else:
        base.update(
            {
                "compliance_score": ver.compliance_score,
                "completeness_score": ver.completeness_score,
            }
        )
    return base


def _model_provider(llm: LLMClient) -> str:
    if isinstance(llm, OpenRouterLLM):
        return "openrouter"
    if isinstance(llm, StubLLM):
        return "stub"
    return "other"


def _span_base_metadata(*, rfp_id: str, user_id: str, llm: LLMClient) -> dict[str, Any]:
    return {
        "rfp_id": rfp_id,
        "user_id": user_id,
        "model_provider": _model_provider(llm),
        "model_name": getattr(llm, "last_model_name", None) or "",
    }


def _runtime_label() -> str:
    return "vercel" if os.environ.get("VERCEL") == "1" else "local"


def _trace_standard_metadata(*, user_id: str, brain: str) -> dict[str, Any]:
    return {
        "user_id": user_id,
        "env": settings.env,
        "runtime": _runtime_label(),
        "workflow_version": "v2",
        "workflow": brain,
    }


def _merge_usage_metadata(llm: LLMClient, meta: dict[str, Any]) -> dict[str, Any]:
    out = dict(meta)
    lm = getattr(llm, "last_model_name", None)
    if lm:
        out["model_name"] = lm
    usage = getattr(llm, "last_usage", None)
    if isinstance(usage, dict):
        for k, v in usage.items():
            out[f"usage_{k}"] = v
    return out


def _run_step_traced(
    lf: Any,
    name: str,
    fn: Any,
    *,
    input_payload: dict[str, Any],
    base_metadata: dict[str, Any],
    llm: LLMClient,
) -> Any:
    t0 = time.perf_counter()
    with lf.start_as_current_observation(
        as_type="span",
        name=name,
        input=input_payload,
        metadata=dict(base_metadata),
    ) as span:
        try:
            out = fn()
        except Exception as e:  # noqa: BLE001
            span.update(
                level="ERROR",
                status_message=str(e),
                metadata=_merge_usage_metadata(
                    llm,
                    {
                        **base_metadata,
                        "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
                        "status": "failed",
                        "failed_step": name,
                    },
                ),
            )
            raise
        latency_ms = (time.perf_counter() - t0) * 1000
        dumped = out.model_dump() if hasattr(out, "model_dump") else out
        span.update(
            output=dumped,
            metadata=_merge_usage_metadata(
                llm,
                {
                    **base_metadata,
                    "latency_ms": round(latency_ms, 2),
                    "agent": name,
                },
            ),
        )
        return out


def _rag_embedding_llm(client_llm: LLMClient) -> OpenRouterLLM | None:
    return client_llm if isinstance(client_llm, OpenRouterLLM) else None


def _new_langfuse_trace_id() -> str:
    """Langfuse OTel ingestion expects a 32-char lowercase hex trace id, not a hyphenated UUID."""
    return uuid.uuid4().hex


def _run_freelance_steps(
    rfp_core: str,
    rfp_gen: str,
    user_id: str,
    client_llm: LLMClient,
    ic: InputClassifierOutput,
    trace_id: str,
    *,
    lf: Any | None,
    base_md: dict[str, Any],
    partial: dict[str, Any],
    dag: DagRun | None = None,
    rag_enabled: bool = True,
    use_freelance_memory_table: bool = True,
    draft_intensity: str = "balanced",
    prior_run_ids: list[str] | None = None,
    learning_snippet_applied: bool = False,
    workspace_snapshot: dict[str, Any] | None = None,
    proposal_depth: str = "full",
) -> dict[str, Any]:
    """Core freelance pipeline (optionally Langfuse-traced per step)."""

    def _ju():
        return run_job_intel_signals(rfp_core, client_llm)

    def _rag(ju: JobUnderstandingOutput):
        return _freelance_rag_with_table_merge(
            rfp_core,
            user_id,
            ju,
            client_llm,
            rag_enabled=rag_enabled,
            use_freelance_memory_table=use_freelance_memory_table,
        )

    depth = (proposal_depth or "full").strip().lower()
    if depth not in ("short", "full"):
        depth = "full"

    ji_fl = dag.node_prompt_versions["job_intel_freelance"] if dag is not None else ""

    def _freelance_job_intel_work() -> dict[str, Any]:
        j0 = run_job_intel_signals(rfp_core, client_llm)
        rg = _freelance_rag_with_table_merge(
            rfp_core,
            user_id,
            j0,
            client_llm,
            rag_enabled=rag_enabled,
            use_freelance_memory_table=use_freelance_memory_table,
        )
        return {"job_understanding": j0.model_dump(), "rag": rg.model_dump()}

    if lf is None:
        intel_raw = _dag_bundle(
            dag,
            "job_intel",
            ji_fl,
            {"rfp_excerpt": rfp_core[:8000]},
            _freelance_job_intel_work,
        )
        ju = JobUnderstandingOutput.model_validate(intel_raw["job_understanding"])
        rag = RagContext.model_validate(intel_raw["rag"])
        rag, had_real_mem = _apply_freelance_cold_start_if_needed(rag)
        partial["job_understanding"] = ju.model_dump()
        partial["rag"] = rag.model_dump()
        sol_fl = dag.node_prompt_versions["solution_freelance"] if dag is not None else ""

        def _freelance_solution_work() -> dict[str, Any]:
            bp = freelance_solution_builder_stage(ju, rag, client_llm)
            st = freelance_strategy_stage(ju, rfp_gen, rag, client_llm, bp)
            return {"blueprint": bp.model_dump(), "strategy": st.model_dump()}

        sol_raw = _dag_bundle(
            dag,
            "solution",
            sol_fl,
            {"job_understanding": ju.model_dump(), "rag": rag.model_dump()},
            _freelance_solution_work,
        )
        blueprint = SolutionBlueprintOutput.model_validate(sol_raw["blueprint"])
        strat = StrategyAgentOutput.model_validate(sol_raw["strategy"])
        prop_pv = dag.node_prompt_versions["proposal"] if dag is not None else ""
        pw = _dag_out(
            dag,
            "proposal",
            prop_pv,
            {
                "job_understanding": ju.model_dump(),
                "rag": rag.model_dump(),
                "strategy": strat.model_dump(),
                "blueprint": blueprint.model_dump(),
                "job_text_excerpt": (rfp_gen or "")[:8000],
                "proposal_depth": depth,
            },
            lambda: freelance_writer_stage(
                ju,
                rag,
                rfp_gen,
                client_llm,
                ic,
                strat,
                blueprint,
                proposal_depth=depth,
            ),
            ProposalWriterOutput,
        )
        ver_pv = dag.node_prompt_versions["verifier_freelance"] if dag is not None else ""
        ver = _dag_out(
            dag,
            "verifier",
            ver_pv,
            {
                "proposal_document": pw.model_dump(),
                "strategy": strat.model_dump(),
                "rag": rag.model_dump(),
                "job_understanding": ju.model_dump(),
                "blueprint": blueprint.model_dump(),
            },
            lambda: freelance_verifier_stage(pw, strat, rag, client_llm, ju, blueprint),
            VerifierAgentOutput,
        )
        partial["solution_blueprint"] = blueprint.model_dump()
        partial["strategy"] = strat.model_dump()
        partial["proposal_document"] = pw.model_dump()
        partial["verification"] = ver.model_dump()
    else:

        def intel_fn():
            return _dag_bundle(
                dag,
                "job_intel",
                dag.node_prompt_versions["job_intel_freelance"] if dag is not None else "",
                {"rfp_excerpt": rfp_core[:8000]},
                _freelance_job_intel_work,
            )

        intel_out = _run_step_traced(
            lf,
            "job_intel",
            intel_fn,
            input_payload={"job_excerpt": rfp_core[:800]},
            base_metadata=base_md,
            llm=client_llm,
        )
        ju = JobUnderstandingOutput.model_validate(intel_out["job_understanding"])
        rag = RagContext.model_validate(intel_out["rag"])
        rag, had_real_mem = _apply_freelance_cold_start_if_needed(rag)
        partial["job_understanding"] = ju.model_dump()
        partial["rag"] = rag.model_dump()

        def _freelance_solution_work_inline() -> dict[str, Any]:
            bp = freelance_solution_builder_stage(ju, rag, client_llm)
            st = freelance_strategy_stage(ju, rfp_gen, rag, client_llm, bp)
            return {"blueprint": bp.model_dump(), "strategy": st.model_dump()}

        def solution_fn():
            return _dag_bundle(
                dag,
                "solution",
                dag.node_prompt_versions["solution_freelance"] if dag is not None else "",
                {"job_understanding": ju.model_dump(), "rag": rag.model_dump()},
                _freelance_solution_work_inline,
            )

        sol_out = _run_step_traced(
            lf,
            "solution",
            solution_fn,
            input_payload={"job": ju.model_dump()},
            base_metadata=base_md,
            llm=client_llm,
        )
        blueprint = SolutionBlueprintOutput.model_validate(sol_out["blueprint"])
        strat = StrategyAgentOutput.model_validate(sol_out["strategy"])
        partial["solution_blueprint"] = blueprint.model_dump()
        partial["strategy"] = strat.model_dump()

        pw = _run_step_traced(
            lf,
            "proposal",
            lambda: _dag_out(
                dag,
                "proposal",
                dag.node_prompt_versions["proposal"] if dag is not None else "",
                {
                    "job_understanding": ju.model_dump(),
                    "rag": rag.model_dump(),
                    "strategy": strat.model_dump(),
                    "blueprint": blueprint.model_dump(),
                    "job_text_excerpt": (rfp_gen or "")[:8000],
                    "proposal_depth": depth,
                },
                lambda: freelance_writer_stage(
                    ju,
                    rag,
                    rfp_gen,
                    client_llm,
                    ic,
                    strat,
                    blueprint,
                    proposal_depth=depth,
                ),
                ProposalWriterOutput,
            ),
            input_payload={"solution_blueprint": blueprint.model_dump(), "strategy": strat.model_dump()},
            base_metadata=base_md,
            llm=client_llm,
        )
        partial["proposal_document"] = pw.model_dump()

        ver = _run_step_traced(
            lf,
            "verifier",
            lambda: _dag_out(
                dag,
                "verifier",
                dag.node_prompt_versions["verifier_freelance"] if dag is not None else "",
                {
                    "proposal_document": pw.model_dump(),
                    "strategy": strat.model_dump(),
                    "rag": rag.model_dump(),
                    "job_understanding": ju.model_dump(),
                    "blueprint": blueprint.model_dump(),
                },
                lambda: freelance_verifier_stage(pw, strat, rag, client_llm, ju, blueprint),
                VerifierAgentOutput,
            ),
            input_payload={"proposal_document": pw.model_dump()},
            base_metadata=base_md,
            llm=client_llm,
        )
        partial["verification"] = ver.model_dump()

    mem_ok = had_real_mem
    mem_status = "grounded" if had_real_mem else "general"
    mem_used = _memory_summary_for_ui(rag, pipeline_mode="freelance")
    warn: str | None = None
    if ver.reply_probability_score is not None:
        reply_pct = int(round(float(ver.reply_probability_score) * 100))
    else:
        reply_pct = ver.score
    ins = build_insights(
        warnings=[],
        missing_context=not mem_ok,
        rag_fallback_mode=False,
    )
    payload = {
        "proposal": _proposal_document_payload(
            pw=pw,
            strat=strat,
            blueprint=blueprint,
            memory_grounded=mem_ok,
            grounding_warning=warn,
            pipeline_mode="freelance",
        ),
        "timeline": _timeline_phases_from_blueprint(blueprint),
        "memory_used": mem_used,
        "memory_status": mem_status,
        "score": ver.score,
        "issues": _flatten_issues(ver),
        "suggestions": list(ver.suggestions or []),
        "trace_id": trace_id,
        "memory_grounded": mem_ok,
        "grounding_warning": warn,
        "pipeline_mode": "freelance",
        "proposal_depth": depth,
        "input_classification": ic.model_dump(),
        "job_understanding": ju.model_dump(),
        "verifier_metrics": _verifier_metrics(ver, "freelance"),
        "reply_likelihood_0_100": max(0, min(100, reply_pct)),
    }
    _enrich_run_payload_and_persist(
        payload,
        rfp_text=rfp_core,
        user_id=user_id,
        llm=client_llm,
        pipeline_mode="freelance",
        ic=ic,
        ju=ju,
        req=None,
        proposal_document=pw,
        ver=ver,
        draft_intensity=draft_intensity,
        prior_run_ids=prior_run_ids,
        learning_snippet_applied=learning_snippet_applied,
        workspace_snapshot=workspace_snapshot,
        dag=dag,
    )
    return attach_run_envelope(payload, execution_status="success", insights=ins)


def execute_proposal_pipeline(
    rfp_text: str,
    user_id: str,
    *,
    rfp_id: str | None = None,
    llm: LLMClient | None = None,
    pipeline_mode: str = "auto",
    workspace_snapshot: dict[str, Any] | None = None,
    rfp_for_generation: str | None = None,
    draft_intensity: str = "balanced",
    prior_run_ids: list[str] | None = None,
    learning_snippet_applied: bool = False,
    proposal_depth: str = "full",
) -> dict[str, Any]:
    client_llm = llm or _build_llm(workspace_snapshot)
    rfp_core = (rfp_text or "").strip()
    rfp_gen = (rfp_for_generation or rfp_core).strip()
    rag_ok, ent_mem, fl_mem = _workspace_rag_flags(workspace_snapshot)
    if not settings.rag_runtime_enabled:
        rag_ok = False
    if not settings.memory_injection_enabled:
        rag_ok = False
        ent_mem = False
        fl_mem = False
    workspace_prefs = ""
    if workspace_snapshot:
        try:
            ws0 = WorkspaceState.model_validate(workspace_snapshot)
            workspace_prefs = workspace_preferences_block(ws0)
        except Exception:  # noqa: BLE001
            workspace_prefs = ""
    hint = _draft_intensity_block(draft_intensity)
    workspace_prefs_effective = f"{workspace_prefs}{hint}".strip()
    rfp_gen_effective = f"{rfp_gen}{hint}".strip()
    rid = _effective_rfp_id(rfp_core, rfp_id)
    lf = get_langfuse_client()
    trace_id = _new_langfuse_trace_id()
    dag = DagRun(
        user_id=user_id,
        trace_id=trace_id,
        pipeline_mode=(pipeline_mode or "auto"),
        llm=client_llm,
        fail_fast_events=settings.persistence_strict_enforced(),
    )
    ic, resolved = _resolve_brain(pipeline_mode, rfp_core, client_llm, dag=dag)
    dag.source_rfp_plain = rfp_core
    dag.source_input_type = str(ic.input_type) if ic else ""
    hist_prior = [str(x).strip() for x in (prior_run_ids or []) if str(x).strip()]

    if resolved == "freelance":
        partial: dict[str, Any] = {}
        try:
            base_md = _span_base_metadata(rfp_id=rid, user_id=user_id, llm=client_llm)
            if lf is None:
                return _run_freelance_steps(
                    rfp_core,
                    rfp_gen_effective,
                    user_id,
                    client_llm,
                    ic,
                    trace_id,
                    lf=None,
                    base_md=base_md,
                    partial=partial,
                    dag=dag,
                    rag_enabled=rag_ok,
                    use_freelance_memory_table=fl_mem,
                    draft_intensity=draft_intensity,
                    prior_run_ids=hist_prior or None,
                    learning_snippet_applied=learning_snippet_applied,
                    workspace_snapshot=workspace_snapshot,
                    proposal_depth=proposal_depth,
                )
            from langfuse.types import TraceContext

            tc = TraceContext(trace_id=trace_id)
            std_meta = _trace_standard_metadata(user_id=user_id, brain="freelance")
            t0_pipeline = time.perf_counter()
            with lf.start_as_current_observation(
                trace_context=tc,
                as_type="chain",
                name="proposal_run_freelance",
                input={"rfp_chars": len(rfp_core), "user_id": user_id, "rfp_id": rid, "brain": "freelance"},
                metadata={"service": "bidforge-api", "trace_status": "running", **std_meta},
            ) as chain:
                try:
                    out = _run_freelance_steps(
                        rfp_core,
                        rfp_gen_effective,
                        user_id,
                        client_llm,
                        ic,
                        trace_id,
                        lf=lf,
                        base_md=base_md,
                        partial=partial,
                        dag=dag,
                        rag_enabled=rag_ok,
                        use_freelance_memory_table=fl_mem,
                        draft_intensity=draft_intensity,
                        prior_run_ids=hist_prior or None,
                        learning_snippet_applied=learning_snippet_applied,
                        workspace_snapshot=workspace_snapshot,
                        proposal_depth=proposal_depth,
                    )
                except (PipelineStepError, LLMTransportError) as e:
                    step = getattr(e, "step", "unknown")
                    merged = {**partial, **(getattr(e, "partial", {}) or {})}
                    chain.update(
                        level="ERROR",
                        status_message=str(e),
                        metadata={
                            **std_meta,
                            "status": "failed",
                            "trace_status": "failed",
                            "failed_step": step,
                            "partial_outputs": merged,
                        },
                    )
                    lf.flush()
                    raise FailedPipeline(
                        trace_id=trace_id,
                        failed_step=step,
                        message=str(e),
                        partial=merged,
                    ) from e
                total_latency_ms = (time.perf_counter() - t0_pipeline) * 1000
                chain.update(
                    output={"score": out["score"], "brain": "freelance"},
                    metadata={
                        **std_meta,
                        "status": "completed",
                        "trace_status": "completed",
                        "total_latency_ms": round(total_latency_ms, 2),
                    },
                )
                chain.score_trace(name="proposal_quality", value=float(out["score"]), data_type="NUMERIC")
                rp = (out.get("verifier_metrics") or {}).get("reply_probability_score")
                if isinstance(rp, (int, float)):
                    chain.score_trace(name="reply_probability", value=float(rp), data_type="NUMERIC")
                mem_al = 1.0 if bool(out.get("memory_grounded")) else 0.0
                chain.score_trace(name="memory_alignment_score", value=mem_al, data_type="NUMERIC")
                ins = out.get("insights") or {}
                degr = 1.0 if bool(ins.get("rag_fallback_mode")) else 0.0
                chain.score_trace(name="degradation_level", value=degr, data_type="NUMERIC")
            lf.flush()
            return out
        except FailedPipeline:
            raise
        except (PipelineStepError, LLMTransportError) as e:
            step = getattr(e, "step", "unknown")
            partial.update(getattr(e, "partial", {}) or {})
            raise FailedPipeline(
                trace_id=trace_id,
                failed_step=step,
                message=str(e),
                partial=partial,
            ) from e

    # --- Enterprise path ---
    if lf is None:
        partial_e: dict[str, Any] = {}
        try:
            ji_pv = dag.node_prompt_versions["job_intel_enterprise"] if dag is not None else ""

            def _enterprise_job_intel_work() -> dict[str, Any]:
                r0 = run_job_intel_extract(rfp_core, client_llm)
                s0 = run_job_intel_matrix(r0, client_llm)
                r1 = _merge_structuring(r0, s0)
                rg = _safe_enterprise_rag(
                    rfp_core,
                    user_id,
                    r1,
                    client_llm,
                    rag_enabled=rag_ok,
                    enterprise_case_studies=ent_mem,
                )
                return {"requirements": r1.model_dump(), "rag": rg.model_dump()}

            intel_raw = _dag_bundle(
                dag,
                "job_intel",
                ji_pv,
                {"rfp_excerpt": rfp_core[:8000]},
                _enterprise_job_intel_work,
            )
            req = RequirementAgentOutput.model_validate(intel_raw["requirements"])
            rag = RagContext.model_validate(intel_raw["rag"])
            partial_e["requirements"] = req.model_dump()
            partial_e["rag"] = rag.model_dump()
            if not rag.has_usable_memory() and settings.require_rag_memory:
                log.warning("Indexed proposal memory empty — continuing with general-intelligence fallback")
            depth_ent = (proposal_depth or "full").strip().lower()
            if depth_ent not in ("short", "full"):
                depth_ent = "full"
            sol_pv = dag.node_prompt_versions["solution_enterprise"] if dag is not None else ""

            def _enterprise_solution_work() -> dict[str, Any]:
                bp = enterprise_solution_builder_stage(req, rag, client_llm)
                st = enterprise_strategy_stage(
                    req,
                    rag,
                    client_llm,
                    bp,
                    workspace_preferences=workspace_prefs_effective,
                )
                return {"blueprint": bp.model_dump(), "strategy": st.model_dump()}

            sol_raw = _dag_bundle(
                dag,
                "solution",
                sol_pv,
                {"requirements": req.model_dump(), "rag": rag.model_dump()},
                _enterprise_solution_work,
            )
            blueprint = SolutionBlueprintOutput.model_validate(sol_raw["blueprint"])
            strat = StrategyAgentOutput.model_validate(sol_raw["strategy"])
            prop_pv = dag.node_prompt_versions["proposal"] if dag is not None else ""
            pw = _dag_out(
                dag,
                "proposal",
                prop_pv,
                {
                    "requirements": req.model_dump(),
                    "rag": rag.model_dump(),
                    "strategy": strat.model_dump(),
                    "blueprint": blueprint.model_dump(),
                    "rfp_excerpt": (rfp_core or "")[:8000],
                    "proposal_depth": depth_ent,
                },
                lambda: enterprise_writer_stage(
                    req,
                    rag,
                    rfp_core,
                    client_llm,
                    ic,
                    strat,
                    blueprint,
                    proposal_depth=depth_ent,
                ),
                ProposalWriterOutput,
            )
            ver_pv = dag.node_prompt_versions["verifier_enterprise"] if dag is not None else ""
            ver = _dag_out(
                dag,
                "verifier",
                ver_pv,
                {
                    "proposal_document": pw.model_dump(),
                    "requirements": req.model_dump(),
                    "rag": rag.model_dump(),
                    "strategy": strat.model_dump(),
                },
                lambda: enterprise_verifier_stage(pw, req, rag, client_llm, strat),
                VerifierAgentOutput,
            )
            stages = PipelineStages(
                rag=rag,
                requirements=req,
                blueprint=blueprint,
                strategy=strat,
                proposal_document=pw,
                verification=ver,
            )
        except (PipelineStepError, LLMTransportError) as e:
            step = getattr(e, "step", "unknown")
            partial_e.update(getattr(e, "partial", {}) or {})
            raise FailedPipeline(
                trace_id=trace_id,
                failed_step=step,
                message=str(e),
                partial=partial_e,
            ) from e
        ver = stages.verification
        mem_ok = stages.rag.has_usable_memory()
        mem_used = _memory_summary_for_ui(stages.rag, pipeline_mode="enterprise")
        warn: str | None = None
        timeline_out = _timeline_phases_from_blueprint(stages.blueprint)
        proposal = _proposal_document_payload(
            pw=stages.proposal_document,
            strat=stages.strategy,
            blueprint=stages.blueprint,
            memory_grounded=mem_ok,
            grounding_warning=warn,
            pipeline_mode="enterprise",
        )
        ins = build_insights(
            warnings=[],
            missing_context=not mem_ok,
            rag_fallback_mode=False,
        )
        ent = {
            "proposal": proposal,
            "timeline": timeline_out,
            "memory_used": mem_used,
            "memory_status": "grounded" if mem_ok else "general",
            "score": ver.score,
            "issues": _flatten_issues(ver),
            "suggestions": list(ver.suggestions or []),
            "trace_id": trace_id,
            "memory_grounded": mem_ok,
            "grounding_warning": warn,
            "pipeline_mode": "enterprise",
            "input_classification": ic.model_dump(),
            "job_understanding": None,
            "hook": None,
            "verifier_metrics": _verifier_metrics(ver, "enterprise"),
            "reply_likelihood_0_100": None,
        }
        _enrich_run_payload_and_persist(
            ent,
            rfp_text=rfp_core,
            user_id=user_id,
            llm=client_llm,
            pipeline_mode="enterprise",
            ic=ic,
            ju=None,
            req=stages.requirements,
            proposal_document=stages.proposal_document,
            ver=ver,
            draft_intensity=draft_intensity,
            prior_run_ids=hist_prior or None,
            learning_snippet_applied=learning_snippet_applied,
            workspace_snapshot=workspace_snapshot,
            dag=dag,
        )
        return attach_run_envelope(ent, execution_status="success", insights=ins)

    from langfuse.types import TraceContext

    tc = TraceContext(trace_id=trace_id)
    base_md = _span_base_metadata(rfp_id=rid, user_id=user_id, llm=client_llm)
    partial_out: dict[str, Any] = {}
    t0_pipeline = time.perf_counter()
    std_meta = _trace_standard_metadata(user_id=user_id, brain="enterprise")

    with lf.start_as_current_observation(
        trace_context=tc,
        as_type="chain",
        name="proposal_run",
        input={"rfp_chars": len(rfp_core), "user_id": user_id, "rfp_id": rid, "brain": "enterprise"},
        metadata={
            "service": "bidforge-api",
            "trace_status": "running",
            **std_meta,
        },
    ) as chain:
        try:

            def _ent_intel_traced_work() -> dict[str, Any]:
                r0 = run_job_intel_extract(rfp_core, client_llm)
                s0 = run_job_intel_matrix(r0, client_llm)
                r1 = _merge_structuring(r0, s0)
                rg = _safe_enterprise_rag(
                    rfp_core,
                    user_id,
                    r1,
                    client_llm,
                    rag_enabled=rag_ok,
                    enterprise_case_studies=ent_mem,
                )
                return {"requirements": r1.model_dump(), "rag": rg.model_dump()}

            intel_out = _run_step_traced(
                lf,
                "job_intel",
                lambda: _dag_bundle(
                    dag,
                    "job_intel",
                    dag.node_prompt_versions["job_intel_enterprise"] if dag is not None else "",
                    {"rfp_excerpt": rfp_core[:8000]},
                    _ent_intel_traced_work,
                ),
                input_payload={"rfp_excerpt": rfp_core[:800]},
                base_metadata=base_md,
                llm=client_llm,
            )
            req = RequirementAgentOutput.model_validate(intel_out["requirements"])
            rag = RagContext.model_validate(intel_out["rag"])
            partial_out["requirements"] = req.model_dump()
            partial_out["rag"] = rag.model_dump()
            if not rag.has_usable_memory() and settings.require_rag_memory:
                log.warning("Indexed proposal memory empty — continuing with general-intelligence fallback")

            depth_ent = (proposal_depth or "full").strip().lower()
            if depth_ent not in ("short", "full"):
                depth_ent = "full"

            def _ent_solution_traced_work() -> dict[str, Any]:
                bp = enterprise_solution_builder_stage(req, rag, client_llm)
                st = enterprise_strategy_stage(
                    req,
                    rag,
                    client_llm,
                    bp,
                    workspace_preferences=workspace_prefs_effective,
                )
                return {"blueprint": bp.model_dump(), "strategy": st.model_dump()}

            sol_out = _run_step_traced(
                lf,
                "solution",
                lambda: _dag_bundle(
                    dag,
                    "solution",
                    dag.node_prompt_versions["solution_enterprise"] if dag is not None else "",
                    {"requirements": req.model_dump(), "rag": rag.model_dump()},
                    _ent_solution_traced_work,
                ),
                input_payload={"requirements": req.model_dump()},
                base_metadata=base_md,
                llm=client_llm,
            )
            blueprint = SolutionBlueprintOutput.model_validate(sol_out["blueprint"])
            strat = StrategyAgentOutput.model_validate(sol_out["strategy"])
            partial_out["solution_blueprint"] = blueprint.model_dump()
            partial_out["strategy"] = strat.model_dump()

            pw = _run_step_traced(
                lf,
                "proposal",
                lambda: _dag_out(
                    dag,
                    "proposal",
                    dag.node_prompt_versions["proposal"] if dag is not None else "",
                    {
                        "requirements": req.model_dump(),
                        "rag": rag.model_dump(),
                        "strategy": strat.model_dump(),
                        "blueprint": blueprint.model_dump(),
                        "rfp_excerpt": (rfp_core or "")[:8000],
                        "proposal_depth": depth_ent,
                    },
                    lambda: enterprise_writer_stage(
                        req,
                        rag,
                        rfp_core,
                        client_llm,
                        ic,
                        strat,
                        blueprint,
                        proposal_depth=depth_ent,
                    ),
                    ProposalWriterOutput,
                ),
                input_payload={"strategy": strat.model_dump(), "blueprint": blueprint.model_dump()},
                base_metadata=base_md,
                llm=client_llm,
            )
            partial_out["proposal_document"] = pw.model_dump()

            ver = _run_step_traced(
                lf,
                "verifier",
                lambda: _dag_out(
                    dag,
                    "verifier",
                    dag.node_prompt_versions["verifier_enterprise"] if dag is not None else "",
                    {
                        "proposal_document": pw.model_dump(),
                        "requirements": req.model_dump(),
                        "rag": rag.model_dump(),
                        "strategy": strat.model_dump(),
                    },
                    lambda: enterprise_verifier_stage(pw, req, rag, client_llm, strat),
                    VerifierAgentOutput,
                ),
                input_payload={"proposal_document": pw.model_dump(), "requirements": req.model_dump()},
                base_metadata=base_md,
                llm=client_llm,
            )
            partial_out["verification"] = ver.model_dump()
        except (PipelineStepError, LLMTransportError) as e:
            step = getattr(e, "step", "unknown")
            partial = {**partial_out, **(getattr(e, "partial", {}) or {})}
            chain.update(
                level="ERROR",
                status_message=str(e),
                metadata={
                    **std_meta,
                    "status": "failed",
                    "trace_status": "failed",
                    "failed_step": step,
                    "partial_outputs": partial,
                },
            )
            lf.flush()
            raise FailedPipeline(
                trace_id=trace_id,
                failed_step=step,
                message=str(e),
                partial=partial,
            ) from e

        stages = PipelineStages(
            rag=rag,
            requirements=req,
            blueprint=blueprint,
            strategy=strat,
            proposal_document=pw,
            verification=ver,
        )
        mem_ok = stages.rag.has_usable_memory()
        mem_used = _memory_summary_for_ui(stages.rag, pipeline_mode="enterprise")
        warn: str | None = None
        timeline_out = _timeline_phases_from_blueprint(stages.blueprint)
        ins = build_insights(
            warnings=[],
            missing_context=not mem_ok,
            rag_fallback_mode=False,
        )
        ent_payload: dict[str, Any] = {
            "proposal": _proposal_document_payload(
                pw=stages.proposal_document,
                strat=stages.strategy,
                blueprint=stages.blueprint,
                memory_grounded=mem_ok,
                grounding_warning=warn,
                pipeline_mode="enterprise",
            ),
            "timeline": timeline_out,
            "memory_used": mem_used,
            "memory_status": "grounded" if mem_ok else "general",
            "score": ver.score,
            "issues": _flatten_issues(ver),
            "suggestions": list(ver.suggestions or []),
            "trace_id": trace_id,
            "memory_grounded": mem_ok,
            "grounding_warning": warn,
            "pipeline_mode": "enterprise",
            "input_classification": ic.model_dump(),
            "job_understanding": None,
            "hook": None,
            "verifier_metrics": _verifier_metrics(ver, "enterprise"),
            "reply_likelihood_0_100": None,
        }
        _enrich_run_payload_and_persist(
            ent_payload,
            rfp_text=rfp_core,
            user_id=user_id,
            llm=client_llm,
            pipeline_mode="enterprise",
            ic=ic,
            ju=None,
            req=stages.requirements,
            proposal_document=stages.proposal_document,
            ver=ver,
            draft_intensity=draft_intensity,
            prior_run_ids=hist_prior or None,
            learning_snippet_applied=learning_snippet_applied,
            workspace_snapshot=workspace_snapshot,
            dag=dag,
        )
        result = attach_run_envelope(
            ent_payload,
            execution_status="success",
            insights=ins,
        )
        total_latency_ms = (time.perf_counter() - t0_pipeline) * 1000
        issue_n = len(result["issues"])
        compliance_n = len(ver.compliance_risks)
        chain.update(
            output={"score": ver.score, "issues_count": issue_n},
            metadata={
                **std_meta,
                "status": "completed",
                "trace_status": "completed",
                "total_latency_ms": round(total_latency_ms, 2),
            },
        )
        chain.score_trace(name="proposal_quality", value=float(ver.score), data_type="NUMERIC")
        chain.score_trace(
            name="workflow_latency_ms",
            value=round(total_latency_ms, 2),
            data_type="NUMERIC",
        )
        chain.score_trace(name="issue_count", value=float(issue_n), data_type="NUMERIC")
        chain.score_trace(
            name="compliance_risk_count",
            value=float(compliance_n),
            data_type="NUMERIC",
        )
        chain.score_trace(name="memory_grounded", value=1.0 if mem_ok else 0.0, data_type="NUMERIC")
        chain.score_trace(
            name="memory_chunk_count",
            value=float(
                len(mem_used.get("similar_proposals") or [])
                + len(mem_used.get("win_patterns") or [])
                + len(mem_used.get("methodology_blocks") or [])
            ),
            data_type="NUMERIC",
        )
        chain.score_trace(
            name="memory_alignment_score",
            value=1.0 if mem_ok else 0.0,
            data_type="NUMERIC",
        )
        chain.score_trace(
            name="degradation_level",
            value=0.0 if mem_ok else 1.0,
            data_type="NUMERIC",
        )
    lf.flush()
    return result


async def execute_proposal_pipeline_async(
    rfp_text: str,
    user_id: str,
    *,
    rfp_id: str | None = None,
    llm: LLMClient | None = None,
    pipeline_mode: str = "auto",
    workspace_snapshot: dict[str, Any] | None = None,
    rfp_for_generation: str | None = None,
    draft_intensity: str = "balanced",
    prior_run_ids: list[str] | None = None,
    learning_snippet_applied: bool = False,
    proposal_depth: str = "full",
) -> dict[str, Any]:
    return await asyncio.wait_for(
        asyncio.to_thread(
            execute_proposal_pipeline,
            rfp_text,
            user_id,
            rfp_id=rfp_id,
            llm=llm,
            pipeline_mode=pipeline_mode,
            workspace_snapshot=workspace_snapshot,
            rfp_for_generation=rfp_for_generation,
            draft_intensity=draft_intensity,
            prior_run_ids=prior_run_ids,
            learning_snippet_applied=learning_snippet_applied,
            proposal_depth=proposal_depth,
        ),
        timeout=settings.pipeline_timeout_s,
    )
