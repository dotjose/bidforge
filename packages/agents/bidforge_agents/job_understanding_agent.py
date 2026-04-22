from __future__ import annotations

from bidforge_prompts.job_understanding import build_job_understanding_messages
from bidforge_schemas import JobUnderstandingOutput
from bidforge_shared import LLMClient

STEP = "job_understanding_agent"


def run_job_understanding_agent(job_text: str, llm: LLMClient) -> JobUnderstandingOutput:
    system, user = build_job_understanding_messages(job_text)
    return llm.complete_json(step=STEP, system=system, user=user, response_model=JobUnderstandingOutput)
