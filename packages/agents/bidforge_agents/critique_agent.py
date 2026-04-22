from __future__ import annotations

import json
from typing import Any

from bidforge_prompts.critique import build_critique_enterprise_messages, build_critique_freelance_messages
from bidforge_schemas import ProposalCritiqueOutput, RequirementAgentOutput, VerifierAgentOutput
from bidforge_shared import LLMClient

STEP = "critique_agent"


def run_critique_agent_freelance(
    ver: VerifierAgentOutput,
    proposal: dict[str, Any],
    hook: dict[str, str],
    freelance_memory: list[dict[str, object]],
    llm: LLMClient,
) -> ProposalCritiqueOutput:
    system, user = build_critique_freelance_messages(
        ver.model_dump_json(),
        json.dumps(proposal),
        json.dumps(hook),
        json.dumps({"freelance_win_patterns": freelance_memory}),
    )
    return llm.complete_json(step=STEP, system=system, user=user, response_model=ProposalCritiqueOutput)


def run_critique_agent_enterprise(
    ver: VerifierAgentOutput,
    formatted_json: str,
    requirements: RequirementAgentOutput,
    llm: LLMClient,
) -> ProposalCritiqueOutput:
    system, user = build_critique_enterprise_messages(
        ver.model_dump_json(),
        formatted_json,
        requirements.model_dump_json(),
    )
    return llm.complete_json(step=STEP, system=system, user=user, response_model=ProposalCritiqueOutput)
