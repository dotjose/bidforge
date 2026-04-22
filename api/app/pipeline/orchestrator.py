"""Stateless orchestration: Langfuse trace + sequential agent stages."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import time
import uuid
from typing import Any

from bidforge_agents import (
    run_formatter_agent,
    run_proposal_agent,
    run_requirement_agent,
    run_strategy_agent,
    run_verifier_agent,
)
from bidforge_agents.critique_agent import run_critique_agent_enterprise, run_critique_agent_freelance
from bidforge_agents.cross_proposal_diff_agent import run_cross_proposal_diff_agent
from bidforge_agents.freelance_hook_agent import run_freelance_hook_agent
from bidforge_agents.freelance_proposal_agent import run_freelance_proposal_agent
from bidforge_agents.input_classifier_agent import run_input_classifier
from bidforge_agents.job_understanding_agent import run_job_understanding_agent
from bidforge_agents.pipeline import PipelineStages, run_stages_after_requirements
from bidforge_agents.proposal_sanitize import sanitize_formatter_output
from bidforge_agents.structuring_agent import run_requirement_structuring_agent
from bidforge_agents.strategy_agent import run_strategy_agent_freelance
from bidforge_agents.timeline_agent import run_timeline_agent
from bidforge_schemas import (
    WorkspaceState,
    CrossProposalDiffOutput,
    FormatterAgentOutput,
    FreelanceHookOutput,
    FreelanceProposalOutput,
    InputClassifierOutput,
    JobUnderstandingOutput,
    RagContext,
    RequirementAgentOutput,
    RequirementStructuringOutput,
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
    fetch_top_freelance_wins_for_diff,
    insert_canonical_proposal_row,
    insert_freelance_win_memory,
    insert_proposal_memory_entries,
    insert_proposal_run,
    merge_freelance_win_rows_into_rag_patterns,
)
from app.pipeline.errors import FailedPipeline
from app.pipeline.run_envelope import attach_run_envelope, build_insights
from app.pipeline.title_inference import infer_proposal_title
from app.rag.retrieval import retrieve_rag_context
from app.workspace.agents import workspace_preferences_block

log = logging.getLogger(__name__)


def _proposal_plaintext_for_persistence(payload: dict[str, Any], *, pipeline_mode: str) -> str:
    prop = payload.get("proposal")
    if not isinstance(prop, dict):
        return ""
    if pipeline_mode == "freelance":
        fw = prop.get("freelance")
        if isinstance(fw, dict):
            keys = ("hook", "understanding_need", "approach", "relevant_experience", "call_to_action")
            parts = [str(fw.get(k) or "").strip() for k in keys]
            return "\n\n".join(p for p in parts if p)
        return ""
    secs = prop.get("sections")
    if isinstance(secs, dict):
        keys2 = ("executive_summary", "technical_approach", "delivery_plan", "risk_management")
        parts2 = [str(secs.get(k) or "").strip() for k in keys2]
        return "\n\n".join(p for p in parts2 if p)
    return ""


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


def _build_llm() -> LLMClient:
    return build_llm_from_settings()


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


def _prior_wins_for_diff_agent(clerk_user_id: str) -> list[dict[str, Any]]:
    rows = fetch_top_freelance_wins_for_diff(clerk_user_id, limit=3)
    return [
        {
            "opening_hook": r.get("opening_hook"),
            "winning_sections": r.get("winning_sections"),
            "score": r.get("score"),
            "job_type": r.get("job_type"),
        }
        for r in rows
        if isinstance(r, dict)
    ]


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
        extra = fetch_freelance_win_memory_rows(user_id, limit=8)
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
    fp: FreelanceProposalOutput,
    ver: VerifierAgentOutput,
    ic: InputClassifierOutput,
    llm: LLMClient,
) -> None:
    if ver.score <= 75:
        return
    hook_text = (fp.hook or "").strip()
    if not hook_text:
        return
    hook_line = hook_text.split("\n")[0][:2000]
    opening_lines = [x.strip() for x in hook_text.split("\n")[:3] if x.strip()]
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
        winning_sections=build_winning_sections_payload(fp.model_dump()),
        score=int(ver.score),
        extracted_patterns=build_extracted_patterns(
            structure_pattern="hook → intent → approach → relevance → CTA",
            opening_lines=opening_lines,
            score=int(ver.score),
        ),
        embedding=emb,
    )


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
    fp: FreelanceProposalOutput | None,
    fmt: FormatterAgentOutput | None,
    ver: VerifierAgentOutput,
) -> None:
    """Adds title, cross_proposal_diff, persisted_run_id; autosaves freelance wins. Mutates payload."""
    icx = ic or InputClassifierOutput(
        input_type="job_post",
        recommended_pipeline="freelance" if pipeline_mode == "freelance" else "enterprise",
        rationale="",
    )
    title = infer_proposal_title(
        rfp_text,
        pipeline_mode=pipeline_mode,
        job_understanding=ju,
        input_classification=icx,
        requirements=req,
    )
    payload["title"] = title
    prior = _prior_wins_for_diff_agent(user_id)
    if fp is not None:
        current: dict[str, Any] = fp.model_dump()
    elif fmt is not None:
        current = {"formatted": fmt.model_dump()}
    else:
        current = {}
    cross = CrossProposalDiffOutput()
    try:
        cross = run_cross_proposal_diff_agent(current, prior, llm)
    except Exception as e:  # noqa: BLE001
        log.warning("cross_proposal_diff_agent skipped: %s", e)
    payload["cross_proposal_diff"] = cross.model_dump()

    trace = str(payload.get("trace_id") or "")
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
    )
    if pid:
        payload["persisted_run_id"] = pid

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
    if pipeline_mode == "freelance" and fp is not None:
        hook_line = (fp.hook or "").strip().split("\n")[0][:2000]
        if hook_line:
            mem_snips.append(("strong_line", hook_line))
        apx = (fp.approach or "").strip()[:2000]
        if apx:
            mem_snips.append(("win_pattern", apx))
    elif fmt is not None:
        ex0 = (fmt.executive_summary or "").strip()[:2000]
        if ex0:
            mem_snips.append(("strong_line", ex0))
        tech0 = (fmt.technical_approach or "").strip()[:2000]
        if tech0:
            mem_snips.append(("win_pattern", tech0))
    if mem_snips:
        insert_proposal_memory_entries(user_id, mem_snips, llm)

    if pipeline_mode == "freelance" and fp is not None and ic is not None and ver.score > 75:
        try:
            _maybe_autosave_high_score_win(user_id, fp, ver, ic, llm)
        except Exception as e:  # noqa: BLE001
            log.warning("freelance win memory autosave failed: %s", e)


def _apply_freelance_cold_start_if_needed(rag: RagContext) -> tuple[RagContext, bool]:
    """Returns (rag_for_agents, had_real_indexed_freelance_memory). Empty memory does not mutate RAG."""
    had_real = rag.has_usable_freelance_memory()
    if had_real:
        return rag, True
    log.debug(
        "No indexed freelance win memory for this account — pipeline continues (memory_status=empty)",
    )
    return rag, False


def _resolve_brain(pipeline_mode: str, rfp_text: str, llm: LLMClient) -> tuple[InputClassifierOutput, str]:
    pm = (pipeline_mode or "auto").strip().lower()
    if pm == "freelance":
        return (
            InputClassifierOutput(
                input_type="manual",
                recommended_pipeline="freelance",
                rationale="User selected Freelance Win Engine.",
            ),
            "freelance",
        )
    if pm == "enterprise":
        return (
            InputClassifierOutput(
                input_type="manual",
                recommended_pipeline="enterprise",
                rationale="User selected Enterprise mode.",
            ),
            "enterprise",
        )
    ic = run_input_classifier(rfp_text, llm)
    mode = ic.recommended_pipeline
    if mode not in ("enterprise", "freelance"):
        mode = "freelance" if ic.input_type in ("job_post", "upwork", "freelancer") else "enterprise"
    if ic.recommended_pipeline != mode:
        ic = ic.model_copy(update={"recommended_pipeline": mode})  # type: ignore[arg-type]
    return ic, mode


def _memory_summary_for_ui(rag: RagContext, *, pipeline_mode: str = "enterprise") -> dict[str, Any]:
    """UI-facing retrieval summary — win patterns only (no document titles or methodology dumps)."""
    fwp = [
        {"id": w.get("id"), "label": w.get("label"), "outcome": w.get("outcome")}
        for w in rag.freelance_win_patterns[:12]
        if str(w.get("outcome") or "").lower() != "synthetic_seed"
    ]
    return {
        "similar_proposals": [],
        "methodology_blocks": [],
        "win_patterns": [
            {"id": w.get("id"), "label": w.get("label"), "outcome": w.get("outcome")}
            for w in rag.win_patterns[:12]
        ],
        "freelance_win_patterns": fwp,
        "pipeline_mode": pipeline_mode,
    }


def _proposal_dict(
    stages: PipelineStages,
    *,
    memory_grounded: bool,
    memory_summary: dict[str, Any],
    grounding_warning: str | None,
) -> dict[str, Any]:
    section_attr = [
        {
            "title": s.title,
            "covers_requirements": list(s.covers_requirements),
            "based_on_memory": list(s.based_on_memory),
        }
        for s in stages.proposal.sections
    ]
    return {
        "sections": {
            "executive_summary": stages.formatted.executive_summary,
            "technical_approach": stages.formatted.technical_approach,
            "delivery_plan": stages.formatted.delivery_plan,
            "risk_management": stages.formatted.risk_management,
        },
        "format_notes": [],
        "strategy": {
            "strategy": stages.strategy.strategy,
            "based_on": stages.strategy.based_on,
            "positioning": stages.strategy.positioning,
            "win_themes": stages.strategy.win_themes,
            "differentiators": stages.strategy.differentiators,
            "response_tone": stages.strategy.response_tone,
            "freelance_hook_strategy": stages.strategy.freelance_hook_strategy or "",
        },
        "memory_summary": memory_summary,
        "memory_grounded": memory_grounded,
        "grounding_warning": grounding_warning,
        "section_attributions": section_attr,
        "pipeline_mode": "enterprise",
    }


def _freelance_proposal_dict(
    *,
    fp: FreelanceProposalOutput,
    strat: StrategyAgentOutput,
    hook: FreelanceHookOutput,
    memory_grounded: bool,
    memory_summary: dict[str, Any],
    grounding_warning: str | None,
) -> dict[str, Any]:
    ex, ta, dp, rm = fp.to_formatter_slots()
    proof_block = "\n\n".join(
        p for p in (fp.approach.strip(), fp.relevant_experience.strip()) if p
    )
    return {
        "sections": {
            "executive_summary": ex,
            "technical_approach": ta,
            "delivery_plan": dp,
            "risk_management": rm,
        },
        "format_notes": [],
        "strategy": {
            "strategy": strat.strategy,
            "based_on": strat.based_on,
            "positioning": strat.positioning,
            "win_themes": strat.win_themes,
            "differentiators": strat.differentiators,
            "response_tone": strat.response_tone,
            "freelance_hook_strategy": strat.freelance_hook_strategy or "",
        },
        "memory_summary": memory_summary,
        "memory_grounded": memory_grounded,
        "grounding_warning": grounding_warning,
        "section_attributions": [],
        "pipeline_mode": "freelance",
        "freelance": {
            "hook": fp.hook,
            "understanding_need": fp.understanding_need,
            "approach": fp.approach,
            "relevant_experience": fp.relevant_experience,
            "call_to_action": fp.call_to_action,
            "opening": fp.hook,
            "body": fp.understanding_need,
            "proof": proof_block,
            "closing": fp.call_to_action,
        },
        "hook": hook.model_dump(),
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
    rag_enabled: bool = True,
    use_freelance_memory_table: bool = True,
) -> dict[str, Any]:
    """Core freelance pipeline (optionally Langfuse-traced per step)."""

    def _ju():
        return run_job_understanding_agent(rfp_core, client_llm)

    def _rag(ju: JobUnderstandingOutput):
        return _freelance_rag_with_table_merge(
            rfp_core,
            user_id,
            ju,
            client_llm,
            rag_enabled=rag_enabled,
            use_freelance_memory_table=use_freelance_memory_table,
        )

    if lf is None:
        ju = _ju()
        partial["job_understanding"] = ju.model_dump()
        rag = _rag(ju)
        rag, had_real_mem = _apply_freelance_cold_start_if_needed(rag)
        partial["rag"] = rag.model_dump()
        strat = run_strategy_agent_freelance(ju, rfp_gen, client_llm, rag_context=rag)
        partial["strategy"] = strat.model_dump()
        hook = run_freelance_hook_agent(strat, ju, rag, rfp_gen, client_llm)
        partial["hook"] = hook.model_dump()
        fp = run_freelance_proposal_agent(strat, hook, ju, rag, rfp_gen, client_llm)
        partial["freelance_proposal"] = fp.model_dump()
        ex, ta_, dp, rm = fp.to_formatter_slots()
        dummy_fmt = FormatterAgentOutput(
            executive_summary=ex,
            technical_approach=ta_,
            delivery_plan=dp,
            risk_management=rm,
        )
        ver = run_verifier_agent(
            dummy_fmt,
            RequirementAgentOutput(),
            client_llm,
            strategy=strat,
            rag_context=rag,
            pipeline_mode="freelance",
            freelance_proposal=fp,
            hook=hook,
            job_understanding=ju,
        )
        partial["verification"] = ver.model_dump()
        critique = run_critique_agent_freelance(
            ver,
            fp.model_dump(),
            hook.model_dump(),
            rag.freelance_win_patterns,
            client_llm,
        )
        partial["critique"] = critique.model_dump()
    else:

        def ju_fn():
            return _ju()

        ju = _run_step_traced(
            lf,
            "job_understanding_agent",
            ju_fn,
            input_payload={"job_excerpt": rfp_core[:800]},
            base_metadata=base_md,
            llm=client_llm,
        )
        partial["job_understanding"] = ju.model_dump()

        rag = _run_step_traced(
            lf,
            "rag_retrieval_freelance",
            lambda: _rag(ju),
            input_payload={"job_excerpt": rfp_core[:800]},
            base_metadata={**base_md, "model_name": settings.openrouter_embedding_model},
            llm=client_llm,
        )
        rag, had_real_mem = _apply_freelance_cold_start_if_needed(rag)
        partial["rag"] = rag.model_dump()

        strat = _run_step_traced(
            lf,
            "strategy_agent_freelance",
            lambda: run_strategy_agent_freelance(ju, rfp_gen, client_llm, rag_context=rag),
            input_payload={"job_understanding": ju.model_dump(), "rag": rag.model_dump()},
            base_metadata=base_md,
            llm=client_llm,
        )
        partial["strategy"] = strat.model_dump()

        hook = _run_step_traced(
            lf,
            "freelance_hook_agent",
            lambda: run_freelance_hook_agent(strat, ju, rag, rfp_gen, client_llm),
            input_payload={"strategy": strat.model_dump()},
            base_metadata=base_md,
            llm=client_llm,
        )
        partial["hook"] = hook.model_dump()

        fp = _run_step_traced(
            lf,
            "freelance_proposal_agent",
            lambda: run_freelance_proposal_agent(strat, hook, ju, rag, rfp_gen, client_llm),
            input_payload={"hook": hook.model_dump()},
            base_metadata=base_md,
            llm=client_llm,
        )
        partial["freelance_proposal"] = fp.model_dump()

        ex2, ta2, dp2, rm2 = fp.to_formatter_slots()
        dummy_fmt = FormatterAgentOutput(
            executive_summary=ex2,
            technical_approach=ta2,
            delivery_plan=dp2,
            risk_management=rm2,
        )
        ver = _run_step_traced(
            lf,
            "freelance_verifier_agent",
            lambda: run_verifier_agent(
                dummy_fmt,
                RequirementAgentOutput(),
                client_llm,
                strategy=strat,
                rag_context=rag,
                pipeline_mode="freelance",
                freelance_proposal=fp,
                hook=hook,
                job_understanding=ju,
            ),
            input_payload={"proposal": fp.model_dump()},
            base_metadata=base_md,
            llm=client_llm,
        )
        partial["verification"] = ver.model_dump()

        critique = _run_step_traced(
            lf,
            "critique_agent",
            lambda: run_critique_agent_freelance(
                ver,
                fp.model_dump(),
                hook.model_dump(),
                rag.freelance_win_patterns,
                client_llm,
            ),
            input_payload={"verifier": ver.model_dump()},
            base_metadata=base_md,
            llm=client_llm,
        )
        partial["critique"] = critique.model_dump()

    mem_ok = had_real_mem
    mem_status = "grounded" if had_real_mem else "empty"
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
        "proposal": _freelance_proposal_dict(
            fp=fp,
            strat=strat,
            hook=hook,
            memory_grounded=mem_ok,
            memory_summary=mem_used,
            grounding_warning=warn,
        ),
        "timeline": [],
        "memory_used": mem_used,
        "memory_status": mem_status,
        "score": ver.score,
        "issues": _flatten_issues(ver),
        "suggestions": list(ver.suggestions or []),
        "trace_id": trace_id,
        "memory_grounded": mem_ok,
        "grounding_warning": warn,
        "pipeline_mode": "freelance",
        "input_classification": ic.model_dump(),
        "job_understanding": ju.model_dump(),
        "hook": hook.model_dump(),
        "critique": critique.model_dump(),
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
        fp=fp,
        fmt=None,
        ver=ver,
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
) -> dict[str, Any]:
    client_llm = llm or _build_llm()
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
    ic, resolved = _resolve_brain(pipeline_mode, rfp_core, client_llm)

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
                    rag_enabled=rag_ok,
                    use_freelance_memory_table=fl_mem,
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
                        rag_enabled=rag_ok,
                        use_freelance_memory_table=fl_mem,
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
            req = run_requirement_agent(rfp_core, client_llm)
            partial_e["requirements"] = req.model_dump()
            struct_out = run_requirement_structuring_agent(req, client_llm)
            req = _merge_structuring(req, struct_out)
            partial_e["requirements"] = req.model_dump()
            rag = _safe_enterprise_rag(
                rfp_core,
                user_id,
                req,
                client_llm,
                rag_enabled=rag_ok,
                enterprise_case_studies=ent_mem,
            )
            partial_e["rag"] = rag.model_dump()
            if not rag.has_usable_memory() and settings.require_rag_memory:
                log.warning("Indexed proposal memory empty — continuing with general-intelligence fallback")
            strat, prop, timeline, fmt, ver = run_stages_after_requirements(
                req,
                client_llm,
                rag_context=rag,
                rfp_text=rfp_core,
                workspace_preferences=workspace_prefs_effective,
            )
            stages = PipelineStages(
                rag=rag,
                requirements=req,
                strategy=strat,
                proposal=prop,
                timeline=timeline,
                formatted=fmt,
                verification=ver,
            )
            critique = run_critique_agent_enterprise(ver, fmt.model_dump_json(), req, client_llm)
            partial_e["critique"] = critique.model_dump()
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
        timeline_out = [p.model_dump() for p in stages.timeline.timeline]
        proposal = _proposal_dict(
            stages,
            memory_grounded=mem_ok,
            memory_summary=mem_used,
            grounding_warning=warn,
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
            "memory_status": "grounded" if mem_ok else "empty",
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
            "critique": critique.model_dump(),
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
            fp=None,
            fmt=stages.formatted,
            ver=ver,
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
            req = _run_step_traced(
                lf,
                "requirement_agent",
                lambda: run_requirement_agent(rfp_core, client_llm),
                input_payload={"rfp_excerpt": rfp_core[:800]},
                base_metadata=base_md,
                llm=client_llm,
            )
            partial_out["requirements"] = req.model_dump()

            struct_out = _run_step_traced(
                lf,
                "requirement_structuring",
                lambda: run_requirement_structuring_agent(req, client_llm),
                input_payload={"requirements": req.model_dump()},
                base_metadata=base_md,
                llm=client_llm,
            )
            req = _merge_structuring(req, struct_out)
            partial_out["requirements"] = req.model_dump()

            rag = _run_step_traced(
                lf,
                "rag_retrieval",
                lambda: _safe_enterprise_rag(
                    rfp_core,
                    user_id,
                    req,
                    client_llm,
                    rag_enabled=rag_ok,
                    enterprise_case_studies=ent_mem,
                ),
                input_payload={"rfp_excerpt": rfp_core[:800]},
                base_metadata={
                    **base_md,
                    "model_name": settings.openrouter_embedding_model,
                },
                llm=client_llm,
            )
            partial_out["rag"] = rag.model_dump()
            if not rag.has_usable_memory() and settings.require_rag_memory:
                log.warning("Indexed proposal memory empty — continuing with general-intelligence fallback")

            strat = _run_step_traced(
                lf,
                "strategy_agent",
                lambda: run_strategy_agent(
                    req,
                    client_llm,
                    rag_context=rag,
                    workspace_preferences=workspace_prefs_effective,
                ),
                input_payload={"requirements": req.model_dump(), "rag": rag.model_dump()},
                base_metadata=base_md,
                llm=client_llm,
            )
            partial_out["strategy"] = strat.model_dump()

            prop = _run_step_traced(
                lf,
                "proposal_agent",
                lambda: run_proposal_agent(
                    strat,
                    client_llm,
                    rag_context=rag,
                    workspace_preferences=workspace_prefs_effective,
                    requirements=req,
                ),
                input_payload={"strategy": strat.model_dump(), "rag": rag.model_dump()},
                base_metadata=base_md,
                llm=client_llm,
            )
            partial_out["proposal"] = prop.model_dump()

            timeline = _run_step_traced(
                lf,
                "timeline_agent",
                lambda: run_timeline_agent(rfp_core, req),
                input_payload={
                    "rfp_excerpt": rfp_core[:800],
                    "matrix_rows": len(req.requirement_matrix),
                },
                base_metadata=base_md,
                llm=client_llm,
            )
            partial_out["timeline"] = timeline.model_dump()

            fmt = _run_step_traced(
                lf,
                "formatter_agent",
                lambda: sanitize_formatter_output(run_formatter_agent(prop, client_llm)),
                input_payload={"proposal": prop.model_dump()},
                base_metadata=base_md,
                llm=client_llm,
            )
            partial_out["formatted"] = fmt.model_dump()

            ver = _run_step_traced(
                lf,
                "verifier_agent",
                lambda: run_verifier_agent(
                    fmt,
                    req,
                    client_llm,
                    strategy=strat,
                    rag_context=rag,
                ),
                input_payload={"formatted": fmt.model_dump(), "requirements": req.model_dump()},
                base_metadata=base_md,
                llm=client_llm,
            )
            partial_out["verification"] = ver.model_dump()

            critique = _run_step_traced(
                lf,
                "critique_agent",
                lambda: run_critique_agent_enterprise(ver, fmt.model_dump_json(), req, client_llm),
                input_payload={"verification": ver.model_dump()},
                base_metadata=base_md,
                llm=client_llm,
            )
            partial_out["critique"] = critique.model_dump()
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
            strategy=strat,
            proposal=prop,
            timeline=timeline,
            formatted=fmt,
            verification=ver,
        )
        mem_ok = stages.rag.has_usable_memory()
        mem_used = _memory_summary_for_ui(stages.rag, pipeline_mode="enterprise")
        warn: str | None = None
        timeline_out = [p.model_dump() for p in stages.timeline.timeline]
        ins = build_insights(
            warnings=[],
            missing_context=not mem_ok,
            rag_fallback_mode=False,
        )
        ent_payload: dict[str, Any] = {
            "proposal": _proposal_dict(
                stages,
                memory_grounded=mem_ok,
                memory_summary=mem_used,
                grounding_warning=warn,
            ),
            "timeline": timeline_out,
            "memory_used": mem_used,
            "memory_status": "grounded" if mem_ok else "empty",
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
            "critique": critique.model_dump(),
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
            fp=None,
            fmt=stages.formatted,
            ver=ver,
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
        ),
        timeout=settings.pipeline_timeout_s,
    )
