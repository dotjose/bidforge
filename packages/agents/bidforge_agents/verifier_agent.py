from __future__ import annotations

import json
from typing import Literal

from bidforge_prompts.freelance_verifier import build_freelance_verifier_messages
from bidforge_prompts.verifier import build_verifier_messages
from bidforge_schemas import (
    FormatterAgentOutput,
    FreelanceHookOutput,
    FreelanceProposalOutput,
    JobUnderstandingOutput,
    RagContext,
    RequirementAgentOutput,
    StrategyAgentOutput,
    VerifierAgentOutput,
)
from bidforge_shared import LLMClient

STEP = "verifier_agent"
STEP_FREELANCE = "freelance_verifier_agent"


def run_verifier_agent(
    formatted: FormatterAgentOutput,
    requirements: RequirementAgentOutput,
    llm: LLMClient,
    *,
    strategy: StrategyAgentOutput | None = None,
    rag_context: RagContext | None = None,
    pipeline_mode: Literal["enterprise", "freelance"] = "enterprise",
    freelance_proposal: FreelanceProposalOutput | None = None,
    hook: FreelanceHookOutput | None = None,
    job_understanding: JobUnderstandingOutput | None = None,
) -> VerifierAgentOutput:
    strat = strategy or StrategyAgentOutput()
    rag = rag_context or RagContext()
    if pipeline_mode == "freelance":
        fp = freelance_proposal or FreelanceProposalOutput()
        hk = hook or FreelanceHookOutput()
        ju = job_understanding or JobUnderstandingOutput()
        mem = {"freelance_win_patterns": rag.freelance_win_patterns}
        system, user = build_freelance_verifier_messages(
            fp.model_dump_json(),
            hk.model_dump_json(),
            ju.model_dump_json(),
            json.dumps(mem),
        )
        return llm.complete_json(step=STEP_FREELANCE, system=system, user=user, response_model=VerifierAgentOutput)
    system, user = build_verifier_messages(
        formatted.model_dump_json(),
        requirements.model_dump_json(),
        strategy_json=strat.model_dump_json(),
        rag_context_json=rag.model_dump_json(),
    )
    return llm.complete_json(step=STEP, system=system, user=user, response_model=VerifierAgentOutput)
