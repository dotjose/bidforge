"""Proposal node — sole long-form writer."""

from __future__ import annotations

import json
from typing import Literal

from bidforge_prompts.proposal import build_proposal_messages
from bidforge_schemas import (
    InputClassifierOutput,
    JobUnderstandingOutput,
    ProposalWriterOutput,
    RagContext,
    RequirementAgentOutput,
    SolutionBlueprintOutput,
    StrategyAgentOutput,
)
from bidforge_shared import LLMClient

STEP = "proposal"


def _experience_memory_json(rag: RagContext, *, brain: Literal["enterprise", "job"]) -> str:
    if brain == "job":
        return json.dumps({"freelance_win_patterns": rag.freelance_win_patterns})
    return json.dumps(
        {
            "similar_proposals": rag.similar_proposals[:16],
            "win_patterns": rag.win_patterns[:16],
            "methodology_blocks": rag.methodology_blocks[:12],
        },
    )


def run_proposal(
    strategy: StrategyAgentOutput,
    blueprint: SolutionBlueprintOutput,
    requirements: RequirementAgentOutput,
    job_signals: JobUnderstandingOutput | None,
    rag: RagContext,
    brief_excerpt: str,
    llm: LLMClient,
    *,
    brain: Literal["enterprise", "job"],
    router_output: InputClassifierOutput | None = None,
    proposal_depth: str = "full",
) -> ProposalWriterOutput:
    ic = router_output or InputClassifierOutput()
    ju = job_signals or JobUnderstandingOutput()
    job_signals_json = ju.model_dump_json() if brain == "job" else "{}"
    system, user = build_proposal_messages(
        strategy.model_dump_json(),
        blueprint.model_dump_json(),
        requirements.model_dump_json(),
        job_signals_json,
        ic.model_dump_json(),
        _experience_memory_json(rag, brain=brain),
        brief_excerpt,
        proposal_depth=(proposal_depth or "full").strip().lower(),
    )
    return llm.complete_json(step=STEP, system=system, user=user, response_model=ProposalWriterOutput)
