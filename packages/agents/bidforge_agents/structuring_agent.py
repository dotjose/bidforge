from __future__ import annotations

from bidforge_prompts.structuring import build_structuring_messages
from bidforge_schemas import RequirementAgentOutput, RequirementStructuringOutput
from bidforge_shared import LLMClient, PipelineStepError

STEP = "requirement_structuring"


def run_requirement_structuring_agent(requirements: RequirementAgentOutput, llm: LLMClient) -> RequirementStructuringOutput:
    system, user = build_structuring_messages(requirements.model_dump_json())
    return llm.complete_json(step=STEP, system=system, user=user, response_model=RequirementStructuringOutput)
