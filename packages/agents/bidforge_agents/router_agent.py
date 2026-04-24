from __future__ import annotations

from bidforge_prompts.router import build_router_messages
from bidforge_schemas import InputClassifierOutput
from bidforge_shared import LLMClient

STEP = "router"


def run_router(job_or_rfp_text: str, llm: LLMClient) -> InputClassifierOutput:
    excerpt = (job_or_rfp_text or "")[:12000]
    system, user = build_router_messages(excerpt)
    return llm.complete_json(step=STEP, system=system, user=user, response_model=InputClassifierOutput)
