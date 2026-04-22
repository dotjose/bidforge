from __future__ import annotations

from bidforge_prompts.proposal import build_proposal_messages
from bidforge_schemas import ProposalAgentOutput, RagContext, RequirementAgentOutput, StrategyAgentOutput
from bidforge_shared import LLMClient

STEP = "proposal_agent"


def run_proposal_agent(
    strategy: StrategyAgentOutput,
    llm: LLMClient,
    *,
    rag_context: RagContext | None = None,
    workspace_preferences: str = "",
    requirements: RequirementAgentOutput | None = None,
) -> ProposalAgentOutput:
    rag = rag_context or RagContext()
    req = requirements or RequirementAgentOutput()
    system, user = build_proposal_messages(
        strategy.model_dump_json(),
        rag.model_dump_json(),
        req.model_dump_json(),
        workspace_preferences=workspace_preferences,
    )
    return llm.complete_json(step=STEP, system=system, user=user, response_model=ProposalAgentOutput)
