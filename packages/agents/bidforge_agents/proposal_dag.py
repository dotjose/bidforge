"""Stage helpers for the 5-node orchestrator (solution → strategy → writer → verifier).

The HTTP DAG (`api/app/pipeline/orchestrator.py`) bundles earlier steps into `job_intel` and
`router`. This module only contains shared call paths for `solution`, `proposal`, and `verifier`.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Literal

from bidforge_schemas import (
    InputClassifierOutput,
    JobUnderstandingOutput,
    ProposalWriterOutput,
    RagContext,
    RequirementAgentOutput,
    SolutionBlueprintOutput,
    StrategyAgentOutput,
    VerifierAgentOutput,
)
from bidforge_shared import LLMClient, PipelineStepError

from bidforge_agents.job_intel_agent import requirements_for_solution_builder
from bidforge_agents.proposal_agent import run_proposal
from bidforge_agents.proposal_quality_gate import (
    validate_proposal_writer_output,
    validate_solution_blueprint,
)
from bidforge_agents.solution_agent import (
    run_solution_blueprint,
    run_solution_strategy_enterprise,
    run_solution_strategy_job,
)
from bidforge_agents.verifier_agent import run_verifier


@dataclass(frozen=True)
class PipelineStages:
    rag: RagContext
    requirements: RequirementAgentOutput
    blueprint: SolutionBlueprintOutput
    strategy: StrategyAgentOutput
    proposal_document: ProposalWriterOutput
    verification: VerifierAgentOutput


def run_proposal_with_quality_retries(
    *,
    brain: Literal["enterprise", "job"],
    strat: StrategyAgentOutput,
    blueprint: SolutionBlueprintOutput,
    requirements: RequirementAgentOutput,
    job_understanding: JobUnderstandingOutput | None,
    rag: RagContext,
    brief_excerpt: str,
    llm: LLMClient,
    input_classification: InputClassifierOutput | None,
    proposal_depth: str,
) -> ProposalWriterOutput:
    depth = (proposal_depth or "full").strip().lower()
    if depth not in ("short", "full"):
        depth = "full"
    pw: ProposalWriterOutput | None = None
    for attempt in range(3):
        try:
            pw = run_proposal(
                strat,
                blueprint,
                requirements,
                job_understanding,
                rag,
                brief_excerpt,
                llm,
                brain=brain,
                router_output=input_classification,
                proposal_depth=depth,
            )
            validate_proposal_writer_output(pw, blueprint=blueprint, source_brief=brief_excerpt)
            return pw
        except PipelineStepError as e:
            if e.step != "proposal_quality" or attempt == 2:
                raise
            time.sleep(0.5 * (2**attempt))
    raise RuntimeError("proposal node quality retries exhausted")


def enterprise_solution_builder_stage(
    requirements: RequirementAgentOutput,
    rag: RagContext,
    llm: LLMClient,
) -> SolutionBlueprintOutput:
    blueprint = run_solution_blueprint(
        requirements,
        llm,
        rag_context=rag,
        job_signals_json="{}",
    )
    validate_solution_blueprint(blueprint)
    return blueprint


def enterprise_strategy_stage(
    requirements: RequirementAgentOutput,
    rag: RagContext,
    llm: LLMClient,
    blueprint: SolutionBlueprintOutput,
    *,
    workspace_preferences: str,
) -> StrategyAgentOutput:
    return run_solution_strategy_enterprise(
        requirements,
        llm,
        rag_context=rag,
        workspace_preferences=workspace_preferences,
        solution_blueprint=blueprint,
    )


def enterprise_writer_stage(
    requirements: RequirementAgentOutput,
    rag: RagContext,
    rfp_text: str,
    llm: LLMClient,
    ic: InputClassifierOutput | None,
    strat: StrategyAgentOutput,
    blueprint: SolutionBlueprintOutput,
    *,
    proposal_depth: str,
) -> ProposalWriterOutput:
    return run_proposal_with_quality_retries(
        brain="enterprise",
        strat=strat,
        blueprint=blueprint,
        requirements=requirements,
        job_understanding=None,
        rag=rag,
        brief_excerpt=rfp_text,
        llm=llm,
        input_classification=ic,
        proposal_depth=proposal_depth,
    )


def enterprise_verifier_stage(
    pw: ProposalWriterOutput,
    requirements: RequirementAgentOutput,
    rag: RagContext,
    llm: LLMClient,
    strat: StrategyAgentOutput,
) -> VerifierAgentOutput:
    return run_verifier(
        pw,
        requirements,
        llm,
        strategy=strat,
        rag_context=rag,
        pipeline_mode="enterprise",
    )


def freelance_solution_builder_stage(
    ju: JobUnderstandingOutput,
    rag: RagContext,
    llm: LLMClient,
) -> SolutionBlueprintOutput:
    req_stub = requirements_for_solution_builder(ju)
    blueprint = run_solution_blueprint(
        req_stub,
        llm,
        rag_context=rag,
        job_signals_json=ju.model_dump_json(),
    )
    validate_solution_blueprint(blueprint)
    return blueprint


def freelance_strategy_stage(
    ju: JobUnderstandingOutput,
    job_text: str,
    rag: RagContext,
    llm: LLMClient,
    blueprint: SolutionBlueprintOutput,
) -> StrategyAgentOutput:
    return run_solution_strategy_job(
        ju,
        job_text,
        llm,
        rag_context=rag,
        solution_blueprint=blueprint,
    )


def freelance_writer_stage(
    ju: JobUnderstandingOutput,
    rag: RagContext,
    job_text: str,
    llm: LLMClient,
    ic: InputClassifierOutput,
    strat: StrategyAgentOutput,
    blueprint: SolutionBlueprintOutput,
    *,
    proposal_depth: str,
) -> ProposalWriterOutput:
    req_stub = requirements_for_solution_builder(ju)
    return run_proposal_with_quality_retries(
        brain="job",
        strat=strat,
        blueprint=blueprint,
        requirements=req_stub,
        job_understanding=ju,
        rag=rag,
        brief_excerpt=job_text,
        llm=llm,
        input_classification=ic,
        proposal_depth=proposal_depth,
    )


def freelance_verifier_stage(
    pw: ProposalWriterOutput,
    strat: StrategyAgentOutput,
    rag: RagContext,
    llm: LLMClient,
    ju: JobUnderstandingOutput,
    blueprint: SolutionBlueprintOutput,
) -> VerifierAgentOutput:
    return run_verifier(
        pw,
        RequirementAgentOutput(),
        llm,
        strategy=strat,
        rag_context=rag,
        pipeline_mode="freelance",
        job_signals=ju,
        solution_blueprint=blueprint,
    )
