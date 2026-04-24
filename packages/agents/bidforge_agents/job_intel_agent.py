"""Job intelligence node — enterprise extraction + matrix, or freelance job signals."""

from __future__ import annotations

from bidforge_prompts.job_intel import (
    build_job_intel_extract_messages,
    build_job_intel_matrix_messages,
    build_job_intel_signals_messages,
)
from bidforge_schemas import (
    JobUnderstandingOutput,
    RequirementAgentOutput,
    RequirementRow,
    RequirementStructuringOutput,
    StructuredRequirementItem,
)
from bidforge_shared import LLMClient, PipelineStepError

STEP_EXTRACT = "job_intel__extract"
STEP_MATRIX = "job_intel__matrix"
STEP_SIGNALS = "job_intel__signals"


def run_job_intel_extract(rfp_text: str, llm: LLMClient) -> RequirementAgentOutput:
    text = (rfp_text or "").strip()
    if len(text) < 1:
        raise PipelineStepError(STEP_EXTRACT, "RFP text is empty")
    system, user = build_job_intel_extract_messages(text)
    return llm.complete_json(step=STEP_EXTRACT, system=system, user=user, response_model=RequirementAgentOutput)


def run_job_intel_matrix(requirements: RequirementAgentOutput, llm: LLMClient) -> RequirementStructuringOutput:
    system, user = build_job_intel_matrix_messages(requirements.model_dump_json())
    return llm.complete_json(step=STEP_MATRIX, system=system, user=user, response_model=RequirementStructuringOutput)


def run_job_intel_signals(job_text: str, llm: LLMClient) -> JobUnderstandingOutput:
    system, user = build_job_intel_signals_messages(job_text)
    return llm.complete_json(step=STEP_SIGNALS, system=system, user=user, response_model=JobUnderstandingOutput)


def requirements_for_solution_builder(ju: JobUnderstandingOutput) -> RequirementAgentOutput:
    """Minimal RequirementAgentOutput from job signals for shared solution + proposal paths."""
    texts: list[str] = []
    for x in ju.explicit_requirements:
        t = str(x).strip()
        if t:
            texts.append(t[:500])
    for x in ju.implicit_requirements:
        t = str(x).strip()
        if t and t not in texts:
            texts.append(t[:500])
    matrix: list[RequirementRow] = []
    for i, desc in enumerate(texts[:16], start=1):
        matrix.append(
            RequirementRow(
                id=f"REQ_{i}",
                type="deliverable",
                description=desc,
                mandatory=True,
                source="Job post",
            )
        )
    if not matrix:
        fallback = (ju.buyer_intent or "Deliver the stated scope with clear acceptance checks.").strip()[:500]
        matrix.append(
            RequirementRow(
                id="REQ_1",
                type="deliverable",
                description=fallback,
                mandatory=True,
                source="Job post",
            )
        )
    structured = [StructuredRequirementItem(ref=r.id, text=r.description) for r in matrix]
    return RequirementAgentOutput(
        requirements=[r.description for r in matrix],
        constraints=[ju.urgency.strip()] if ju.urgency.strip() else [],
        risks=[str(x).strip() for x in ju.risk_concerns if str(x).strip()][:12],
        compliance_items=[],
        structured_requirements=structured,
        requirement_matrix=matrix,
    )
