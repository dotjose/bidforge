from __future__ import annotations

import json

from bidforge_prompts.strategy import build_strategy_messages
from bidforge_prompts.strategy_freelance import build_strategy_freelance_messages
from bidforge_schemas import JobUnderstandingOutput, RagContext, RequirementAgentOutput, StrategyAgentOutput
from bidforge_shared import LLMClient

STEP = "strategy_agent"
STEP_FREELANCE = "strategy_agent_freelance"


def run_strategy_agent(
    requirements: RequirementAgentOutput,
    llm: LLMClient,
    *,
    rag_context: RagContext | None = None,
    workspace_preferences: str = "",
) -> StrategyAgentOutput:
    rag = rag_context or RagContext()
    system, user = build_strategy_messages(
        requirements.model_dump_json(),
        rag.model_dump_json(),
        workspace_preferences=workspace_preferences,
    )
    return llm.complete_json(step=STEP, system=system, user=user, response_model=StrategyAgentOutput)


def run_strategy_agent_freelance(
    job: JobUnderstandingOutput,
    job_text: str,
    llm: LLMClient,
    *,
    rag_context: RagContext | None = None,
) -> StrategyAgentOutput:
    rag = rag_context or RagContext()
    mem = {"freelance_win_patterns": rag.freelance_win_patterns}
    system, user = build_strategy_freelance_messages(
        job.model_dump_json(),
        job_text,
        json.dumps(mem),
    )
    return llm.complete_json(step=STEP_FREELANCE, system=system, user=user, response_model=StrategyAgentOutput)
