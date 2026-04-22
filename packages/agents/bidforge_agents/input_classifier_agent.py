from __future__ import annotations

from bidforge_prompts.classifier import build_classifier_messages
from bidforge_schemas import InputClassifierOutput
from bidforge_shared import LLMClient

STEP = "input_classifier"


def run_input_classifier(job_or_rfp_text: str, llm: LLMClient) -> InputClassifierOutput:
    excerpt = (job_or_rfp_text or "")[:12000]
    system, user = build_classifier_messages(excerpt)
    return llm.complete_json(step=STEP, system=system, user=user, response_model=InputClassifierOutput)
