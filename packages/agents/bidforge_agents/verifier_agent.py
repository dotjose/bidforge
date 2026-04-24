"""Verifier node — enterprise or job-post scoring (read-only)."""

from __future__ import annotations

import json

from bidforge_prompts.verifier import build_verifier_enterprise_messages, build_verifier_job_messages
from bidforge_schemas import (
    JobUnderstandingOutput,
    ProposalWriterOutput,
    RagContext,
    RequirementAgentOutput,
    SolutionBlueprintOutput,
    StrategyAgentOutput,
    VerifierAgentOutput,
)
from bidforge_shared import LLMClient

STEP_ENTERPRISE = "verifier"
STEP_JOB = "verifier_job"


def run_verifier(
    proposal_document: ProposalWriterOutput,
    requirements: RequirementAgentOutput,
    llm: LLMClient,
    *,
    strategy: StrategyAgentOutput | None = None,
    rag_context: RagContext | None = None,
    pipeline_mode: str = "enterprise",
    job_signals: JobUnderstandingOutput | None = None,
    solution_blueprint: SolutionBlueprintOutput | None = None,
) -> VerifierAgentOutput:
    strat = strategy or StrategyAgentOutput()
    rag = rag_context or RagContext()
    if pipeline_mode == "freelance":
        ju = job_signals or JobUnderstandingOutput()
        bp = solution_blueprint or SolutionBlueprintOutput()
        mem = {"freelance_win_patterns": rag.freelance_win_patterns}
        system, user = build_verifier_job_messages(
            proposal_document.model_dump_json(),
            ju.model_dump_json(),
            json.dumps(mem),
            bp.model_dump_json(),
        )
        return llm.complete_json(step=STEP_JOB, system=system, user=user, response_model=VerifierAgentOutput)
    system, user = build_verifier_enterprise_messages(
        proposal_document.model_dump_json(),
        requirements.model_dump_json(),
        strategy_json=strat.model_dump_json(),
        rag_context_json=rag.model_dump_json(),
    )
    return llm.complete_json(step=STEP_ENTERPRISE, system=system, user=user, response_model=VerifierAgentOutput)
