"""Solution node — blueprint + strategy (enterprise or job)."""

from __future__ import annotations

import json

from bidforge_prompts.solution import (
    build_solution_blueprint_messages,
    build_solution_strategy_enterprise_messages,
    build_solution_strategy_job_messages,
)
from bidforge_schemas import (
    JobUnderstandingOutput,
    RagContext,
    RequirementAgentOutput,
    SolutionBlueprintOutput,
    StrategyAgentOutput,
)
from bidforge_shared import LLMClient

STEP_BLUEPRINT = "solution__blueprint"
STEP_STRATEGY_ENT = "solution__strategy"
STEP_STRATEGY_JOB = "solution__strategy_job"


def run_solution_blueprint(
    requirements: RequirementAgentOutput,
    llm: LLMClient,
    *,
    rag_context: RagContext | None = None,
    job_signals_json: str = "{}",
) -> SolutionBlueprintOutput:
    rag = rag_context or RagContext()
    system, user = build_solution_blueprint_messages(
        requirements.model_dump_json(),
        rag.model_dump_json(),
        job_signals_json=job_signals_json,
    )
    return llm.complete_json(step=STEP_BLUEPRINT, system=system, user=user, response_model=SolutionBlueprintOutput)


def run_solution_strategy_enterprise(
    requirements: RequirementAgentOutput,
    llm: LLMClient,
    *,
    rag_context: RagContext | None = None,
    workspace_preferences: str = "",
    solution_blueprint: SolutionBlueprintOutput | None = None,
) -> StrategyAgentOutput:
    rag = rag_context or RagContext()
    bp = solution_blueprint or SolutionBlueprintOutput()
    system, user = build_solution_strategy_enterprise_messages(
        requirements.model_dump_json(),
        rag.model_dump_json(),
        solution_blueprint_json=bp.model_dump_json(),
        workspace_preferences=workspace_preferences,
    )
    return llm.complete_json(step=STEP_STRATEGY_ENT, system=system, user=user, response_model=StrategyAgentOutput)


def run_solution_strategy_job(
    job: JobUnderstandingOutput,
    job_text: str,
    llm: LLMClient,
    *,
    rag_context: RagContext | None = None,
    solution_blueprint: SolutionBlueprintOutput | None = None,
) -> StrategyAgentOutput:
    rag = rag_context or RagContext()
    mem = {"freelance_win_patterns": rag.freelance_win_patterns}
    bp = solution_blueprint or SolutionBlueprintOutput()
    system, user = build_solution_strategy_job_messages(
        job.model_dump_json(),
        job_text,
        json.dumps(mem),
        solution_blueprint_json=bp.model_dump_json(),
    )
    return llm.complete_json(step=STEP_STRATEGY_JOB, system=system, user=user, response_model=StrategyAgentOutput)
