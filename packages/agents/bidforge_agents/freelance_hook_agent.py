from __future__ import annotations

import json

from bidforge_prompts.freelance_hook import build_freelance_hook_messages
from bidforge_schemas import FreelanceHookOutput, JobUnderstandingOutput, RagContext, StrategyAgentOutput
from bidforge_shared import LLMClient

STEP = "freelance_hook_agent"


def run_freelance_hook_agent(
    strategy: StrategyAgentOutput,
    job: JobUnderstandingOutput,
    rag: RagContext,
    job_text: str,
    llm: LLMClient,
) -> FreelanceHookOutput:
    mem = {"freelance_win_patterns": rag.freelance_win_patterns}
    system, user = build_freelance_hook_messages(
        strategy.model_dump_json(),
        job.model_dump_json(),
        json.dumps(mem),
        job_text,
    )
    return llm.complete_json(step=STEP, system=system, user=user, response_model=FreelanceHookOutput)
