from __future__ import annotations

import json

from bidforge_prompts.freelance_proposal import build_freelance_proposal_messages
from bidforge_schemas import (
    FreelanceHookOutput,
    FreelanceProposalOutput,
    JobUnderstandingOutput,
    RagContext,
    StrategyAgentOutput,
)
from bidforge_shared import LLMClient

STEP = "freelance_proposal_agent"


def run_freelance_proposal_agent(
    strategy: StrategyAgentOutput,
    hook: FreelanceHookOutput,
    job: JobUnderstandingOutput,
    rag: RagContext,
    job_text: str,
    llm: LLMClient,
) -> FreelanceProposalOutput:
    mem = {"freelance_win_patterns": rag.freelance_win_patterns}
    system, user = build_freelance_proposal_messages(
        hook.hook,
        hook.trust_signal,
        strategy.model_dump_json(),
        job.model_dump_json(),
        json.dumps(mem),
        job_text,
    )
    return llm.complete_json(step=STEP, system=system, user=user, response_model=FreelanceProposalOutput)
