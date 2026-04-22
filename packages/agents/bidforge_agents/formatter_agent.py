from __future__ import annotations

from bidforge_prompts.formatter import build_formatter_messages
from bidforge_schemas import FormatterAgentOutput, ProposalAgentOutput
from bidforge_shared import LLMClient

STEP = "formatter_agent"


def run_formatter_agent(proposal: ProposalAgentOutput, llm: LLMClient) -> FormatterAgentOutput:
    system, user = build_formatter_messages(proposal.model_dump_json())
    return llm.complete_json(step=STEP, system=system, user=user, response_model=FormatterAgentOutput)
