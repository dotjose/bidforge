from __future__ import annotations

from bidforge_prompts.requirement import build_requirement_messages
from bidforge_schemas import RequirementAgentOutput
from bidforge_shared import LLMClient, PipelineStepError

STEP = "requirement_agent"


def run_requirement_agent(rfp_text: str, llm: LLMClient) -> RequirementAgentOutput:
    text = (rfp_text or "").strip()
    if len(text) < 1:
        raise PipelineStepError(STEP, "RFP text is empty")
    system, user = build_requirement_messages(text)
    return llm.complete_json(step=STEP, system=system, user=user, response_model=RequirementAgentOutput)
